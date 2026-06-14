import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

from donna.glue.router.session_router import SessionRouter
from donna.telephony.local_provider import LocalVoiceSession, TWILIO_FRAME_BYTES


def test_handle_mulaw_frame_accumulates_partial_chunks():
    async def _run():
        router = MagicMock(spec=SessionRouter)
        session = LocalVoiceSession(
            call_sid="CA1",
            stream_sid="MS1",
            agent_mode="inbound_intake",
            caller_name=None,
            is_returning=False,
            router=router,
            dashboard_ws="ws://localhost:3999",
            echo_mode=False,
        )

        pcm16 = np.full(256, 5000, dtype=np.int16).tobytes()
        speech_result = {"is_speaking": False, "speech_ended": True, "audio": pcm16 * 2}

        with patch("donna.telephony.local_provider.twilio_payload_to_pcm16_16k", return_value=pcm16):
            with patch.object(session.vad, "process", return_value=speech_result):
                with patch.object(session, "_on_speech", new=AsyncMock(return_value=[])) as on_speech:
                    await session.handle_mulaw_frame("AAAA")
                    assert on_speech.await_count == 0
                    assert len(session.pcm_buffer) > 0
                    await session.handle_mulaw_frame("AAAA")
                    assert on_speech.await_count == 1

    asyncio.run(_run())


def test_speak_returns_chunked_frames():
    async def _run():
        router = MagicMock(spec=SessionRouter)
        session = LocalVoiceSession(
            call_sid="CA2",
            stream_sid="MS2",
            agent_mode="inbound_intake",
            caller_name=None,
            is_returning=False,
            router=router,
            dashboard_ws="ws://localhost:3999",
            echo_mode=False,
        )
        mulaw = b"\xff" * (TWILIO_FRAME_BYTES * 3 + 10)
        with patch("donna.telephony.local_provider.synthesize", return_value=b"RIFF...."):
            with patch(
                "donna.telephony.local_provider.wav_to_twilio_payload",
                return_value=__import__("base64").b64encode(mulaw).decode(),
            ):
                with patch("donna.telephony.local_provider.broadcast_event", new=AsyncMock()):
                    frames = await session._speak("Test response")
        assert len(frames) == 4

    asyncio.run(_run())
