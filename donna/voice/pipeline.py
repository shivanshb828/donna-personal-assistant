"""Donna voice pipeline — the main loop.

Wake word → Record → STT → Agent → TTS → Play
Emits events to dashboard via WebSocket.
"""

import os
import sys
import json
import asyncio
import struct
from pathlib import Path

import pyaudio

sys.path.insert(0, str(Path(__file__).parent.parent))

from voice.stt import transcribe
from voice.tts import synthesize, play_audio
from voice.vad import create_vad
from voice.wake_word import create_wake_word

# Audio capture settings
RATE = 16000
CHANNELS = 1
CHUNK = 1024  # ~64ms at 16kHz
FORMAT = pyaudio.paInt16

# Dashboard WebSocket
DASHBOARD_WS_URL = os.environ.get("DASHBOARD_WS_URL", "ws://localhost:3001")


async def emit_event(event: dict):
    """Send event to dashboard via WebSocket."""
    try:
        import websockets
        async with websockets.connect(DASHBOARD_WS_URL) as ws:
            await ws.send(json.dumps(event))
    except Exception:
        pass  # Dashboard not connected — not fatal


async def query_agent(user_text: str, session_id: str = "default") -> str:
    """Send text to Donna agent and get response.

    Tries OpenClaw CLI first, falls back to Ollama direct.
    """
    # Option A: OpenClaw CLI
    try:
        proc = await asyncio.create_subprocess_exec(
            "openclaw", "chat",
            "--agent", "donna",
            "--session", session_id,
            "--message", user_text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode == 0 and stdout.strip():
            return stdout.decode().strip()
    except (FileNotFoundError, asyncio.TimeoutError):
        pass

    # Option B: Direct Ollama API
    import httpx
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("DONNA_LLM_MODEL", "nemotron:120b")

    system_prompt = Path(__file__).parent.parent / "agent" / "donna.yaml"
    # Extract system_prompt from YAML (simple parse)
    sys_prompt = ""
    if system_prompt.exists():
        import yaml
        with open(system_prompt) as f:
            config = yaml.safe_load(f)
            sys_prompt = config.get("system_prompt", "You are Donna, an AI legal secretary.")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{ollama_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_text},
                ],
                "max_tokens": 300,
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def main():
    print("=" * 60)
    print("  DONNA — AI Legal Secretary")
    print("  Say 'Hey Donna' to start (or press Enter)")
    print("  All processing runs locally. Zero internet.")
    print("=" * 60)

    # Initialize components
    vad = create_vad(use_silero=True, min_silence_ms=800)
    wake_detector = create_wake_word(use_audio=True)

    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    print("\nListening for wake word...")
    session_id = "demo-session"
    wake_active = False

    try:
        while True:
            pcm_chunk = stream.read(CHUNK, exception_on_overflow=False)

            if not wake_active:
                # Listen for wake word
                if wake_detector.detect(pcm_chunk):
                    wake_active = True
                    vad.reset()
                    print("\n[DONNA ACTIVATED] Listening...")
                    await emit_event({"type": "donna_activated"})

                    # Play activation chime or brief acknowledgment
                    ack = synthesize("Yes?")
                    play_audio(ack)
                continue

            # Active — accumulate audio until speech ends
            result = vad.process_chunk(pcm_chunk)

            if result["speech_ended"] and result["audio"]:
                # Speech complete — transcribe
                print("  Processing speech...")
                user_text = transcribe(result["audio"])

                if not user_text or len(user_text.strip()) < 2:
                    print("  (no speech detected, listening again...)")
                    wake_active = False
                    wake_detector.reset()
                    print("\nListening for wake word...")
                    continue

                print(f"  You: {user_text}")
                await emit_event({"type": "user_speech", "text": user_text})

                # Query Donna
                print("  Donna is thinking...")
                donna_text = await query_agent(user_text, session_id)
                print(f"  Donna: {donna_text}")
                await emit_event({"type": "donna_speech", "text": donna_text})

                # Speak response
                audio = synthesize(donna_text)
                play_audio(audio)

                # Ready for next utterance (stay active for follow-up)
                vad.reset()
                wake_active = False
                wake_detector.reset()
                print("\nListening for wake word...")

    except KeyboardInterrupt:
        print("\n\nDonna shutting down. Goodbye.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()


if __name__ == "__main__":
    asyncio.run(main())
