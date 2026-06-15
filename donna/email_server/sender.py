"""
Donna outbound email sender.

Two paths:
  requires_approval=True  → save draft to /gbio/donna/drafts/, notify M1 dashboard
  requires_approval=False → send immediately via SMTP (admin emails only)

Called by M2's tools/email_sender.py when Donna calls the send_email tool.
Also called by approval_server.py when the lawyer approves a draft.

Email types:
  adjuster_follow_up      — requires approval
  records_request         — requires approval
  client_update           — requires approval
  deposition_notice       — requires approval
  lien_notice             — requires approval
  appointment_confirmation — auto-send (no approval)
  demand_acknowledgment   — auto-send (no approval)
"""

import asyncio
import json
import logging
import smtplib
import ssl
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Literal

import httpx

from . import config

log = logging.getLogger(__name__)

EmailType = Literal[
    "adjuster_follow_up",
    "records_request",
    "client_update",
    "deposition_notice",
    "lien_notice",
    "appointment_confirmation",
    "demand_acknowledgment",
]

# These types are sent immediately — no lawyer approval needed
_AUTO_SEND_TYPES = {"appointment_confirmation", "demand_acknowledgment", "email_reply"}


# ── Draft queue ───────────────────────────────────────────────────────────────

def _drafts_dir(case_id: str) -> Path:
    p = Path(config.DRAFTS_DIR) / case_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _sent_dir(case_id: str) -> Path:
    p = Path(config.SENT_DIR) / case_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write_draft(draft: dict) -> Path:
    path = _drafts_dir(draft["case_id"]) / f"{draft['draft_id']}.json"
    path.write_text(json.dumps(draft, indent=2))
    return path


def load_draft(draft_id: str, case_id: str) -> dict:
    path = Path(config.DRAFTS_DIR) / case_id / f"{draft_id}.json"
    return json.loads(path.read_text())


def mark_sent(draft: dict) -> None:
    draft_path = Path(config.DRAFTS_DIR) / draft["case_id"] / f"{draft['draft_id']}.json"
    draft["status"] = "sent"
    draft["sent_at"] = datetime.now(timezone.utc).isoformat()
    sent_path = _sent_dir(draft["case_id"]) / f"{draft['draft_id']}.json"
    sent_path.write_text(json.dumps(draft, indent=2))
    if draft_path.exists():
        draft_path.unlink()
    log.info("Email marked sent | draft_id=%s to=%s", draft["draft_id"], draft["to"])


def mark_rejected(draft_id: str, case_id: str, reason: str = "") -> None:
    draft = load_draft(draft_id, case_id)
    draft["status"] = "rejected"
    draft["rejected_at"] = datetime.now(timezone.utc).isoformat()
    draft["reject_reason"] = reason
    path = Path(config.DRAFTS_DIR) / case_id / f"{draft_id}.json"
    path.write_text(json.dumps(draft, indent=2))
    log.info("Email draft rejected | draft_id=%s reason=%s", draft_id, reason)


def list_drafts(case_id: str) -> list[dict]:
    drafts_path = Path(config.DRAFTS_DIR) / case_id
    if not drafts_path.exists():
        return []
    result = []
    for f in sorted(drafts_path.glob("*.json")):
        try:
            d = json.loads(f.read_text())
            if d.get("status") == "pending_approval":
                result.append(d)
        except Exception:
            pass
    return result


# ── SMTP send ─────────────────────────────────────────────────────────────────

def _build_mime(draft: dict) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    from_field = f"{config.OUTBOUND_FROM_NAME} <{config.OUTBOUND_FROM_ADDRESS}>"
    msg["From"] = from_field
    msg["To"] = draft["to"]
    msg["Subject"] = draft["subject"]
    msg["Message-ID"] = f"<donna-{draft['draft_id']}@lawfirm.donna>"
    if draft.get("reply_to_message_id"):
        msg["In-Reply-To"] = f"<{draft['reply_to_message_id']}>"
        msg["References"] = f"<{draft['reply_to_message_id']}>"
    msg.attach(MIMEText(draft["body"], "plain"))
    return msg


def _smtp_send(msg: MIMEMultipart) -> None:
    host = config.OUTBOUND_SMTP_HOST
    port = config.OUTBOUND_SMTP_PORT
    user = config.OUTBOUND_SMTP_USER
    password = config.OUTBOUND_SMTP_PASS

    if config.OUTBOUND_SMTP_TLS:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as smtp:
            smtp.send_message(msg)


