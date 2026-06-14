from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

from donna.glue.router.session_router import SessionRouter
from donna.glue.tools.registry import ToolRegistry
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

    app = FastAPI(title="Donna Telephony", version="0.1.0")
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
            llm=DonnaLLM(ollama_url=cfg.ollama_url, model=cfg.ollama_model),
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

    return app


app = create_app()
