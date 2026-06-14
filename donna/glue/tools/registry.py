from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from donna.glue.test_data import connect as connect_context, init_context_db
from donna.glue.tools.calendar import book_calendar
from donna.telephony import db as telephony_db


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: dict
    error: str | None = None


REQUIRED_CONSENTS = {
    "intake.start": {"ai_disclosure", "recording"},
    "case.create": {"ai_disclosure", "recording", "data_storage"},
    "calendar.create_event": {"ai_disclosure", "recording"},
}


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "record_consent",
            "description": "Record explicit caller consent for AI disclosure, recording, or data storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "consent_type": {
                        "type": "string",
                        "enum": ["ai_disclosure", "recording", "data_storage"],
                    },
                    "granted": {"type": "boolean"},
                },
                "required": ["consent_type", "granted"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "intake.start",
            "description": "Start a new personal injury intake for this caller.",
            "parameters": {
                "type": "object",
                "properties": {
                    "caller_name": {"type": "string"},
                    "phone": {"type": "string"},
                    "incident_date": {"type": "string"},
                    "incident_location": {"type": "string"},
                    "injury_summary": {"type": "string"},
                    "incident_type": {"type": "string"},
                },
                "required": ["caller_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "intake.update",
            "description": "Add or update intake details collected during the call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_date": {"type": "string"},
                    "incident_location": {"type": "string"},
                    "injury_summary": {"type": "string"},
                    "fault_party": {"type": "string"},
                    "treatment_status": {"type": "string"},
                    "insurance_info": {"type": "string"},
                    "prior_attorney": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "case.qualify",
            "description": "Evaluate whether the firm can likely take this personal injury matter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "jurisdiction": {"type": "string"},
                    "incident_date": {"type": "string"},
                    "at_fault_clear": {"type": "boolean"},
                    "injury_present": {"type": "boolean"},
                    "prior_attorney": {"type": "boolean"},
                },
                "required": ["jurisdiction", "injury_present"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "case.create",
            "description": "Create a case record from a qualified intake.",
            "parameters": {
                "type": "object",
                "properties": {
                    "caller_name": {"type": "string"},
                    "phone": {"type": "string"},
                    "case_type": {"type": "string"},
                    "incident_date": {"type": "string"},
                    "incident_location": {"type": "string"},
                    "injuries": {"type": "string"},
                    "treatment_received": {"type": "string"},
                },
                "required": ["caller_name", "case_type", "incident_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "case.decline",
            "description": "Politely decline the matter and record the reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "referral_note": {"type": "string"},
                },
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calendar.create_event",
            "description": "Book a consultation on the firm calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string"},
                    "case_id": {"type": "string"},
                    "title": {"type": "string"},
                    "scheduled_at": {"type": "string", "description": "ISO-8601 datetime"},
                    "duration_minutes": {"type": "integer", "default": 30},
                    "attendee": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["client_id", "title", "scheduled_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify.dashboard",
            "description": "Send a note to the firm dashboard chat thread for this caller.",
            "parameters": {
                "type": "object",
                "properties": {
                    "body": {"type": "string"},
                },
                "required": ["body"],
            },
        },
    },
]


class ToolRegistry:
    def __init__(
        self,
        *,
        telephony_db_path: Path,
        context_db_path: Path,
        calendar_db_path: Path,
    ) -> None:
        self.telephony_db_path = telephony_db_path
        self.context_db_path = context_db_path
        self.calendar_db_path = calendar_db_path
        self._intake_ids: dict[str, str] = {}
        self._client_ids: dict[str, str] = {}
        self._case_ids: dict[str, str] = {}

    def execute(
        self,
        *,
        call_sid: str,
        tool_name: str,
        args: dict,
        enforce_consent: bool = True,
    ) -> ToolResult:
        if enforce_consent:
            required = REQUIRED_CONSENTS.get(tool_name, set())
            for consent_type in required:
                if not telephony_db.has_consent(self.telephony_db_path, call_sid, consent_type):
                    return ToolResult(
                        ok=False,
                        data={},
                        error=f"Missing required consent: {consent_type}",
                    )

        handlers = {
            "record_consent": self._record_consent,
            "intake.start": self._intake_start,
            "intake.update": self._intake_update,
            "case.qualify": self._case_qualify,
            "case.create": self._case_create,
            "case.decline": self._case_decline,
            "calendar.create_event": self._calendar_create_event,
            "notify.dashboard": self._notify_dashboard,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return ToolResult(ok=False, data={}, error=f"Unknown tool: {tool_name}")
        try:
            return handler(call_sid, args)
        except Exception as exc:
            return ToolResult(ok=False, data={}, error=str(exc))

    def _record_consent(self, call_sid: str, args: dict) -> ToolResult:
        consent_type = args.get("consent_type")
        granted = bool(args.get("granted"))
        if consent_type not in {"ai_disclosure", "recording", "data_storage"}:
            return ToolResult(ok=False, data={}, error="Invalid consent_type")
        telephony_db.record_consent(
            self.telephony_db_path,
            call_session_id=call_sid,
            consent_type=consent_type,
            granted=granted,
        )
        return ToolResult(ok=True, data={"consent_type": consent_type, "granted": granted})

    def _intake_start(self, call_sid: str, args: dict) -> ToolResult:
        caller_name = (args.get("caller_name") or "").strip()
        if not caller_name:
            return ToolResult(ok=False, data={}, error="caller_name is required")
        phone = args.get("phone")
        session = telephony_db.get_call_session(self.telephony_db_path, call_sid)
        if not phone and session:
            phone = session.phone
        fields = {
            "caller_name": caller_name,
            "phone": phone,
            "incident_date": args.get("incident_date"),
            "incident_location": args.get("incident_location"),
            "injury_summary": args.get("injury_summary"),
            "incident_type": args.get("incident_type"),
        }
        intake_id = telephony_db.create_intake_record(
            self.telephony_db_path,
            call_session_id=call_sid,
            fields=fields,
        )
        self._intake_ids[call_sid] = intake_id
        telephony_db.update_call_phase(self.telephony_db_path, call_sid, "INTAKE")
        return ToolResult(ok=True, data={"intake_id": intake_id, "fields": fields})

    def _intake_update(self, call_sid: str, args: dict) -> ToolResult:
        intake_id = self._intake_ids.get(call_sid)
        if not intake_id:
            existing = telephony_db.get_intake_for_call(self.telephony_db_path, call_sid)
            if not existing:
                return ToolResult(ok=False, data={}, error="No intake started for this call")
            intake_id = existing["id"]
            self._intake_ids[call_sid] = intake_id
        telephony_db.update_intake_record(self.telephony_db_path, intake_id, args)
        return ToolResult(ok=True, data={"intake_id": intake_id, "updated": args})

    def _case_qualify(self, call_sid: str, args: dict) -> ToolResult:
        jurisdiction = (args.get("jurisdiction") or "CA").upper()
        injury_present = bool(args.get("injury_present"))
        prior_attorney = bool(args.get("prior_attorney"))
        at_fault_clear = args.get("at_fault_clear")

        qualified = injury_present and not prior_attorney
        reasons: list[str] = []
        if not injury_present:
            reasons.append("No reported injury")
        if prior_attorney:
            reasons.append("Caller already has another attorney")
        if jurisdiction not in {"CA", "CALIFORNIA"}:
            reasons.append(f"Jurisdiction {jurisdiction} may be outside firm coverage")

        telephony_db.update_call_phase(self.telephony_db_path, call_sid, "QUALIFICATION")
        intake_id = self._intake_ids.get(call_sid)
        if intake_id:
            telephony_db.update_intake_record(
                self.telephony_db_path,
                intake_id,
                {"qualified": int(qualified), "jurisdiction": jurisdiction, "at_fault_clear": at_fault_clear},
            )
        return ToolResult(
            ok=True,
            data={
                "qualified": qualified,
                "reasons": reasons,
                "next_step": "calendar.create_event" if qualified else "case.decline",
            },
        )

    def _case_create(self, call_sid: str, args: dict) -> ToolResult:
        caller_name = args.get("caller_name", "Unknown Caller")
        phone = args.get("phone")
        session = telephony_db.get_call_session(self.telephony_db_path, call_sid)
        if not phone and session:
            phone = session.phone
        client_id = f"client-{uuid4()}"
        case_id = f"case-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid4().hex[:6]}"
        self.context_db_path.parent.mkdir(parents=True, exist_ok=True)
        init_context_db(self.context_db_path)
        recording = telephony_db.has_consent(self.telephony_db_path, call_sid, "recording")
        ai_disclosure = telephony_db.has_consent(self.telephony_db_path, call_sid, "ai_disclosure")
        data_storage = telephony_db.has_consent(self.telephony_db_path, call_sid, "data_storage")
        with connect_context(self.context_db_path) as conn:
            conn.execute(
                """
                INSERT INTO clients (id, name, phone, email, consent_recording, consent_ai_disclosure, consent_data_storage)
                VALUES (?, ?, ?, NULL, ?, ?, ?)
                """,
                (client_id, caller_name, phone, int(recording), int(ai_disclosure), int(data_storage)),
            )
            conn.execute(
                """
                INSERT INTO cases
                  (id, client_id, case_type, incident_date, incident_location, at_fault_party,
                   injuries, treatment_received, witnesses, status, statute_of_limitations_date, state_jurisdiction)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', 'intake', ?, ?)
                """,
                (
                    case_id,
                    client_id,
                    args.get("case_type", "personal_injury"),
                    args.get("incident_date", datetime.now(UTC).date().isoformat()),
                    args.get("incident_location"),
                    "Under investigation",
                    args.get("injuries"),
                    args.get("treatment_received"),
                    (datetime.now(UTC).date() + timedelta(days=730)).isoformat(),
                    "CA",
                ),
            )
        self._client_ids[call_sid] = client_id
        self._case_ids[call_sid] = case_id
        telephony_db.update_call_phase(self.telephony_db_path, call_sid, "CLOSE")
        return ToolResult(ok=True, data={"client_id": client_id, "case_id": case_id})

    def _case_decline(self, call_sid: str, args: dict) -> ToolResult:
        reason = args.get("reason", "Unable to assist")
        intake_id = self._intake_ids.get(call_sid)
        if intake_id:
            telephony_db.update_intake_record(
                self.telephony_db_path,
                intake_id,
                {"qualified": 0, "decline_reason": reason},
            )
        telephony_db.update_call_phase(self.telephony_db_path, call_sid, "CLOSE")
        return ToolResult(
            ok=True,
            data={"declined": True, "reason": reason, "referral_note": args.get("referral_note")},
        )

    def _calendar_create_event(self, call_sid: str, args: dict) -> ToolResult:
        client_id = args.get("client_id") or self._client_ids.get(call_sid)
        if not client_id:
            return ToolResult(ok=False, data={}, error="client_id is required")
        result = book_calendar(
            self.calendar_db_path,
            client_id=client_id,
            event_type="consult",
            title=args.get("title", "Initial consultation"),
            scheduled_at=args["scheduled_at"],
            duration_minutes=int(args.get("duration_minutes", 30)),
            case_id=args.get("case_id") or self._case_ids.get(call_sid),
            attendee=args.get("attendee"),
            notes=args.get("notes"),
        )
        telephony_db.update_call_phase(self.telephony_db_path, call_sid, "BOOKING")
        return ToolResult(ok=True, data=result)

    def _notify_dashboard(self, call_sid: str, args: dict) -> ToolResult:
        body = args.get("body", "")
        telephony_db.add_message(
            self.telephony_db_path,
            body=body,
            direction="outbound",
            channel="chat",
            call_session_id=call_sid,
        )
        return ToolResult(ok=True, data={"sent": True, "body": body})
