from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, Iterable
import io
import os
import wave
from dataclasses import dataclass

import httpx

STT_URL = os.getenv("DONNA_STT_URL", "http://localhost:9000/v1/audio/transcriptions")
STT_MODEL = os.getenv("DONNA_STT_MODEL", "Systran/faster-whisper-tiny.en")
STT_WARM_SECONDS = float(os.getenv("DONNA_STT_WARM_SECONDS", "0.5"))


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


def warm_stt() -> None:
    sample_count = max(1, int(16000 * STT_WARM_SECONDS))
    silent_pcm = b"\x00\x00" * sample_count
    transcribe_audio(silent_pcm)


@dataclass
class TranscriptionEvent:
    text: str
    is_final: bool = False


async def stream_transcription(
    audio_chunks: AsyncIterable[bytes] | Iterable[bytes],
) -> AsyncIterable[TranscriptionEvent]:
    collected = bytearray()
    if hasattr(audio_chunks, "__aiter__"):
        async for chunk in audio_chunks:
            collected.extend(chunk)
    else:
        for chunk in audio_chunks:
            collected.extend(chunk)

    text = await asyncio.to_thread(transcribe_audio, bytes(collected))
    if text:
        yield TranscriptionEvent(text=text, is_final=True)


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
