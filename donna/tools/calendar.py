"""Calendar management tools for Donna."""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import parser as dateparser

sys.path.insert(0, str(Path(__file__).parent.parent))
from knowledge.db import book_calendar_event, get_upcoming_events


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "book_calendar",
            "description": "Schedule a calendar event for a client — consultations, depositions, follow-ups, court dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "Client ID"},
                    "case_id": {"type": "string", "description": "Case ID (if applicable)"},
                    "event_type": {
                        "type": "string",
                        "enum": ["consult", "deposition", "follow_up", "court_date", "filing_deadline"],
                        "description": "Type of calendar event",
                    },
                    "title": {"type": "string", "description": "Event title"},
                    "datetime_str": {"type": "string", "description": "When to schedule (natural language OK: 'next Tuesday at 2pm')"},
                    "duration_minutes": {"type": "integer", "description": "Duration in minutes", "default": 60},
                    "notes": {"type": "string", "description": "Additional notes"},
                },
                "required": ["client_id", "event_type", "title", "datetime_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_events",
            "description": "Get upcoming calendar events for the next N days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {"type": "integer", "description": "Number of days to look ahead", "default": 7},
                },
            },
        },
    },
]


def book_calendar(
    client_id: str,
    event_type: str,
    title: str,
    datetime_str: str,
    case_id: str = "",
    duration_minutes: int = 60,
    notes: str = "",
) -> dict:
    try:
        scheduled = dateparser.parse(datetime_str)
        if scheduled is None:
            return {"status": "error", "message": f"Could not understand the date: {datetime_str}"}
    except Exception:
        return {"status": "error", "message": f"Could not parse date: {datetime_str}"}

    scheduled_iso = scheduled.strftime("%Y-%m-%dT%H:%M:%S")
    friendly_date = scheduled.strftime("%A, %B %d at %I:%M %p")

    event_id = book_calendar_event(
        client_id=client_id,
        case_id=case_id,
        event_type=event_type,
        title=title,
        scheduled_at=scheduled_iso,
        duration_minutes=duration_minutes,
        notes=notes,
    )

    return {
        "status": "booked",
        "event_id": event_id,
        "formatted_confirmation": f"Done. {title} scheduled for {friendly_date}.",
    }


def get_upcoming(days_ahead: int = 7) -> dict:
    events = get_upcoming_events(days_ahead)
    return {
        "count": len(events),
        "events": events,
        "message": f"You have {len(events)} events in the next {days_ahead} days.",
    }
