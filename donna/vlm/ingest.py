"""
VLM document ingest server — localhost:8765/ingest

Receives document_ingest envelopes from the email router.
Runs qwen2.5vl via Ollama to extract text/meaning from attachments.
Stores result in SQLite (documents table) + ChromaDB for semantic search.

Envelope: { source, session_id, text: "/path/to/file", type: "document_ingest",
            metadata: { case_id, sender_email, filename, doc_type_hint } }
"""

from __future__ import annotations

import base64
import logging
import os
import sqlite3
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

try:
    import chromadb as _chromadb
    _CHROMA_AVAILABLE = True
except ImportError:
    _chromadb = None  # type: ignore
    _CHROMA_AVAILABLE = False
    log.warning("chromadb not installed — document indexing disabled; SQLite only")

from donna.telephony.config import TelephonyConfig

OLLAMA_URL   = os.getenv("DONNA_OLLAMA_URL", "http://localhost:11434")
VLM_MODEL    = os.getenv("DONNA_VLM_MODEL", "qwen2.5vl:7b")
CHROMA_HOST  = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT  = int(os.getenv("CHROMA_PORT", "8001"))

# Use the same SQLite paths as voice pipeline and IPC server
_cfg = TelephonyConfig.from_env()
CONTEXT_DB   = str(_cfg.context_db)   # donna_m3_context.sqlite — cases, clients, notes
CALENDAR_DB  = str(_cfg.calendar_db)  # donna_m3_calendar.sqlite

_collection = None
if _CHROMA_AVAILABLE:
    try:
        _chroma = _chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        _collection = _chroma.get_or_create_collection("donna_documents")
    except Exception as _e:
        log.warning("ChromaDB unavailable (%s) — SQLite-only mode", _e)

app = FastAPI(title="Donna VLM Ingest")


class IngestEnvelope(BaseModel):
    source: str
    session_id: str
    text: str                   # file path
    type: str
    metadata: dict | None = None


@app.get("/health")
def health():
    return {"status": "ok", "model": VLM_MODEL}


@app.post("/ingest")
async def ingest(envelope: IngestEnvelope):
    file_path = Path(envelope.text)
    meta      = envelope.metadata or {}
    case_id   = meta.get("case_id", "unmatched")
    filename  = meta.get("filename", file_path.name)
    doc_type  = meta.get("doc_type_hint", "other")

    log.info("Ingesting | case=%s file=%s type=%s", case_id, filename, doc_type)

    if not file_path.exists():
        log.error("File not found: %s", file_path)
        return {"status": "error", "message": f"File not found: {file_path}"}

    # ── Run qwen2.5vl via Ollama ────────────────────────────────────────────
    summary = await _run_vlm(file_path, doc_type)
    log.info("VLM summary | case=%s file=%s summary_len=%d", case_id, filename, len(summary))

    # ── Persist to SQLite ────────────────────────────────────────────────────
    doc_id = f"doc-{uuid.uuid4()}"
    _save_to_sqlite(
        doc_id=doc_id, case_id=case_id, filename=filename,
        doc_type=doc_type, file_path=str(file_path), summary=summary,
    )

    # ── Index in ChromaDB for semantic search ────────────────────────────────
    _index_in_chroma(
        doc_id=doc_id, case_id=case_id, filename=filename,
        doc_type=doc_type, summary=summary,
    )

    # ── Feed summary back to IPC → Donna LLM so she can update case notes ───
    await _notify_ipc(envelope.session_id, case_id, filename, doc_type, summary)

    return {
        "status": "ok",
        "doc_id": doc_id,
        "case_id": case_id,
        "filename": filename,
        "summary_preview": summary[:200],
    }


async def _run_vlm(file_path: Path, doc_type: str) -> str:
    """Send file to qwen2.5vl via Ollama and return extracted summary."""
    suffix = file_path.suffix.lower()

    # Encode file as base64 for Ollama multimodal input
    raw = file_path.read_bytes()
    b64 = base64.b64encode(raw).decode()

    prompt = _build_vlm_prompt(doc_type, file_path.name)

    payload = {
        "model": VLM_MODEL,
        "prompt": prompt,
        "images": [b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 512},
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as exc:
        log.error("VLM call failed: %s", exc)
        return f"[VLM extraction failed: {exc}]"


def _build_vlm_prompt(doc_type: str, filename: str) -> str:
    base = (
        "You are a legal document analyst for a personal injury law firm. "
        "Extract all key facts from this document. Be concise and precise. "
        "Output plain text, no markdown."
    )
    specific = {
        "police_report":     "Extract: incident date, location, parties involved, officer name, report number, fault determination.",
        "medical_record":    "Extract: patient name, date of visit, diagnosis, treatment, physician name, follow-up instructions, prognosis.",
        "adjuster_letter":   "Extract: insurance carrier, claim number, adjuster name, offer amount (if any), key positions taken.",
        "eob":               "Extract: service dates, procedure codes, amounts billed, amounts paid, patient responsibility.",
        "witness_statement": "Extract: witness name, contact info, what they observed, date of statement.",
    }.get(doc_type, "Extract all relevant legal and factual information from this document.")

    return f"{base}\n\nDocument: {filename}\nTask: {specific}"


def _save_to_sqlite(*, doc_id, case_id, filename, doc_type, file_path, summary):
    try:
        conn = sqlite3.connect(CONTEXT_DB)
        conn.execute(
            """INSERT OR REPLACE INTO documents
               (id, case_id, filename, doc_type, file_path, summary)
               VALUES (?,?,?,?,?,?)""",
            (doc_id, case_id, filename, doc_type, file_path, summary),
        )
        # Also add a case note so the lawyer sees this in the case timeline
        conn.execute(
            """INSERT INTO case_notes (id, case_id, note_type, content, created_by)
               VALUES (?,?,'document_ingested',?,?)""",
            (f"note-{uuid.uuid4()}", case_id,
             f"Document received via email: {filename} ({doc_type}). Summary: {summary[:300]}",
             "donna"),
        )
        conn.commit()
        conn.close()
        log.info("Saved to SQLite: %s → case %s", doc_id, case_id)
    except Exception as exc:
        log.error("SQLite save failed: %s", exc)


def _index_in_chroma(*, doc_id, case_id, filename, doc_type, summary):
    if _collection is None:
        log.debug("ChromaDB not available — skipping vector index for %s", doc_id)
        return
    try:
        _collection.upsert(
            ids=[doc_id],
            documents=[summary],
            metadatas=[{"case_id": case_id, "filename": filename, "doc_type": doc_type}],
        )
        log.info("Indexed in ChromaDB: %s", doc_id)
    except Exception as exc:
        log.error("ChromaDB index failed: %s", exc)


async def _notify_ipc(session_id: str, case_id: str, filename: str, doc_type: str, summary: str):
    """Tell Donna about the new document so she can update case notes/memory."""
    envelope = {
        "source": "vlm",
        "session_id": session_id,
        "text": (
            f"A new document was received for case {case_id} via email.\n"
            f"File: {filename} (type: {doc_type})\n"
            f"Extracted content:\n{summary}"
        ),
        "type": "user_input",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("http://localhost:8000/ipc", json=envelope)
            resp.raise_for_status()
    except Exception as exc:
        log.warning("IPC notify failed (non-fatal): %s", exc)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("donna.vlm.ingest:app", host="127.0.0.1", port=8765, reload=False)
