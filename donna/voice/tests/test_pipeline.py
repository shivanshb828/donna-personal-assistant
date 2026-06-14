import asyncio
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("pyaudio")

from donna.glue.router.session_router import RouterResult
from donna.voice import pipeline


def test_run_text_query_uses_shared_router_and_emits_tool_events(capsys):
    runtime = pipeline.LocalVoiceRuntime(session_id="local-test-1", router=MagicMock())
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
