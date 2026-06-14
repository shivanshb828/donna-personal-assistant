# Donna — Document Intelligence Pipeline
## Architecture, IPC Contract, and Email Server Integration

---

## Overview

The document intelligence pipeline is a background service that receives files (medical records, police reports, adjuster letters, etc.), runs LLM extraction and analysis, and writes structured context back to the local Donna data layer. Today that means SQLite plus optional Chroma indexing; GBrain is a possible later-phase add-on. Donna then synthesizes that context and notifies the lawyer.

---

## Why Donna + VLM Are Separate

The VLM (document parser) extracts raw facts from a file. Donna interprets them in context.

| VLM (document parser) | Donna (via OpenClaw) |
|---|---|
| "Date: 3/3, body part: neck, provider: Dr. Smith" | "That neck injury was never mentioned at intake — flagging it." |
| "Police report says airbags deployed" | "Client said minor impact. That's a contradiction — risk score drops." |
| Raw extraction, no memory | Cross-references local case memory, knows full case history |
| No tools | Calls `update_case_file`, notifies lawyer, updates risk score |
| Stateless | Persistent session across turns |

**The VLM extracts. Donna interprets, contextualizes, and acts.**

---

## Full Flow

```
Client emails → email server extracts attachment + case context
             → saves file to ./documents/{case_id}/filename.pdf
             → POSTs IPC envelope to pipeline at http://localhost:8765/ingest

pipeline     → receives envelope
             → auto-detects or uses doc_type_hint
             → LLM extracts structured facts
             → runs consistency check across all case documents
             → runs litigation risk score
             → writes summaries and case context to the local data layer

SQLite / Chroma → updated (facts, flags, risk score, summary)

pipeline     → sends pipeline_complete IPC envelope

Donna        → reads pipeline_complete
             → notifies lawyer: "Got a police report for Sarah Chen.
                                 Risk score updated to 6/10.
                                 Found 2 inconsistencies — want me to flag them?"
```

---

## IPC Envelope — Trigger (Email Server → Pipeline)

**Endpoint:** `POST http://localhost:8765/ingest`
**Content-Type:** `application/json`

```json
{
  "source": "email",
  "session_id": "<uuid-v4>",
  "text": "./documents/case-2026-001/police-report.pdf",
  "type": "document_ingest",
  "metadata": {
    "case_id": "case-2026-001",
    "sender_email": "adjuster@allstate.com",
    "email_subject": "[DONNA] case-2026-001 - police report from SJPD",
    "filename": "police-report.pdf",
    "doc_type_hint": "police_report"
  }
}
```

**`doc_type_hint` is optional** — pipeline auto-detects from filename/content if omitted.

Valid values: `medical_record`, `police_report`, `adjuster_letter`, `eob`, `witness_statement`, `prior_medical`, `other`

**Immediate response (async — processing happens in background):**
```json
{ "status": "accepted", "job_id": "<uuid>", "case_id": "case-2026-001" }
```

---

## IPC Envelope — Completion (Pipeline → Donna)

When processing is done, the pipeline sends this back through the IPC bus:

```json
{
  "source": "pipeline",
  "session_id": "<same uuid as ingest>",
  "text": "Processed police-report.pdf for case-2026-001. Risk updated to 6/10. 2 inconsistency flags.",
  "type": "pipeline_complete",
  "metadata": {
    "case_id": "case-2026-001",
    "document": "police-report.pdf",
    "risk_score": 6,
    "inconsistency_count": 2,
    "job_id": "<uuid>"
  }
}
```

Donna reads `type: "pipeline_complete"` and notifies the lawyer.

---

## Email Subject Line Format (Required Convention)

The email server must parse `case_id` from the subject line. Agreed format:

```
[DONNA] {case_id} - {optional description}
```

Examples:
- `[DONNA] case-2026-001 - police report from SJPD`
- `[DONNA] case-2026-001 - Allstate adjuster letter`
- `[DONNA] case-2026-002 - urgent care records`

If subject does not match this format, the email server should reply to sender: *"Please include a case ID in your subject line: [DONNA] case-XXXX-XXX - description"*

---

## Filesystem Convention

All documents saved to:
```
./documents/{case_id}/{filename}
```

Example:
```
./documents/case-2026-001/police-report.pdf
./documents/case-2026-001/allstate-adjuster-letter.pdf
./documents/case-2026-002/urgent-care-records.pdf
```

