import email
import hashlib
import logging
import re
from email.message import Message
from pathlib import Path

from bs4 import BeautifulSoup

from . import config

log = logging.getLogger(__name__)

# Subject must match: [DONNA] {case_id} - optional description
_CASE_ID_RE = re.compile(r"\[DONNA\]\s+([a-zA-Z0-9][a-zA-Z0-9_-]*)\s*(?:-.*)?$", re.IGNORECASE)

_DOC_TYPE_MAP = {
    "medical": "medical_record",
    "records": "medical_record",
    "er_report": "medical_record",
    "urgent_care": "medical_record",
    "police": "police_report",
    "incident": "police_report",
    "adjuster": "adjuster_letter",
    "demand": "adjuster_letter",
    "eob": "eob",
    "explanation": "eob",
    "witness": "witness_statement",
    "prior": "prior_medical",
}


def parse_case_id(subject: str) -> str | None:
    m = _CASE_ID_RE.search(subject or "")
    return m.group(1) if m else None


def infer_doc_type(filename: str) -> str:
    stem = Path(filename).stem.lower().replace("-", "_").replace(" ", "_")
    for keyword, doc_type in _DOC_TYPE_MAP.items():
        if keyword in stem:
            return doc_type
    return "other"


def _strip_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _extract_body(msg: Message) -> str:
    plain_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = part.get("Content-Disposition", "")
            if "attachment" in cd:
                continue
            if ct == "text/plain":
                plain_parts.append(part.get_payload(decode=True).decode(errors="replace"))
            elif ct == "text/html":
                html_parts.append(part.get_payload(decode=True).decode(errors="replace"))
    else:
        ct = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            text = payload.decode(errors="replace")
            if ct == "text/html":
                html_parts.append(text)
            else:
                plain_parts.append(text)

    if plain_parts:
        return "\n".join(plain_parts).strip()
    if html_parts:
        return _strip_html("\n".join(html_parts))
    return ""


def _save_attachment(part: Message, case_id: str, save_base: Path) -> str:
    filename = part.get_filename() or "attachment"
    filename = re.sub(r"[^\w.\-]", "_", filename)
    dest_dir = save_base / case_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        h = hashlib.md5(part.get_payload(decode=True)).hexdigest()[:6]
        dest = dest_dir / f"{stem}_{h}{suffix}"
    dest.write_bytes(part.get_payload(decode=True))
    log.info("Attachment saved: %s", dest)
    return str(dest)


def parse_email(raw_bytes: bytes, save_dir: str | None = None) -> dict:
    """
    Parse raw email bytes into a structured dict.

    Returns:
        {
            sender: str,
            subject: str,
            body: str,
            case_id: str | None,    # from [DONNA] {case_id} - ... subject line
            attachments: [
                {
                    path: str,          # path to saved file
                    filename: str,
                    doc_type_hint: str, # inferred from filename
                }
            ],
            message_id: str,
            in_reply_to: str | None,
        }
    """
    msg = email.message_from_bytes(raw_bytes)
    save_base = Path(save_dir or config.ATTACHMENT_SAVE_DIR)

    sender = msg.get("From", "unknown")
    subject = msg.get("Subject", "(no subject)")
    message_id = (msg.get("Message-ID") or "").strip("<>").strip()
    in_reply_to = (msg.get("In-Reply-To") or "").strip("<>").strip() or None
    case_id = parse_case_id(subject)

    if not case_id:
        log.warning("Email has no [DONNA] case_id in subject — attachments go to 'unmatched/': subject=%r", subject)

    body = _extract_body(msg)

    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            cd = part.get("Content-Disposition", "")
            if "attachment" in cd and part.get_filename():
                try:
                    filename = part.get_filename()
                    dest_case_id = case_id or "unmatched"
                    path = _save_attachment(part, dest_case_id, save_base)
                    attachments.append({
                        "path": path,
                        "filename": filename,
                        "doc_type_hint": infer_doc_type(filename),
                    })
                except Exception as exc:
                    log.error("Failed to save attachment %s: %s", part.get_filename(), exc)

    return {
        "sender": sender,
        "subject": subject,
        "body": body,
        "case_id": case_id,
        "attachments": attachments,
        "message_id": message_id,
        "in_reply_to": in_reply_to,
    }
