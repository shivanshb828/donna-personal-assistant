"""Wake-word detection for "Hey Donna" using openwakeword.

openwakeword supports custom wake words. For hackathon, use the closest
built-in model ("hey_jarvis") and optionally train a custom "hey_donna"
model if time permits.
"""

import os
import numpy as np


class WakeWordDetector:
    """Detects "Hey Donna" wake word in audio stream."""

    def __init__(self, threshold: float = 0.5, model_name: str = "hey_jarvis"):
        """
        Args:
            threshold: Detection confidence threshold (0-1).
            model_name: openwakeword model name. Use "hey_jarvis" as default
                       or path to custom "hey_donna.onnx" if trained.
        """
        self.threshold = threshold
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return

        try:
            import openwakeword
            from openwakeword.model import Model

            openwakeword.utils.download_models()

            custom_path = os.environ.get("DONNA_WAKEWORD_MODEL")
            if custom_path and os.path.exists(custom_path):
                self._model = Model(wakeword_models=[custom_path])
                self.model_name = "hey_donna"
            else:
                self._model = Model(wakeword_models=[self.model_name])
        except ImportError:
            raise RuntimeError("Install openwakeword: pip install openwakeword")

    def detect(self, pcm_chunk: bytes) -> bool:
        """Check if wake word is detected in audio chunk.

        Args:
            pcm_chunk: Raw 16-bit PCM audio at 16kHz mono.
                      openwakeword expects 1280 samples (80ms) per frame.

        Returns:
            True if wake word detected above threshold.
        """
        self._load_model()

        audio = np.frombuffer(pcm_chunk, dtype=np.int16)
        prediction = self._model.predict(audio)

        for key, score in prediction.items():
            if score >= self.threshold:
                return True
        return False

    def reset(self):
        if self._model is not None:
            self._model.reset()


class KeyboardWakeWord:
    """Fallback: press Enter to activate Donna."""

    def __init__(self):
        self._triggered = False

    def check_trigger(self) -> bool:
        """Non-blocking check if Enter was pressed."""
        import select
        import sys
        if select.select([sys.stdin], [], [], 0.0)[0]:
            sys.stdin.readline()
            return True
        return False

    def detect(self, pcm_chunk: bytes) -> bool:
        return self._triggered

    def reset(self):
        self._triggered = False


def create_wake_word(use_audio: bool = True, **kwargs) -> WakeWordDetector:
    """Factory — audio wake word if available, keyboard fallback."""
    if use_audio:
        try:
            detector = WakeWordDetector(**kwargs)
            detector._load_model()
            return detector
        except Exception:
            pass
    return KeyboardWakeWord()
