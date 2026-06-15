from __future__ import annotations

import asyncio
import io
import inspect
import os
import subprocess
import threading
import time
import wave
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx

KOKORO_URL = os.getenv("DONNA_KOKORO_URL", "http://localhost:8880/v1/audio/speech")
KOKORO_VOICE = os.getenv("DONNA_KOKORO_VOICE", "af_heart")
PIPER_MODEL = os.getenv("DONNA_PIPER_MODEL", "en_US-amy-medium")
TTS_WARM_TEXT = os.getenv("DONNA_TTS_WARM_TEXT", "Ready.")


def _synthesize_kokoro(text: str) -> bytes:
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            KOKORO_URL,
            json={"model": "kokoro", "input": text, "voice": KOKORO_VOICE, "response_format": "wav"},
        )
    resp.raise_for_status()
    return resp.content


def _synthesize_piper(text: str) -> bytes:
    result = subprocess.run(
        ["piper", "--model", PIPER_MODEL, "--output-raw"],
        input=text.encode(),
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f"piper failed: {result.stderr.decode()}")
    # piper --output-raw gives raw PCM16 at 22050Hz — wrap in WAV
    pcm = result.stdout
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(pcm)
    return buf.getvalue()


def synthesize(text: str) -> bytes:
    for fn, name in [(_synthesize_kokoro, "Kokoro"), (_synthesize_piper, "Piper")]:
        try:
            audio = fn(text)
            print(f"[TTS] {name}")
            return audio
        except Exception as e:
            print(f"[TTS] {name} failed: {e}")
    raise RuntimeError("All TTS backends failed")


def warm_tts(text: str | None = None) -> bytes:
    return synthesize(text or TTS_WARM_TEXT)


def play_audio(
    audio_bytes: bytes,
    *,
    stop_event: threading.Event | None = None,
    on_start: Callable[[], None] | None = None,
) -> None:
    import pyaudio
    buf = io.BytesIO(audio_bytes)
    with wave.open(buf, "rb") as wf:
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pa.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True,
        )
        try:
            chunk = 1024
            if on_start:
                on_start()
            data = wf.readframes(chunk)
            while data:
                if stop_event and stop_event.is_set():
                    break
                stream.write(data)
                data = wf.readframes(chunk)
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()


SentenceAudioHandler = Callable[[str, bytes, threading.Event], Awaitable[None] | None]


@dataclass
class SentenceSynthesisStats:
    first_audio_seconds: float | None = None
    total_seconds: float = 0.0
    sentence_count: int = 0


class SentenceSynthesisQueue:
    def __init__(
        self,
        *,
        audio_handler: SentenceAudioHandler,
        started_at: float | None = None,
    ) -> None:
        self.audio_handler = audio_handler
        self.started_at = started_at or time.perf_counter()
        self.stats = SentenceSynthesisStats()
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._stop_event = threading.Event()

    async def enqueue(self, text: str) -> None:
        sentence = text.strip()
        if not sentence:
            return
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker())
        await self._queue.put(sentence)

    def cancel(self) -> None:
        self._stop_event.set()
        while True:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

    async def finish(self) -> SentenceSynthesisStats:
        if self._worker_task is None:
            return self.stats
        await self._queue.put(None)
        await self._worker_task
        return self.stats

    async def _worker(self) -> None:
        while True:
            sentence = await self._queue.get()
            if sentence is None:
                return
            if self._stop_event.is_set():
                continue
            started = time.perf_counter()
            audio = await asyncio.to_thread(synthesize, sentence)
            self.stats.total_seconds += time.perf_counter() - started
            self.stats.sentence_count += 1
            if self.stats.first_audio_seconds is None:
                self.stats.first_audio_seconds = round(time.perf_counter() - self.started_at, 3)
            maybe_awaitable = self.audio_handler(sentence, audio, self._stop_event)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable


if __name__ == "__main__":
    print("TTS test: synthesizing...")
    audio = synthesize("Hello, I'm Donna. How can I help you today?")
    print(f"Got {len(audio)} bytes. Playing...")
    play_audio(audio)
    print("Done.")
