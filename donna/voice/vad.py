from __future__ import annotations

import os

import numpy as np


DEFAULT_SILENCE_FRAMES = 12
PUSH_TO_TALK_SILENCE_FRAMES = 10


def _silence_frames(profile: str = "default", override: int | None = None) -> int:
    if override is not None:
        return override
    env_value = os.getenv("DONNA_VAD_SILENCE_FRAMES")
    if env_value:
        try:
            return max(1, int(env_value))
        except ValueError:
            pass
    if profile == "push_to_talk":
        return PUSH_TO_TALK_SILENCE_FRAMES
    return DEFAULT_SILENCE_FRAMES


class SileroVAD:
    THRESHOLD = 0.5
    SILENCE_FRAMES = DEFAULT_SILENCE_FRAMES

    def __init__(self, *, profile: str = "default", silence_frames: int | None = None):
        import torch
        self.model, utils = torch.hub.load(
            "snakers4/silero-vad", "silero_vad", force_reload=False
        )
        self.model.eval()
        self.silence_frames = _silence_frames(profile, silence_frames)
        self._audio_buf = b""
        self._silence_count = 0
        self._speaking = False

    def process(self, chunk: bytes) -> dict:
        import torch
        audio_np = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
        tensor = torch.from_numpy(audio_np)
        with torch.no_grad():
            conf = self.model(tensor, 16000).item()
        is_speaking = bool(conf >= self.THRESHOLD)
        if is_speaking:
            self._speaking = True
            self._silence_count = 0
        else:
            self._silence_count += 1
        self._audio_buf += chunk
        speech_ended = self._speaking and self._silence_count >= self.silence_frames
        # Capture buffer BEFORE reset so speech_ended doesn't return empty audio
        audio_out = self._audio_buf
        if speech_ended:
            self.reset()
        return {"is_speaking": is_speaking, "speech_ended": speech_ended, "audio": audio_out}

    def reset(self):
        self._audio_buf = b""
        self._silence_count = 0
        self._speaking = False


class EnergyVAD:
    THRESHOLD = 500
    SILENCE_FRAMES = DEFAULT_SILENCE_FRAMES

    def __init__(self, *, profile: str = "default", silence_frames: int | None = None):
        self.silence_frames = _silence_frames(profile, silence_frames)
        self._audio_buf = b""
        self._silence_count = 0
        self._speaking = False

    def process(self, chunk: bytes) -> dict:
        audio_np = np.frombuffer(chunk, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_np.astype(np.float32) ** 2))
        is_speaking = bool(rms >= self.THRESHOLD)
        if is_speaking:
            self._speaking = True
            self._silence_count = 0
        else:
            self._silence_count += 1
        self._audio_buf += chunk
        speech_ended = self._speaking and self._silence_count >= self.silence_frames
        # Capture buffer BEFORE reset so speech_ended doesn't return empty audio
        audio_out = self._audio_buf
        if speech_ended:
            self.reset()
        return {"is_speaking": is_speaking, "speech_ended": speech_ended, "audio": audio_out}

    def reset(self):
        self._audio_buf = b""
        self._silence_count = 0
        self._speaking = False


def create_vad(*, profile: str = "default"):
    try:
        vad = SileroVAD(profile=profile)
        print("[VAD] Silero-VAD loaded")
        return vad
    except Exception as e:
        print(f"[VAD] Silero failed ({e}), using energy VAD")
        return EnergyVAD(profile=profile)
