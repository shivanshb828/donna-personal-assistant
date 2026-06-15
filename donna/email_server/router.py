import asyncio
import logging
import os
import random
import re
import uuid

import httpx

from . import config

log = logging.getLogger(__name__)

_RETRY_ATTEMPTS = 3
_RETRY_BACKOFF = 2.0
_IPC_SECRET = os.getenv("DONNA_IPC_SECRET", "")
_LAWYER_EMAIL = os.getenv("DONNA_LAWYER_EMAIL", "")


def _derive_session_id(parsed: dict) -> str:
    # Use case_id as session anchor when available (best thread continuity for a case)
    if parsed.get("case_id"):
        return parsed["case_id"]
    thread_key = parsed.get("in_reply_to") or parsed.get("message_id")
    if thread_key:
        return thread_key
    return str(uuid.uuid4())


def _build_text(parsed: dict) -> str:
    lines = [
        f"From: {parsed['sender']}",
        f"Subject: {parsed['subject']}",
        "",
        parsed["body"],
    ]
    return "\n".join(lines)


def _headers() -> dict:
    if _IPC_SECRET:
        return {"X-Donna-Secret": _IPC_SECRET}
    return {}


async def _post_with_retry(url: str, payload: dict, label: str) -> None:
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=_headers())
                resp.raise_for_status()
                log.info("%s routed | status=%s", label, resp.status_code)
                return
        except Exception as exc:
            log.warning("%s attempt %d/%d failed: %s", label, attempt, _RETRY_ATTEMPTS, exc)
            if attempt < _RETRY_ATTEMPTS:
                await asyncio.sleep(_RETRY_BACKOFF)
    log.error("%s — all %d attempts failed, dropping", label, _RETRY_ATTEMPTS)


async def _post_with_retry_json(url: str, payload: dict, label: str) -> dict | None:
    """Like _post_with_retry but returns the JSON response body."""
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=_headers())
                resp.raise_for_status()
                log.info("%s routed | status=%s", label, resp.status_code)
                return resp.json()
        except Exception as exc:
            log.warning("%s attempt %d/%d failed: %s", label, attempt, _RETRY_ATTEMPTS, exc)
            if attempt < _RETRY_ATTEMPTS:
                await asyncio.sleep(_RETRY_BACKOFF)
    log.error("%s — all %d attempts failed, dropping", label, _RETRY_ATTEMPTS)
    return None


async def _route_document_ingest(parsed: dict, attachment: dict, session_id: str) -> None:
    """Send a document_ingest envelope to the VLM pipeline for one attachment."""
    envelope = {
        "source": "email",
        "session_id": session_id,
        "text": attachment["path"],
        "type": "document_ingest",
        "metadata": {
            "case_id": parsed.get("case_id") or "unmatched",
            "sender_email": parsed["sender"],
            "email_subject": parsed["subject"],
            "filename": attachment["filename"],
            "doc_type_hint": attachment["doc_type_hint"],
        },
    }
    label = f"document_ingest:{attachment['filename']}:{session_id}"
    log.info(
        "Routing document to pipeline | case_id=%s file=%s type=%s",
        envelope["metadata"]["case_id"],
        attachment["filename"],
        attachment["doc_type_hint"],
    )
    await _post_with_retry(config.PIPELINE_INGEST_URL, envelope, label)


_MISSING_DOCS_VARIANTS = [
    """\
Send over whatever you have when you get a chance:

  • Police or incident report
  • ER or hospital discharge summary
  • Photos — scene, injuries, vehicle damage
  • Your insurance info and the other party's

Don't need everything right now. Send what you have and we'll work with it.""",
    """\
If you have any of these, send them when you can:

  • Incident or police report
  • Medical records or ER paperwork
  • Photos of the scene or your injuries
  • Insurance cards (yours and theirs)

Whatever you've got is a start.""",
    """\
A few things that'll help the attorney review your case:

  • Any police or incident report
  • Medical records / discharge papers
  • Scene or injury photos
  • Insurance info from both sides

No rush — pull together what you have.""",
]

# Regex to catch tool-name artifacts leaking into client-facing replies
_TOOL_NAME_RE = re.compile(
    r"\b(intake\.(start|update)|case\.(qualify|create|decline)|calendar\.create_event"
    r"|notify\.dashboard|record_consent|schedule_followup)\b",
    re.IGNORECASE,
)


