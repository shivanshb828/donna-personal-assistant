"""Text-to-speech — Kokoro-FastAPI (primary) with Piper fallback.

Kokoro-FastAPI: OpenAI-compatible /v1/audio/speech endpoint.
Piper: Local ONNX inference, no server needed.
"""

import os
import io
import wave
import httpx

KOKORO_URL = os.environ.get("KOKORO_URL", "http://localhost:8880")
KOKORO_VOICE = os.environ.get("KOKORO_VOICE", "af_heart")  # female, warm
TTS_ENGINE = os.environ.get("TTS_ENGINE", "kokoro")  # kokoro or piper


def synthesize_kokoro(text: str) -> bytes:
    """Generate speech via Kokoro-FastAPI. Returns WAV bytes."""
    resp = httpx.post(
        f"{KOKORO_URL}/v1/audio/speech",
        json={
            "model": "kokoro",
            "input": text,
            "voice": KOKORO_VOICE,
            "response_format": "wav",
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.content


def synthesize_piper(text: str) -> bytes:
    """Generate speech via Piper TTS (local). Returns WAV bytes."""
    try:
        from piper import PiperVoice

        model_path = os.environ.get("PIPER_MODEL", "en_US-lessac-medium.onnx")
        voice = PiperVoice.load(model_path)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            voice.synthesize_wav(text, wf)
        return buf.getvalue()
    except ImportError:
        raise RuntimeError("Piper TTS not installed. Run: pip install piper-tts")


def synthesize(text: str) -> bytes:
    """Generate speech using configured TTS engine. Returns WAV bytes."""
    if TTS_ENGINE == "kokoro":
        try:
            return synthesize_kokoro(text)
        except Exception:
            # Fallback to piper if kokoro unavailable
            return synthesize_piper(text)
    else:
        return synthesize_piper(text)


def play_audio(wav_bytes: bytes):
    """Play WAV audio through speakers."""
    try:
        import pyaudio

        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            p = pyaudio.PyAudio()
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
            )
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
            stream.stop_stream()
            stream.close()
            p.terminate()
    except ImportError:
        raise RuntimeError("Install pyaudio for audio playback: pip install pyaudio")


if __name__ == "__main__":
    text = "Case file created for Sarah Chen, slip and fall, March 3rd. I've added it to your dashboard."
    print(f"Synthesizing: {text}")
    try:
        audio = synthesize(text)
        print(f"Got {len(audio)} bytes of audio. Playing...")
        play_audio(audio)
        print("Done.")
    except Exception as e:
        print(f"TTS test failed: {e}")
        print(f"Is Kokoro running at {KOKORO_URL}? Or install piper: pip install piper-tts")
