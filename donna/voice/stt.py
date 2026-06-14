import io
import os
import wave

import httpx

STT_URL = os.getenv("DONNA_STT_URL", "http://localhost:9000/v1/audio/transcriptions")
STT_MODEL = os.getenv("DONNA_STT_MODEL", "Systran/faster-distil-whisper-large-v3")


def _pcm16_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def transcribe_audio(audio_bytes: bytes) -> str:
    wav_bytes = _pcm16_to_wav(audio_bytes)
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            STT_URL,
            files={"file": ("audio.wav", wav_bytes, "audio/wav")},
            data={"model": STT_MODEL},
        )
    resp.raise_for_status()
    return resp.json().get("text", "").strip()


if __name__ == "__main__":
    import pyaudio
    RATE, CHUNK, SECONDS = 16000, 1024, 5
    pa = pyaudio.PyAudio()
    stream = pa.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)
    print(f"Recording {SECONDS}s for STT test...")
    try:
        frames = [stream.read(CHUNK) for _ in range(int(RATE / CHUNK * SECONDS))]
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
    audio = b"".join(frames)
    print("Transcribing...")
    print("Result:", transcribe_audio(audio))
