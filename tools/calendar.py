"""Calendar tools — book_calendar, check_calendar_conflicts, get_upcoming_events."""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

import psycopg  # psycopg3 — PGLite exposes a Postgres wire protocol

GBRAIN_DSN = os.environ.get("GBRAIN_DSN", "postgresql://donna@localhost:7700/donna")

DEFAULT_BUFFER_MINUTES = 15


def _conn():
    return psycopg.connect(GBRAIN_DSN)


# ── check_calendar_conflicts ──────────────────────────────────────────────────

def check_calendar_conflicts(
    *,
    proposed_start: str,
    proposed_end: str,
    buffer_minutes: int = DEFAULT_BUFFER_MINUTES,
    travel_note: str | None = None,
) -> dict[str, Any]:
    """
    Before booking, check for conflicts or back-to-back events within buffer_minutes.
    Always call this before book_calendar.
    """
    start = datetime.fromisoformat(proposed_start).astimezone(timezone.utc)
    end = datetime.fromisoformat(proposed_end).astimezone(timezone.utc)
    buffer = timedelta(minutes=buffer_minutes)

    window_start = start - buffer
    window_end = end + buffer

    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, scheduled_at,
                   scheduled_at + (duration_minutes * interval '1 minute') AS ends_at,
                   attendee, lawyer_name
            FROM calendar_events
            WHERE scheduled_at < %s
              AND scheduled_at + (duration_minutes * interval '1 minute') > %s
            ORDER BY scheduled_at
            """,
            (window_end, window_start),
        ).fetchall()

    conflicts = []
    warnings = []

    for row in rows:
        ev_start = row[2].astimezone(timezone.utc)
        ev_end = row[3].astimezone(timezone.utc)

        # Hard conflict — actual time overlap
        if ev_start < end and ev_end > start:
            conflicts.append({
                "event_id": row[0],
                "title": row[1],
                "starts_at": ev_start.isoformat(),
                "ends_at": ev_end.isoformat(),
                "type": "overlap",
            })
        else:
            # Soft warning — within buffer window
            gap_minutes = int(
                abs((start - ev_end).total_seconds() / 60)
                if ev_end <= start
                else abs((ev_start - end).total_seconds() / 60)
            )
            msg = f"'{row[1]}' is only {gap_minutes} min away."
            if travel_note:
                msg += f" Note: {travel_note}"
            warnings.append({
                "event_id": row[0],
                "title": row[1],
                "gap_minutes": gap_minutes,
                "message": msg,
            })

    return {
        "safe_to_book": len(conflicts) == 0,
        "conflicts": conflicts,
        "warnings": warnings,
        "checked_window": {
            "from": window_start.isoformat(),
            "to": window_end.isoformat(),
            "buffer_minutes": buffer_minutes,
        },
    }


# ── book_calendar ─────────────────────────────────────────────────────────────

def book_calendar(
    *,
    client_id: str,
    event_type: str,
    title: str,
    scheduled_at: str,
    duration_minutes: int = 60,
    case_id: str | None = None,
    attendee: str | None = None,
    lawyer_name: str | None = None,
    location: str | None = None,
    notes: str | None = None,
    price: float | None = None,
) -> dict[str, Any]:
    """Book a calendar event. Always call check_calendar_conflicts first."""
    start = datetime.fromisoformat(scheduled_at).astimezone(timezone.utc)
    end = start + timedelta(minutes=duration_minutes)

    # Auto conflict check — hard block if overlap exists
    conflict_check = check_calendar_conflicts(
        proposed_start=start.isoformat(),
        proposed_end=end.isoformat(),
    )
    if not conflict_check["safe_to_book"]:
        return {
            "status": "conflict",
            "message": "Cannot book — time conflict with existing event.",
            "conflicts": conflict_check["conflicts"],
        }

    event_id = f"evt-{uuid4()}"

    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO calendar_events
              (id, case_id, client_id, lawyer_name, event_type, title,
               scheduled_at, duration_minutes, attendee, location, notes, price)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (event_id, case_id, client_id, lawyer_name, event_type, title,
             start, duration_minutes, attendee, location, notes, price),
        )

    confirmation = f"Done. {title} scheduled for {start.strftime('%A, %B %-d at %-I:%M %p')}."
    if conflict_check["warnings"]:
        gaps = ", ".join(w["message"] for w in conflict_check["warnings"])
        confirmation += f" Note: {gaps}"

    return {
        "status": "booked",
        "event_id": event_id,
        "title": title,
        "scheduled_at": start.isoformat(),
        "ends_at": end.isoformat(),
        "attendee": attendee,
        "warnings": conflict_check["warnings"],
        "formatted_confirmation": confirmation,
    }


# ── get_upcoming_events ───────────────────────────────────────────────────────

def get_upcoming_events(
    *,
    query: str | None = None,
    case_id: str | None = None,
    client_id: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    clauses = ["scheduled_at >= NOW()"]
    values: list[Any] = []

    if query:
        clauses.append(
            "to_tsvector('english', title || ' ' || coalesce(notes,'') || ' ' || coalesce(attendee,'')) "
            "@@ plainto_tsquery('english', %s)"
        )
        values.append(query)
    if case_id:
        clauses.append("case_id = %s")
        values.append(case_id)
    if client_id:
        clauses.append("client_id = %s")
        values.append(client_id)

    values.append(limit)

    with _conn() as conn:
        rows = conn.execute(
            f"""
            SELECT id, title, event_type, scheduled_at,
                   duration_minutes, attendee, lawyer_name, location, notes, price, case_id
            FROM calendar_events
            WHERE {' AND '.join(clauses)}
            ORDER BY scheduled_at ASC
            LIMIT %s
            """,
            values,
        ).fetchall()

    events = [
        {
            "event_id": r[0], "title": r[1], "event_type": r[2],
            "scheduled_at": r[3].isoformat(), "duration_minutes": r[4],
            "attendee": r[5], "lawyer_name": r[6], "location": r[7],
            "notes": r[8], "price": float(r[9]) if r[9] else None, "case_id": r[10],
        }
        for r in rows
    ]

    return {
        "count": len(events),
        "events": events,
        "message": f"You have {len(events)} upcoming event(s).",
    }


# ── Tool definitions for OpenClaw/GBrain MCP ─────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_calendar_conflicts",
            "description": "Check for conflicts or tight back-to-back events before booking. Always call before book_calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "proposed_start": {"type": "string", "description": "ISO-8601 start datetime"},
                    "proposed_end":   {"type": "string", "description": "ISO-8601 end datetime"},
                    "buffer_minutes": {"type": "integer", "default": 15},
                    "travel_note":    {"type": "string"},
                },
                "required": ["proposed_start", "proposed_end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_calendar",
            "description": "Book a calendar event. Internally re-checks conflicts and blocks on hard overlap.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id":        {"type": "string"},
                    "event_type":       {"type": "string", "enum": ["consult","deposition","follow_up","court_date","filing_deadline","other"]},
                    "title":            {"type": "string"},
                    "scheduled_at":     {"type": "string", "description": "ISO-8601 datetime"},
                    "duration_minutes": {"type": "integer", "default": 60},
                    "case_id":          {"type": "string"},
                    "attendee":         {"type": "string"},
                    "lawyer_name":      {"type": "string"},
                    "location":         {"type": "string"},
                    "notes":            {"type": "string"},
                    "price":            {"type": "number"},
                },
                "required": ["client_id", "event_type", "title", "scheduled_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_events",
            "description": "List upcoming calendar events, optionally filtered by case or client.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":     {"type": "string"},
                    "case_id":   {"type": "string"},
                    "client_id": {"type": "string"},
                    "limit":     {"type": "integer", "default": 10},
                },
            },
        },
    },
]
