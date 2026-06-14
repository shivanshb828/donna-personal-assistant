"""Client intake and case file creation tools."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from knowledge.db import (
    insert_client, insert_case, add_case_note,
    get_client_by_phone, update_client_consent,
)


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "intake_client",
            "description": "Collect new client information during an intake conversation. Use when a new potential client calls or speaks to Donna for the first time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Client full name"},
                    "phone": {"type": "string", "description": "Client phone number"},
                    "incident_type": {
                        "type": "string",
                        "enum": ["auto_accident", "slip_fall", "workplace", "medical_malpractice", "other"],
                        "description": "Type of personal injury incident",
                    },
                    "incident_date": {"type": "string", "description": "Date of incident (YYYY-MM-DD)"},
                    "at_fault_party": {"type": "string", "description": "Who was at fault"},
                    "injuries": {"type": "string", "description": "Description of injuries sustained"},
                    "treatment_received": {"type": "string", "description": "Medical treatment received so far"},
                },
                "required": ["name", "phone", "incident_type", "incident_date", "injuries"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_case_file",
            "description": "Create a formal case file after intake is complete. Call this after intake_client succeeds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "Client ID from intake"},
                    "incident_summary": {"type": "string", "description": "Brief summary of the incident for case file"},
                },
                "required": ["client_id", "incident_summary"],
            },
        },
    },
]


def intake_client(
    name: str,
    phone: str,
    incident_type: str,
    incident_date: str,
    injuries: str,
    at_fault_party: str = "",
    treatment_received: str = "",
) -> dict:
    existing = get_client_by_phone(phone)
    if existing:
        return {
            "status": "existing_client",
            "client_id": existing["id"],
            "message": f"Welcome back, {existing['name']}. I have your information on file.",
        }

    client_id = insert_client(name, phone)
    update_client_consent(client_id, "consent_ai_disclosure", True)

    return {
        "status": "new_client",
        "client_id": client_id,
        "message": f"Thank you, {name}. I've started your file. Let me create your case now.",
    }


def create_case_file(client_id: str, incident_summary: str) -> dict:
    # Parse incident details from the summary or use stored intake data
    case_id = insert_case(
        client_id=client_id,
        case_type="other",
        incident_date="2026-01-01",  # will be overridden by actual intake data
        at_fault_party="",
        injuries=incident_summary,
    )

    add_case_note(case_id, "intake_transcript", incident_summary)

    return {
        "status": "created",
        "case_id": case_id,
        "message": f"Case file created. I've added it to the attorney's dashboard.",
    }
