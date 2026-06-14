"""Speech-to-text via faster-whisper-server (OpenAI-compatible API)."""

import os
import io
import wave
import httpx

WHISPER_URL = os.environ.get("WHISPER_URL", "http://localhost:9000")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "Systran/faster-distil-whisper-large-v3")


def audio_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Convert raw PCM16 audio to WAV bytes for upload."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def transcribe(audio_bytes: bytes, sample_rate: int = 16000) -> str:
    """Send audio to faster-whisper-server and return transcription text.

    Args:
        audio_bytes: Raw PCM16 mono audio bytes, or WAV bytes.
        sample_rate: Sample rate of the audio (default 16kHz).

    Returns:
        Transcribed text string.
    """
    # If raw PCM, wrap in WAV container
    if not audio_bytes[:4] == b"RIFF":
        audio_bytes = audio_to_wav_bytes(audio_bytes, sample_rate)

    resp = httpx.post(
        f"{WHISPER_URL}/v1/audio/transcriptions",
        files={"file": ("audio.wav", audio_bytes, "audio/wav")},
        data={"model": WHISPER_MODEL},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json().get("text", "").strip()


if __name__ == "__main__":
    # Quick test: record 3 seconds from mic and transcribe
    try:
        import pyaudio
        RATE = 16000
        CHUNK = 1024
        SECONDS = 3

        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)

        print(f"Recording {SECONDS}s... speak now.")
        frames = []
        for _ in range(0, int(RATE / CHUNK * SECONDS)):
            frames.append(stream.read(CHUNK))
        stream.stop_stream()
        stream.close()
        p.terminate()

        audio = b"".join(frames)
        text = transcribe(audio)
        print(f"Transcribed: {text}")
    except ImportError:
        print("Install pyaudio for mic test: pip install pyaudio")
    except Exception as e:
        print(f"STT test failed: {e}")
        print(f"Is faster-whisper-server running at {WHISPER_URL}?")
