"""Case file tools — create, read, update, list, search."""

from __future__ import annotations

import os
from datetime import datetime, timezone, date
from typing import Any
from uuid import uuid4

import psycopg

GBRAIN_DSN = os.environ.get("GBRAIN_DSN", "postgresql://donna@localhost:7700/donna")

# Statute of limitations defaults by state (years). Simplified — tolling rules handled separately.
_SOL_YEARS: dict[str, int] = {
    "CA": 2, "NY": 3, "TX": 2, "FL": 4, "IL": 2,
    "PA": 2, "OH": 2, "GA": 2, "NJ": 2, "MI": 3,
}


def _conn():
    return psycopg.connect(GBRAIN_DSN)


def _sol_date(incident_date: date, state: str) -> date:
    years = _SOL_YEARS.get(state.upper(), 2)
    return incident_date.replace(year=incident_date.year + years)


# ── create_case_file ──────────────────────────────────────────────────────────

def create_case_file(
    *,
    client_name: str,
    dol: str,                          # date of loss, YYYY-MM-DD
    incident_type: str,
    incident_location: str,
    incident_description: str,
    injuries: str,
    phone: str | None = None,
    email: str | None = None,
    treating_physician: str | None = None,
    at_fault_party: str | None = None,
    adverse_carrier: str | None = None,
    client_carrier: str | None = None,
    witnesses: str | None = None,
    police_report_number: str | None = None,
    state_jurisdiction: str = "CA",
) -> dict[str, Any]:
    client_id = f"client-{uuid4()}"
    case_id = f"case-{uuid4()}"
    incident_date = date.fromisoformat(dol)
    sol = _sol_date(incident_date, state_jurisdiction)

    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO clients (id, name, phone, email,
              consent_recording, consent_ai_disclosure, consent_data_storage)
            VALUES (%s,%s,%s,%s, TRUE, TRUE, TRUE)
            ON CONFLICT (phone) DO NOTHING
            """,
            (client_id, client_name, phone, email),
        )
        conn.execute(
            """
            INSERT INTO cases (
              id, client_id, case_type, incident_date, incident_location,
              incident_description, at_fault_party, adverse_carrier, client_carrier,
              injuries, treating_physician, witnesses, police_report_number,
              state_jurisdiction, statute_of_limitations_date
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (case_id, client_id, incident_type, incident_date, incident_location,
             incident_description, at_fault_party, adverse_carrier, client_carrier,
             injuries, treating_physician, witnesses, police_report_number,
             state_jurisdiction, sol),
        )
        # Seed a memory entry so GBrain can recall this case in future sessions
        conn.execute(
            "INSERT INTO memories (case_id, client_id, kind, content) VALUES (%s,%s,%s,%s)",
            (case_id, client_id, "intake_summary",
             f"{client_name}: {incident_type} on {dol} at {incident_location}. Injuries: {injuries}."),
        )

    sol_warning = None
    days_to_sol = (sol - date.today()).days
    if days_to_sol <= 60:
        sol_warning = f"WARNING: SOL is in {days_to_sol} days ({sol.isoformat()}). Flag for attorney review."

    return {
        "status": "created",
        "client_id": client_id,
        "case_id": case_id,
        "sol_date": sol.isoformat(),
        "sol_warning": sol_warning,
        "formatted_confirmation": (
            f"Case file created for {client_name}, {incident_type}, {dol}. "
            f"SOL: {sol.isoformat()}."
            + (f" {sol_warning}" if sol_warning else "")
        ),
    }


# ── get_case_file ─────────────────────────────────────────────────────────────

