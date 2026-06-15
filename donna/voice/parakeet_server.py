from __future__ import annotations

import io
import os
import threading
import time
import wave
from dataclasses import dataclass

import numpy as np
import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from transformers import AutoModelForCTC, AutoProcessor

TARGET_SAMPLE_RATE = 16000


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def _wav_to_float32(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if sample_width != 2:
        raise ValueError(f"unsupported sample width: {sample_width}")

    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    audio /= 32768.0
    return audio, sample_rate


def _resample(audio: np.ndarray, source_rate: int, target_rate: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    if source_rate == target_rate:
        return audio
    duration = len(audio) / float(source_rate)
    target_length = max(1, int(round(duration * target_rate)))
    source_positions = np.linspace(0.0, duration, num=len(audio), endpoint=False)
    target_positions = np.linspace(0.0, duration, num=target_length, endpoint=False)
    return np.interp(target_positions, source_positions, audio).astype(np.float32)


@dataclass
class ParakeetConfig:
    model_name: str = os.getenv("DONNA_PARAKEET_MODEL", "nvidia/parakeet-ctc-0.6b")
    device: str = os.getenv("DONNA_PARAKEET_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    max_audio_seconds: float = float(os.getenv("DONNA_PARAKEET_MAX_AUDIO_SECONDS", "30"))
    compile_model: bool = _env_flag("DONNA_PARAKEET_COMPILE", False)


class ParakeetRuntime:
    def __init__(self, cfg: ParakeetConfig) -> None:
        self.cfg = cfg
        self.lock = threading.Lock()
        self.device = torch.device(cfg.device if cfg.device == "cpu" or torch.cuda.is_available() else "cpu")
        self.dtype = torch.float16 if self.device.type == "cuda" else torch.float32

        if self.device.type == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.set_float32_matmul_precision("high")

        self.processor = AutoProcessor.from_pretrained(cfg.model_name)
        self.model = AutoModelForCTC.from_pretrained(cfg.model_name, torch_dtype=self.dtype)
        self.model.to(self.device)
        self.model.eval()
        if cfg.compile_model and hasattr(torch, "compile"):
            self.model = torch.compile(self.model, mode="reduce-overhead", fullgraph=False)

        # Warm the kernels and cache path once at startup.
        self.transcribe(np.zeros(TARGET_SAMPLE_RATE, dtype=np.float32), TARGET_SAMPLE_RATE)

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        if not len(audio):
            return ""
        if sample_rate != TARGET_SAMPLE_RATE:
            audio = _resample(audio, sample_rate, TARGET_SAMPLE_RATE)
            sample_rate = TARGET_SAMPLE_RATE

        if len(audio) > int(self.cfg.max_audio_seconds * sample_rate):
            raise ValueError("audio too long")

        inputs = self.processor(
            audio=audio,
            sampling_rate=sample_rate,
            return_tensors="pt",
        )
        input_values = inputs["input_values"].to(self.device)
        attention_mask = inputs.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.device)

        with self.lock, torch.inference_mode():
            outputs = self.model(input_values=input_values, attention_mask=attention_mask)
            predicted_ids = torch.argmax(outputs.logits, dim=-1)

        text = self.processor.batch_decode(predicted_ids)[0]
        return _normalize_text(text)


cfg = ParakeetConfig()
app = FastAPI(title="Donna Parakeet STT")
runtime: ParakeetRuntime | None = None


@app.on_event("startup")
def _startup() -> None:
    global runtime
    runtime = ParakeetRuntime(cfg)


@app.get("/health")
def health() -> dict:
    assert runtime is not None
    return {
        "ok": True,
        "model": cfg.model_name,
        "device": str(runtime.device),
    }


@app.post("/v1/audio/transcriptions")
async def transcriptions(
    file: UploadFile = File(...),
    model: str = Form(default=""),
    language: str = Form(default="en"),
    response_format: str = Form(default="json"),
) -> dict:
    del model, language, response_format
    assert runtime is not None

    started = time.perf_counter()
    try:
        audio_bytes = await file.read()
        audio, sample_rate = _wav_to_float32(audio_bytes)
        text = runtime.transcribe(audio, sample_rate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except wave.Error as exc:
        raise HTTPException(status_code=400, detail=f"invalid wav: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "text": text,
        "model": cfg.model_name,
        "seconds": round(time.perf_counter() - started, 3),
    }
