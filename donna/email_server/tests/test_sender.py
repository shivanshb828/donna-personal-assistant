import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from donna.email_server.sender import (
    send_email,
    approve_and_send,
    reject_draft,
    list_drafts,
    load_draft,
    _AUTO_SEND_TYPES,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _patch_dirs(tmp_path):
    """Patch DRAFTS_DIR and SENT_DIR to tmp_path for isolation."""
    return [
        patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")),
        patch("donna.email_server.sender.config.SENT_DIR", str(tmp_path / "sent")),
    ]


# ── approval-required emails ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_email_requires_approval_queues_draft(tmp_path):
    with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")), \
         patch("donna.email_server.sender.config.SENT_DIR", str(tmp_path / "sent")), \
         patch("donna.email_server.sender._notify_dashboard", new_callable=AsyncMock) as mock_notify:

        result = await send_email(
            to="adjuster@allstate.com",
            subject="[DONNA] case-2026-001 - follow-up",
            body="Dear Ms. Johnson, following up on the settlement offer...",
            case_id="case-2026-001",
            email_type="adjuster_follow_up",
        )

    assert result["status"] == "queued"
    assert result["requires_approval"] is True
    draft_id = result["draft_id"]

    # draft file must exist on disk
    draft_path = tmp_path / "drafts" / "case-2026-001" / f"{draft_id}.json"
    assert draft_path.exists()
    draft = json.loads(draft_path.read_text())
    assert draft["to"] == "adjuster@allstate.com"
    assert draft["status"] == "pending_approval"
    assert draft["email_type"] == "adjuster_follow_up"

    # dashboard notified
    mock_notify.assert_called_once()
    event = mock_notify.call_args[0][0]
    assert event["type"] == "email_draft_pending"
    assert event["draft_id"] == draft_id


@pytest.mark.asyncio
async def test_all_non_admin_types_require_approval(tmp_path):
    non_auto_types = [
        "adjuster_follow_up", "records_request", "client_update",
        "deposition_notice", "lien_notice",
    ]
    for email_type in non_auto_types:
        with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")), \
             patch("donna.email_server.sender.config.SENT_DIR", str(tmp_path / "sent")), \
             patch("donna.email_server.sender._notify_dashboard", new_callable=AsyncMock):
            result = await send_email(
                to="test@example.com",
                subject=f"[DONNA] case-001 - test {email_type}",
                body="test",
                case_id="case-001",
                email_type=email_type,
            )
        assert result["status"] == "queued", f"{email_type} should be queued, got {result['status']}"


# ── auto-send emails ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_appointment_confirmation_auto_sends(tmp_path):
    with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")), \
         patch("donna.email_server.sender.config.SENT_DIR", str(tmp_path / "sent")), \
         patch("donna.email_server.sender._notify_dashboard", new_callable=AsyncMock), \
         patch("donna.email_server.sender._smtp_send") as mock_smtp:

        result = await send_email(
            to="client@example.com",
            subject="[DONNA] case-2026-001 - appointment confirmation",
            body="Confirming your consultation on Monday at 10am.",
            case_id="case-2026-001",
            email_type="appointment_confirmation",
        )

    assert result["status"] == "sent"
    mock_smtp.assert_called_once()


@pytest.mark.asyncio
async def test_auto_send_smtp_failure_returns_error(tmp_path):
    with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")), \
         patch("donna.email_server.sender.config.SENT_DIR", str(tmp_path / "sent")), \
         patch("donna.email_server.sender._notify_dashboard", new_callable=AsyncMock), \
         patch("donna.email_server.sender._smtp_send", side_effect=Exception("SMTP unavailable")):

        result = await send_email(
            to="client@example.com",
            subject="[DONNA] case-001 - confirmation",
            body="test",
            case_id="case-001",
            email_type="appointment_confirmation",
        )

    assert result["status"] == "error"
    assert "SMTP unavailable" in result["error"]


# ── approve flow ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approve_and_send_sends_draft(tmp_path):
    # First queue a draft
    with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")), \
         patch("donna.email_server.sender.config.SENT_DIR", str(tmp_path / "sent")), \
         patch("donna.email_server.sender._notify_dashboard", new_callable=AsyncMock):
        result = await send_email(
            to="adjuster@allstate.com",
            subject="[DONNA] case-001 - follow-up",
            body="Following up.",
            case_id="case-001",
            email_type="adjuster_follow_up",
        )
    draft_id = result["draft_id"]

    # Now approve it
    with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")), \
         patch("donna.email_server.sender.config.SENT_DIR", str(tmp_path / "sent")), \
         patch("donna.email_server.sender._notify_dashboard", new_callable=AsyncMock) as mock_notify, \
         patch("donna.email_server.sender._smtp_send") as mock_smtp:
        result = await approve_and_send(draft_id, "case-001")

    assert result["status"] == "sent"
    mock_smtp.assert_called_once()

    # draft file should be gone, sent file should exist
    assert not (tmp_path / "drafts" / "case-001" / f"{draft_id}.json").exists()
    assert (tmp_path / "sent" / "case-001" / f"{draft_id}.json").exists()

    # dashboard notified with email_sent
    sent_event = mock_notify.call_args[0][0]
    assert sent_event["type"] == "email_sent"


@pytest.mark.asyncio
async def test_approve_nonexistent_draft_returns_error(tmp_path):
    with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")), \
         patch("donna.email_server.sender.config.SENT_DIR", str(tmp_path / "sent")):
        result = await approve_and_send("nonexistent-id", "case-001")
    assert result["status"] == "error"


# ── reject flow ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reject_draft_marks_as_rejected(tmp_path):
    with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")), \
         patch("donna.email_server.sender.config.SENT_DIR", str(tmp_path / "sent")), \
         patch("donna.email_server.sender._notify_dashboard", new_callable=AsyncMock):
        result = await send_email(
            to="adjuster@allstate.com",
            subject="[DONNA] case-001 - follow-up",
            body="Following up.",
            case_id="case-001",
            email_type="adjuster_follow_up",
        )
    draft_id = result["draft_id"]

    with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")), \
         patch("donna.email_server.sender.config.SENT_DIR", str(tmp_path / "sent")), \
         patch("donna.email_server.sender._notify_dashboard", new_callable=AsyncMock) as mock_notify:
        result = await reject_draft(draft_id, "case-001", reason="Wrong amount cited")

    assert result["status"] == "rejected"

    # draft file updated (not moved) with rejected status
    draft = json.loads(
        (tmp_path / "drafts" / "case-001" / f"{draft_id}.json").read_text()
    )
    assert draft["status"] == "rejected"
    assert draft["reject_reason"] == "Wrong amount cited"

    reject_event = mock_notify.call_args[0][0]
    assert reject_event["type"] == "email_rejected"


# ── list_drafts ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_drafts_returns_pending_only(tmp_path):
    with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")), \
         patch("donna.email_server.sender.config.SENT_DIR", str(tmp_path / "sent")), \
         patch("donna.email_server.sender._notify_dashboard", new_callable=AsyncMock):
        await send_email(to="a@b.com", subject="[DONNA] case-001 - s1", body="b", case_id="case-001", email_type="adjuster_follow_up")
        await send_email(to="a@b.com", subject="[DONNA] case-001 - s2", body="b", case_id="case-001", email_type="records_request")

    with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")):
        drafts = list_drafts("case-001")

    assert len(drafts) == 2
    assert all(d["status"] == "pending_approval" for d in drafts)


# ── thread continuity (reply_to_message_id) ───────────────────────────────────

@pytest.mark.asyncio
async def test_reply_to_message_id_stored_in_draft(tmp_path):
    with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")), \
         patch("donna.email_server.sender.config.SENT_DIR", str(tmp_path / "sent")), \
         patch("donna.email_server.sender._notify_dashboard", new_callable=AsyncMock):
        result = await send_email(
            to="adjuster@allstate.com",
            subject="[DONNA] case-001 - re: offer",
            body="Thank you for your offer...",
            case_id="case-001",
            email_type="adjuster_follow_up",
            reply_to_message_id="original-offer@allstate.com",
        )
    draft_id = result["draft_id"]

    with patch("donna.email_server.sender.config.DRAFTS_DIR", str(tmp_path / "drafts")):
        draft = load_draft(draft_id, "case-001")

    assert draft["reply_to_message_id"] == "original-offer@allstate.com"
