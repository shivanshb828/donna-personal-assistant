"""
Donna email inbound channel.

Two modes:
  smtp (default) — local aiosmtpd listener, receives forwarded email
  imap           — polls an external Gmail/Outlook mailbox for unread messages

Usage:
    python -m donna.email_server.server           # SMTP mode (uses config.yaml)
    python -m donna.email_server.server --mode imap
    DONNA_EMAIL_USER=x DONNA_EMAIL_PASS=y python -m donna.email_server.server --mode imap
"""

import asyncio
import logging
import sys
from email.errors import MessageError

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope as SmtpEnvelope, Session as SmtpSession, SMTP

from . import config
from .parser import parse_email
from .router import route_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


class DonnaHandler:
    async def handle_DATA(self, server: SMTP, session: SmtpSession, envelope: SmtpEnvelope) -> str:
        raw = envelope.content if isinstance(envelope.content, bytes) else envelope.content.encode()
        try:
            parsed = parse_email(raw)
        except Exception as exc:
            log.error("Failed to parse email from %s: %s", envelope.mail_from, exc)
            return "500 Parse error"

        log.info(
            "Email received | from=%s subject=%r attachments=%d",
            parsed["sender"],
            parsed["subject"],
            len(parsed["attachments"]),
        )

        asyncio.ensure_future(route_email(parsed))
        return "250 Message accepted for delivery"


def _run_smtp():
    handler = DonnaHandler()
    controller = Controller(
        handler,
        hostname=config.SMTP_HOST,
        port=config.SMTP_PORT,
    )
    controller.start()
    log.info(
        "Donna SMTP listener on %s:%s → session router %s",
        config.SMTP_HOST,
        config.SMTP_PORT,
        config.SESSION_ROUTER_URL,
    )
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        log.info("Shutting down.")
    finally:
        controller.stop()


def _run_imap():
    from .imap_poller import run_poller
    log.info("Starting IMAP polling mode → session router %s", config.SESSION_ROUTER_URL)
    try:
        asyncio.run(run_poller())
    except KeyboardInterrupt:
        log.info("Shutting down.")


def run(mode: str | None = None):
    effective_mode = mode or config.MODE
    if effective_mode == "imap":
        _run_imap()
    else:
        _run_smtp()


if __name__ == "__main__":
    _mode = None
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        if idx + 1 < len(sys.argv):
            _mode = sys.argv[idx + 1]
    run(_mode)
