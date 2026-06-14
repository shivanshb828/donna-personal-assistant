from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ContextHit:
    source: str
    case_id: str
    title: str
    snippet: str


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_context_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS metadata (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cases (
              id TEXT PRIMARY KEY,
              client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
              case_type TEXT NOT NULL,
              incident_date TEXT NOT NULL,
              incident_location TEXT,
              at_fault_party TEXT,
              injuries TEXT,
              treatment_received TEXT,
              witnesses TEXT,
              status TEXT NOT NULL,
              statute_of_limitations_date TEXT,
              state_jurisdiction TEXT DEFAULT 'CA'
            );

            CREATE TABLE IF NOT EXISTS clients (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              phone TEXT UNIQUE,
              email TEXT,
              consent_recording INTEGER DEFAULT 0,
              consent_ai_disclosure INTEGER DEFAULT 0,
              consent_data_storage INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS facts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
              label TEXT NOT NULL,
              value TEXT NOT NULL,
              verified INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS case_notes (
              id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
              note_type TEXT NOT NULL,
              content TEXT NOT NULL,
              created_by TEXT DEFAULT 'donna'
            );

            CREATE TABLE IF NOT EXISTS documents (
              id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
              filename TEXT NOT NULL,
              doc_type TEXT NOT NULL,
              file_path TEXT,
              summary TEXT
            );

            CREATE TABLE IF NOT EXISTS memories (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
              kind TEXT NOT NULL,
              content TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )


def seed_context_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS memories;
            DROP TABLE IF EXISTS documents;
            DROP TABLE IF EXISTS case_notes;
            DROP TABLE IF EXISTS facts;
            DROP TABLE IF EXISTS cases;
            DROP TABLE IF EXISTS clients;
            """
        )
    init_context_db(db_path)
    with connect(db_path) as conn:
        for table in ("memories", "documents", "case_notes", "facts", "cases", "clients"):
            conn.execute(f"DELETE FROM {table}")

        clients = [
            ("client-maria-lopez", "Maria Lopez", "+14085550101", "maria.lopez@example.com", 1, 1, 1),
            ("client-andre-patel", "Andre Patel", "+15105550102", "andre.patel@example.com", 1, 1, 1),
        ]
        conn.executemany(
            (
                "INSERT INTO clients "
                "(id, name, phone, email, consent_recording, consent_ai_disclosure, consent_data_storage) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
            clients,
        )

        cases = [
            (
                "case-2026-001",
                "client-maria-lopez",
                "auto_accident",
                "2026-06-13",
                "San Jose, CA",
                "Other driver, details pending",
                "Neck pain reported after collision",
                "Medical evaluation pending",
                "",
                "intake",
                "2028-06-13",
                "CA",
            ),
            (
                "case-2026-002",
                "client-andre-patel",
                "slip_fall",
                "2026-05-28",
                "Oakland, CA",
                "Grocery store, liability under investigation",
                "Wrist pain",
                "Urgent care visit same day",
                "",
                "records_gathering",
                "2028-05-28",
                "CA",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO cases
              (id, client_id, case_type, incident_date, incident_location, at_fault_party,
               injuries, treatment_received, witnesses, status, statute_of_limitations_date,
               state_jurisdiction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            cases,
        )

        notes = [
            (
                "note-001",
                "case-2026-001",
                "intake_transcript",
                "Maria Lopez reports being rear-ended at a stop light in San Jose and having neck pain.",
                "donna",
            ),
            (
                "note-002",
                "case-2026-002",
                "medical_update",
                "Andre Patel reports urgent care treatment after slipping in a grocery aisle.",
                "donna",
            ),
        ]
        conn.executemany(
            "INSERT INTO case_notes (id, case_id, note_type, content, created_by) VALUES (?, ?, ?, ?, ?)",
            notes,
        )

        facts = [
            ("case-2026-001", "Insurance", "Other driver reportedly has State Farm.", 0),
            ("case-2026-001", "Treatment", "Client has not yet completed a medical evaluation.", 0),
            ("case-2026-001", "Evidence", "Client says photos of bumper damage are available.", 0),
            ("case-2026-002", "Treatment", "Urgent care visit occurred the same day as the fall.", 1),
            ("case-2026-002", "Evidence", "Store incident report requested but not received.", 0),
        ]
        conn.executemany(
            "INSERT INTO facts (case_id, label, value, verified) VALUES (?, ?, ?, ?)",
            facts,
        )

        documents = [
            (
                "doc-001",
                "case-2026-001",
                "maria-lopez-intake-notes.md",
                "intake_notes",
                "/gbio/donna/cases/case-2026-001/intake-notes.md",
                "Maria Lopez reports neck pain after a rear-end collision in San Jose.",
            ),
            (
                "doc-002",
                "case-2026-002",
                "andre-patel-urgent-care-summary.pdf",
                "medical_record",
                "/gbio/donna/cases/case-2026-002/urgent-care-summary.pdf",
                "Urgent care summary notes wrist pain after a fall and recommends follow-up.",
            ),
        ]
        conn.executemany(
            "INSERT INTO documents (id, case_id, filename, doc_type, file_path, summary) VALUES (?, ?, ?, ?, ?, ?)",
            documents,
        )

        memories = [
            ("case-2026-001", "case_summary", "Ask Maria for medical evaluation status and insurance claim number."),
            ("case-2026-002", "case_summary", "Follow up on grocery store incident report and surveillance preservation."),
        ]
        conn.executemany(
            "INSERT INTO memories (case_id, kind, content) VALUES (?, ?, ?)",
            memories,
        )


def search_context(db_path: Path, query: str, limit: int = 5) -> list[ContextHit]:
    needle = f"%{query.lower()}%"
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT 'case' AS source, c.id AS case_id, cl.name AS title,
              c.case_type || ': ' || c.injuries || ' at ' || c.incident_location AS snippet
            FROM cases c
            JOIN clients cl ON cl.id = c.client_id
            WHERE lower(cl.name || ' ' || c.case_type || ' ' || c.injuries || ' ' || c.incident_location) LIKE ?
            UNION ALL
            SELECT 'fact' AS source, case_id, label AS title, value AS snippet
            FROM facts
            WHERE lower(label || ' ' || value) LIKE ?
            UNION ALL
            SELECT 'note' AS source, case_id, note_type AS title, content AS snippet
            FROM case_notes
            WHERE lower(note_type || ' ' || content) LIKE ?
            UNION ALL
            SELECT 'document' AS source, case_id, filename AS title, summary AS snippet
            FROM documents
            WHERE lower(filename || ' ' || summary) LIKE ?
            UNION ALL
            SELECT 'memory' AS source, case_id, kind AS title, content AS snippet
            FROM memories
            WHERE lower(kind || ' ' || content) LIKE ?
            LIMIT ?
            """,
            (needle, needle, needle, needle, needle, limit),
        ).fetchall()

    return [
        ContextHit(
            source=row["source"],
            case_id=row["case_id"],
            title=row["title"],
            snippet=row["snippet"],
        )
        for row in rows
    ]
