from pathlib import Path
from unittest.mock import MagicMock

import pytest

from donna.glue.router.session_router import SessionRouter
from donna.glue.tools.registry import ToolRegistry
from donna.telephony.db import create_call_session, init_telephony_db
from donna.telephony.llm import DonnaLLM, LLMResult


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
