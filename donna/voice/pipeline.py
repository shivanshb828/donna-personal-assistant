"""
Donna voice pipeline - push-to-talk mode.
Press ENTER to start recording. Donna auto-stops when you go silent.
"""

import asyncio
import io
import os
import sys
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any
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

from .stt import transcribe_audio, warm_stt
from .tts import SentenceSynthesisQueue, play_audio, warm_tts
from .vad import create_vad
from .dashboard_bridge import emit_to_dashboard

RATE = 16000
CHUNK = 512
FORMAT = pyaudio.paInt16
CHANNELS = 1
MAX_RECORD_SECONDS = 30

LOCAL_AGENT_MODE = "local_assistant"
STARTUP_WARM_TIMEOUT_SECONDS = float(os.getenv("DONNA_STARTUP_WARM_TIMEOUT_SECONDS", "15"))
MIN_TURN_SECONDS = float(os.getenv("DONNA_MIN_TURN_SECONDS", "0.5"))
MAX_INTERRUPT_SECONDS = float(os.getenv("DONNA_MAX_INTERRUPT_SECONDS", "8"))
INTERRUPT_GRACE_SECONDS = float(os.getenv("DONNA_INTERRUPT_GRACE_SECONDS", "0.35"))
INTERRUPT_MIN_SPEECH_CHUNKS = max(1, int(os.getenv("DONNA_INTERRUPT_MIN_SPEECH_CHUNKS", "5")))
INTERRUPT_MIN_CONFIDENCE = float(os.getenv("DONNA_INTERRUPT_MIN_CONFIDENCE", "0.85"))
INTERRUPT_MIN_RMS = float(os.getenv("DONNA_INTERRUPT_MIN_RMS", "1200"))


@dataclass(frozen=True)
class LocalVoiceRuntime:
    session_id: str
    router: SessionRouter
    record_vad: Any
    interrupt_vad: Any


@dataclass
class InterruptionTracker:
    interrupted: bool = False
    audio: bytes | None = None
    speech_chunks: int = 0

    def feed(
        self,
        *,
        vad,
        chunk: bytes,
        stop_event: threading.Event | None = None,
        can_interrupt: bool = True,
    ) -> bool:
        result = vad.process(chunk)
        confidence = float(result.get("confidence", 1.0))
        rms = float(result.get("rms", float("inf")))
        voice_like = (
            result["is_speaking"]
            and confidence >= INTERRUPT_MIN_CONFIDENCE
            and rms >= INTERRUPT_MIN_RMS
        )
        if not can_interrupt and not self.interrupted:
            self.speech_chunks = 0
            return False
        if voice_like:
            self.speech_chunks += 1
        elif not self.interrupted:
            self.speech_chunks = 0
        if (
            not self.interrupted
            and self.speech_chunks >= INTERRUPT_MIN_SPEECH_CHUNKS
        ):
            self.interrupted = True
            if stop_event is not None:
                stop_event.set()
        if self.interrupted:
            self.audio = result["audio"]
        return bool(self.interrupted and result["speech_ended"])


@dataclass
class PlaybackCapture:
    interrupted: bool = False
    audio: bytes | None = None
    error: Exception | None = None


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
    return LocalVoiceRuntime(
        session_id=session_id,
        router=router,
        record_vad=create_vad(profile="push_to_talk"),
        interrupt_vad=create_vad(profile="push_to_talk"),
    )


async def _warm_local_runtime(runtime: LocalVoiceRuntime) -> None:
    async def _run(label: str, fn) -> Exception | None:
        try:
            await asyncio.wait_for(asyncio.to_thread(fn), timeout=STARTUP_WARM_TIMEOUT_SECONDS)
        except Exception as exc:
            return RuntimeError(f"{label}: {exc}")
        return None

    results = await asyncio.gather(
        _run("llm", runtime.router.llm.warm),
        _run("stt", warm_stt),
        _run("tts", warm_tts),
    )
    failures = [
        str(result)
        for result in results
        if result is not None
    ]
    if failures:
        raise RuntimeError("; ".join(failures))


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


def _reset_vad(vad) -> None:
    reset = getattr(vad, "reset", None)
    if callable(reset):
        reset()


def _flush_input_stream(stream) -> None:
    available = getattr(stream, "get_read_available", lambda: 0)()
    while available >= CHUNK:
        stream.read(CHUNK, exception_on_overflow=False)
        available = getattr(stream, "get_read_available", lambda: 0)()


