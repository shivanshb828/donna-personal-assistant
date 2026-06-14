"""SQLite database layer for Donna AI Legal Secretary."""

import sqlite3
import uuid
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

DB_PATH = os.environ.get("DONNA_DB_PATH", str(Path(__file__).parent / "donna.db"))
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Statute of limitations by state (years)
SOL_BY_STATE = {
    "CA": 2, "NY": 3, "TX": 2, "FL": 4, "IL": 2,
    "PA": 2, "OH": 2, "GA": 2, "NC": 3, "MI": 3,
    "NJ": 2, "VA": 2, "WA": 3, "AZ": 2, "MA": 3,
    "TN": 1, "IN": 2, "MO": 5, "MD": 3, "WI": 3,
    "CO": 2, "MN": 2, "SC": 3, "AL": 2, "LA": 1,
    "KY": 1, "OR": 2, "OK": 2, "CT": 2, "UT": 4,
}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database from schema.sql."""
    conn = get_conn()
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    conn.close()


# --- Clients ---

def insert_client(name: str, phone: str, email: Optional[str] = None) -> str:
    client_id = str(uuid.uuid4())[:8]
    conn = get_conn()
    conn.execute(
        "INSERT INTO clients (id, name, phone, email) VALUES (?, ?, ?, ?)",
        (client_id, name, phone, email),
    )
    conn.commit()
    conn.close()
    return client_id


def get_client_by_phone(phone: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM clients WHERE phone = ?", (phone,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_client_consent(client_id: str, consent_type: str, value: bool = True):
    conn = get_conn()
    conn.execute(
        f"UPDATE clients SET {consent_type} = ? WHERE id = ?",
        (int(value), client_id),
    )
    conn.commit()
    conn.close()


# --- Cases ---

def insert_case(
    client_id: str,
    case_type: str,
    incident_date: str,
    at_fault_party: str,
    injuries: str,
    state: str = "CA",
    incident_location: str = "",
    treatment_received: str = "",
    witnesses: str = "",
) -> str:
    case_id = str(uuid.uuid4())[:8]
    sol_years = SOL_BY_STATE.get(state, 2)
    inc_date = datetime.strptime(incident_date, "%Y-%m-%d")
    sol_date = (inc_date + timedelta(days=365 * sol_years)).strftime("%Y-%m-%d")

    conn = get_conn()
    conn.execute(
        """INSERT INTO cases
        (id, client_id, case_type, incident_date, incident_location,
         at_fault_party, injuries, treatment_received, witnesses,
         statute_of_limitations_date, state_jurisdiction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (case_id, client_id, case_type, incident_date, incident_location,
         at_fault_party, injuries, treatment_received, witnesses,
         sol_date, state),
    )
    conn.commit()
    conn.close()
    return case_id


def get_case_status(client_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT c.*, cl.name as client_name, cl.phone
        FROM cases c JOIN clients cl ON c.client_id = cl.id
        WHERE c.client_id = ? ORDER BY c.created_at DESC""",
        (client_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_cases(status: Optional[str] = None) -> list[dict]:
    conn = get_conn()
    if status:
        rows = conn.execute(
            """SELECT c.*, cl.name as client_name FROM cases c
            JOIN clients cl ON c.client_id = cl.id
            WHERE c.status = ? ORDER BY c.created_at DESC""",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT c.*, cl.name as client_name FROM cases c
            JOIN clients cl ON c.client_id = cl.id
            ORDER BY c.created_at DESC""",
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def check_sol_deadline(incident_date: str, state: str = "CA") -> dict:
    sol_years = SOL_BY_STATE.get(state, 2)
    inc_date = datetime.strptime(incident_date, "%Y-%m-%d")
    sol_date = inc_date + timedelta(days=365 * sol_years)
    days_remaining = (sol_date - datetime.now()).days
    return {
        "deadline_date": sol_date.strftime("%Y-%m-%d"),
        "days_remaining": max(0, days_remaining),
        "is_urgent": days_remaining < 60,
        "state": state,
        "sol_years": sol_years,
    }


def get_urgent_deadlines(days_ahead: int = 90) -> list[dict]:
    cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    conn = get_conn()
    rows = conn.execute(
        """SELECT c.*, cl.name as client_name FROM cases c
        JOIN clients cl ON c.client_id = cl.id
        WHERE c.statute_of_limitations_date <= ?
        AND c.status NOT IN ('settled', 'closed')
        ORDER BY c.statute_of_limitations_date ASC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Case Notes ---

def add_case_note(case_id: str, note_type: str, content: str, created_by: str = "donna") -> str:
    note_id = str(uuid.uuid4())[:8]
    conn = get_conn()
    conn.execute(
        "INSERT INTO case_notes (id, case_id, note_type, content, created_by) VALUES (?, ?, ?, ?, ?)",
        (note_id, case_id, note_type, content, created_by),
    )
    conn.commit()
    conn.close()
    return note_id


# --- Calendar ---

def book_calendar_event(
    client_id: str,
    case_id: str,
    event_type: str,
    title: str,
    scheduled_at: str,
    duration_minutes: int = 60,
    notes: str = "",
) -> str:
    event_id = str(uuid.uuid4())[:8]
    conn = get_conn()
    conn.execute(
        """INSERT INTO calendar
        (id, client_id, case_id, event_type, title, scheduled_at, duration_minutes, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, client_id, case_id, event_type, title, scheduled_at, duration_minutes, notes),
    )
    conn.commit()
    conn.close()
    return event_id


def get_upcoming_events(days_ahead: int = 7) -> list[dict]:
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%S")
    conn = get_conn()
    rows = conn.execute(
        """SELECT cal.*, cl.name as client_name FROM calendar cal
        LEFT JOIN clients cl ON cal.client_id = cl.id
        WHERE cal.scheduled_at BETWEEN ? AND ?
        ORDER BY cal.scheduled_at ASC""",
        (now, cutoff),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Documents ---

def register_document(case_id: str, filename: str, doc_type: str, file_path: str = "") -> str:
    doc_id = str(uuid.uuid4())[:8]
    conn = get_conn()
    conn.execute(
        "INSERT INTO documents (id, case_id, filename, doc_type, file_path) VALUES (?, ?, ?, ?, ?)",
        (doc_id, case_id, filename, doc_type, file_path),
    )
    conn.commit()
    conn.close()
    return doc_id


# --- Conversation Log ---

def log_conversation(session_id: str, role: str, content: str, tool_calls: str = ""):
    log_id = str(uuid.uuid4())[:8]
    conn = get_conn()
    conn.execute(
        "INSERT INTO conversation_log (id, session_id, role, content, tool_calls) VALUES (?, ?, ?, ?, ?)",
        (log_id, session_id, role, content, tool_calls),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
