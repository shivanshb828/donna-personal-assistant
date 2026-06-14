from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import json
import sqlite3
from uuid import uuid4


@dataclass(frozen=True)
class CallSession:
    id: str
    phone: str | None
    agent_mode: str
    phase: str
    started_at: str
    ended_at: str | None
    duration_seconds: int | None
    outcome: str | None
    transcript: str | None
    is_returning: bool


@dataclass(frozen=True)
class Lead:
    id: str
    name: str
    phone: str
    source: str | None
    incident_summary: str | None
    status: str
    created_at: str


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_telephony_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS call_sessions (
              id TEXT PRIMARY KEY,
              phone TEXT,
              agent_mode TEXT NOT NULL DEFAULT 'inbound_intake',
              phase TEXT NOT NULL DEFAULT 'DISCLOSURE',
              started_at TEXT NOT NULL,
              ended_at TEXT,
              duration_seconds INTEGER,
              outcome TEXT,
              transcript TEXT,
              is_returning INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS consents (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              call_session_id TEXT NOT NULL REFERENCES call_sessions(id) ON DELETE CASCADE,
              consent_type TEXT NOT NULL,
              granted INTEGER NOT NULL,
              recorded_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS intake_records (
              id TEXT PRIMARY KEY,
              call_session_id TEXT REFERENCES call_sessions(id) ON DELETE SET NULL,
              client_id TEXT,
              incident_date TEXT,
              incident_location TEXT,
              injury_summary TEXT,
              fault_party TEXT,
              treatment_status TEXT,
              insurance_info TEXT,
              qualified INTEGER,
              decline_reason TEXT,
              raw_fields TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
              id TEXT PRIMARY KEY,
              client_id TEXT,
              case_id TEXT,
              call_session_id TEXT,
              direction TEXT NOT NULL,
              channel TEXT NOT NULL,
              body TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS leads (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              phone TEXT NOT NULL UNIQUE,
              source TEXT,
              incident_summary TEXT,
              status TEXT NOT NULL DEFAULT 'new',
              created_at TEXT NOT NULL
            );
            """
        )


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit())
    if not digits:
        return None
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if phone.startswith("+"):
        return phone
    return f"+{digits}"


def create_call_session(
    db_path: Path,
    *,
    call_sid: str,
    phone: str | None,
    agent_mode: str = "inbound_intake",
    is_returning: bool = False,
) -> CallSession:
    init_telephony_db(db_path)
    started_at = datetime.now(UTC).isoformat(timespec="seconds")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO call_sessions (id, phone, agent_mode, phase, started_at, is_returning)
            VALUES (?, ?, ?, 'DISCLOSURE', ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              phone = excluded.phone,
              agent_mode = excluded.agent_mode,
              started_at = excluded.started_at,
              is_returning = excluded.is_returning
            """,
            (call_sid, normalize_phone(phone), agent_mode, started_at, int(is_returning)),
        )
    return CallSession(
        id=call_sid,
        phone=normalize_phone(phone),
        agent_mode=agent_mode,
        phase="DISCLOSURE",
        started_at=started_at,
        ended_at=None,
        duration_seconds=None,
        outcome=None,
        transcript=None,
        is_returning=is_returning,
    )


def get_call_session(db_path: Path, call_sid: str) -> CallSession | None:
    init_telephony_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM call_sessions WHERE id = ?", (call_sid,)).fetchone()
    if not row:
        return None
    return _row_to_session(row)


def update_call_phase(db_path: Path, call_sid: str, phase: str) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE call_sessions SET phase = ? WHERE id = ?", (phase, call_sid))


def complete_call_session(
    db_path: Path,
    *,
    call_sid: str,
    duration_seconds: int,
    outcome: str | None = None,
    transcript: str | None = None,
) -> None:
    ended_at = datetime.now(UTC).isoformat(timespec="seconds")
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE call_sessions
            SET ended_at = ?, duration_seconds = ?, outcome = ?, transcript = ?
            WHERE id = ?
            """,
            (ended_at, duration_seconds, outcome, transcript, call_sid),
        )


def lookup_prior_session_by_phone(db_path: Path, phone: str) -> CallSession | None:
    init_telephony_db(db_path)
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM call_sessions
            WHERE phone = ? AND ended_at IS NOT NULL
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (normalized,),
        ).fetchone()
    return _row_to_session(row) if row else None


def record_consent(
    db_path: Path,
    *,
    call_session_id: str,
    consent_type: str,
    granted: bool,
) -> None:
    init_telephony_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO consents (call_session_id, consent_type, granted, recorded_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                call_session_id,
                consent_type,
                int(granted),
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )


def has_consent(db_path: Path, call_session_id: str, consent_type: str) -> bool:
    init_telephony_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT granted FROM consents
            WHERE call_session_id = ? AND consent_type = ?
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (call_session_id, consent_type),
        ).fetchone()
    return bool(row and row["granted"])


def create_intake_record(
    db_path: Path,
    *,
    call_session_id: str | None = None,
    client_id: str | None = None,
    fields: dict | None = None,
) -> str:
    init_telephony_db(db_path)
    intake_id = f"intake-{uuid4()}"
    fields = fields or {}
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO intake_records
              (id, call_session_id, client_id, incident_date, incident_location,
               injury_summary, fault_party, treatment_status, insurance_info,
               qualified, decline_reason, raw_fields, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                intake_id,
                call_session_id,
                client_id,
                fields.get("incident_date"),
                fields.get("incident_location"),
                fields.get("injury_summary"),
                fields.get("fault_party"),
                fields.get("treatment_status"),
                fields.get("insurance_info"),
                fields.get("qualified"),
                fields.get("decline_reason"),
                json.dumps(fields),
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
    return intake_id


def update_intake_record(db_path: Path, intake_id: str, fields: dict) -> None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT raw_fields FROM intake_records WHERE id = ?", (intake_id,)).fetchone()
        merged = {}
        if row and row["raw_fields"]:
            merged.update(json.loads(row["raw_fields"]))
        merged.update(fields)
        conn.execute(
            """
            UPDATE intake_records
            SET incident_date = COALESCE(?, incident_date),
                incident_location = COALESCE(?, incident_location),
                injury_summary = COALESCE(?, injury_summary),
                fault_party = COALESCE(?, fault_party),
                treatment_status = COALESCE(?, treatment_status),
                insurance_info = COALESCE(?, insurance_info),
                qualified = COALESCE(?, qualified),
                decline_reason = COALESCE(?, decline_reason),
                raw_fields = ?
            WHERE id = ?
            """,
            (
                merged.get("incident_date"),
                merged.get("incident_location"),
                merged.get("injury_summary"),
                merged.get("fault_party"),
                merged.get("treatment_status"),
                merged.get("insurance_info"),
                merged.get("qualified"),
                merged.get("decline_reason"),
                json.dumps(merged),
                intake_id,
            ),
        )


def get_intake_for_call(db_path: Path, call_session_id: str) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM intake_records WHERE call_session_id = ? ORDER BY created_at DESC LIMIT 1",
            (call_session_id,),
        ).fetchone()
    return dict(row) if row else None


def add_message(
    db_path: Path,
    *,
    body: str,
    direction: str,
    channel: str,
    client_id: str | None = None,
    case_id: str | None = None,
    call_session_id: str | None = None,
) -> str:
    init_telephony_db(db_path)
    message_id = f"msg-{uuid4()}"
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages (id, client_id, case_id, call_session_id, direction, channel, body, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                client_id,
                case_id,
                call_session_id,
                direction,
                channel,
                body,
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
    return message_id


def list_messages(
    db_path: Path,
    *,
    client_id: str | None = None,
    call_session_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    init_telephony_db(db_path)
    clauses: list[str] = []
    values: list[str | int] = []
    if client_id:
        clauses.append("client_id = ?")
        values.append(client_id)
    if call_session_id:
        clauses.append("call_session_id = ?")
        values.append(call_session_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    values.append(limit)
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM messages {where} ORDER BY created_at ASC LIMIT ?",
            values,
        ).fetchall()
    return [dict(row) for row in rows]


def create_lead(
    db_path: Path,
    *,
    name: str,
    phone: str,
    source: str | None = None,
    incident_summary: str | None = None,
) -> Lead:
    init_telephony_db(db_path)
    lead_id = f"lead-{uuid4()}"
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    normalized = normalize_phone(phone) or phone
    with connect(db_path) as conn:
        existing = conn.execute("SELECT * FROM leads WHERE phone = ?", (normalized,)).fetchone()
        if existing:
            return Lead(
                id=existing["id"],
                name=existing["name"],
                phone=existing["phone"],
                source=existing["source"],
                incident_summary=existing["incident_summary"],
                status=existing["status"],
                created_at=existing["created_at"],
            )
        conn.execute(
            """
            INSERT INTO leads (id, name, phone, source, incident_summary, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'new', ?)
            """,
            (lead_id, name, normalized, source, incident_summary, created_at),
        )
    return Lead(
        id=lead_id,
        name=name,
        phone=normalize_phone(phone) or phone,
        source=source,
        incident_summary=incident_summary,
        status="new",
        created_at=created_at,
    )


def list_leads(db_path: Path, *, status: str | None = None, limit: int = 100) -> list[Lead]:
    init_telephony_db(db_path)
    with connect(db_path) as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM leads WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM leads ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [
        Lead(
            id=row["id"],
            name=row["name"],
            phone=row["phone"],
            source=row["source"],
            incident_summary=row["incident_summary"],
            status=row["status"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def update_lead_status(db_path: Path, lead_id: str, status: str) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))


def _row_to_session(row: sqlite3.Row) -> CallSession:
    return CallSession(
        id=row["id"],
        phone=row["phone"],
        agent_mode=row["agent_mode"],
        phase=row["phase"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        duration_seconds=row["duration_seconds"],
        outcome=row["outcome"],
        transcript=row["transcript"],
        is_returning=bool(row["is_returning"]),
    )
