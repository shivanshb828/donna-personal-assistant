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

SMTP_HOST: str = _cfg["smtp"]["host"]
SMTP_PORT: int = _cfg["smtp"]["port"]

IMAP_HOST: str = _cfg["imap"]["host"]
IMAP_PORT: int = _cfg["imap"]["port"]
IMAP_SSL: bool = _cfg["imap"]["use_ssl"]
IMAP_USER: str = os.getenv("DONNA_EMAIL_USER") or _cfg["imap"]["username"]
IMAP_PASS: str = os.getenv("DONNA_EMAIL_PASS") or _cfg["imap"]["password"]
IMAP_POLL_INTERVAL: int = _cfg["imap"]["poll_interval_seconds"]
IMAP_MAILBOX: str = _cfg["imap"]["mailbox"]
IMAP_MARK_READ: bool = _cfg["imap"]["mark_read"]

# Plain email body text → Donna's LLM via M1
SESSION_ROUTER_URL: str = os.getenv("DONNA_SESSION_ROUTER_URL") or _cfg["session_router"]["url"]

# Attachment documents → VLM document pipeline
PIPELINE_INGEST_URL: str = os.getenv("DONNA_PIPELINE_INGEST_URL") or _cfg["pipeline"]["ingest_url"]

# Base dir — files land at {ATTACHMENT_SAVE_DIR}/{case_id}/{filename}
ATTACHMENT_SAVE_DIR: str = os.getenv("DONNA_ATTACHMENT_DIR") or _cfg["attachments"]["save_dir"]
