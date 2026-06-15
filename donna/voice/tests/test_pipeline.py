import asyncio
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("pyaudio")

from donna.glue.router.session_router import RouterResult
from donna.voice import pipeline


def test_run_text_query_uses_shared_router_and_emits_tool_events(capsys):
    runtime = pipeline.LocalVoiceRuntime(
        session_id="local-test-1",
        router=MagicMock(),
        record_vad=MagicMock(),
        interrupt_vad=MagicMock(),
    )
    runtime.router.handle_turn.return_value = RouterResult(
        reply="Maria Lopez is recovering and has a consultation scheduled.",
        tool_results=[
            {
                "tool": "notify.dashboard",
                "ok": True,
                "data": {"sent": True},
                "error": None,
            }
        ],
    )

    async def _run() -> None:
        with patch("donna.voice.pipeline.emit_to_dashboard") as emit:
            await pipeline._run_text_query("How is Maria Lopez doing?", runtime)
        assert runtime.router.handle_turn.call_args.kwargs == {
            "call_sid": "local-test-1",
            "user_text": "How is Maria Lopez doing?",
            "agent_mode": "local_assistant",
        }
        events = [call.args[0] for call in emit.await_args_list]
        assert [event["type"] for event in events] == [
            "user_speech",
            "tool_result",
            "donna_speech",
            "turn_timing",
        ]
        assert all(event["callSid"] == "local-test-1" for event in events)
        assert all(event["sessionId"] == "local-test-1" for event in events)
        assert events[-1]["llm_seconds"] >= 0
        assert events[-1]["total_seconds"] >= events[-1]["llm_seconds"]

    asyncio.run(_run())

    output = capsys.readouterr().out
    assert "You: How is Maria Lopez doing?" in output
    assert "Donna: Maria Lopez is recovering and has a consultation scheduled." in output


def test_interruption_tracker_sets_stop_event_and_accumulates_audio():
    tracker = pipeline.InterruptionTracker()
    stop_event = MagicMock()

    vad = MagicMock()
    vad.process.side_effect = [
        {"is_speaking": True, "speech_ended": False, "audio": b"hello", "confidence": 0.95, "rms": 1800},
        {"is_speaking": True, "speech_ended": False, "audio": b"hello!", "confidence": 0.95, "rms": 1800},
        {"is_speaking": True, "speech_ended": False, "audio": b"hello!!", "confidence": 0.95, "rms": 1800},
        {"is_speaking": True, "speech_ended": False, "audio": b"hello!!!", "confidence": 0.95, "rms": 1800},
        {"is_speaking": True, "speech_ended": False, "audio": b"hello!!!!", "confidence": 0.95, "rms": 1800},
        {"is_speaking": False, "speech_ended": True, "audio": b"hello!!!!\x00", "confidence": 0.4, "rms": 100},
    ]

    assert tracker.feed(vad=vad, chunk=b"chunk-1", stop_event=stop_event) is False
    stop_event.set.assert_not_called()
    assert tracker.interrupted is False
    assert tracker.audio is None

    assert tracker.feed(vad=vad, chunk=b"chunk-2", stop_event=stop_event) is False
    stop_event.set.assert_not_called()
    assert tracker.interrupted is False

    assert tracker.feed(vad=vad, chunk=b"chunk-3", stop_event=stop_event) is False
    stop_event.set.assert_not_called()
    assert tracker.interrupted is False

    assert tracker.feed(vad=vad, chunk=b"chunk-4", stop_event=stop_event) is False
    stop_event.set.assert_not_called()
    assert tracker.interrupted is False

    assert tracker.feed(vad=vad, chunk=b"chunk-5", stop_event=stop_event) is False
    stop_event.set.assert_called_once()
    assert tracker.interrupted is True

    assert tracker.feed(vad=vad, chunk=b"chunk-6", stop_event=stop_event) is True
    assert tracker.audio == b"hello!!!!\x00"


def test_interruption_tracker_ignores_audio_during_grace_window():
    tracker = pipeline.InterruptionTracker()
    stop_event = MagicMock()

    vad = MagicMock()
    vad.process.return_value = {"is_speaking": True, "speech_ended": False, "audio": b"echo"}

    assert tracker.feed(vad=vad, chunk=b"chunk-1", stop_event=stop_event, can_interrupt=False) is False
    stop_event.set.assert_not_called()
    assert tracker.interrupted is False
    assert tracker.speech_chunks == 0


def test_interruption_tracker_ignores_low_rms_or_low_confidence_audio():
    tracker = pipeline.InterruptionTracker()
    stop_event = MagicMock()

    vad = MagicMock()
    vad.process.side_effect = [
        {"is_speaking": True, "speech_ended": False, "audio": b"music", "confidence": 0.95, "rms": 300},
        {"is_speaking": True, "speech_ended": False, "audio": b"music", "confidence": 0.3, "rms": 2000},
    ]

    assert tracker.feed(vad=vad, chunk=b"chunk-1", stop_event=stop_event) is False
    assert tracker.feed(vad=vad, chunk=b"chunk-2", stop_event=stop_event) is False
    stop_event.set.assert_not_called()
    assert tracker.interrupted is False
    assert tracker.speech_chunks == 0
