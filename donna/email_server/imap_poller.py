"""
IMAP polling mode for Donna's email inbound channel.

Polls an external mailbox (Gmail, Outlook) for unread messages,
parses each one, and routes it to Donna's session router.

Activated when config.MODE == "imap".
Run via:  python -m donna.email_server.server --mode imap
"""

import asyncio
import imaplib
import logging
import os

from . import config
from .parser import parse_email
from .router import route_email

log = logging.getLogger(__name__)

# Emails from these addresses are always processed regardless of subject line.
# Set DONNA_KNOWN_SENDERS as comma-separated list in .env to override.
_DEFAULT_KNOWN_SENDERS = [
    "shivansh.bansal828@gmail.com",
    "aayushgandhi134@gmail.com",
]

def _known_senders() -> list[str]:
    env = os.getenv("DONNA_KNOWN_SENDERS", "")
    if env:
        return [s.strip().lower() for s in env.split(",") if s.strip()]
    return _DEFAULT_KNOWN_SENDERS


def _search_uids(conn, *criteria) -> set[bytes]:
    _, data = conn.search(None, *criteria)
    return set(data[0].split()) if data[0] else set()


def _fetch_unread(conn: imaplib.IMAP4_SSL | imaplib.IMAP4) -> list[tuple]:
    conn.select(config.IMAP_MAILBOX)

    # Gate 1: [DONNA] subject tag (existing behaviour)
    uid_set = _search_uids(conn, "UNSEEN", "SUBJECT", "[DONNA]")

    # Gate 2: known senders — process regardless of subject
    for sender in _known_senders():
        uid_set |= _search_uids(conn, "UNSEEN", "FROM", sender)

    if not uid_set:
        return []

    log.info("IMAP: %d unread email(s) matched filters", len(uid_set))
    raw_emails = []
    for uid in uid_set:
        _, msg_data = conn.fetch(uid, "(RFC822)")
        for part in msg_data:
            if isinstance(part, tuple):
                raw_emails.append((uid, part[1]))
        if config.IMAP_MARK_READ:
            conn.store(uid, "+FLAGS", "\\Seen")

    return raw_emails


def _connect() -> imaplib.IMAP4_SSL | imaplib.IMAP4:
    if config.IMAP_SSL:
        conn = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
    else:
        conn = imaplib.IMAP4(config.IMAP_HOST, config.IMAP_PORT)
    conn.login(config.IMAP_USER, config.IMAP_PASS)
    log.info("IMAP connected to %s as %s", config.IMAP_HOST, config.IMAP_USER)
    return conn


_seen_uids: set[bytes] = set()  # dedup across poll cycles within one process lifetime


async def poll_once() -> int:
    """Fetch and route all unread emails. Returns count processed."""
    loop = asyncio.get_event_loop()

    conn = await loop.run_in_executor(None, _connect)
    try:
        items = await loop.run_in_executor(None, _fetch_unread, conn)
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    if not items:
        return 0

    tasks = []
    for uid, raw in items:
        if uid in _seen_uids:
            log.debug("Skipping already-processed uid=%s", uid)
            continue
        _seen_uids.add(uid)
        try:
            parsed = parse_email(raw)
            log.info(
                "IMAP email fetched | uid=%s from=%s subject=%r",
                uid.decode(),
                parsed["sender"],
                parsed["subject"],
            )
            tasks.append(route_email(parsed))
        except Exception as exc:
            log.error("Failed to parse email uid=%s: %s", uid, exc)

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    return len(tasks)


async def run_poller():
    """Poll indefinitely at the configured interval."""
    log.info(
        "IMAP poller started | host=%s user=%s interval=%ss",
        config.IMAP_HOST,
        config.IMAP_USER,
        config.IMAP_POLL_INTERVAL,
    )
    while True:
        try:
            count = await poll_once()
            if count:
                log.info("IMAP poll: processed %d email(s)", count)
        except Exception as exc:
            log.error("IMAP poll error: %s", exc)
        await asyncio.sleep(config.IMAP_POLL_INTERVAL)
