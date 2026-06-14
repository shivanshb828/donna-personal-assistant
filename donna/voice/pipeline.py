"""
Donna voice pipeline — push-to-talk mode.
Press ENTER to start recording. Donna auto-stops when you go silent.
"""

import asyncio
import io
import os
import sys
import wave
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx
import pyaudio

from donna.glue.context_bridge import lookup_context_block

from .stt import transcribe_audio
from .tts import play_audio, synthesize
from .vad import create_vad
from .dashboard_bridge import emit_to_dashboard

RATE = 16000
CHUNK = 512
FORMAT = pyaudio.paInt16
CHANNELS = 1
MAX_RECORD_SECONDS = 30

OLLAMA_URL = os.getenv("DONNA_OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("DONNA_MODEL", "nemotron-3-nano")
OLLAMA_MODEL_FALLBACKS = [
    m.strip()
    for m in os.getenv(
        "DONNA_MODEL_FALLBACKS",
        "nemotron-3-nano,nemotron-3-super",
    ).split(",")
    if m.strip()
]
CONTEXT_DB = Path(
    os.getenv("DONNA_CONTEXT_DB", str(_REPO_ROOT / "data/donna_m3_context.sqlite"))
)


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


def _build_ollama_prompt(text: str, context_block: str) -> str:
    parts = [
        "You are Donna, a professional AI legal secretary for a personal injury law firm. "
        "Keep responses concise (1-2 sentences). No legal advice.",
    ]
    if context_block:
        parts.append(context_block)
    parts.append(f"Client: {text}\nDonna:")
    return "\n\n".join(parts)


async def _query_ollama(text: str, context_block: str = "") -> str:
    models: list[str] = []
    for name in [OLLAMA_MODEL, *OLLAMA_MODEL_FALLBACKS]:
        if name not in models:
            models.append(name)

    last_error: Exception | None = None
    prompt = _build_ollama_prompt(text, context_block)

    for model in models:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    OLLAMA_URL,
                    json={"model": model, "prompt": prompt, "stream": False},
                )
            resp.raise_for_status()
            body = resp.json().get("response", "").strip()
            if body:
                if model != models[0]:
                    print(f"[Ollama fallback model: {model}]")
                return body
        except Exception as exc:
            last_error = exc
            print(f"[Ollama error for {model}: {exc}]")

    if last_error:
        raise last_error
    return ""


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


async def _run_text_query(text: str) -> None:
    context_block = lookup_context_block(text, db_path=CONTEXT_DB)
    if context_block:
        print("[Loaded case context from local DB]")
    print(f"You: {text}")
    print("Donna thinking...")
    response = await _query_ollama(text, context_block)
    print(f"Donna: {response}")


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

    if "--test-mic" in args:
        _test_mic(pa)
        pa.terminate()
        return

    print("=" * 50)
    print("  DONNA — PI Attorney AI")
    print("  Press ENTER to speak. Ctrl+C to quit.")
    print("=" * 50)

    await emit_to_dashboard({"type": "pipeline_status", "status": "ready"})

    try:
        while True:
            input("\n[Press ENTER to speak to Donna]")

            await emit_to_dashboard({"type": "pipeline_status", "status": "listening"})

            audio = _record_until_silence(pa)
            if len(audio) < RATE * 2 * 0.5:  # less than 0.5s → skip
                print("[Too short, try again]")
                await emit_to_dashboard({"type": "pipeline_status", "status": "ready"})
                continue

            await emit_to_dashboard({"type": "pipeline_status", "status": "processing"})

            print("Transcribing...")
            try:
                user_text = transcribe_audio(audio)
            except Exception as e:
                print(f"[STT error: {e}]")
                await emit_to_dashboard({"type": "pipeline_status", "status": "ready"})
                continue

            if not user_text:
                print("[Nothing heard, try again]")
                await emit_to_dashboard({"type": "pipeline_status", "status": "ready"})
                continue

            print(f"You: {user_text}")
            await emit_to_dashboard({"type": "user_speech", "text": user_text})

            context_block = lookup_context_block(user_text, db_path=CONTEXT_DB)
            if context_block:
                print("[Loaded case context from local DB]")

            print("Donna thinking...")
            try:
                response = await _query_ollama(user_text, context_block)
            except Exception as e:
                print(f"[Agent error: {e}]")
                response = "I'm sorry, I'm having trouble connecting right now."

            print(f"Donna: {response}")
            await emit_to_dashboard({"type": "donna_speech", "text": response})
            await emit_to_dashboard({"type": "pipeline_status", "status": "speaking"})

            try:
                audio_out = synthesize(response)
                play_audio(audio_out)
            except Exception as e:
                print(f"[TTS error: {e}]")

            await emit_to_dashboard({"type": "pipeline_status", "status": "ready"})

    except KeyboardInterrupt:
        print("\nDonna signing off.")
    finally:
        pa.terminate()


if __name__ == "__main__":
    asyncio.run(main())
