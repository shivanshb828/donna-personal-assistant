from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pytest

from donna.email_server.parser import parse_email, parse_case_id, infer_doc_type


# ── helpers ──────────────────────────────────────────────────────────────────

def _plain(body: str, subject="[DONNA] case-2026-001 - adjuster update",
           sender="adjuster@insurance.com") -> bytes:
    msg = MIMEText(body, "plain")
    msg["From"] = sender
    msg["Subject"] = subject
    msg["Message-ID"] = "<abc123@insurance.com>"
    return msg.as_bytes()


def _html(html: str, subject="[DONNA] case-2026-002 - hearing notice") -> bytes:
    msg = MIMEText(html, "html")
    msg["From"] = "court@judiciary.gov"
    msg["Subject"] = subject
    msg["Message-ID"] = "<html001@judiciary.gov>"
    return msg.as_bytes()


def _multipart(body: str, attachment_data: bytes, filename: str,
               subject="[DONNA] case-2026-001 - medical records") -> bytes:
    msg = MIMEMultipart()
    msg["From"] = "adjuster@carrier.com"
    msg["Subject"] = subject
    msg["Message-ID"] = "<multi001@carrier.com>"
    msg["In-Reply-To"] = "<prev001@carrier.com>"
    msg.attach(MIMEText(body, "plain"))
    part = MIMEApplication(attachment_data, Name=filename)
    part["Content-Disposition"] = f'attachment; filename="{filename}"'
    msg.attach(part)
    return msg.as_bytes()


# ── parse_case_id ─────────────────────────────────────────────────────────────

def test_parse_case_id_standard():
    assert parse_case_id("[DONNA] case-2026-001 - police report from SJPD") == "case-2026-001"

def test_parse_case_id_no_description():
    assert parse_case_id("[DONNA] case-2026-001") == "case-2026-001"

def test_parse_case_id_missing():
    assert parse_case_id("Settlement Offer — Smith case") is None

def test_parse_case_id_case_insensitive():
    assert parse_case_id("[donna] case-2026-007 - records") == "case-2026-007"


# ── infer_doc_type ────────────────────────────────────────────────────────────

def test_infer_doc_type_police():
    assert infer_doc_type("police-report.pdf") == "police_report"

def test_infer_doc_type_medical():
    assert infer_doc_type("urgent_care_records.pdf") == "medical_record"

def test_infer_doc_type_adjuster():
    assert infer_doc_type("adjuster-letter-march.pdf") == "adjuster_letter"

def test_infer_doc_type_eob():
    assert infer_doc_type("eob_march_2026.pdf") == "eob"

def test_infer_doc_type_fallback():
    assert infer_doc_type("unknown-document.docx") == "other"


# ── parse_email ───────────────────────────────────────────────────────────────

def test_plain_email_with_case_id(tmp_path):
    raw = _plain("Settlement update: offer is $50k.")
    result = parse_email(raw, save_dir=str(tmp_path))

    assert result["sender"] == "adjuster@insurance.com"
    assert result["case_id"] == "case-2026-001"
    assert "Settlement update" in result["body"]
    assert result["attachments"] == []
    assert result["message_id"] == "abc123@insurance.com"
    assert result["in_reply_to"] is None


def test_email_without_case_id_logs_warning(tmp_path, caplog):
    import logging
    raw = _plain("Just a note.", subject="No case ID here")
    with caplog.at_level(logging.WARNING, logger="donna.email_server.parser"):
        result = parse_email(raw, save_dir=str(tmp_path))
    assert result["case_id"] is None
    assert "no [DONNA] case_id" in caplog.text


def test_html_email_stripped(tmp_path):
    html = "<html><body><h1>Hearing Notice</h1><p>Monday <b>9am</b>.</p></body></html>"
    raw = _html(html)
    result = parse_email(raw, save_dir=str(tmp_path))
    assert "Hearing Notice" in result["body"]
    assert "<h1>" not in result["body"]
    assert result["case_id"] == "case-2026-002"


def test_attachment_saved_under_case_id_dir(tmp_path):
    pdf_bytes = b"%PDF-1.4 fake content"
    raw = _multipart("See attached medical records.", pdf_bytes, "urgent_care_records.pdf")
    result = parse_email(raw, save_dir=str(tmp_path))

    assert len(result["attachments"]) == 1
    att = result["attachments"][0]
    saved = Path(att["path"])
    assert saved.exists()
    assert saved.read_bytes() == pdf_bytes
    assert "case-2026-001" in str(saved)
    assert att["doc_type_hint"] == "medical_record"
    assert att["filename"] == "urgent_care_records.pdf"


def test_attachment_without_case_id_goes_to_unmatched(tmp_path):
    pdf_bytes = b"%PDF fake"
    raw = _multipart("Some attachment.", pdf_bytes, "report.pdf",
                     subject="No case ID in subject")
    result = parse_email(raw, save_dir=str(tmp_path))
    assert result["case_id"] is None
    assert "unmatched" in result["attachments"][0]["path"]


def test_attachment_collision_handled(tmp_path):
    pdf1 = b"%PDF content one"
    pdf2 = b"%PDF content two"
    raw1 = _multipart("First", pdf1, "report.pdf")
    raw2 = _multipart("Second", pdf2, "report.pdf")

    r1 = parse_email(raw1, save_dir=str(tmp_path))
    r2 = parse_email(raw2, save_dir=str(tmp_path))

    p1 = Path(r1["attachments"][0]["path"])
    p2 = Path(r2["attachments"][0]["path"])
    assert p1 != p2
    assert p1.read_bytes() == pdf1
    assert p2.read_bytes() == pdf2