The email server is responsible for saving the file before POSTing the IPC envelope. The pipeline assumes the file exists at `text` path when it receives the envelope.

---

## Responsibility Split

### Email Server (other instance builds this)

| Task | Notes |
|------|-------|
| Receive inbound email (SMTP/IMAP) | Standard email server setup |
| Parse `case_id` from subject line | Format: `[DONNA] {case_id} - ...` |
| Save attachment to `./documents/{case_id}/` | Create directory if not exists |
| Infer `doc_type_hint` from filename or body | Optional but helpful |
| `POST` IPC envelope to `http://localhost:8765/ingest` | Fire and forget after `202 Accepted` |

### Pipeline (M2 builds this)

| Task | Notes |
|------|-------|
| `POST /ingest` HTTP endpoint | Accepts envelope, returns `202 Accepted` immediately |
| Auto-detect document type | From filename + first-page LLM classification |
| LLM extraction per document type | Medical, police, adjuster, EOB, witness, prior medical |
| Narrative consistency check (#6) | Cross-document contradiction detection |
| Litigation risk score (#7) | 0–10 structured reasoning chain |
| Write all outputs to GBrain | Facts, flags, score, summary, pipeline run metadata |
| Send `pipeline_complete` IPC envelope | Donna picks this up and notifies lawyer |

---

## Pipeline File Structure

```
dell-hack/
  pipeline/
    __init__.py
    ingestion.py           # HTTP server (POST /ingest), orchestrates pipeline
    document_parser.py     # LLM extraction per document type
    consistency_checker.py # Cross-doc contradiction detection (#6)
    risk_scorer.py         # Structured 0-10 reasoning chain (#7)
    gbrain_writer.py       # Writes all outputs to GBrain
    prompts/
      extract_medical.md
      extract_police.md
      extract_adjuster.md
      check_consistency.md
      score_risk.md
```

---

## Document Types + What Gets Extracted

| Document Type | Key Extracted Fields |
|---|---|
| Medical record | Date of service, provider, chief complaint, diagnosis, treatment, restrictions, causation language, next appointment |
| Police / incident report | Date/time/location, parties, at-fault notes, witnesses, citations, airbag deployment, speed |
| Adjuster correspondence | Adjuster name + carrier, claim number, coverage position, IME/recorded statement requests |
| EOB | Billed vs. paid amounts, denial codes, lien implications |
| Witness statement | Account of incident, corroboration or contradiction of client version |
| Prior medical records | Prior injury body parts, treatment history, pre-existing condition overlap |

---

## Consistency Check Logic (#6)

Runs after 2+ documents are parsed for a case. Flags:

| Check | Sources | Flag if… |
|-------|---------|----------|
| First complaint date | Intake vs. ER record | ER date > 3 days after incident, no explanation |
| Body parts | Intake injuries vs. medical records | Record treats body part never reported at intake |
| Impact severity | Client description vs. police report | Airbag deployed but client says minor impact |
| Prior injuries | Intake disclosure vs. prior records | Prior treatment to same body part not disclosed |
| Treatment continuity | Medical record dates | Gap > 30 days without explanation |
| Witness account | Witness statement vs. client account | Contradicts client on speed, location, sequence |

Each flag: `{ source_a, source_b, field, client_version, document_version, severity: high|medium|low }`

---

## Risk Score Logic (#7)

Four-factor structured reasoning chain, total 0–10:

| Factor | Max | How scored |
|--------|-----|-----------|
| Liability clarity | 3 | Police report at-fault determination, witness count, citation issued |
| Damages documentation | 3 | Medical record quality, treatment continuity, causation language in records |
| Plaintiff credibility | 2 | Consistency score from #6 (zero flags = 2, each high-severity flag = -1, floor 0) |
| Jurisdiction favorability | 2 | CourtListener verdict trends for incident type + jurisdiction |

Output: `{ score, rationale (1 paragraph), risk_factors[] (top 3), recommended_action }`

---

## GBrain Write-Back

After pipeline completes, writes:

| Data | GBrain target |
|------|--------------|
| Extracted document facts | `facts` nodes linked to case |
| Document summary | `documents` node, `summary` field |
| Inconsistency flags | `memories` nodes, `kind: "inconsistency_flag"` |
| Risk score + rationale | `cases` node, `risk_score` + `risk_rationale` |
| Pipeline run metadata | `memories` node, `kind: "pipeline_run"` |
