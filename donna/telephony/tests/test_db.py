from pathlib import Path

import pytest

from donna.telephony.db import (
    add_message,
    complete_call_session,
    create_call_session,
    create_intake_record,
    create_lead,
    get_call_session,
    has_consent,
    init_telephony_db,
    list_leads,
    list_messages,
    normalize_phone,
    record_consent,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "telephony.sqlite"
    init_telephony_db(path)
    return path


def test_normalize_phone():
    assert normalize_phone("(408) 555-0101") == "+14085550101"
    assert normalize_phone("+15105550102") == "+15105550102"


def test_call_session_lifecycle(db_path: Path):
    create_call_session(db_path, call_sid="CA001", phone="+14085550101")
    session = get_call_session(db_path, "CA001")
    assert session is not None
    assert session.agent_mode == "inbound_intake"
    complete_call_session(db_path, call_sid="CA001", duration_seconds=42, outcome="BOOKING")
    updated = get_call_session(db_path, "CA001")
    assert updated.duration_seconds == 42


def test_consent_and_intake(db_path: Path):
    create_call_session(db_path, call_sid="CA002", phone="+14085550101")
    record_consent(db_path, call_session_id="CA002", consent_type="recording", granted=True)
    assert has_consent(db_path, "CA002", "recording")
    intake_id = create_intake_record(db_path, call_session_id="CA002", fields={"injury_summary": "neck pain"})
    assert intake_id.startswith("intake-")


def test_leads_and_messages(db_path: Path):
    lead = create_lead(db_path, name="Jane Doe", phone="4085550199", incident_summary="rear-end")
    leads = list_leads(db_path)
    assert any(item.id == lead.id for item in leads)
    msg_id = add_message(db_path, body="Follow up tomorrow", direction="outbound", channel="chat")
    messages = list_messages(db_path)
    assert any(item["id"] == msg_id for item in messages)
