"""Case status and statute of limitations tools."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from knowledge.db import get_case_status, check_sol_deadline, get_urgent_deadlines


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_case_status",
            "description": "Get the current status of a client's case(s). Use when a client asks about their case.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "Client ID"},
                },
                "required": ["client_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_sol_deadline",
            "description": "Check statute of limitations deadline. Use when discussing timing urgency of a case.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_date": {"type": "string", "description": "Date of incident (YYYY-MM-DD)"},
                    "state": {"type": "string", "description": "State jurisdiction (2-letter code)", "default": "CA"},
                },
                "required": ["incident_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_deadlines",
            "description": "Get all cases with upcoming statute of limitations deadlines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {"type": "integer", "description": "Days to look ahead", "default": 90},
                },
            },
        },
    },
]


def get_status(client_id: str) -> dict:
    cases = get_case_status(client_id)
    if not cases:
        return {"status": "no_cases", "message": "No cases found for this client."}

    latest = cases[0]
    sol_info = check_sol_deadline(latest["incident_date"], latest.get("state_jurisdiction", "CA"))

    return {
        "client_name": latest.get("client_name", ""),
        "case_id": latest["id"],
        "case_type": latest["case_type"],
        "status": latest["status"],
        "incident_date": latest["incident_date"],
        "sol_deadline": sol_info["deadline_date"],
        "sol_days_remaining": sol_info["days_remaining"],
        "sol_is_urgent": sol_info["is_urgent"],
        "total_cases": len(cases),
    }


def check_deadline(incident_date: str, state: str = "CA") -> dict:
    result = check_sol_deadline(incident_date, state)

    if result["is_urgent"]:
        result["message"] = (
            f"URGENT: Only {result['days_remaining']} days remaining until the statute of limitations "
            f"expires on {result['deadline_date']}. The attorney should be notified immediately."
        )
    else:
        result["message"] = (
            f"The statute of limitations deadline is {result['deadline_date']}, "
            f"which is {result['days_remaining']} days from now."
        )

    return result


def get_deadlines(days_ahead: int = 90) -> dict:
    urgent = get_urgent_deadlines(days_ahead)
    return {
        "count": len(urgent),
        "cases": urgent,
        "message": f"{len(urgent)} case(s) with deadlines in the next {days_ahead} days.",
    }
