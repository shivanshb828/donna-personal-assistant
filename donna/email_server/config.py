import os
from pathlib import Path
from typing import Any

import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load() -> dict[str, Any]:
    path = Path(os.getenv("DONNA_EMAIL_CONFIG", str(_CONFIG_PATH)))
    with open(path) as f:
        return yaml.safe_load(f)


_cfg = _load()

MODE: str = _cfg.get("mode", "smtp")

# ── Inbound SMTP listener ─────────────────────────────────────────────────────
SMTP_HOST: str = _cfg["smtp"]["host"]
SMTP_PORT: int = _cfg["smtp"]["port"]

# ── Inbound IMAP poller ───────────────────────────────────────────────────────
IMAP_HOST: str = _cfg["imap"]["host"]
IMAP_PORT: int = _cfg["imap"]["port"]
IMAP_SSL: bool = _cfg["imap"]["use_ssl"]
IMAP_USER: str = os.getenv("DONNA_EMAIL_USER") or _cfg["imap"]["username"]
IMAP_PASS: str = os.getenv("DONNA_EMAIL_PASS") or _cfg["imap"]["password"]
IMAP_POLL_INTERVAL: int = _cfg["imap"]["poll_interval_seconds"]
IMAP_MAILBOX: str = _cfg["imap"]["mailbox"]
IMAP_MARK_READ: bool = _cfg["imap"]["mark_read"]

# ── IPC routing ───────────────────────────────────────────────────────────────
SESSION_ROUTER_URL: str = os.getenv("DONNA_SESSION_ROUTER_URL") or _cfg["session_router"]["url"]
PIPELINE_INGEST_URL: str = os.getenv("DONNA_PIPELINE_INGEST_URL") or _cfg["pipeline"]["ingest_url"]

# ── Storage ───────────────────────────────────────────────────────────────────
ATTACHMENT_SAVE_DIR: str = os.getenv("DONNA_ATTACHMENT_DIR") or _cfg["attachments"]["save_dir"]
DRAFTS_DIR: str = os.getenv("DONNA_DRAFTS_DIR") or _cfg["drafts"]["dir"]
SENT_DIR: str = os.getenv("DONNA_SENT_DIR") or _cfg["drafts"]["sent_dir"]

# ── Outbound SMTP ─────────────────────────────────────────────────────────────
OUTBOUND_SMTP_HOST: str = os.getenv("DONNA_SMTP_HOST") or _cfg["outbound_smtp"]["host"]
OUTBOUND_SMTP_PORT: int = int(os.getenv("DONNA_SMTP_PORT") or _cfg["outbound_smtp"]["port"])
OUTBOUND_SMTP_TLS: bool = _cfg["outbound_smtp"]["use_tls"]
OUTBOUND_FROM_ADDRESS: str = os.getenv("DONNA_EMAIL_USER") or _cfg["outbound_smtp"]["from_address"]
OUTBOUND_FROM_NAME: str = _cfg["outbound_smtp"]["from_name"]
OUTBOUND_SMTP_USER: str = os.getenv("DONNA_EMAIL_USER") or ""
OUTBOUND_SMTP_PASS: str = os.getenv("DONNA_EMAIL_PASS") or ""

# ── Approval server ───────────────────────────────────────────────────────────
APPROVAL_HOST: str = _cfg["approval_server"]["host"]
APPROVAL_PORT: int = _cfg["approval_server"]["port"]
