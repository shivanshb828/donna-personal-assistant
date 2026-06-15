from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

from donna.glue.router.session_router import SessionRouter
from donna.glue.tools.registry import ToolRegistry
from donna.glue.dashboard_data import (
    list_calendar_events,
    list_cases,
    list_pending_email_drafts,
)
from donna.telephony.config import TelephonyConfig
from donna.telephony.db import (
    complete_call_session,
    create_call_session,
    create_lead,
    get_call_session,
    init_telephony_db,
    list_leads,
    list_messages,
    lookup_prior_session_by_phone,
    normalize_phone,
)
from donna.telephony.events import broadcast_event
from donna.telephony.local_provider import LocalVoiceSession, build_media_message
from donna.telephony.llm import DonnaLLM
from donna.telephony.tokens import StreamTokenStore
from donna.telephony.twilio_validate import read_twilio_form, request_url, validate_twilio_signature
from donna.telephony.twiml import build_hangup_twiml, build_stream_twiml
from donna.voice.stt import warm_stt
from donna.voice.tts import warm_tts

STARTUP_WARM_TIMEOUT_SECONDS = 15.0


async def _validate_twilio(request: Request, cfg: TelephonyConfig, path: str, form_data: dict[str, str]) -> bool:
    if not cfg.validate_twilio_signature:
        return True
    if not cfg.twilio_auth_token:
        return False
    signature = request.headers.get("X-Twilio-Signature")
    url = request_url(request, cfg.public_url, path)
    return validate_twilio_signature(
        auth_token=cfg.twilio_auth_token,
        url=url,
        form_data=form_data,
        signature=signature,
    )