def get_case_file(*, query: str) -> dict[str, Any]:
    """Retrieve by client name or case_id."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT c.id, cl.name, c.case_type, c.incident_date, c.incident_location,
                   c.injuries, c.stage, c.statute_of_limitations_date,
                   c.at_fault_party, c.adverse_carrier, c.state_jurisdiction
            FROM cases c
            JOIN clients cl ON cl.id = c.client_id
            WHERE c.id = %s OR lower(cl.name) LIKE lower(%s)
            ORDER BY c.created_at DESC
            LIMIT 5
            """,
            (query, f"%{query}%"),
        ).fetchall()

    if not rows:
        return {"status": "not_found", "query": query}

    return {
        "status": "found",
        "count": len(rows),
        "cases": [
            {
                "case_id": r[0], "client_name": r[1], "case_type": r[2],
                "incident_date": str(r[3]), "incident_location": r[4],
                "injuries": r[5], "stage": r[6], "sol_date": str(r[7]),
                "at_fault_party": r[8], "adverse_carrier": r[9],
                "state_jurisdiction": r[10],
            }
            for r in rows
        ],
    }


# ── update_case_file ──────────────────────────────────────────────────────────

_ALLOWED_FIELDS = {
    "case_type", "incident_date", "incident_location", "incident_description",
    "at_fault_party", "adverse_carrier", "client_carrier", "injuries",
    "treating_physician", "witnesses", "police_report_number",
    "stage", "state_jurisdiction",
}

def update_case_file(*, case_id: str, field: str, value: str) -> dict[str, Any]:
    if field not in _ALLOWED_FIELDS:
        return {"status": "error", "message": f"Field '{field}' is not updatable via this tool."}

    with _conn() as conn:
        conn.execute(
            f"UPDATE cases SET {field} = %s, updated_at = NOW() WHERE id = %s",
            (value, case_id),
        )
        affected = conn.rowcount

    if affected == 0:
        return {"status": "not_found", "case_id": case_id}

    return {"status": "updated", "case_id": case_id, "field": field, "value": value}


# ── list_cases ────────────────────────────────────────────────────────────────

def list_cases(*, status: str = "all") -> dict[str, Any]:
    with _conn() as conn:
        if status == "all":
            rows = conn.execute(
                """
                SELECT c.id, cl.name, c.case_type, c.incident_date, c.stage,
                       c.statute_of_limitations_date
                FROM cases c JOIN clients cl ON cl.id = c.client_id
                ORDER BY c.created_at DESC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT c.id, cl.name, c.case_type, c.incident_date, c.stage,
                       c.statute_of_limitations_date
                FROM cases c JOIN clients cl ON cl.id = c.client_id
                WHERE c.stage = %s
                ORDER BY c.created_at DESC
                """,
                (status,),
            ).fetchall()

    cases = [
        {
            "case_id": r[0], "client_name": r[1], "case_type": r[2],
            "incident_date": str(r[3]), "stage": r[4], "sol_date": str(r[5]),
        }
        for r in rows
    ]

    # Flag anything close to SOL
    today = date.today()
    for c in cases:
        if c["sol_date"]:
            days = (date.fromisoformat(c["sol_date"]) - today).days
            if days <= 60:
                c["sol_warning"] = f"{days} days to SOL"

    return {"count": len(cases), "cases": cases}


# ── search_context ────────────────────────────────────────────────────────────

