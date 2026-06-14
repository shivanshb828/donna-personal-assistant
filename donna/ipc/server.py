"""
Donna IPC server — localhost:8000/ipc

Single entry point for ALL non-voice channels: email, dashboard text, VLM callbacks.
Uses the same SessionRouter + DonnaLLM + ToolRegistry stack as the voice pipeline,
so email threads and voice calls share session state, tools, and SQLite.

Envelope: { source, session_id, text, type }
  user_input       → SessionRouter.handle_turn() → tools → SQLite
  document_ingest  → forward to VLM ingest at :8765
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from donna.glue.router.session_router import SessionRouter
from donna.glue.tools.registry import ToolRegistry
from donna.telephony.config import TelephonyConfig
from donna.telephony.db import create_call_session, get_call_session
from donna.telephony.llm import DonnaLLM

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger(__name__)

VLM_INGEST_URL = os.getenv("DONNA_PIPELINE_INGEST_URL", "http://localhost:8765/ingest")

# One SessionRouter is enough — it manages per-session_id history internally
_cfg: TelephonyConfig | None = None
_router: SessionRouter | None = None


def _get_router() -> SessionRouter:
    global _cfg, _router
    if _router is None:
        _cfg = TelephonyConfig.from_env()
        _router = SessionRouter(
            telephony_db_path=_cfg.telephony_db,
            context_db_path=_cfg.context_db,
            calendar_db_path=_cfg.calendar_db,
            llm=DonnaLLM(ollama_url=_cfg.ollama_url, model=_cfg.ollama_model),
            tools=ToolRegistry(
                telephony_db_path=_cfg.telephony_db,
                context_db_path=_cfg.context_db,
                calendar_db_path=_cfg.calendar_db,
            ),
            firm_name=_cfg.firm_name,
        )
        log.info("SessionRouter initialised | model=%s", _cfg.ollama_model)
    return _router


def _ensure_session(session_id: str, source: str) -> None:
    """Create a call session record if one doesn't exist yet (email threads need this)."""
    cfg = TelephonyConfig.from_env()
    existing = get_call_session(cfg.telephony_db, session_id)
    if not existing:
        create_call_session(
            cfg.telephony_db,
            call_sid=session_id,
            phone=None,
            agent_mode="local_assistant",  # email/text → local_assistant mode (no voice phase gates)
            is_returning=False,
        )
        log.info("Created session | id=%s source=%s", session_id, source)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Donna IPC server starting on :8000")
    _get_router()  # warm up on startup
    yield
    log.info("Donna IPC server shut down")


app = FastAPI(title="Donna IPC Server", lifespan=lifespan)


class IPCEnvelope(BaseModel):
    source: str
    session_id: str
    text: str
    type: str
    metadata: dict | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ipc")
async def handle_ipc(envelope: IPCEnvelope):
    log.info(
        "IPC | source=%s session=%s type=%s len=%d",
        envelope.source, envelope.session_id, envelope.type, len(envelope.text),
    )

    # Attachments → VLM pipeline (non-blocking)
    if envelope.type == "document_ingest":
        asyncio.ensure_future(_forward_to_vlm(envelope))
        return {"status": "accepted", "routed_to": "vlm"}

    if envelope.type != "user_input":
        return {"status": "ignored", "type": envelope.type}

    # Ensure session record exists (email threads don't go through telephony server)
    _ensure_session(envelope.session_id, envelope.source)

    router = _get_router()
    try:
        result = await asyncio.to_thread(
            router.handle_turn,
            call_sid=envelope.session_id,
            user_text=envelope.text,
            agent_mode="local_assistant",
        )
    except Exception as exc:
        log.error("SessionRouter error session=%s: %s", envelope.session_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    log.info("Donna reply session=%s phase=%s: %s", envelope.session_id, result.phase, result.reply[:120])
    return {
        "status": "ok",
        "session_id": envelope.session_id,
        "reply": result.reply,
        "phase": result.phase,
        "tool_results": result.tool_results,
        "envelope": {
            "source": "donna",
            "session_id": envelope.session_id,
            "text": result.reply,
            "type": "agent_response",
        },
    }


async def _forward_to_vlm(envelope: IPCEnvelope) -> None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(VLM_INGEST_URL, json=envelope.model_dump())
            resp.raise_for_status()
            log.info("VLM forward ok | file=%s", envelope.text)
    except Exception as exc:
        log.error("VLM forward failed | file=%s: %s", envelope.text, exc)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("donna.ipc.server:app", host="127.0.0.1", port=8000, reload=False)
