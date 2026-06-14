from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from donna.telephony.config import TelephonyConfig
from donna.telephony.server import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    config = TelephonyConfig(
        port=3002,
        public_url="http://testserver",
        twilio_account_sid="",
        twilio_auth_token="",
        twilio_phone_number="",
        telephony_db=tmp_path / "telephony.sqlite",
        context_db=tmp_path / "context.sqlite",
        calendar_db=tmp_path / "calendar.sqlite",
        dashboard_ws="ws://localhost:3999",
        ollama_url="http://localhost:11434",
        ollama_model="test-model",
        firm_name="Test Firm",
        echo_mode=True,
        validate_twilio_signature=False,
    )
    return TestClient(create_app(config))


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_voice_inbound_returns_twiml(client: TestClient):
    resp = client.post("/voice", data={"CallSid": "CA1234567890abcdef1234567890ab", "From": "+14085550101"})
    assert resp.status_code == 200
    assert "Stream" in resp.text


def test_leads_api(client: TestClient):
    create = client.post(
        "/api/leads",
        json={"name": "Jane Doe", "phone": "+14085550199", "incident_summary": "rear-end collision"},
    )
    assert create.status_code == 200
    listing = client.get("/api/leads")
    assert listing.status_code == 200
    assert len(listing.json()["leads"]) == 1
