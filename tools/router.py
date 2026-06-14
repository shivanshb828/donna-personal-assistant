"""
IPC envelope router — receives tool_call envelopes from Donna's LLM output
and dispatches to the correct tool function.

IPC envelope schema (M1's contract):
  { source, session_id, text, type }

When type == "tool_call", `text` is a JSON string:
  { "tool": "<name>", "args": { ... } }

Router returns a tool_result envelope:
  { source: "tool", session_id, text: <JSON result>, type: "tool_result" }
"""

from __future__ import annotations

import json
from typing import Any

from tools.calendar import book_calendar, check_calendar_conflicts, get_upcoming_events
from tools.case_files import (
    create_case_file, get_case_file, update_case_file,
    list_cases, search_context, log_payment, get_payment_summary, log_court_date,
)
from tools.case_law import search_case_law, analyze_case_weaknesses, profile_adverse_adjuster

# Stubs — implemented by the LLM document parser + risk scorer instance
def _stub(name: str):
    def _fn(**kwargs):
        return {"status": "not_implemented", "tool": name, "note": "Handled by doc-parser instance."}
    return _fn

_DISPATCH: dict[str, Any] = {
    # Calendar
    "check_calendar_conflicts": check_calendar_conflicts,
    "book_calendar":            book_calendar,
    "get_upcoming_events":      get_upcoming_events,
    # Case files
    "create_case_file":   create_case_file,
    "get_case_file":      get_case_file,
    "update_case_file":   update_case_file,
    "list_cases":         list_cases,
    "search_context":     search_context,
    "log_payment":        log_payment,
    "get_payment_summary": get_payment_summary,
    "log_court_date":     log_court_date,
    # Case law
    "search_case_law":         search_case_law,
    "analyze_case_weaknesses": analyze_case_weaknesses,
    "profile_adverse_adjuster": profile_adverse_adjuster,
    # Doc parser / risk scorer stubs (other instance)
    "summarize_document":          _stub("summarize_document"),
    "check_narrative_consistency": _stub("check_narrative_consistency"),
    "score_litigation_risk":       _stub("score_litigation_risk"),
}


def handle_envelope(envelope: dict) -> dict:
    """
    Accepts an IPC envelope. If type == "tool_call", dispatches and returns
    a tool_result envelope. Otherwise returns the envelope unchanged.
    """
    if envelope.get("type") != "tool_call":
        return envelope

    session_id = envelope.get("session_id", "")
    try:
        payload = json.loads(envelope["text"])
        tool_name = payload["tool"]
        args = payload.get("args", {})
    except (KeyError, json.JSONDecodeError) as exc:
        return _error_envelope(session_id, str(exc))

    fn = _DISPATCH.get(tool_name)
    if fn is None:
        return _error_envelope(session_id, f"Unknown tool: {tool_name}")

    try:
        result = fn(**args)
    except Exception as exc:
        return _error_envelope(session_id, f"Tool error ({tool_name}): {exc}")

    return {
        "source": "tool",
        "session_id": session_id,
        "text": json.dumps(result),
        "type": "tool_result",
    }


def _error_envelope(session_id: str, message: str) -> dict:
    return {
        "source": "tool",
        "session_id": session_id,
        "text": json.dumps({"status": "error", "message": message}),
        "type": "tool_result",
    }
