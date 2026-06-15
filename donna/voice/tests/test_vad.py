import struct
import numpy as np
import pytest

from donna.voice.vad import EnergyVAD, create_vad


def _silent_chunk(n_samples=512) -> bytes:
    return (np.zeros(n_samples, dtype=np.int16)).tobytes()


def _loud_chunk(n_samples=512, amplitude=2000) -> bytes:
    return (np.full(n_samples, amplitude, dtype=np.int16)).tobytes()


class TestEnergyVAD:
    def test_silence_not_speaking(self):
        vad = EnergyVAD()
        result = vad.process(_silent_chunk())
        assert not result["is_speaking"]
        assert not result["speech_ended"]

    def test_loud_chunk_is_speaking(self):
        vad = EnergyVAD()
        result = vad.process(_loud_chunk())
        assert result["is_speaking"]
        assert result["rms"] > 0
        assert 0.0 <= result["confidence"] <= 1.0

    def test_speech_ended_after_silence(self):
        vad = EnergyVAD()
        # trigger speaking
        vad.process(_loud_chunk())
        # feed enough silence to trigger end
        ended = False
        for _ in range(EnergyVAD.SILENCE_FRAMES + 1):
            result = vad.process(_silent_chunk())
            if result["speech_ended"]:
                ended = True
                break
        assert ended, "speech_ended never fired"

    def test_speech_ended_audio_not_empty(self):
        # Regression: reset() was called before building return dict → empty audio on speech_ended
        vad = EnergyVAD()
        vad.process(_loud_chunk())
        final_result = None
        for _ in range(EnergyVAD.SILENCE_FRAMES + 1):
            result = vad.process(_silent_chunk())
            if result["speech_ended"]:
                final_result = result
                break
        assert final_result is not None
        assert len(final_result["audio"]) > 0, "speech_ended returned empty audio (reset bug)"

    def test_audio_accumulates(self):
        vad = EnergyVAD()
        chunk = _loud_chunk()
        vad.process(chunk)
        result = vad.process(chunk)
        assert len(result["audio"]) == len(chunk) * 2

    def test_reset_clears_buffer(self):
        vad = EnergyVAD()
        vad.process(_loud_chunk())
        vad.reset()
        assert vad._audio_buf == b""
        assert vad._speaking is False
        assert vad._silence_count == 0


class TestCreateVad:
    def test_returns_something(self):
        vad = create_vad()
        assert vad is not None

    def test_has_process_method(self):
        vad = create_vad()
        assert callable(getattr(vad, "process", None))