def _clean_reply(text: str) -> str:
    """Strip tool-call artifacts that the LLM occasionally leaks into reply text."""
    text = _TOOL_NAME_RE.sub("", text)
    # Collapse multiple blank lines left by removal
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def _route_email_text(parsed: dict, session_id: str) -> None:
    """
    Route email body → IPC → Donna reply.

    Outbound emails:
      1. CLIENT  — Donna's direct reply. If no docs attached, appends a document request.
      2. LAWYER  — Intake summary with assessment, tools called, and original message.
    """
    envelope = {
        "source": "email",
        "session_id": session_id,
        "text": _build_text(parsed),
        "type": "user_input",
    }
    label = f"user_input:{session_id}"
    log.info(
        "Routing email text to session router | session_id=%s sender=%s subject=%r",
        session_id, parsed["sender"], parsed["subject"],
    )
    result = await _post_with_retry_json(config.SESSION_ROUTER_URL, envelope, label)

    donna_reply = ""
    phase = "UNKNOWN"
    tool_results: list = []
    if result:
        raw_reply = result.get("reply") or result.get("text") or ""
        donna_reply = _clean_reply(raw_reply)
        phase = result.get("phase", "UNKNOWN")
        tool_results = result.get("tool_results") or []

    client_email = parsed.get("sender", "unknown")
    subject = parsed.get("subject", "")
    body = parsed.get("body", "")
    attachments = parsed.get("attachments", [])
    case_id = session_id

    from datetime import datetime, timezone
    from .sender import send_email as _send

    now = datetime.now(timezone.utc).strftime("%B %d, %Y at %I:%M %p UTC")

    # ── 1. Reply to CLIENT ────────────────────────────────────────────────────
    missing_docs = not attachments
    doc_request_block = f"\n\n{random.choice(_MISSING_DOCS_VARIANTS)}" if missing_docs else ""

    fallback_reply = random.choice([
        "Got your message. We'll be in touch shortly.",
        "Received. Someone will follow up with you soon.",
        "Thanks — we have your message and will be in touch.",
    ])

    client_body = f"""\
{donna_reply if donna_reply else fallback_reply}
{doc_request_block}

— Donna
"""
    try:
        outcome = await _send(
            to=client_email,
            subject=f"Re: {subject}",
            body=client_body,
            case_id=case_id,
            email_type="appointment_confirmation",
            requires_approval=False,
            session_id=session_id,
        )
        log.info("Client reply sent | to=%s missing_docs=%s outcome=%s", client_email, missing_docs, outcome)
    except Exception as exc:
        log.error("Failed to send client reply: %s", exc)

    # ── 2. Notify LAWYER ──────────────────────────────────────────────────────
    if not _LAWYER_EMAIL:
        return

    phase_labels = {
        "DISCLOSURE":    "Initial contact",
        "INTAKE":        "Intake in progress",
        "QUALIFICATION": "Qualifying",
        "BOOKING":       "Booking consultation",
        "CLOSE":         "Complete",
    }
    phase_label = phase_labels.get(phase, phase)

    attachment_lines = ""
    if attachments:
        names = [a.get("filename", "unknown") for a in attachments]
        attachment_lines = f"\nDocuments received ({len(names)}):\n" + "\n".join(f"  • {n}" for n in names) + "\n"
    else:
        attachment_lines = "\nDocuments: none — Donna requested them from client.\n"

    tool_lines = ""
    if tool_results:
        rows = []
        for tr in tool_results:
            name = tr.get("tool") or tr.get("name") or "unknown"
            status = tr.get("status") or tr.get("result", {}).get("status") or "ok"
            data = tr.get("result") or tr.get("output") or {}
            notes = ""
            if isinstance(data, dict):
                for key in ("case_id", "event_id", "appointment_time", "fee_estimate", "reason", "message"):
                    if data.get(key):
                        notes += f" | {key}={data[key]}"
            rows.append(f"  • {name}  [{status}]{notes}")
        tool_lines = "\nTools called:\n" + "\n".join(rows) + "\n"

    lawyer_body = f"""\
Hi Dhruva,

New client email processed by Donna.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DONNA'S ASSESSMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{donna_reply.strip() if donna_reply else "(no reply captured)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CASE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Case ID:   {case_id}
Received:  {now}
From:      {client_email}
Status:    {phase_label}
{attachment_lines}{tool_lines}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLIENT'S MESSAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{body.strip()}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Donna has already replied to {client_email}.
"""
    try:
        outcome = await _send(
            to=_LAWYER_EMAIL,
            subject=f"[Intake] {case_id} — {client_email}",
            body=lawyer_body,
            case_id=case_id,
            email_type="appointment_confirmation",
            requires_approval=False,
            session_id=session_id,
        )
        log.info("Lawyer summary sent | to=%s outcome=%s", _LAWYER_EMAIL, outcome)
    except Exception as exc:
        log.error("Failed to send lawyer summary: %s", exc)


async def route_email(parsed: dict) -> None:
    """
    Main routing entry point.

    - Attachments → VLM pipeline (document_ingest, one per file)
    - Email body text → M1 session router (user_input), only if body is non-empty
    """
    session_id = _derive_session_id(parsed)
    tasks = []

    for attachment in parsed.get("attachments", []):
        tasks.append(_route_document_ingest(parsed, attachment, session_id))

    if parsed.get("body", "").strip():
        tasks.append(_route_email_text(parsed, session_id))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