def _record_until_silence(pa: pyaudio.PyAudio, *, vad) -> bytes:
    _reset_vad(vad)
    stream = pa.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    print("[Recording... speak now]")
    collected = b""
    max_chunks = int(RATE / CHUNK * MAX_RECORD_SECONDS)
    try:
        _flush_input_stream(stream)
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
    playback_capture = PlaybackCapture()

    async def _play_sentence(_: str, audio: bytes, stop_event) -> None:
        playback_done = threading.Event()
        monitor_thread: threading.Thread | None = None
        if _env_flag("DONNA_ENABLE_LOCAL_BARGE_IN", True) and not stop_event.is_set():
            monitor_thread = threading.Thread(
                target=_monitor_for_interruption,
                args=(runtime.interrupt_vad, stop_event, playback_done, playback_capture),
                daemon=True,
            )
            monitor_thread.start()
        try:
            await asyncio.to_thread(play_audio, audio, stop_event=stop_event)
        finally:
            playback_done.set()
            if monitor_thread is not None:
                await asyncio.to_thread(monitor_thread.join, 0.25)

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
        "interrupted": playback_capture.interrupted,
        "interrupted_audio": playback_capture.audio,
        "interruption_error": playback_capture.error,
    }


def _monitor_for_interruption(vad, stop_event, playback_done, capture: PlaybackCapture) -> None:
    import pyaudio

    tracker = InterruptionTracker()
    _reset_vad(vad)
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )
    max_chunks = max(1, int(RATE / CHUNK * MAX_INTERRUPT_SECONDS))
    grace_chunks = max(0, int(RATE / CHUNK * INTERRUPT_GRACE_SECONDS))
    try:
        _flush_input_stream(stream)
        for chunk_index in range(max_chunks):
            if playback_done.is_set() and not tracker.interrupted:
                return
            if stop_event.is_set() and not tracker.interrupted:
                return
            chunk = stream.read(CHUNK, exception_on_overflow=False)
            if tracker.feed(
                vad=vad,
                chunk=chunk,
                stop_event=stop_event,
                can_interrupt=chunk_index >= grace_chunks,
            ):
                capture.interrupted = True
                capture.audio = tracker.audio
                return
        capture.interrupted = tracker.interrupted
        capture.audio = tracker.audio
    except Exception as exc:
        capture.error = exc
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


def _has_enough_audio(audio: bytes | None) -> bool:
    if not audio:
        return False
    return len(audio) >= RATE * 2 * MIN_TURN_SECONDS


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

    print("Warming Donna...")
    try:
        await _warm_local_runtime(runtime)
    except Exception as e:
        print(f"[Warmup warning: {e}]")

    await _emit_local_call_started(runtime)
    await _emit_local_event(runtime, {"type": "pipeline_status", "status": "ready"})

    try:
        while True:
            input("\n[Press ENTER to speak to Donna]")

            await _emit_local_event(runtime, {"type": "pipeline_status", "status": "listening"})

            record_started = time.perf_counter()
            audio = _record_until_silence(pa, vad=runtime.record_vad)
            recording_seconds = _seconds_since(record_started)
            if not _has_enough_audio(audio):
                print("[Too short, try again]")
                await _emit_local_event(runtime, {"type": "pipeline_status", "status": "ready"})
                continue

            pending_audio = audio
            pending_recording_seconds = recording_seconds
            while pending_audio is not None:
                total_started = time.perf_counter()
                current_audio = pending_audio
                current_recording_seconds = pending_recording_seconds
                pending_audio = None
                pending_recording_seconds = 0.0

                await _emit_local_event(runtime, {"type": "pipeline_status", "status": "processing"})

                print("Transcribing...")
                try:
                    stt_started = time.perf_counter()
                    user_text = transcribe_audio(current_audio)
                    stt_seconds = _seconds_since(stt_started)
                except Exception as e:
                    print(f"[STT error: {e}]")
                    await _emit_local_event(runtime, {"type": "pipeline_status", "status": "ready"})
                    break

                if not user_text:
                    print("[Nothing heard, try again]")
                    await _emit_local_event(runtime, {"type": "pipeline_status", "status": "ready"})
                    break

                print(f"You: {user_text}")
                print("Donna thinking...")
                interruption_audio = None
                interruption_error = None
                try:
                    if _env_flag("DONNA_ENABLE_STREAMING_LLM", True) or _env_flag("DONNA_ENABLE_STREAMING_TTS", True):
                        result, streaming_timing = await _handle_local_turn_streaming(runtime, user_text)
                        llm_seconds = streaming_timing["llm_seconds"]
                        first_token_seconds = streaming_timing["first_token_seconds"]
                        first_sentence_seconds = streaming_timing["first_sentence_seconds"]
                        first_audio_seconds = streaming_timing["first_audio_seconds"]
                        tts_total_seconds = streaming_timing["tts_total_seconds"]
                        interrupted = streaming_timing["interrupted"]
                        interruption_audio = streaming_timing["interrupted_audio"]
                        interruption_error = streaming_timing["interruption_error"]
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
                if interruption_error is not None:
                    print(f"[Interruption monitor warning: {interruption_error}]")
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
                        "recording_seconds": current_recording_seconds,
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

                if interrupted and _has_enough_audio(interruption_audio):
                    print("[Interruption detected, switching turns]")
                    pending_audio = interruption_audio
                    continue

                await _emit_local_event(runtime, {"type": "pipeline_status", "status": "ready"})
                break

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
