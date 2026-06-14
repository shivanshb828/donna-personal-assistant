from pathlib import Path
from unittest.mock import MagicMock

import pytest

from donna.glue.tools.registry import ToolRegistry
from donna.telephony.db import create_call_session, init_telephony_db, record_consent


@pytest.fixture
def registry(tmp_path: Path) -> ToolRegistry:
    telephony_db = tmp_path / "telephony.sqlite"
    context_db = tmp_path / "context.sqlite"
    calendar_db = tmp_path / "calendar.sqlite"
    init_telephony_db(telephony_db)
    return ToolRegistry(
        telephony_db_path=telephony_db,
        context_db_path=context_db,
        calendar_db_path=calendar_db,
    )


def test_record_consent(registry: ToolRegistry, tmp_path: Path):
    telephony_db = tmp_path / "telephony.sqlite"
    create_call_session(telephony_db, call_sid="CA1", phone="+14085550101")
    result = registry.execute(
        call_sid="CA1",
        tool_name="record_consent",
        args={"consent_type": "ai_disclosure", "granted": True},
    )
    assert result.ok


def test_intake_requires_consent(registry: ToolRegistry, tmp_path: Path):
    telephony_db = tmp_path / "telephony.sqlite"
    create_call_session(telephony_db, call_sid="CA2", phone="+14085550101")
    result = registry.execute(
        call_sid="CA2",
        tool_name="intake.start",
        args={"caller_name": "Maria Lopez"},
    )
    assert not result.ok
    record_consent(telephony_db, call_session_id="CA2", consent_type="ai_disclosure", granted=True)
    record_consent(telephony_db, call_session_id="CA2", consent_type="recording", granted=True)
    result = registry.execute(
        call_sid="CA2",
        tool_name="intake.start",
        args={"caller_name": "Maria Lopez", "injury_summary": "neck pain"},
    )
    assert result.ok


def test_case_qualify(registry: ToolRegistry, tmp_path: Path):
    telephony_db = tmp_path / "telephony.sqlite"
    create_call_session(telephony_db, call_sid="CA3", phone="+14085550101")
    result = registry.execute(
        call_sid="CA3",
        tool_name="case.qualify",
        args={"jurisdiction": "CA", "injury_present": True, "prior_attorney": False},
    )
    assert result.ok
    assert result.data["qualified"] is True