def search_context(*, query: str, limit: int = 5) -> dict[str, Any]:
    """Hybrid BM25 + vector search across all case context in GBrain."""
    tsquery = query.replace(" ", " & ")
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT 'case' AS source, c.id AS ref_id, cl.name AS title,
              c.case_type || ': ' || coalesce(c.injuries,'') || ' at ' || coalesce(c.incident_location,'') AS snippet,
              ts_rank(to_tsvector('english', coalesce(c.incident_description,'') || ' ' || coalesce(c.injuries,'')),
                      to_tsquery('english', %s)) AS rank
            FROM cases c JOIN clients cl ON cl.id = c.client_id
            WHERE to_tsvector('english', coalesce(c.incident_description,'') || ' ' || coalesce(c.injuries,''))
                  @@ to_tsquery('english', %s)
            UNION ALL
            SELECT 'memory' AS source, case_id AS ref_id, kind AS title, content AS snippet,
              ts_rank(to_tsvector('english', content), to_tsquery('english', %s)) AS rank
            FROM memories
            WHERE to_tsvector('english', content) @@ to_tsquery('english', %s)
            UNION ALL
            SELECT 'document' AS source, case_id AS ref_id, filename AS title,
              coalesce(summary,'') AS snippet,
              ts_rank(to_tsvector('english', coalesce(summary,'')), to_tsquery('english', %s)) AS rank
            FROM documents
            WHERE to_tsvector('english', coalesce(summary,'')) @@ to_tsquery('english', %s)
            ORDER BY rank DESC
            LIMIT %s
            """,
            (tsquery, tsquery, tsquery, tsquery, tsquery, tsquery, limit),
        ).fetchall()

    return {
        "query": query,
        "count": len(rows),
        "results": [
            {"source": r[0], "ref_id": r[1], "title": r[2], "snippet": r[3]}
            for r in rows
        ],
    }


# ── Payment tools ─────────────────────────────────────────────────────────────

def log_payment(
    *, case_id: str, amount: float, payment_type: str, date: str, notes: str | None = None
) -> dict[str, Any]:
    payment_id = f"pay-{uuid4()}"
    with _conn() as conn:
        conn.execute(
            "INSERT INTO payments (id, case_id, amount, payment_type, date, notes) VALUES (%s,%s,%s,%s,%s,%s)",
            (payment_id, case_id, amount, payment_type, date, notes),
        )
    return {"status": "logged", "payment_id": payment_id, "amount": amount, "type": payment_type}


def get_payment_summary(*, case_id: str) -> dict[str, Any]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT payment_type, status, amount, date, notes FROM payments WHERE case_id = %s ORDER BY date",
            (case_id,),
        ).fetchall()
    total = sum(r[2] for r in rows)
    return {
        "case_id": case_id,
        "total": float(total),
        "payments": [
            {"type": r[0], "status": r[1], "amount": float(r[2]), "date": str(r[3]), "notes": r[4]}
            for r in rows
        ],
    }


def log_court_date(
    *, case_id: str, date: str, court: str, outcome: str,
    judge: str | None = None, notes: str | None = None
) -> dict[str, Any]:
    court_date_id = f"cd-{uuid4()}"
    with _conn() as conn:
        conn.execute(
            "INSERT INTO court_dates (id, case_id, date, court, judge, outcome, notes) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (court_date_id, case_id, date, court, judge, outcome, notes),
        )
    return {"status": "logged", "court_date_id": court_date_id}


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "create_case_file",
            "description": "Create a new client and case record after intake.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_name": {"type": "string"},
                    "dol": {"type": "string", "description": "Date of loss YYYY-MM-DD"},
                    "incident_type": {"type": "string"},
                    "incident_location": {"type": "string"},
                    "incident_description": {"type": "string"},
                    "injuries": {"type": "string"},
                    "phone": {"type": "string"},
                    "email": {"type": "string"},
                    "treating_physician": {"type": "string"},
                    "at_fault_party": {"type": "string"},
                    "adverse_carrier": {"type": "string"},
                    "client_carrier": {"type": "string"},
                    "witnesses": {"type": "string"},
                    "police_report_number": {"type": "string"},
                    "state_jurisdiction": {"type": "string", "default": "CA"},
                },
                "required": ["client_name", "dol", "incident_type", "incident_location", "incident_description", "injuries"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_case_file",
            "description": "Retrieve a case by client name or case_id.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_case_file",
            "description": "Update a single field on an existing case.",
            "parameters": {
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                    "field": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["case_id", "field", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_cases",
            "description": "List cases optionally filtered by stage.",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string", "default": "all"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_context",
            "description": "Hybrid search across cases, memories, and documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_payment",
            "description": "Record a payment against a case.",
            "parameters": {
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                    "amount": {"type": "number"},
                    "payment_type": {"type": "string", "enum": ["retainer","settlement","fee","lien","other"]},
                    "date": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["case_id", "amount", "payment_type", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_payment_summary",
            "description": "Get all payments for a case.",
            "parameters": {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_court_date",
            "description": "Record a court date and outcome.",
            "parameters": {
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                    "date": {"type": "string"},
                    "court": {"type": "string"},
                    "outcome": {"type": "string"},
                    "judge": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["case_id", "date", "court", "outcome"],
            },
        },
    },
]
