import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from donna.email_server.imap_poller import poll_once


def _make_imap_mock(raw_emails: list[bytes], uids: list[bytes]):
    conn = MagicMock()
    conn.select.return_value = ("OK", [b"1"])
    conn.search.return_value = ("OK", [b" ".join(uids)])

    fetch_responses = []
    for uid, raw in zip(uids, raw_emails):
        fetch_responses.append(("OK", [(b"RFC822", raw)]))
    conn.fetch.side_effect = fetch_responses

    conn.store.return_value = ("OK", [])
    conn.logout.return_value = ("BYE", [])
    return conn


def _make_raw_email(body: str = "Test body",
                    subject: str = "[DONNA] case-2026-001 - claim update") -> bytes:
    from email.mime.text import MIMEText
    msg = MIMEText(body, "plain")
    msg["From"] = "adjuster@carrier.com"
    msg["Subject"] = subject
    msg["Message-ID"] = "<imap001@carrier.com>"
    return msg.as_bytes()


@pytest.mark.asyncio
async def test_poll_once_no_unread():
    conn = MagicMock()
    conn.select.return_value = ("OK", [b"0"])
    conn.search.return_value = ("OK", [b""])
    conn.logout.return_value = ("BYE", [])

    with patch("donna.email_server.imap_poller._connect", return_value=conn), \
         patch("donna.email_server.imap_poller._fetch_unread", return_value=[]):
        count = await poll_once()

    assert count == 0


@pytest.mark.asyncio
async def test_poll_once_routes_unread_emails():
    raw = _make_raw_email("Settlement confirmed.")
    routed = []

    async def fake_route(parsed, **kwargs):
        routed.append(parsed)

    conn = MagicMock()
    conn.logout.return_value = ("BYE", [])

    with patch("donna.email_server.imap_poller._connect", return_value=conn), \
         patch("donna.email_server.imap_poller._fetch_unread", return_value=[(b"1", raw)]), \
         patch("donna.email_server.imap_poller.route_email", side_effect=fake_route):
        count = await poll_once()

    assert count == 1
    assert len(routed) == 1
    assert routed[0]["sender"] == "adjuster@carrier.com"
    assert "Settlement confirmed" in routed[0]["body"]


@pytest.mark.asyncio
async def test_poll_once_routes_continue_on_route_error():
    """If routing one email fails, the others still get routed."""
    good_raw = _make_raw_email("Good email")
    routed = []
    call_count = 0

    async def fake_route(parsed, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("route failed")
        routed.append(parsed)

    conn = MagicMock()
    conn.logout.return_value = ("BYE", [])

    good_raw2 = _make_raw_email("Second good email", subject="Second")
    items = [(b"1", good_raw), (b"2", good_raw2)]

    with patch("donna.email_server.imap_poller._connect", return_value=conn), \
         patch("donna.email_server.imap_poller._fetch_unread", return_value=items), \
         patch("donna.email_server.imap_poller.route_email", side_effect=fake_route):
        count = await poll_once()

    assert count == 2        # both attempted
    assert len(routed) == 1  # second one succeeded despite first failing


@pytest.mark.asyncio
async def test_poll_once_marks_emails_read():
    raw = _make_raw_email()
    conn = _make_imap_mock([raw], [b"42"])

    with patch("donna.email_server.imap_poller._connect", return_value=conn), \
         patch("donna.email_server.imap_poller.route_email", new_callable=AsyncMock):
        await poll_once()

    conn.store.assert_called_with(b"42", "+FLAGS", "\\Seen")
