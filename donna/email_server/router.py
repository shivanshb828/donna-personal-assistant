import asyncio
import logging
import os
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


async def _route_email_text(parsed: dict, session_id: str) -> None:
    """Send the email body as a user_input envelope to M1's session router, then email lawyer."""
    envelope = {
        "source": "email",
        "session_id": session_id,
        "text": _build_text(parsed),
        "type": "user_input",
    }
    label = f"user_input:{session_id}"
    log.info(
        "Routing email text to session router | session_id=%s sender=%s subject=%r",
        session_id,
        parsed["sender"],
        parsed["subject"],
    )
    result = await _post_with_retry_json(config.SESSION_ROUTER_URL, envelope, label)

    if not _LAWYER_EMAIL:
        log.info("DONNA_LAWYER_EMAIL not set — skipping lawyer notification")
        return

    donna_reply = ""
    if result:
        donna_reply = result.get("reply") or result.get("text") or ""

    client_email = parsed.get("sender", "unknown")
    subject = parsed.get("subject", "")
    body = parsed.get("body", "")

    intake_body = (
        f"New intake received via email.\n\n"
        f"From: {client_email}\n"
        f"Subject: {subject}\n\n"
        f"--- Client Message ---\n{body}\n\n"
        f"--- Donna's Assessment ---\n{donna_reply or '(no reply captured)'}\n"
    )

    from .sender import send_email as _send
    try:
        outcome = await _send(
            to=_LAWYER_EMAIL,
            subject=f"[Intake] {subject}",
            body=intake_body,
            case_id=session_id,
            email_type="appointment_confirmation",  # auto-send, no approval gate
            requires_approval=False,
            session_id=session_id,
        )
        log.info("Lawyer intake email dispatched | to=%s outcome=%s", _LAWYER_EMAIL, outcome)
    except Exception as exc:
        log.error("Failed to send lawyer intake email: %s", exc)


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
