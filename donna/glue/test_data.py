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
    """Seed demo context DB with 2 client profiles + firm profile. Used by tests and init scripts."""
    import sys
    from pathlib import Path as _Path
    _scripts = _Path(__file__).resolve().parents[2] / "scripts"
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))
    from seed_demo_unified import _seed_context, _wipe_context
    _wipe_context(db_path)
    _seed_context(db_path)


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
