-- GBrain Postgres Schema — Donna
-- Runs on PGLite (Postgres 17 WASM) on the GBIO
-- pgvector extension handles all semantic search columns

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for BM25-style text search

-- ── Clients ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clients (
  id            TEXT PRIMARY KEY,           -- e.g. "client-uuid4"
  name          TEXT NOT NULL,
  phone         TEXT UNIQUE,
  email         TEXT,
  consent_recording       BOOLEAN DEFAULT FALSE,
  consent_ai_disclosure   BOOLEAN DEFAULT FALSE,
  consent_data_storage    BOOLEAN DEFAULT FALSE,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  embedding     vector(768)                 -- semantic search over name + intake notes
);

-- ── Cases ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cases (
  id                          TEXT PRIMARY KEY,
  client_id                   TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  case_type                   TEXT NOT NULL,  -- auto_accident | slip_fall | dog_bite | etc.
  incident_date               DATE NOT NULL,
  incident_location           TEXT,
  incident_description        TEXT,
  at_fault_party              TEXT,
  adverse_carrier             TEXT,
  client_carrier              TEXT,
  injuries                    TEXT,
  treating_physician          TEXT,
  witnesses                   TEXT,
  police_report_number        TEXT,
  stage  TEXT NOT NULL DEFAULT 'intake'
    CHECK (stage IN ('intake','investigation','demand','negotiation','litigation','settlement','closed')),
  state_jurisdiction          TEXT DEFAULT 'CA',
  statute_of_limitations_date DATE,
  created_at                  TIMESTAMPTZ DEFAULT NOW(),
  updated_at                  TIMESTAMPTZ DEFAULT NOW(),
  embedding                   vector(768)   -- semantic search over full case context
);

-- ── Calendar Events ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS calendar_events (
  id               TEXT PRIMARY KEY,
  case_id          TEXT REFERENCES cases(id) ON DELETE SET NULL,
  client_id        TEXT REFERENCES clients(id) ON DELETE SET NULL,
  lawyer_name      TEXT,
  event_type       TEXT NOT NULL
    CHECK (event_type IN ('consult','deposition','follow_up','court_date','filing_deadline','other')),
  title            TEXT NOT NULL,
  scheduled_at     TIMESTAMPTZ NOT NULL,
  duration_minutes INTEGER DEFAULT 60,
  attendee         TEXT,
  location         TEXT,
  notes            TEXT,
  price            NUMERIC(10,2),           -- billable amount for this event
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calendar_scheduled_at ON calendar_events(scheduled_at);

-- ── Case Law (from CourtListener) ─────────────────────────────────────────────
-- Populated by search_case_law and analyze_case_weaknesses tool calls.
-- Only stores cases actually retrieved from the API — no fabrication.
CREATE TABLE IF NOT EXISTS case_law (
  id                  TEXT PRIMARY KEY,     -- CourtListener opinion ID (numeric, as text)
  case_name           TEXT NOT NULL,
  citation            TEXT,                 -- e.g. "922 F.3d 101"
  court               TEXT,                 -- CourtListener court ID e.g. "ca9"
  date_filed          DATE,
  snippet             TEXT,                 -- verbatim snippet from CourtListener API
  courtlistener_url   TEXT NOT NULL,        -- full URL — required for anti-hallucination
  precedential_status TEXT DEFAULT 'Published',
  cite_count          INTEGER DEFAULT 0,
  retrieved_at        TIMESTAMPTZ DEFAULT NOW(),
  embedding           vector(768)           -- semantic search over case_name + snippet
);

CREATE INDEX IF NOT EXISTS idx_case_law_court ON case_law(court);
CREATE INDEX IF NOT EXISTS idx_case_law_cite_count ON case_law(cite_count DESC);

-- ── Case ↔ Case Law junction (which cases reference which opinions) ───────────
CREATE TABLE IF NOT EXISTS case_citations (
  case_id       TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  opinion_id    TEXT NOT NULL REFERENCES case_law(id) ON DELETE CASCADE,
  role          TEXT NOT NULL CHECK (role IN ('weakness','strength','defense_arg','general')),
  added_at      TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (case_id, opinion_id, role)
);

-- ── Documents ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
  id          TEXT PRIMARY KEY,
  case_id     TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  filename    TEXT NOT NULL,
  doc_type    TEXT NOT NULL,  -- police_report | medical_record | adjuster_letter | demand | other
  file_path   TEXT,
  summary     TEXT,           -- filled by LLM doc parser instance
  embedding   vector(768),    -- filled by LLM doc parser instance
  uploaded_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Payments ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payments (
  id           TEXT PRIMARY KEY,
  case_id      TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  amount       NUMERIC(12,2) NOT NULL,
  payment_type TEXT NOT NULL CHECK (payment_type IN ('retainer','settlement','fee','lien','other')),
  status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','received','disbursed')),
  date         DATE NOT NULL,
  notes        TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Court Dates ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS court_dates (
  id        TEXT PRIMARY KEY,
  case_id   TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  date      DATE NOT NULL,
  court     TEXT NOT NULL,
  judge     TEXT,
  outcome   TEXT,   -- e.g. "continued", "settled", "verdict for plaintiff"
  notes     TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Memories (Donna's session-persistent notes per case) ──────────────────────
-- GBrain writes here automatically; also writable by tool calls.
CREATE TABLE IF NOT EXISTS memories (
  id        BIGSERIAL PRIMARY KEY,
  case_id   TEXT REFERENCES cases(id) ON DELETE CASCADE,
  client_id TEXT REFERENCES clients(id) ON DELETE CASCADE,
  kind      TEXT NOT NULL,    -- intake_progress | follow_up | case_summary | adjuster_note
  content   TEXT NOT NULL,
  embedding vector(768),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Full-text search indexes (BM25 via pg_trgm) ───────────────────────────────
CREATE INDEX IF NOT EXISTS idx_cases_fts    ON cases    USING gin(to_tsvector('english', coalesce(incident_description,'') || ' ' || coalesce(injuries,'') || ' ' || coalesce(at_fault_party,'')));
CREATE INDEX IF NOT EXISTS idx_case_law_fts ON case_law USING gin(to_tsvector('english', coalesce(case_name,'') || ' ' || coalesce(snippet,'')));
CREATE INDEX IF NOT EXISTS idx_documents_fts ON documents USING gin(to_tsvector('english', coalesce(summary,'')));
CREATE INDEX IF NOT EXISTS idx_memories_fts  ON memories  USING gin(to_tsvector('english', content));

-- ── HNSW vector indexes (pgvector) ───────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_clients_embedding   ON clients   USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_cases_embedding     ON cases     USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_case_law_embedding  ON case_law  USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_memories_embedding  ON memories  USING hnsw (embedding vector_cosine_ops);
