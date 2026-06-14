"""
Donna IPC server — HTTP endpoint at localhost:8000/ipc

Receives IPC envelopes from email server, voice pipeline, and any other channel.
Routes to DonnaAgent (Ollama direct) and executes tool calls against SQLite.

Envelope schema: { source, session_id, text, type }
  type == "user_input"       → feed to DonnaAgent.chat()
  type == "document_ingest"  → forward to VLM pipeline at :8765
  type == "tool_result"      → inject into agent history (unused for now)
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from donna.integration.agent_bridge import DonnaAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger(__name__)

VLM_INGEST_URL = os.getenv("DONNA_PIPELINE_INGEST_URL", "http://localhost:8765/ingest")

# One DonnaAgent per session_id — persists conversation history
_sessions: dict[str, DonnaAgent] = {}


def _get_agent(session_id: str) -> DonnaAgent:
    if session_id not in _sessions:
        _sessions[session_id] = DonnaAgent(session_id=session_id)
        log.info("New session: %s", session_id)
    return _sessions[session_id]


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Donna IPC server starting on :8000")
    yield
    log.info("Donna IPC server shutting down")


app = FastAPI(title="Donna IPC Server", lifespan=lifespan)


class IPCEnvelope(BaseModel):
    source: str
    session_id: str
    text: str
    type: str
    metadata: dict | None = None


@app.get("/health")
async def health():
    return {"status": "ok", "sessions": len(_sessions)}


@app.post("/ipc")
async def handle_ipc(envelope: IPCEnvelope):
    log.info(
        "IPC received | source=%s session=%s type=%s text_len=%d",
        envelope.source, envelope.session_id, envelope.type, len(envelope.text),
    )

    # Document attachments → VLM pipeline
    if envelope.type == "document_ingest":
        asyncio.ensure_future(_forward_to_vlm(envelope))
        return {"status": "accepted", "routed_to": "vlm"}

    # Text input → Donna LLM
    if envelope.type == "user_input":
        agent = _get_agent(envelope.session_id)
        try:
            reply = await agent.chat(envelope.text)
        except Exception as exc:
            log.error("Agent error session=%s: %s", envelope.session_id, exc)
            raise HTTPException(status_code=500, detail=str(exc))

        log.info("Donna reply session=%s: %s", envelope.session_id, reply[:120])
        return {
            "status": "ok",
            "session_id": envelope.session_id,
            "reply": reply,
            "envelope": {
                "source": "donna",
                "session_id": envelope.session_id,
                "text": reply,
                "type": "agent_response",
            },
        }

    return {"status": "ignored", "type": envelope.type}


async def _forward_to_vlm(envelope: IPCEnvelope) -> None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(VLM_INGEST_URL, json=envelope.model_dump())
            resp.raise_for_status()
            log.info("Forwarded to VLM | file=%s status=%s", envelope.text, resp.status_code)
    except Exception as exc:
        log.error("VLM forward failed | file=%s: %s", envelope.text, exc)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("donna.ipc.server:app", host="127.0.0.1", port=8000, reload=False)
