import io
import wave
from unittest.mock import MagicMock, patch
import asyncio

import numpy as np
import pytest

from donna.voice.stt import TranscriptionEvent, _pcm16_to_wav, stream_transcription, transcribe_audio


def _make_pcm(seconds=0.5, rate=16000) -> bytes:
    n = int(rate * seconds)
    return (np.zeros(n, dtype=np.int16)).tobytes()


class TestPcmToWav:
    def test_valid_wav_header(self):
        pcm = _make_pcm()
        wav = _pcm16_to_wav(pcm)
        buf = io.BytesIO(wav)
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 16000
            assert wf.getsampwidth() == 2

    def test_wav_contains_pcm_data(self):
        pcm = _make_pcm(1.0)
        wav = _pcm16_to_wav(pcm)
        buf = io.BytesIO(wav)
        with wave.open(buf, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
        assert frames == pcm


class TestTranscribeAudio:
    def test_returns_text(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "Hello world"}
        mock_response.raise_for_status = MagicMock()

        with patch("donna.voice.stt.httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.return_value = mock_response
            result = transcribe_audio(_make_pcm())

        assert result == "Hello world"

    def test_strips_whitespace(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "  hello  "}
        mock_response.raise_for_status = MagicMock()

        with patch("donna.voice.stt.httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.return_value = mock_response
            result = transcribe_audio(_make_pcm())

        assert result == "hello"

    def test_empty_response(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        with patch("donna.voice.stt.httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.return_value = mock_response
            result = transcribe_audio(_make_pcm())

        assert result == ""

    def test_server_error_raises(self):
        import httpx
        with patch("donna.voice.stt.httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.post.side_effect = httpx.ConnectError("refused")
            with pytest.raises(httpx.ConnectError):
                transcribe_audio(_make_pcm())


def test_stream_transcription_emits_final_event():
    async def _run() -> None:
        with patch("donna.voice.stt.transcribe_audio", return_value="hello world"):
            events = [
                event
                async for event in stream_transcription([_make_pcm(0.25), _make_pcm(0.25)])
            ]
        assert events == [TranscriptionEvent(text="hello world", is_final=True)]

    asyncio.run(_run())
