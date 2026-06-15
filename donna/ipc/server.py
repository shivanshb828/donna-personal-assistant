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
import json
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from donna.glue.router.session_router import SessionRouter
from donna.glue.tools.registry import ToolRegistry
from donna.telephony.config import TelephonyConfig
from donna.telephony.db import create_call_session, get_call_session
from donna.telephony.events import broadcast_event
from donna.telephony.llm import DonnaLLM

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger(__name__)

VLM_INGEST_URL = os.getenv("DONNA_PIPELINE_INGEST_URL", "http://localhost:8765/ingest")
EMAIL_DASHBOARD_TYPES = frozenset({"email_draft_pending", "email_sent", "email_rejected"})

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

    # Outbound email lifecycle → dashboard WebSocket relay
    if envelope.type in EMAIL_DASHBOARD_TYPES:
        cfg = TelephonyConfig.from_env()
        try:
            payload = json.loads(envelope.text)
        except json.JSONDecodeError:
            payload = {"type": envelope.type, "session_id": envelope.session_id}
        payload.setdefault("type", envelope.type)
        await broadcast_event(cfg.dashboard_ws, payload)
        return {"status": "ok", "routed_to": "dashboard"}

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

    # Auto-reply via email when request came from the email channel
    if envelope.source == "email" and envelope.metadata:
        sender_email = envelope.metadata.get("sender_email")
        if sender_email:
            asyncio.ensure_future(_send_email_reply(
                to=sender_email,
                reply_text=result.reply,
                case_id=envelope.metadata.get("case_id") or envelope.session_id,
                original_subject=envelope.metadata.get("email_subject", "Your inquiry"),
            ))

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


async def _send_email_reply(*, to: str, reply_text: str, case_id: str, original_subject: str) -> None:
    """Send Donna's reply back to the client via email (auto-send, no approval needed)."""
    try:
        from donna.email_server.sender import send_email
        subject = f"Re: {original_subject}" if not original_subject.startswith("Re:") else original_subject
        await send_email(
            to=to,
            subject=subject,
            body=reply_text,
            case_id=case_id,
            email_type="email_reply",
            requires_approval=False,
        )
        log.info("Email auto-reply sent | to=%s case=%s", to, case_id)
    except Exception as exc:
        log.error("Email auto-reply failed | to=%s: %s", to, exc)


async def _forward_to_vlm(envelope: IPCEnvelope) -> None:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(VLM_INGEST_URL, json=envelope.model_dump())
            resp.raise_for_status()
            log.info("VLM forward ok | file=%s", envelope.text)
    except Exception as exc:
        log.error("VLM forward failed | file=%s: %s", envelope.text, exc)


# ── Lawyer query endpoint ─────────────────────────────────────────────────────
# The dashboard "Ask Donna" panel POSTs here.
# Primary path: OpenClaw lawyer agent via HTTP gateway.
# Fallback:     donna.lawyer.agent (Ollama-direct, no OpenClaw needed).

OPENCLAW_URL = os.getenv("OPENCLAW_URL", "http://localhost:18789")
OPENCLAW_TOKEN = os.getenv("OPENCLAW_GATEWAY_TOKEN", "")


class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None


