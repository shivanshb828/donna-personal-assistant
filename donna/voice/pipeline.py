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
from .tts import play_audio, synthesize
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


def _record_until_silence(pa: pyaudio.PyAudio) -> bytes:
    vad = create_vad()
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
                llm_started = time.perf_counter()
                result = await _handle_local_turn(runtime, user_text)
                llm_seconds = _seconds_since(llm_started)
                response = result.reply
            except Exception as e:
                print(f"[Agent error: {e}]")
                response = "I'm sorry, I'm having trouble connecting right now."
                llm_seconds = _seconds_since(llm_started)

            print(f"Donna: {response}")
            await _emit_local_event(runtime, {"type": "pipeline_status", "status": "speaking"})

            try:
                tts_started = time.perf_counter()
                audio_out = synthesize(response)
                play_audio(audio_out)
                tts_seconds = _seconds_since(tts_started)
            except Exception as e:
                print(f"[TTS error: {e}]")
                tts_seconds = _seconds_since(tts_started)

            await _emit_turn_timing(
                runtime,
                {
                    "recording_seconds": recording_seconds,
                    "stt_seconds": stt_seconds,
                    "llm_seconds": llm_seconds,
                    "tts_seconds": tts_seconds,
                    "total_seconds": _seconds_since(total_started),
                },
            )

            await _emit_local_event(runtime, {"type": "pipeline_status", "status": "ready"})

    except KeyboardInterrupt:
        print("\nDonna signing off.")
    finally:
        pa.terminate()


if __name__ == "__main__":
    asyncio.run(main())
