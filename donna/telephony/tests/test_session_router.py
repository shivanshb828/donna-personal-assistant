from pathlib import Path
import asyncio
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from donna.glue.router.session_router import SessionRouter
from donna.glue.tools.registry import ToolRegistry
from donna.telephony.db import create_call_session, get_call_session, init_telephony_db, update_call_phase
from donna.telephony.llm import DonnaLLM, LLMResult, LLMStreamChunk


@pytest.fixture
def router(tmp_path: Path) -> SessionRouter:
    telephony_db = tmp_path / "telephony.sqlite"
    context_db = tmp_path / "context.sqlite"
    calendar_db = tmp_path / "calendar.sqlite"
    init_telephony_db(telephony_db)
    llm = MagicMock(spec=DonnaLLM)
    llm.chat.return_value = LLMResult(text="I can help with that.")
    llm.parse_tool_args.side_effect = DonnaLLM.parse_tool_args
    return SessionRouter(
        telephony_db_path=telephony_db,
        context_db_path=context_db,
        calendar_db_path=calendar_db,
        llm=llm,
        tools=ToolRegistry(
            telephony_db_path=telephony_db,
            context_db_path=context_db,
            calendar_db_path=calendar_db,
        ),
    )


def test_greeting_inbound(router: SessionRouter):
    text = router.greeting(call_sid="CA1", agent_mode="inbound_intake")
    assert "Donna" in text
    assert "AI" in text


def test_greeting_outbound(router: SessionRouter):
    text = router.greeting(call_sid="CA2", agent_mode="outbound_lead", caller_name="Maria")
    assert "Maria" in text


def test_handle_turn(router: SessionRouter, tmp_path: Path):
    create_call_session(tmp_path / "telephony.sqlite", call_sid="CA3", phone="+14085550101")
    result = router.handle_turn(call_sid="CA3", user_text="I was in a car accident", agent_mode="inbound_intake")
    assert "help" in result.reply.lower()


def test_local_assistant_can_start_intake_without_consent(router: SessionRouter, tmp_path: Path):
    telephony_db = tmp_path / "telephony.sqlite"
    create_call_session(telephony_db, call_sid="LOCAL1", phone=None, agent_mode="local_assistant")
    router.llm.chat.side_effect = [
        LLMResult(
            text="",
            tool_calls=[
                {
                    "function": {
                        "name": "intake.start",
                        "arguments": {"caller_name": "Maria Lopez"},
                    }
                }
            ],
        ),
        LLMResult(text="I've started Maria Lopez's intake. What happened in the incident?"),
    ]

    result = router.handle_turn(
        call_sid="LOCAL1",
        user_text="Start an intake for Maria Lopez",
        agent_mode="local_assistant",
    )

    assert result.tool_results[0]["ok"] is True
    assert get_call_session(telephony_db, "LOCAL1").phase == "INTAKE"
    first_tools = {
        tool["function"]["name"]
        for tool in router.llm.chat.call_args_list[0].kwargs["tools"]
    }
    assert "intake.start" in first_tools
    assert "calendar.create_event" not in first_tools


def test_disclosure_phase_gates_telephony_tools(router: SessionRouter, tmp_path: Path):
    create_call_session(tmp_path / "telephony.sqlite", call_sid="CA4", phone="+14085550101")
    router.llm.chat.return_value = LLMResult(text="Let me ask a few questions first.")

    router.handle_turn(
        call_sid="CA4",
        user_text="Can you book me tomorrow?",
        agent_mode="inbound_intake",
    )

    tool_names = {
        tool["function"]["name"]
        for tool in router.llm.chat.call_args.kwargs["tools"]
    }
    assert "record_consent" in tool_names
    assert "calendar.create_event" not in tool_names


def test_calendar_confirmation_skips_second_llm_turn(router: SessionRouter, tmp_path: Path):
    telephony_db = tmp_path / "telephony.sqlite"
    create_call_session(telephony_db, call_sid="LOCAL2", phone=None, agent_mode="local_assistant")
    update_call_phase(telephony_db, "LOCAL2", "BOOKING")
    router.llm.chat.side_effect = [
        LLMResult(
            text="",
            tool_calls=[
                {
                    "function": {
                        "name": "calendar.create_event",
                        "arguments": {
                            "client_id": "client-123",
                            "scheduled_at": "2026-06-19T10:00:00-07:00",
                            "title": "Consultation",
                        },
                    }
                }
            ],
        )
    ]

    with patch("donna.glue.tools.registry.book_calendar", return_value={"formatted_confirmation": "Booked for June 19 at 10:00 AM."}):
        result = router.handle_turn(
            call_sid="LOCAL2",
            user_text="Book me for tomorrow at ten.",
            agent_mode="local_assistant",
        )

    assert result.reply == "Booked for June 19 at 10:00 AM."
    assert router.llm.chat.call_count == 1


def test_stream_turn_emits_sentence_boundaries(router: SessionRouter, tmp_path: Path):
    telephony_db = tmp_path / "telephony.sqlite"
    create_call_session(telephony_db, call_sid="LOCAL3", phone=None, agent_mode="local_assistant")

    async def _chat_stream(**kwargs):
        yield LLMStreamChunk(text_delta="Maria is recovering.", text="Maria is recovering.", first_token_seconds=0.21)
        yield LLMStreamChunk(
            text_delta=" Her consultation is booked.",
            text="Maria is recovering. Her consultation is booked.",
            done=True,
            first_token_seconds=0.21,
        )

    router.llm.chat_stream = _chat_stream

    async def _run() -> None:
        seen: list[str] = []
        outcome = await router.stream_turn(
            call_sid="LOCAL3",
            user_text="Status update",
            agent_mode="local_assistant",
            on_sentence=seen.append,
        )
        assert outcome.result.reply == "Maria is recovering. Her consultation is booked."
        assert seen == ["Maria is recovering.", "Her consultation is booked."]
        assert outcome.first_token_seconds == 0.21
        assert outcome.first_sentence_seconds is not None

    asyncio.run(_run())


def test_stream_turn_short_circuits_record_consent(router: SessionRouter, tmp_path: Path):
    telephony_db = tmp_path / "telephony.sqlite"
    create_call_session(telephony_db, call_sid="LOCAL4", phone=None, agent_mode="local_assistant")

    async def _chat_stream(**kwargs):
        yield LLMStreamChunk(
            text="",
            tool_calls=[
                {
                    "function": {
                        "name": "record_consent",
                        "arguments": {"consent_type": "recording", "granted": True},
                    }
                }
            ],
            done=True,
            first_token_seconds=0.14,
        )

    router.llm.chat_stream = _chat_stream
    router.llm.parse_tool_args.side_effect = DonnaLLM.parse_tool_args

    async def _run() -> None:
        seen: list[str] = []
        outcome = await router.stream_turn(
            call_sid="LOCAL4",
            user_text="Yes, you can record me.",
            agent_mode="local_assistant",
            on_sentence=seen.append,
        )
        assert outcome.result.reply == "Thanks. I've noted your consent. Please tell me what happened."
        assert seen == ["Thanks.", "I've noted your consent.", "Please tell me what happened."]

    asyncio.run(_run())
