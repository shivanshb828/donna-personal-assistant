import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from donna.email_server.router import _derive_session_id, _build_text, route_email

_BASE_PARSED = {
    "sender": "adjuster@carrier.com",
    "subject": "[DONNA] case-2026-001 - settlement offer",
    "body": "We are prepared to offer $50,000.",
    "case_id": "case-2026-001",
    "attachments": [],
    "message_id": "msg001@carrier.com",
    "in_reply_to": None,
}


# ── session_id derivation ─────────────────────────────────────────────────────

def test_session_id_uses_case_id_when_present():
    assert _derive_session_id(_BASE_PARSED) == "case-2026-001"

def test_session_id_falls_back_to_in_reply_to():
    parsed = {**_BASE_PARSED, "case_id": None, "in_reply_to": "prev001@carrier.com"}
    assert _derive_session_id(parsed) == "prev001@carrier.com"

def test_session_id_falls_back_to_message_id():
    parsed = {**_BASE_PARSED, "case_id": None, "in_reply_to": None}
    assert _derive_session_id(parsed) == "msg001@carrier.com"

def test_session_id_fallback_to_uuid():
    parsed = {**_BASE_PARSED, "case_id": None, "in_reply_to": None, "message_id": ""}
    sid = _derive_session_id(parsed)
    assert len(sid) > 0


# ── envelope text ─────────────────────────────────────────────────────────────

def test_build_text_format():
    text = _build_text(_BASE_PARSED)
    assert text.startswith("From: adjuster@carrier.com")
    assert "Subject: [DONNA] case-2026-001 - settlement offer" in text
    assert "We are prepared to offer $50,000" in text


# ── route_email: no attachments → user_input to session router ────────────────

@pytest.mark.asyncio
async def test_route_email_text_only_posts_user_input():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("donna.email_server.router.httpx.AsyncClient", return_value=mock_client), \
         patch("donna.email_server.router.config.SESSION_ROUTER_URL", "http://localhost:8000/ipc"), \
         patch("donna.email_server.router.config.PIPELINE_INGEST_URL", "http://localhost:8765/ingest"):
        await route_email(_BASE_PARSED)

    mock_client.post.assert_called_once()
    url, = mock_client.post.call_args[0]
    envelope = mock_client.post.call_args[1]["json"]
    assert url == "http://localhost:8000/ipc"
    assert envelope["type"] == "user_input"
    assert envelope["source"] == "email"
    assert envelope["session_id"] == "case-2026-001"


# ── route_email: attachment → document_ingest to pipeline ────────────────────

@pytest.mark.asyncio
async def test_route_email_with_attachment_posts_document_ingest():
    parsed = {
        **_BASE_PARSED,
        "body": "",
        "attachments": [{
            "path": "./documents/case-2026-001/police-report.pdf",
            "filename": "police-report.pdf",
            "doc_type_hint": "police_report",
        }],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 202
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("donna.email_server.router.httpx.AsyncClient", return_value=mock_client), \
         patch("donna.email_server.router.config.PIPELINE_INGEST_URL", "http://localhost:8765/ingest"), \
         patch("donna.email_server.router.config.SESSION_ROUTER_URL", "http://localhost:8000/ipc"):
        await route_email(parsed)

    mock_client.post.assert_called_once()
    url, = mock_client.post.call_args[0]
    envelope = mock_client.post.call_args[1]["json"]
    assert url == "http://localhost:8765/ingest"
    assert envelope["type"] == "document_ingest"
    assert envelope["text"] == "./documents/case-2026-001/police-report.pdf"
    assert envelope["metadata"]["case_id"] == "case-2026-001"
    assert envelope["metadata"]["doc_type_hint"] == "police_report"
    assert envelope["metadata"]["filename"] == "police-report.pdf"


# ── route_email: body + attachment → both endpoints called ───────────────────

@pytest.mark.asyncio
async def test_route_email_body_and_attachment_posts_both():
    parsed = {
        **_BASE_PARSED,
        "body": "See attached records.",
        "attachments": [{
            "path": "./documents/case-2026-001/records.pdf",
            "filename": "records.pdf",
            "doc_type_hint": "medical_record",
        }],
    }

    posted_urls = []
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()

    async def capture_post(url, **kwargs):
        posted_urls.append(url)
        return mock_resp

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=capture_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("donna.email_server.router.httpx.AsyncClient", return_value=mock_client), \
         patch("donna.email_server.router.config.PIPELINE_INGEST_URL", "http://localhost:8765/ingest"), \
         patch("donna.email_server.router.config.SESSION_ROUTER_URL", "http://localhost:8000/ipc"):
        await route_email(parsed)

    assert "http://localhost:8765/ingest" in posted_urls
    assert "http://localhost:8000/ipc" in posted_urls


# ── retry behaviour ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_route_retries_on_failure():
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("donna.email_server.router.httpx.AsyncClient", return_value=mock_client), \
         patch("donna.email_server.router.asyncio.sleep", new_callable=AsyncMock), \
         patch("donna.email_server.router.config.SESSION_ROUTER_URL", "http://localhost:8000/ipc"), \
         patch("donna.email_server.router.config.PIPELINE_INGEST_URL", "http://localhost:8765/ingest"):
        await route_email(_BASE_PARSED)  # must not raise

    assert mock_client.post.call_count == 3  # _RETRY_ATTEMPTS
