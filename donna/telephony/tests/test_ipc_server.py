import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from donna.ipc.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_ipc_forwards_email_draft_to_dashboard(client):
    payload = {
        "source": "email",
        "session_id": "case-2026-001",
        "text": json.dumps(
            {
                "type": "email_draft_pending",
                "draft_id": "draft-1",
                "case_id": "case-2026-001",
                "to": "adjuster@insurance.com",
                "subject": "Follow up",
                "email_type": "adjuster_follow_up",
                "preview": "Hello",
            }
        ),
        "type": "email_draft_pending",
    }

    with patch("donna.ipc.server.broadcast_event", new_callable=AsyncMock) as broadcast:
        resp = client.post("/ipc", json=payload)

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "routed_to": "dashboard"}
    broadcast.assert_awaited_once()
    event = broadcast.await_args.args[1]
    assert event["type"] == "email_draft_pending"
    assert event["draft_id"] == "draft-1"


def test_ipc_ignores_unknown_types(client):
    resp = client.post(
        "/ipc",
        json={
            "source": "test",
            "session_id": "x",
            "text": "hello",
            "type": "unknown_event",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
