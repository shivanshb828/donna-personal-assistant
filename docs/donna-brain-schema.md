# Donna GBrain schema

Markdown layout for Donna's legal secretary brain. Adapt GBrain's MECE filing rules for **personal injury case management** instead of generic startup `people/` / `companies/` trees.

## Top-level directories

```text
donna-brain/
├── clients/           # One page per client (contact, consent flags)
├── cases/             # One page per matter (PI facts, status, SOL dates)
├── intake/            # Raw intake transcripts and structured summaries
├── calendar/          # Event notes linked to cases (mirror of M3 calendar tool)
├── documents/         # Doc summaries + file paths on GBIO
├── facts/             # Verified / unverified fact tables per case
├── memories/          # Agent-generated case summaries and follow-ups
└── firm/              # Firm-wide policies, templates, disclaimers
```

## Page conventions

### Client page (`clients/maria-lopez.md`)

- Contact info, consent for recording / AI disclosure
- Links to active cases: `[[cases/case-2026-001]]`

### Case page (`cases/case-2026-001.md`)

- Compiled truth at top: incident type, date, jurisdiction, status
- Timeline at bottom: intake notes, medical updates, calendar events
- Entity links GBrain extracts automatically (`client`, `witness`, `insurer`)

### Intake page (`intake/2026-06-14-maria-rear-end.md`)

- Full transcript snippet
- Structured fields: injuries, treatment, at-fault party, evidence

## Seed data mapping (M3 SQLite → GBrain)

| SQLite source | GBrain path |
|---------------|-------------|
| `clients` row Maria Lopez | `clients/maria-lopez.md` |
| `cases` case-2026-001 | `cases/case-2026-001.md` |
| `case_notes` intake | `intake/` + timeline on case page |
| `facts` | `facts/case-2026-001/` or inline on case page |
| `documents` | `documents/maria-lopez-intake-notes.md` |
| `memories` | `memories/case-2026-001-summary.md` |

Run `python3 scripts/context_lookup.py Maria` against SQLite to validate seed content before transcribing into brain pages.

## Skills to prioritize (from GBrain skillpack)

| Skill | Donna use |
|-------|-----------|
| `query` | Case/client lookup before responding |
| `ingest` / `voice-note-ingest` | Post-call intake from voice pipeline |
| `meeting-ingestion` | Deposition / client meeting notes |
| `briefing` | Pre-call case brief for attorney |
| `maintain` / `citation-fixer` | Overnight brain consolidation |
| `brain-ops` | Health checks on Dell |

Skip startup-centric skills (`invested_in`, portfolio reports) unless repurposed for insurer parties.

## Privacy / demo rules

- Mark unverified facts explicitly (matches SQLite `verified=0`)
- No legal advice in compiled truth sections — intake and scheduling only
- Consent flags on client pages must match `clients.consent_*` columns in seed DB

## OpenClaw resolver

After `gbrain skillpack scaffold`, read `skills/RESOLVER.md` in the OpenClaw workspace. Add Donna-specific routing hints:

- User mentions a client name → `query` + case pages under `cases/`
- New accident description → `ingest` + `intake.start` M3 tool
- Scheduling language → `calendar.create_event` M3 tool + `calendar/` brain page
