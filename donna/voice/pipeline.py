"""
Donna voice pipeline - push-to-talk mode.
Press ENTER to start recording. Donna auto-stops when you go silent.
"""

import asyncio
import io
import os
import sys
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pyaudio

from donna.glue.router.session_router import RouterResult, SessionRouter
from donna.glue.tools.registry import ToolRegistry
from donna.telephony.config import TelephonyConfig
from donna.telephony.db import create_call_session
from donna.telephony.llm import DonnaLLM

from .stt import transcribe_audio
from .tts import SentenceSynthesisQueue, play_audio
from .vad import create_vad
from .dashboard_bridge import emit_to_dashboard

RATE = 16000
CHUNK = 512
FORMAT = pyaudio.paInt16
CHANNELS = 1
MAX_RECORD_SECONDS = 30

LOCAL_AGENT_MODE = "local_assistant"


@dataclass(frozen=True)
class LocalVoiceRuntime:
    session_id: str
    router: SessionRouter


def _create_local_voice_runtime() -> LocalVoiceRuntime:
    cfg = TelephonyConfig.from_env()
    session_id = os.getenv("DONNA_LOCAL_SESSION_ID", f"local-{uuid4().hex[:12]}")
    create_call_session(
        cfg.telephony_db,
        call_sid=session_id,
        phone=None,
        agent_mode=LOCAL_AGENT_MODE,
        is_returning=False,
    )
    router = SessionRouter(
        telephony_db_path=cfg.telephony_db,
        context_db_path=cfg.context_db,
        calendar_db_path=cfg.calendar_db,
        llm=DonnaLLM(ollama_url=cfg.ollama_url, model=cfg.ollama_model),
        tools=ToolRegistry(
            telephony_db_path=cfg.telephony_db,
            context_db_path=cfg.context_db,
            calendar_db_path=cfg.calendar_db,
        ),
        firm_name=cfg.firm_name,
    )
    return LocalVoiceRuntime(session_id=session_id, router=router)


def _seconds_since(started: float) -> float:
    return round(time.perf_counter() - started, 3)


def _print_turn_timing(timing: dict) -> None:
    parts = [
        f"{key}={value:.3f}s"
        for key, value in timing.items()
        if isinstance(value, int | float)
    ]
    print(f"[Timing] {' '.join(parts)}")


async def _emit_turn_timing(runtime: LocalVoiceRuntime, timing: dict) -> None:
    _print_turn_timing(timing)
    await _emit_local_event(runtime, {"type": "turn_timing", **timing})


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _record_until_silence(pa: pyaudio.PyAudio) -> bytes:
    vad = create_vad(profile="push_to_talk")
    stream = pa.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    print("[Recording... speak now]")
    collected = b""
    max_chunks = int(RATE / CHUNK * MAX_RECORD_SECONDS)
    try:
        for _ in range(max_chunks):
            chunk = stream.read(CHUNK, exception_on_overflow=False)
            result = vad.process(chunk)
            collected = result["audio"]
            if result["speech_ended"]:
                break
    finally:
        stream.stop_stream()
        stream.close()
    return collected


async def _emit_local_event(runtime: LocalVoiceRuntime, event: dict) -> None:
    enriched = {
        **event,
        "callSid": runtime.session_id,
        "sessionId": runtime.session_id,
    }
    await emit_to_dashboard(enriched)


async def _emit_local_call_started(runtime: LocalVoiceRuntime) -> None:
    await _emit_local_event(
        runtime,
        {
            "type": "call_started",
            "callerPhone": "Local Mic",
            "agentMode": LOCAL_AGENT_MODE,
            "isReturning": False,
        },
    )


async def _run_router_turn(runtime: LocalVoiceRuntime, text: str) -> RouterResult:
    return await asyncio.to_thread(
        runtime.router.handle_turn,
        call_sid=runtime.session_id,
        user_text=text,
        agent_mode=LOCAL_AGENT_MODE,
    )


