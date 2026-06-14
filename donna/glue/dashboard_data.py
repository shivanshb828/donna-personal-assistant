from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from donna.glue.test_data import connect as connect_context
from donna.glue.tools.calendar import init_calendar_db, search_events


def list_cases(context_db: Path) -> list[dict]:
    if not context_db.exists():
        return []
    with connect_context(context_db) as conn:
        rows = conn.execute(
            """
            SELECT
              c.id AS case_id,
              cl.name AS client_name,
              c.case_type,
              c.incident_date,
              c.status AS stage,
              c.statute_of_limitations_date AS sol_date
            FROM cases c
            JOIN clients cl ON cl.id = c.client_id
            ORDER BY c.incident_date DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def list_calendar_events(calendar_db: Path, *, limit: int = 50) -> list[dict]:
    if not calendar_db.exists():
        return []
    init_calendar_db(calendar_db)
    with connect_context(calendar_db) as conn:
        rows = conn.execute(
            """
            SELECT id, title, event_type, scheduled_at, duration_minutes, attendee, case_id, notes
            FROM calendar
            ORDER BY scheduled_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    events: list[dict] = []
    for row in rows:
        events.append(
            {
                "event_id": row["id"],
                "title": row["title"],
                "event_type": row["event_type"] or "other",
                "scheduled_at": row["scheduled_at"],
                "duration_minutes": row["duration_minutes"] or 60,
                "attendee": row["attendee"],
                "case_id": row["case_id"],
                "notes": row["notes"],
            }
        )
    return events


def list_pending_email_drafts(drafts_dir: Path) -> list[dict]:
    root = Path(drafts_dir)
    if not root.exists():
        return []
    drafts: list[dict] = []
    for case_dir in sorted(root.iterdir()):
        if not case_dir.is_dir():
            continue
        for draft_file in sorted(case_dir.glob("*.json")):
            try:
                draft = json.loads(draft_file.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if draft.get("status") != "pending_approval":
                continue
            drafts.append(draft)
    drafts.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return drafts
