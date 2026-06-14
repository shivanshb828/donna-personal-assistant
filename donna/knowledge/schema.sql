-- Donna AI Legal Secretary — SQLite Schema
-- All data stored locally. Never leaves this machine.

CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT UNIQUE,
    email TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    consent_recording INTEGER DEFAULT 0,
    consent_ai_disclosure INTEGER DEFAULT 0,
    consent_data_storage INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id),
    case_type TEXT NOT NULL,          -- auto_accident, slip_fall, workplace, medical_malpractice, other
    incident_date TEXT NOT NULL,
    incident_location TEXT,
    at_fault_party TEXT,
    injuries TEXT,
    treatment_received TEXT,
    witnesses TEXT,
    status TEXT DEFAULT 'intake',     -- intake, discovery, negotiation, settled, closed
    statute_of_limitations_date TEXT,
    state_jurisdiction TEXT DEFAULT 'CA',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS case_notes (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id),
    note_type TEXT NOT NULL,          -- client_call, attorney_note, medical_update, intake_transcript
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    created_by TEXT DEFAULT 'donna'   -- donna or attorney name
);

CREATE TABLE IF NOT EXISTS calendar (
    id TEXT PRIMARY KEY,
    client_id TEXT REFERENCES clients(id),
    case_id TEXT REFERENCES cases(id),
    event_type TEXT NOT NULL,         -- consult, deposition, follow_up, court_date, filing_deadline
    title TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    duration_minutes INTEGER DEFAULT 60,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id),
    filename TEXT NOT NULL,
    doc_type TEXT NOT NULL,           -- police_report, medical_record, insurance_letter, photo, other
    file_path TEXT,
    chroma_collection_id TEXT,
    uploaded_at TEXT DEFAULT (datetime('now')),
    summary TEXT                      -- cached LLM summary
);

CREATE TABLE IF NOT EXISTS conversation_log (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,               -- user, donna
    content TEXT NOT NULL,
    tool_calls TEXT,                  -- JSON array of tool calls made
    created_at TEXT DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_cases_client ON cases(client_id);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_sol ON cases(statute_of_limitations_date);
CREATE INDEX IF NOT EXISTS idx_calendar_date ON calendar(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_documents_case ON documents(case_id);
CREATE INDEX IF NOT EXISTS idx_conversation_session ON conversation_log(session_id);
