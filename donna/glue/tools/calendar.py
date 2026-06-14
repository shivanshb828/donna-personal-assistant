from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from uuid import uuid4


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    title: str
    start: str
    end: str
    attendee: str | None
    case_id: str | None
    notes: str | None


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "book_calendar",
            "description": "Schedule a local calendar event for a client or case.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string"},
                    "case_id": {"type": "string"},
                    "event_type": {
                        "type": "string",
                        "enum": ["consult", "deposition", "follow_up", "court_date", "filing_deadline"],
                    },
                    "title": {"type": "string"},
                    "scheduled_at": {"type": "string", "description": "ISO-8601 datetime"},
                    "duration_minutes": {"type": "integer", "default": 60},
                    "attendee": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["client_id", "event_type", "title", "scheduled_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_events",
            "description": "Return upcoming local calendar events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "case_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
            },
        },
    },
]


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_calendar_db(db_path: Path) -> None:
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS calendar (
              id TEXT PRIMARY KEY,
              client_id TEXT,
              case_id TEXT,
              event_type TEXT NOT NULL,
              title TEXT NOT NULL,
              scheduled_at TEXT NOT NULL,
              duration_minutes INTEGER DEFAULT 60,
              attendee TEXT,
              notes TEXT,
              created_at TEXT NOT NULL
            );
            """
        )


def create_event(
    db_path: Path,
    *,
    title: str,
    start: str,
    end: str,
    event_type: str = "follow_up",
    client_id: str | None = None,
    attendee: str | None = None,
    case_id: str | None = None,
    notes: str | None = None,
) -> CalendarEvent:
    start_dt = _parse_iso_datetime("start", start)
    end_dt = _parse_iso_datetime("end", end)
    duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
    if duration_minutes <= 0:
        raise ValueError("end must be after start")
    event = CalendarEvent(
        id=f"evt-{uuid4()}",
        title=title,
        start=start,
        end=end,
        attendee=attendee,
        case_id=case_id,
        notes=notes,
    )
    init_calendar_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO calendar
              (id, client_id, case_id, event_type, title, scheduled_at, duration_minutes, attendee, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                client_id,
                event.case_id,
                event_type,
                event.title,
                event.start,
                duration_minutes,
                event.attendee,
                event.notes,
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
    return event


def book_calendar(
    db_path: Path,
    *,
    client_id: str,
    event_type: str,
    title: str,
    scheduled_at: str,
    duration_minutes: int = 60,
    case_id: str | None = None,
    attendee: str | None = None,
    notes: str | None = None,
) -> dict:
    start_dt = _parse_iso_datetime("scheduled_at", scheduled_at)
    end_dt = start_dt.timestamp() + duration_minutes * 60
    end = datetime.fromtimestamp(end_dt, tz=start_dt.tzinfo).isoformat()
    event = create_event(
        db_path,
        title=title,
        start=scheduled_at,
        end=end,
        event_type=event_type,
        client_id=client_id,
        attendee=attendee,
        case_id=case_id,
        notes=notes,
    )
    return {
        "status": "booked",
        "event_id": event.id,
        "event": asdict(event),
        "formatted_confirmation": f"Done. {title} scheduled for {scheduled_at}.",
    }


def get_upcoming_events(
    db_path: Path,
    *,
    query: str | None = None,
    case_id: str | None = None,
    limit: int = 10,
) -> dict:
    events = search_events(db_path, query=query, case_id=case_id, limit=limit)
    return {
        "count": len(events),
        "events": [asdict(event) for event in events],
        "message": f"You have {len(events)} matching event(s).",
    }


def search_events(
    db_path: Path,
    *,
    query: str | None = None,
    case_id: str | None = None,
    limit: int = 10,
) -> list[CalendarEvent]:
    init_calendar_db(db_path)
    clauses: list[str] = []
    values: list[str | int] = []

    if query:
        clauses.append("lower(title || ' ' || coalesce(attendee, '') || ' ' || coalesce(notes, '')) LIKE ?")
        values.append(f"%{query.lower()}%")
    if case_id:
        clauses.append("case_id = ?")
        values.append(case_id)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    values.append(limit)

    with _connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT id, title, scheduled_at AS start, duration_minutes, attendee, case_id, notes
            FROM calendar
            {where}
            ORDER BY scheduled_at ASC
            LIMIT ?
            """,
            values,
        ).fetchall()

    return [_row_to_event(row) for row in rows]


def seed_calendar_db(db_path: Path) -> None:
    init_calendar_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM calendar")
    create_event(
        db_path,
        title="Maria Lopez intake follow-up",
        start="2026-06-19T10:00:00-07:00",
        end="2026-06-19T10:30:00-07:00",
        event_type="follow_up",
        client_id="client-maria-lopez",
        attendee="Maria Lopez",
        case_id="case-2026-001",
        notes="Ask about medical evaluation and insurance claim number.",
    )


def _row_to_event(row: sqlite3.Row) -> CalendarEvent:
    start_dt = _parse_iso_datetime("scheduled_at", row["start"])
    end = datetime.fromtimestamp(
        start_dt.timestamp() + row["duration_minutes"] * 60,
        tz=start_dt.tzinfo,
    ).isoformat()
    return CalendarEvent(
        id=row["id"],
        title=row["title"],
        start=row["start"],
        end=end,
        attendee=row["attendee"],
        case_id=row["case_id"],
        notes=row["notes"],
    )


def _parse_iso_datetime(field: str, value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 datetime") from exc
