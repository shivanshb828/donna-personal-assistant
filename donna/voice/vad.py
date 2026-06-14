"""Voice Activity Detection using silero-vad.

Detects when user starts and stops speaking. Used by the pipeline to know
when to send audio to STT.
"""

import numpy as np
import torch


class VoiceActivityDetector:
    """Silero VAD wrapper for real-time speech detection."""

    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000, min_silence_ms: int = 800):
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.min_silence_samples = int(sample_rate * min_silence_ms / 1000)

        self.model, self.utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )
        self.model.eval()

        self._is_speaking = False
        self._silence_counter = 0
        self._audio_buffer = []

    def reset(self):
        self._is_speaking = False
        self._silence_counter = 0
        self._audio_buffer = []
        self.model.reset_states()

    def process_chunk(self, pcm_chunk: bytes) -> dict:
        """Process a chunk of PCM16 audio. Returns speech state.

        Args:
            pcm_chunk: Raw 16-bit PCM audio at 16kHz mono.

        Returns:
            dict with keys:
                - is_speaking: bool
                - speech_ended: bool (True when silence after speech detected)
                - audio: bytes (full utterance audio if speech_ended, else None)
        """
        audio_int16 = np.frombuffer(pcm_chunk, dtype=np.int16)
        audio_float = audio_int16.astype(np.float32) / 32768.0
        tensor = torch.from_numpy(audio_float)

        # silero-vad expects 512 samples at 16kHz
        chunk_size = 512
        speech_prob = 0.0
        for i in range(0, len(tensor), chunk_size):
            chunk = tensor[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = torch.nn.functional.pad(chunk, (0, chunk_size - len(chunk)))
            speech_prob = self.model(chunk, self.sample_rate).item()

        result = {"is_speaking": False, "speech_ended": False, "audio": None}

        if speech_prob >= self.threshold:
            if not self._is_speaking:
                self._is_speaking = True
                self._audio_buffer = []
            self._silence_counter = 0
            self._audio_buffer.append(pcm_chunk)
            result["is_speaking"] = True

        elif self._is_speaking:
            self._audio_buffer.append(pcm_chunk)
            self._silence_counter += len(audio_int16)

            if self._silence_counter >= self.min_silence_samples:
                result["speech_ended"] = True
                result["audio"] = b"".join(self._audio_buffer)
                self.reset()

        return result


# Simpler energy-based fallback if silero unavailable
class EnergyVAD:
    """Simple energy-threshold VAD as fallback."""

    def __init__(self, threshold: int = 500, min_silence_ms: int = 800, sample_rate: int = 16000):
        self.threshold = threshold
        self.min_silence_samples = int(sample_rate * min_silence_ms / 1000)
        self._is_speaking = False
        self._silence_counter = 0
        self._audio_buffer = []

    def reset(self):
        self._is_speaking = False
        self._silence_counter = 0
        self._audio_buffer = []

    def process_chunk(self, pcm_chunk: bytes) -> dict:
        audio = np.frombuffer(pcm_chunk, dtype=np.int16)
        energy = np.abs(audio).mean()

        result = {"is_speaking": False, "speech_ended": False, "audio": None}

        if energy >= self.threshold:
            if not self._is_speaking:
                self._is_speaking = True
                self._audio_buffer = []
            self._silence_counter = 0
            self._audio_buffer.append(pcm_chunk)
            result["is_speaking"] = True

        elif self._is_speaking:
            self._audio_buffer.append(pcm_chunk)
            self._silence_counter += len(audio)

            if self._silence_counter >= self.min_silence_samples:
                result["speech_ended"] = True
                result["audio"] = b"".join(self._audio_buffer)
                self.reset()

        return result


def create_vad(use_silero: bool = True, **kwargs):
    """Factory — silero if available, energy fallback otherwise."""
    if use_silero:
        try:
            return VoiceActivityDetector(**kwargs)
        except Exception:
            pass
    return EnergyVAD(**kwargs)