async def _query_openclaw(question: str) -> str:
    """Call the OpenClaw lawyer agent via its HTTP gateway."""
    headers = {"Content-Type": "application/json"}
    if OPENCLAW_TOKEN:
        headers["Authorization"] = f"Bearer {OPENCLAW_TOKEN}"

    payload = {
        "model": "lawyer",
        "messages": [{"role": "user", "content": question}],
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        # Try OpenAI-compatible endpoint with agent header
        resp = await client.post(
            f"{OPENCLAW_URL}/v1/chat/completions",
            headers={**headers, "X-OpenClaw-Agent": "lawyer"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


@app.post("/api/query")
async def lawyer_query(body: QueryRequest):
    """Natural-language query against the case database, routed through OpenClaw."""
    log.info("Query | question=%s", body.question[:120])

    # Primary: OpenClaw gateway
    try:
        answer = await _query_openclaw(body.question)
        log.info("Query answered via OpenClaw")
        return {"answer": answer, "source": "openclaw"}
    except Exception as oc_err:
        log.warning("OpenClaw unavailable (%s) — falling back to Ollama-direct", oc_err)

    # Fallback: Ollama-direct lawyer agent (same tool layer, no OpenClaw dependency)
    try:
        from donna.lawyer.agent import ask as lawyer_ask
        answer = await asyncio.to_thread(lawyer_ask, body.question)
        return {"answer": answer, "source": "ollama-direct"}
    except Exception as exc:
        log.error("Lawyer query failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Game plan + risk score ────────────────────────────────────────────────────

def _compute_risk_score(case: dict) -> dict:
    """
    Rule-based risk scorer. Returns score 0-100 + label + flags.
    Higher score = higher risk (less likely to take the case).
    """
    score = 0
    flags = []

    # SOL proximity
    sol_date = case.get("sol_date") or case.get("statute_of_limitations")
    if sol_date:
        try:
            from datetime import date
            days_left = (date.fromisoformat(sol_date[:10]) - date.today()).days
            if days_left < 0:
                score += 50; flags.append("SOL EXPIRED")
            elif days_left < 30:
                score += 35; flags.append(f"SOL in {days_left}d — urgent")
            elif days_left < 90:
                score += 15; flags.append(f"SOL in {days_left}d")
        except Exception:
            pass

    # Liability clarity
    fault = (case.get("fault_party") or "").lower()
    if not fault:
        score += 10; flags.append("Fault party unclear")
    elif "shared" in fault or "partial" in fault:
        score += 8; flags.append("Shared fault — comparative negligence risk")

    # Prior attorney
    if case.get("prior_attorney"):
        score += 12; flags.append("Prior attorney — check for fee lien")

    # Medical treatment
    treatment = (case.get("treatment_status") or "").lower()
    if not treatment or treatment == "none":
        score += 10; flags.append("No documented medical treatment")
    elif "ongoing" in treatment:
        score -= 5  # ongoing treatment = stronger damages

    # Incident type modifiers
    inc_type = (case.get("incident_type") or case.get("case_type") or "").lower()
    if "medical_malpractice" in inc_type:
        score += 8; flags.append("Med-mal — expert witness required")
    elif "workplace" in inc_type:
        score += 5; flags.append("Workers' comp bar may apply")

    score = max(0, min(100, score))
    if score >= 50:
        label, color = "High Risk", "red"
    elif score >= 25:
        label, color = "Medium Risk", "amber"
    else:
        label, color = "Low Risk", "green"

    return {"score": score, "label": label, "color": color, "flags": flags}


def _generate_game_plan(case: dict, risk: dict) -> dict:
    """Rule-based game plan — no LLM needed, fast and deterministic."""
    steps = []
    inc_type = (case.get("incident_type") or case.get("case_type") or "auto_accident").lower()
    stage = case.get("stage", "intake")

    # Universal first steps
    if stage == "intake":
        steps.append({"priority": "high", "action": "Complete signed retainer agreement", "owner": "Attorney"})
        steps.append({"priority": "high", "action": "Obtain all medical records & bills", "owner": "Donna"})
        steps.append({"priority": "high", "action": "Preserve all evidence (photos, dashcam, witness contacts)", "owner": "Client"})

    if "auto" in inc_type or "vehicle" in inc_type:
        steps += [
            {"priority": "high",   "action": "Order police report",                         "owner": "Donna"},
            {"priority": "high",   "action": "Notify client's insurer of representation",   "owner": "Attorney"},
            {"priority": "medium", "action": "Request adjuster assignment & claim number",   "owner": "Donna"},
            {"priority": "medium", "action": "Send lien letter to treating providers",       "owner": "Attorney"},
            {"priority": "low",    "action": "Evaluate need for accident reconstruction",    "owner": "Attorney"},
        ]
    elif "slip" in inc_type or "fall" in inc_type:
        steps += [
            {"priority": "high",   "action": "Obtain incident report from property owner",  "owner": "Donna"},
            {"priority": "high",   "action": "Preserve surveillance footage (72-hr window)","owner": "Attorney"},
            {"priority": "medium", "action": "Document hazard condition with photos",        "owner": "Client"},
            {"priority": "medium", "action": "Identify property owner / insurance carrier",  "owner": "Donna"},
        ]
    elif "workplace" in inc_type:
        steps += [
            {"priority": "high",   "action": "File workers' comp claim within deadline",    "owner": "Attorney"},
            {"priority": "high",   "action": "Identify third-party liability (equipment, contractor)", "owner": "Attorney"},
            {"priority": "medium", "action": "Obtain OSHA report if applicable",            "owner": "Donna"},
        ]
    elif "medical" in inc_type:
        steps += [
            {"priority": "high",   "action": "Retain medical expert early",                 "owner": "Attorney"},
            {"priority": "high",   "action": "Obtain complete medical records pre/post",     "owner": "Donna"},
            {"priority": "medium", "action": "Review standard of care with expert",          "owner": "Attorney"},
        ]

    # SOL flag → top of list
    for flag in risk["flags"]:
        if "SOL" in flag:
            steps.insert(0, {"priority": "urgent", "action": f"⚠️  {flag} — file or toll immediately", "owner": "Attorney"})

    # Settlement range estimate (very rough)
    treatment = (case.get("treatment_status") or "").lower()
    if "surgery" in treatment or "hospital" in treatment:
        settlement_range = "$50,000 – $250,000+"
    elif "ongoing" in treatment or "physical therapy" in treatment:
        settlement_range = "$15,000 – $75,000"
    elif treatment and treatment != "none":
        settlement_range = "$5,000 – $25,000"
    else:
        settlement_range = "TBD — awaiting medical evaluation"

    return {
        "steps": steps,
        "settlement_range": settlement_range,
        "case_type": inc_type,
        "stage": stage,
    }


class GamePlanRequest(BaseModel):
    case_id: str


@app.post("/api/gameplan")
async def get_gameplan(body: GamePlanRequest):
    """Generate risk score + action game plan for a case."""
    cfg = TelephonyConfig.from_env()
    import sqlite3
    case = None

    # Try context DB first
    try:
        with sqlite3.connect(cfg.context_db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM intakes WHERE case_id=? ORDER BY created_at DESC LIMIT 1",
                (body.case_id,),
            ).fetchone()
            if row:
                case = dict(row)
    except Exception:
        pass

    # Fallback to telephony DB
    if not case:
        try:
            with sqlite3.connect(cfg.telephony_db) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM call_sessions WHERE call_sid=? LIMIT 1",
                    (body.case_id,),
                ).fetchone()
                if row:
                    case = dict(row)
        except Exception:
            pass

    if not case:
        case = {"case_id": body.case_id, "stage": "intake"}

    risk = _compute_risk_score(case)
    plan = _generate_game_plan(case, risk)

    return {
        "case_id": body.case_id,
        "risk": risk,
        "game_plan": plan,
        "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
    }


@app.get("/api/cases/{case_id}/risk")
async def get_risk_score(case_id: str):
    """Quick risk score for a single case (no full game plan)."""
    req = GamePlanRequest(case_id=case_id)
    result = await get_gameplan(req)
    return {"case_id": case_id, "risk": result["risk"]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("donna.ipc.server:app", host="127.0.0.1", port=8000, reload=False)