async def _handle_local_turn(runtime: LocalVoiceRuntime, text: str) -> RouterResult:
    await _emit_local_event(runtime, {"type": "user_speech", "text": text})
    result = await _run_router_turn(runtime, text)
    for tool_result in result.tool_results:
        await _emit_local_event(runtime, {"type": "tool_result", **tool_result})
    await _emit_local_event(runtime, {"type": "donna_speech", "text": result.reply})
    return result


async def _handle_local_turn_streaming(runtime: LocalVoiceRuntime, text: str) -> tuple[RouterResult, dict]:
    await _emit_local_event(runtime, {"type": "user_speech", "text": text})
    speaking_started = False

    async def _play_sentence(_: str, audio: bytes, stop_event) -> None:
        await asyncio.to_thread(play_audio, audio, stop_event=stop_event)

    tts_queue = SentenceSynthesisQueue(audio_handler=_play_sentence, started_at=time.perf_counter())

    async def _on_sentence(sentence: str) -> None:
        nonlocal speaking_started
        if not speaking_started:
            speaking_started = True
            await _emit_local_event(runtime, {"type": "pipeline_status", "status": "speaking"})
        await _emit_local_event(runtime, {"type": "donna_speech", "text": sentence})
        await tts_queue.enqueue(sentence)

    llm_started = time.perf_counter()
    outcome = await runtime.router.stream_turn(
        call_sid=runtime.session_id,
        user_text=text,
        agent_mode=LOCAL_AGENT_MODE,
        on_sentence=_on_sentence,
    )
    for tool_result in outcome.result.tool_results:
        await _emit_local_event(runtime, {"type": "tool_result", **tool_result})
    tts_stats = await tts_queue.finish()
    return outcome.result, {
        "llm_seconds": _seconds_since(llm_started),
        "first_token_seconds": outcome.first_token_seconds,
        "first_sentence_seconds": outcome.first_sentence_seconds,
        "first_audio_seconds": tts_stats.first_audio_seconds,
        "tts_total_seconds": round(tts_stats.total_seconds, 3),
        "interrupted": False,
    }


def _test_mic(pa: pyaudio.PyAudio):
    print("Mic test: recording 3s then playing back...")
    stream = pa.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    try:
        frames = [stream.read(CHUNK) for _ in range(int(RATE / CHUNK * 3))]
    finally:
        stream.stop_stream()
        stream.close()
    pcm = b"".join(frames)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(pcm)
    play_audio(buf.getvalue())
    print("Mic test done.")


async def _run_text_query(text: str, runtime: LocalVoiceRuntime | None = None) -> None:
    runtime = runtime or _create_local_voice_runtime()
    total_started = time.perf_counter()
    print(f"You: {text}")
    print("Donna thinking...")
    llm_started = time.perf_counter()
    result = await _handle_local_turn(runtime, text)
    print(f"Donna: {result.reply}")
    await _emit_turn_timing(
        runtime,
        {
            "llm_seconds": _seconds_since(llm_started),
            "total_seconds": _seconds_since(total_started),
        },
    )


