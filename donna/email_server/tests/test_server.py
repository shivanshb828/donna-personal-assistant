import asyncio
import platform
import socket
from unittest.mock import AsyncMock, patch

import pytest
import aiosmtplib

from donna.email_server.server import DonnaHandler

# Live SMTP bind is unreliable on macOS (port ready_timeout); runs fine on GB10 Linux.
skip_on_mac = pytest.mark.skipif(platform.system() == "Darwin", reason="SMTP bind unreliable on macOS — passes on GB10")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_raw_email(body: str = "Test body") -> bytes:
    from email.mime.text import MIMEText
    msg = MIMEText(body, "plain")
    msg["From"] = "sender@test.com"
    msg["To"] = "donna@lawfirm.local"
    msg["Subject"] = "Test Email"
    msg["Message-ID"] = "<test001@test.com>"
    return msg.as_bytes()


class _FakeSession:
    peer = ("127.0.0.1", 12345)


class _FakeSmtpEnvelope:
    def __init__(self, content: bytes):
        self.mail_from = "sender@test.com"
        self.rcpt_tos = ["donna@lawfirm.local"]
        self.content = content


@pytest.mark.asyncio
async def test_handle_data_calls_parse_and_route(tmp_path):
    raw = _make_raw_email("Adjuster update: claim approved.")
    envelope = _FakeSmtpEnvelope(raw)
    handler = DonnaHandler()

    with patch("donna.email_server.server.parse_email") as mock_parse, \
         patch("donna.email_server.server.route_email", new_callable=AsyncMock) as mock_route, \
         patch("donna.email_server.server.asyncio.ensure_future") as mock_future:

        mock_parse.return_value = {
            "sender": "sender@test.com",
            "subject": "[DONNA] case-2026-001 - test",
            "body": "Adjuster update: claim approved.",
            "case_id": "case-2026-001",
            "attachments": [],
            "message_id": "test001@test.com",
            "in_reply_to": None,
        }

        result = await handler.handle_DATA(None, _FakeSession(), envelope)

    assert result == "250 Message accepted for delivery"
    mock_parse.assert_called_once_with(raw)
    mock_future.assert_called_once()


@pytest.mark.asyncio
async def test_handle_data_returns_500_on_parse_error():
    raw = b"garbage bytes that are not valid email content \x00\x01"
    envelope = _FakeSmtpEnvelope(raw)
    handler = DonnaHandler()

    with patch("donna.email_server.server.parse_email", side_effect=Exception("parse fail")), \
         patch("donna.email_server.server.asyncio.ensure_future") as mock_future:

        result = await handler.handle_DATA(None, _FakeSession(), envelope)

    assert result == "500 Parse error"
    mock_future.assert_not_called()


@skip_on_mac
@pytest.mark.asyncio
async def test_live_smtp_roundtrip(tmp_path):
    """
    Spin up the actual aiosmtpd controller on an ephemeral port and
    send a real SMTP message through it.
    """
    from aiosmtpd.controller import Controller

    received_parsed = []

    async def fake_route(parsed, **kwargs):
        received_parsed.append(parsed)

    handler = DonnaHandler()

    with patch("donna.email_server.server.parse_email", wraps=lambda raw: {
        "sender": "live@test.com",
        "subject": "[DONNA] case-live-001 - roundtrip",
        "body": "This is a live SMTP roundtrip test.",
        "case_id": "case-live-001",
        "attachments": [],
        "message_id": "live001@test.com",
        "in_reply_to": None,
    }), patch("donna.email_server.server.route_email", side_effect=fake_route):

        port = _free_port()
        controller = Controller(handler, hostname="127.0.0.1", port=port)
        controller.start()

        try:
            await aiosmtplib.send(
                _make_raw_email("Live roundtrip"),
                hostname="127.0.0.1",
                port=port,
                sender="live@test.com",
                recipients=["donna@lawfirm.local"],
            )
            await asyncio.sleep(0.1)  # let handle_DATA fire
        finally:
            controller.stop()

    assert len(received_parsed) == 1
    assert received_parsed[0]["sender"] == "live@test.com"