def create_app(config: TelephonyConfig | None = None) -> FastAPI:
    cfg = config or TelephonyConfig.from_env()
    init_telephony_db(cfg.telephony_db)
    shared_llm = DonnaLLM(ollama_url=cfg.ollama_url, model=cfg.ollama_model)

    async def _run_warm(label: str, fn) -> Exception | None:
        try:
            await asyncio.wait_for(asyncio.to_thread(fn), timeout=STARTUP_WARM_TIMEOUT_SECONDS)
        except Exception as exc:
            return RuntimeError(f"{label}: {exc}")
        return None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        started = time.perf_counter()
        results = await asyncio.gather(
            _run_warm("llm", shared_llm.warm),
            _run_warm("stt", warm_stt),
            _run_warm("tts", warm_tts),
        )
        for result in results:
            if result is not None:
                print(f"[Warmup warning] {result}")
        print(f"[Warmup] completed in {time.perf_counter() - started:.2f}s")
        yield

    app = FastAPI(title="Donna Telephony", version="0.1.0", lifespan=lifespan)
    tokens = StreamTokenStore()
    sessions: dict[str, LocalVoiceSession] = {}

    def _tool_registry() -> ToolRegistry:
        return ToolRegistry(
            telephony_db_path=cfg.telephony_db,
            context_db_path=cfg.context_db,
            calendar_db_path=cfg.calendar_db,
        )

    def _router() -> SessionRouter:
        return SessionRouter(
            telephony_db_path=cfg.telephony_db,
            context_db_path=cfg.context_db,
            calendar_db_path=cfg.calendar_db,
            llm=shared_llm,
            tools=_tool_registry(),
            firm_name=cfg.firm_name,
        )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "twilio_configured": cfg.twilio_configured,
            "echo_mode": cfg.echo_mode,
            "media_stream_ws_url": cfg.media_stream_ws_url,
        }

    @app.post("/voice")
    async def voice_inbound(request: Request) -> Response:
        form_data = await read_twilio_form(request)
        if not await _validate_twilio(request, cfg, "/voice", form_data):
            return Response(content=build_hangup_twiml("Unauthorized."), media_type="text/xml", status_code=403)
        call_sid = form_data.get("CallSid", "")
        caller = form_data.get("From", "")
        phone = normalize_phone(caller)
        prior = lookup_prior_session_by_phone(cfg.telephony_db, phone) if phone else None
        create_call_session(
            cfg.telephony_db,
            call_sid=call_sid,
            phone=phone,
            agent_mode="inbound_intake",
            is_returning=prior is not None,
        )
        await broadcast_event(cfg.dashboard_ws, {
            "type": "call_started",
            "callSid": call_sid,
            "callerPhone": phone,
            "agentMode": "inbound_intake",
            "isReturning": prior is not None,
        })
        stream_token = tokens.issue(call_sid)
        twiml = build_stream_twiml(
            media_stream_ws_url=cfg.media_stream_ws_url,
            call_sid=call_sid,
            stream_token=stream_token,
        )
        return Response(content=twiml, media_type="text/xml")

    @app.post("/voice/outbound")
    async def voice_outbound(request: Request) -> Response:
        form_data = await read_twilio_form(request)
        if not await _validate_twilio(request, cfg, "/voice/outbound", form_data):
            return Response(content=build_hangup_twiml("Unauthorized."), media_type="text/xml", status_code=403)
        call_sid = form_data.get("CallSid", "")
        callee = form_data.get("To", "")
        phone = normalize_phone(callee)
        create_call_session(
            cfg.telephony_db,
            call_sid=call_sid,
            phone=phone,
            agent_mode="outbound_lead",
            is_returning=False,
        )
        await broadcast_event(cfg.dashboard_ws, {
            "type": "call_started",
            "callSid": call_sid,
            "callerPhone": phone,
            "agentMode": "outbound_lead",
            "isReturning": False,
        })
        stream_token = tokens.issue(call_sid)
        twiml = build_stream_twiml(
            media_stream_ws_url=cfg.media_stream_ws_url,
            call_sid=call_sid,
            stream_token=stream_token,
        )
        return Response(content=twiml, media_type="text/xml")

    @app.websocket("/media-stream")
    async def media_stream(ws: WebSocket) -> None:
        await ws.accept()
        session: LocalVoiceSession | None = None
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                event = frame.get("event")

                if event == "connected":
                    continue

                if event == "start":
                    start = frame.get("start", {})
                    call_sid = start.get("callSid")
                    stream_sid = start.get("streamSid")
                    params = start.get("customParameters") or {}
                    token = params.get("streamToken")
                    if not call_sid or not stream_sid or not tokens.consume(call_sid, token):
                        if call_sid:
                            complete_call_session(
                                cfg.telephony_db,
                                call_sid=call_sid,
                                duration_seconds=1,
                                outcome="auth_failed",
                            )
                        await ws.close(code=1008)
                        return
                    db_session = get_call_session(cfg.telephony_db, call_sid)
                    session = LocalVoiceSession(
                        call_sid=call_sid,
                        stream_sid=stream_sid,
                        agent_mode=db_session.agent_mode if db_session else "inbound_intake",
                        caller_name=None,
                        is_returning=db_session.is_returning if db_session else False,
                        router=_router(),
                        dashboard_ws=cfg.dashboard_ws,
                        echo_mode=cfg.echo_mode,
                    )
                    sessions[call_sid] = session
                    await broadcast_event(cfg.dashboard_ws, {
                        "type": "pipeline_status",
                        "status": "ready",
                        "callSid": call_sid,
                    })
                    if not cfg.echo_mode:
                        for payload in await session.send_greeting():
                            await ws.send_text(build_media_message(stream_sid=stream_sid, payload_b64=payload))
                    continue

                if event == "media" and session:
                    payload = frame.get("media", {}).get("payload", "")
                    for out_payload in await session.handle_mulaw_frame(payload):
                        await ws.send_text(build_media_message(stream_sid=session.stream_sid, payload_b64=out_payload))
                    continue

                if event == "clear" and session:
                    session.clear_playback()
                    continue

                if event == "stop" and session:
                    duration = max(1, int(time.time() - session.started_at))
                    outcome = get_call_session(cfg.telephony_db, session.call_sid)
                    complete_call_session(
                        cfg.telephony_db,
                        call_sid=session.call_sid,
                        duration_seconds=duration,
                        outcome=outcome.phase if outcome else "incomplete",
                        transcript=session.transcript,
                    )
                    await broadcast_event(cfg.dashboard_ws, {
                        "type": "call_ended",
                        "callSid": session.call_sid,
                        "duration": duration,
                        "outcome": outcome.phase if outcome else "incomplete",
                    })
                    sessions.pop(session.call_sid, None)
                    break
        except WebSocketDisconnect:
            if session:
                duration = max(1, int(time.time() - session.started_at))
                complete_call_session(
                    cfg.telephony_db,
                    call_sid=session.call_sid,
                    duration_seconds=duration,
                    outcome="disconnected",
                    transcript=session.transcript,
                )
                await broadcast_event(cfg.dashboard_ws, {
                    "type": "call_ended",
                    "callSid": session.call_sid,
                    "duration": duration,
                    "outcome": "disconnected",
                })
                sessions.pop(session.call_sid, None)
        except Exception:
            if session:
                duration = max(1, int(time.time() - session.started_at))
                complete_call_session(
                    cfg.telephony_db,
                    call_sid=session.call_sid,
                    duration_seconds=duration,
                    outcome="error",
                    transcript=session.transcript,
                )
                await broadcast_event(cfg.dashboard_ws, {
                    "type": "call_ended",
                    "callSid": session.call_sid,
                    "duration": duration,
                    "outcome": "error",
                })
                sessions.pop(session.call_sid, None)
            raise

    @app.post("/api/calls/outbound")
    async def api_outbound_call(request: Request) -> JSONResponse:
        body = await request.json()
        phone = normalize_phone(body.get("phone", ""))
        lead_id = body.get("lead_id")
        if not phone:
            return JSONResponse({"error": "phone is required"}, status_code=400)
        if not cfg.twilio_configured or not cfg.public_url:
            return JSONResponse({"error": "Twilio or PUBLIC_URL not configured"}, status_code=500)

        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/{cfg.twilio_account_sid}/Calls.json"
        )
        data = {
            "To": phone,
            "From": cfg.twilio_phone_number,
            "Url": f"{cfg.public_url.rstrip('/')}/voice/outbound",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, data=data, auth=(cfg.twilio_account_sid, cfg.twilio_auth_token))
        if resp.status_code >= 400:
            return JSONResponse({"error": "Failed to place outbound call", "detail": resp.text}, status_code=502)
        call_sid = resp.json().get("sid")
        if lead_id:
            from donna.telephony.db import update_lead_status

            update_lead_status(cfg.telephony_db, lead_id, "contacted")
        return JSONResponse({"ok": True, "callSid": call_sid, "to": phone})

    @app.get("/api/leads")
    async def api_list_leads(status: str | None = None) -> dict:
        leads = list_leads(cfg.telephony_db, status=status)
        return {"leads": [lead.__dict__ for lead in leads]}

    @app.post("/api/leads")
    async def api_create_lead(request: Request) -> JSONResponse:
        body = await request.json()
        name = (body.get("name") or "").strip()
        phone = body.get("phone", "")
        if not name or not phone:
            return JSONResponse({"error": "name and phone are required"}, status_code=400)
        lead = create_lead(
            cfg.telephony_db,
            name=name,
            phone=phone,
            source=body.get("source"),
            incident_summary=body.get("incident_summary"),
        )
        return JSONResponse({"ok": True, "lead": lead.__dict__})

    @app.get("/api/messages")
    async def api_list_messages(client_id: str | None = None, call_sid: str | None = None) -> dict:
        messages = list_messages(cfg.telephony_db, client_id=client_id, call_session_id=call_sid)
        return {"messages": messages}

    @app.get("/api/calls/{call_sid}")
    async def api_get_call(call_sid: str) -> JSONResponse:
        session = get_call_session(cfg.telephony_db, call_sid)
        if not session:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({"session": session.__dict__})

    @app.get("/api/cases")
    async def api_list_cases() -> dict:
        return {"cases": list_cases(cfg.context_db)}

    @app.get("/api/calendar/events")
    async def api_list_calendar_events(limit: int = 50) -> dict:
        return {"events": list_calendar_events(cfg.calendar_db, limit=limit)}

    @app.get("/api/emails/drafts")
    async def api_list_email_drafts() -> dict:
        import os

        drafts_dir = Path(os.getenv("DONNA_DRAFTS_DIR", "data/donna/drafts"))
        return {"drafts": list_pending_email_drafts(drafts_dir)}

    @app.post("/api/emails/{draft_id}/approve")
    async def api_approve_email(draft_id: str, request: Request) -> JSONResponse:
        from donna.email_server.sender import approve_and_send
        body = await request.json()
        case_id = body.get("case_id", "")
        if not case_id:
            return JSONResponse({"error": "case_id is required"}, status_code=400)
        result = await approve_and_send(draft_id=draft_id, case_id=case_id)
        if result.get("status") == "error":
            return JSONResponse(result, status_code=422)
        return JSONResponse(result)

    @app.post("/api/emails/{draft_id}/reject")
    async def api_reject_email(draft_id: str, request: Request) -> JSONResponse:
        from donna.email_server.sender import reject_draft
        body = await request.json()
        case_id = body.get("case_id", "")
        reason = body.get("reason", "")
        if not case_id:
            return JSONResponse({"error": "case_id is required"}, status_code=400)
        result = await reject_draft(draft_id=draft_id, case_id=case_id, reason=reason)
        if result.get("status") == "error":
            return JSONResponse(result, status_code=422)
        return JSONResponse(result)

    @app.post("/api/query")
    async def api_query(request: Request) -> JSONResponse:
        body = await request.json()
        question = (body.get("question") or "").strip()
        if not question:
            return JSONResponse({"error": "question is required"}, status_code=400)
        openclaw_url = os.getenv("OPENCLAW_GATEWAY_URL", "http://localhost:7701")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{openclaw_url}/query",
                    json={"question": question},
                )
                resp.raise_for_status()
                data = resp.json()
                answer = data.get("answer") or data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return JSONResponse({"answer": answer, "source": "openclaw"})
        except Exception:
            pass
        try:
            from donna.lawyer.agent import ask as lawyer_ask
            answer = await asyncio.to_thread(lawyer_ask, question)
            return JSONResponse({"answer": answer, "source": "ollama-direct"})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @app.post("/api/gameplan")
    async def api_gameplan(request: Request) -> JSONResponse:
        import sqlite3
        from datetime import date
        body = await request.json()
        case_id = (body.get("case_id") or "").strip()
        if not case_id:
            return JSONResponse({"error": "case_id is required"}, status_code=400)
        case: dict = {}
        for db_path, query, params in [
            (cfg.context_db, "SELECT * FROM intakes WHERE case_id=? ORDER BY created_at DESC LIMIT 1", (case_id,)),
            (cfg.telephony_db, "SELECT * FROM call_sessions WHERE call_sid=? LIMIT 1", (case_id,)),
        ]:
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    row = conn.execute(query, params).fetchone()
                    if row:
                        case = dict(row)
                        break
            except Exception:
                pass
        if not case:
            case = {"case_id": case_id, "stage": "intake"}

        def _risk(c: dict) -> dict:
            score, flags = 0, []
            sol = c.get("sol_date") or c.get("statute_of_limitations")
            if sol:
                try:
                    days = (date.fromisoformat(sol[:10]) - date.today()).days
                    if days < 0: score += 50; flags.append("SOL EXPIRED")
                    elif days < 30: score += 35; flags.append(f"SOL in {days}d — urgent")
                    elif days < 90: score += 15; flags.append(f"SOL in {days}d")
                except Exception: pass
            fault = (c.get("fault_party") or "").lower()
            if not fault: score += 10; flags.append("Fault party unclear")
            elif "shared" in fault or "partial" in fault: score += 8; flags.append("Shared fault")
            if c.get("prior_attorney"): score += 12; flags.append("Prior attorney — check fee lien")
            tx = (c.get("treatment_status") or "").lower()
            if not tx or tx == "none": score += 10; flags.append("No documented treatment")
            elif "ongoing" in tx: score -= 5
            score = max(0, min(100, score))
            label, color = ("High Risk", "red") if score >= 50 else ("Medium Risk", "amber") if score >= 25 else ("Low Risk", "green")
            return {"score": score, "label": label, "color": color, "flags": flags}

        def _plan(c: dict, risk: dict) -> dict:
            steps = []
            inc = (c.get("incident_type") or c.get("case_type") or "auto_accident").lower()
            if c.get("stage", "intake") == "intake":
                steps.append({"priority": "high", "action": "Complete signed retainer agreement", "owner": "Attorney"})
                steps.append({"priority": "high", "action": "Obtain all medical records & bills", "owner": "Donna"})
                steps.append({"priority": "high", "action": "Preserve evidence (photos, dashcam, witnesses)", "owner": "Client"})
            if "auto" in inc or "vehicle" in inc:
                steps += [
                    {"priority": "high", "action": "Order police report", "owner": "Donna"},
                    {"priority": "high", "action": "Notify client insurer of representation", "owner": "Attorney"},
                    {"priority": "medium", "action": "Request adjuster assignment & claim number", "owner": "Donna"},
                ]
            elif "slip" in inc or "fall" in inc:
                steps += [
                    {"priority": "high", "action": "Obtain incident report from property owner", "owner": "Donna"},
                    {"priority": "high", "action": "Preserve surveillance footage (72-hr window)", "owner": "Attorney"},
                ]
            for flag in risk["flags"]:
                if "SOL" in flag:
                    steps.insert(0, {"priority": "urgent", "action": f"⚠️  {flag} — file or toll immediately", "owner": "Attorney"})
            tx = (c.get("treatment_status") or "").lower()
            if "surgery" in tx or "hospital" in tx: sr = "$50,000 – $250,000+"
            elif "ongoing" in tx or "physical therapy" in tx: sr = "$15,000 – $75,000"
            elif tx and tx != "none": sr = "$5,000 – $25,000"
            else: sr = "TBD — awaiting medical evaluation"
            return {"steps": steps, "settlement_range": sr, "case_type": inc, "stage": c.get("stage", "intake")}

        import datetime
        risk = _risk(case)
        plan = _plan(case, risk)
        return JSONResponse({"case_id": case_id, "risk": risk, "game_plan": plan,
                             "generated_at": datetime.datetime.utcnow().isoformat()})

    @app.get("/api/cases/{case_id}/risk")
    async def api_case_risk(case_id: str) -> JSONResponse:
        import sqlite3
        from datetime import date
        case: dict = {}
        for db_path, query, params in [
            (cfg.context_db, "SELECT * FROM intakes WHERE case_id=? ORDER BY created_at DESC LIMIT 1", (case_id,)),
            (cfg.telephony_db, "SELECT * FROM call_sessions WHERE call_sid=? LIMIT 1", (case_id,)),
        ]:
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    row = conn.execute(query, params).fetchone()
                    if row:
                        case = dict(row)
                        break
            except Exception:
                pass
        if not case:
            case = {}
        score, flags = 0, []
        sol = case.get("sol_date") or case.get("statute_of_limitations")
        if sol:
            try:
                days = (date.fromisoformat(sol[:10]) - date.today()).days
                if days < 0: score += 50; flags.append("SOL EXPIRED")
                elif days < 30: score += 35; flags.append(f"SOL in {days}d — urgent")
                elif days < 90: score += 15; flags.append(f"SOL in {days}d")
            except Exception: pass
        if case.get("prior_attorney"): score += 12; flags.append("Prior attorney")
        tx = (case.get("treatment_status") or "").lower()
        if not tx or tx == "none": score += 10; flags.append("No documented treatment")
        score = max(0, min(100, score))
        label, color = ("High Risk", "red") if score >= 50 else ("Medium Risk", "amber") if score >= 25 else ("Low Risk", "green")
        return JSONResponse({"case_id": case_id, "risk": {"score": score, "label": label, "color": color, "flags": flags}})

    return app


app = create_app()