async def main():
    args = sys.argv[1:]

    if "--text" in args:
        idx = args.index("--text")
        if idx + 1 >= len(args):
            print("Usage: python -m donna.voice.pipeline --text \"your message\"")
            return
        await _run_text_query(args[idx + 1])
        return

    pa = pyaudio.PyAudio()
    runtime = _create_local_voice_runtime()

    if "--test-mic" in args:
        _test_mic(pa)
        pa.terminate()
        return

    print("=" * 50)
    print("  DONNA — PI Attorney AI")
    print("  Press ENTER to speak. Ctrl+C to quit.")
    print("=" * 50)

    await _emit_local_call_started(runtime)
    await _emit_local_event(runtime, {"type": "pipeline_status", "status": "ready"})

    try:
        while True:
            input("\n[Press ENTER to speak to Donna]")

            total_started = time.perf_counter()
            await _emit_local_event(runtime, {"type": "pipeline_status", "status": "listening"})

            record_started = time.perf_counter()
            audio = _record_until_silence(pa)
            recording_seconds = _seconds_since(record_started)
            if len(audio) < RATE * 2 * 0.5:  # less than 0.5s -> skip
                print("[Too short, try again]")
                await _emit_local_event(runtime, {"type": "pipeline_status", "status": "ready"})
                continue

            await _emit_local_event(runtime, {"type": "pipeline_status", "status": "processing"})

            print("Transcribing...")
            try:
                stt_started = time.perf_counter()
                user_text = transcribe_audio(audio)
                stt_seconds = _seconds_since(stt_started)
            except Exception as e:
                print(f"[STT error: {e}]")
                await _emit_local_event(runtime, {"type": "pipeline_status", "status": "ready"})
                continue

            if not user_text:
                print("[Nothing heard, try again]")
                await _emit_local_event(runtime, {"type": "pipeline_status", "status": "ready"})
                continue

            print(f"You: {user_text}")
            print("Donna thinking...")
            try:
                if _env_flag("DONNA_ENABLE_STREAMING_LLM", True) or _env_flag("DONNA_ENABLE_STREAMING_TTS", True):
                    result, streaming_timing = await _handle_local_turn_streaming(runtime, user_text)
                    llm_seconds = streaming_timing["llm_seconds"]
                    first_token_seconds = streaming_timing["first_token_seconds"]
                    first_sentence_seconds = streaming_timing["first_sentence_seconds"]
                    first_audio_seconds = streaming_timing["first_audio_seconds"]
                    tts_total_seconds = streaming_timing["tts_total_seconds"]
                    interrupted = streaming_timing["interrupted"]
                else:
                    llm_started = time.perf_counter()
                    result = await _handle_local_turn(runtime, user_text)
                    llm_seconds = _seconds_since(llm_started)
                    first_token_seconds = None
                    first_sentence_seconds = None
                    first_audio_seconds = None
                    tts_total_seconds = 0.0
                    interrupted = False
                response = result.reply
            except Exception as e:
                print(f"[Agent error: {e}]")
                response = "I'm sorry, I'm having trouble connecting right now."
                llm_seconds = 0.0
                first_token_seconds = None
                first_sentence_seconds = None
                first_audio_seconds = None
                tts_total_seconds = 0.0
                interrupted = False

            print(f"Donna: {response}")
            if not (_env_flag("DONNA_ENABLE_STREAMING_LLM", True) or _env_flag("DONNA_ENABLE_STREAMING_TTS", True)):
                await _emit_local_event(runtime, {"type": "pipeline_status", "status": "speaking"})
                try:
                    tts_queue = SentenceSynthesisQueue(
                        audio_handler=lambda _sentence, audio, stop_event: asyncio.to_thread(
                            play_audio,
                            audio,
                            stop_event=stop_event,
                        ),
                        started_at=time.perf_counter(),
                    )
                    await tts_queue.enqueue(response)
                    tts_stats = await tts_queue.finish()
                    first_audio_seconds = tts_stats.first_audio_seconds
                    tts_total_seconds = round(tts_stats.total_seconds, 3)
                except Exception as e:
                    print(f"[TTS error: {e}]")
                    first_audio_seconds = None
                    tts_total_seconds = 0.0

            await _emit_turn_timing(
                runtime,
                {
                    "recording_seconds": recording_seconds,
                    "stt_seconds": stt_seconds,
                    "llm_seconds": llm_seconds,
                    "first_token_seconds": first_token_seconds,
                    "first_sentence_seconds": first_sentence_seconds,
                    "first_audio_seconds": first_audio_seconds,
                    "tts_total_seconds": tts_total_seconds,
                    "interrupted": interrupted,
                    "total_seconds": _seconds_since(total_started),
                },
            )

            await _emit_local_event(runtime, {"type": "pipeline_status", "status": "ready"})

    except KeyboardInterrupt:
        print("\nDonna signing off.")
    finally:
        await _emit_local_event(
            runtime,
            {
                "type": "call_ended",
                "duration": 0,
                "outcome": "local_session",
            },
        )
        pa.terminate()


if __name__ == "__main__":
    asyncio.run(main())