# ── Dashboard notification ────────────────────────────────────────────────────

async def _notify_dashboard(event: dict) -> None:
    """Fire-and-forget IPC notification to M1's session router."""
    envelope = {
        "source": "email",
        "session_id": event.get("case_id", "system"),
        "text": json.dumps(event),
        "type": event["type"],
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(config.SESSION_ROUTER_URL, json=envelope)
    except Exception as exc:
        log.warning("Dashboard notification failed: %s", exc)


# ── Public API ────────────────────────────────────────────────────────────────

async def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    case_id: str,
    email_type: EmailType,
    reply_to_message_id: str | None = None,
    requires_approval: bool | None = None,
    session_id: str | None = None,
    donna_reasoning: str = "",
) -> dict:
    """
    Main entry point called by M2's tools/email_sender.py.

    Returns:
        { status: "queued"|"sent", draft_id: str, ... }
    """
    draft_id = str(uuid.uuid4())
    auto = email_type in _AUTO_SEND_TYPES
    needs_approval = (not auto) if requires_approval is None else requires_approval

    draft = {
        "draft_id": draft_id,
        "case_id": case_id,
        "status": "pending_approval" if needs_approval else "sending",
        "email_type": email_type,
        "to": to,
        "subject": subject,
        "body": body,
        "reply_to_message_id": reply_to_message_id,
        "session_id": session_id or case_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "donna_reasoning": donna_reasoning,
    }

    if needs_approval:
        _write_draft(draft)
        log.info(
            "Email draft queued for approval | draft_id=%s type=%s to=%s case=%s",
            draft_id, email_type, to, case_id,
        )
        await _notify_dashboard({
            "type": "email_draft_pending",
            "draft_id": draft_id,
            "case_id": case_id,
            "to": to,
            "subject": subject,
            "email_type": email_type,
            "preview": body[:200],
        })
        return {"status": "queued", "draft_id": draft_id, "requires_approval": True}

    # Auto-send path
    try:
        msg = _build_mime(draft)
        await asyncio.get_event_loop().run_in_executor(None, _smtp_send, msg)
        mark_sent(draft)
        log.info("Email sent immediately | draft_id=%s type=%s to=%s", draft_id, email_type, to)
        await _notify_dashboard({
            "type": "email_sent",
            "draft_id": draft_id,
            "case_id": case_id,
            "to": to,
            "subject": subject,
            "email_type": email_type,
            "sent_at": draft["sent_at"],
        })
        return {"status": "sent", "draft_id": draft_id}
    except Exception as exc:
        log.error("Failed to send email | draft_id=%s error=%s", draft_id, exc)
        return {"status": "error", "draft_id": draft_id, "error": str(exc)}


async def approve_and_send(draft_id: str, case_id: str) -> dict:
    """
    Called by M1's approval server when the lawyer clicks Approve.
    Loads the draft, sends it, marks as sent.
    """
    try:
        draft = load_draft(draft_id, case_id)
    except FileNotFoundError:
        log.error("Draft not found | draft_id=%s case_id=%s", draft_id, case_id)
        return {"status": "error", "error": "draft not found"}

    if draft.get("status") != "pending_approval":
        return {"status": "error", "error": f"draft status is {draft.get('status')}, not pending_approval"}

    try:
        msg = _build_mime(draft)
        await asyncio.get_event_loop().run_in_executor(None, _smtp_send, msg)
        mark_sent(draft)
        log.info("Draft approved and sent | draft_id=%s to=%s", draft_id, draft["to"])
        await _notify_dashboard({
            "type": "email_sent",
            "draft_id": draft_id,
            "case_id": case_id,
            "to": draft["to"],
            "subject": draft["subject"],
            "email_type": draft["email_type"],
            "sent_at": draft.get("sent_at"),
        })
        return {"status": "sent", "draft_id": draft_id}
    except Exception as exc:
        log.error("Failed to send approved draft | draft_id=%s error=%s", draft_id, exc)
        return {"status": "error", "draft_id": draft_id, "error": str(exc)}


async def reject_draft(draft_id: str, case_id: str, reason: str = "") -> dict:
    """Called by M1 when the lawyer clicks Reject."""
    try:
        mark_rejected(draft_id, case_id, reason)
        await _notify_dashboard({
            "type": "email_rejected",
            "draft_id": draft_id,
            "case_id": case_id,
            "reason": reason,
        })
        return {"status": "rejected", "draft_id": draft_id}
    except FileNotFoundError:
        return {"status": "error", "error": "draft not found"}
