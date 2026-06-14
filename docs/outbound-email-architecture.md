# Donna Outbound Email + OpenClaw Integration Architecture

> **Owners:** M1 (approval UI, session router), M2 (tool registry, sender dispatch), M4 (email server, sender.py)
> **Status:** Design — M4 implements `sender.py`; M1 builds approval dashboard; M2 registers `send_email` tool

---

## 1. How Donna Lives in OpenClaw

```
┌─────────────────────────────────────────────────────────────────────┐
│  GBIO (GB10 Grace Blackwell) — everything runs here, nothing leaves │
│                                                                     │
│  ┌────────────────┐    IPC bus (localhost:8000)    ┌─────────────┐ │
│  │  Email Server  │ ──── user_input ──────────────► │   OpenClaw  │ │
│  │  (M4, port     │                                │  (agent     │ │
│  │   1025/IMAP)   │ ◄─── pipeline_complete ───────  │   runtime)  │ │
│  └────────────────┘                                │             │ │
│                                                    │  ┌────────┐ │ │
│  ┌────────────────┐    IPC bus                     │  │ Donna  │ │ │
│  │   Dashboard    │ ◄─── agent_response ──────────  │  │ (LLM)  │ │ │
│  │  (M1, React)   │                                │  └────────┘ │ │
│  │                │ ──── email_approved ──────────► │             │ │
│  └────────────────┘                                └──────┬──────┘ │
│                                                           │        │
│  ┌────────────────┐    tool_call dispatch                 │        │
│  │  M2 Tool Layer │ ◄─────────────────────────────────────┘        │
│  │  (tools/*.py)  │                                                │
│  │                │ ──── send_email ──► sender.py ──► SMTP out     │
│  └────────────────┘                                                │
│                                                                     │
│  ┌────────────────┐    POST /ingest (localhost:8765)               │
│  │  VLM Pipeline  │ ◄── attachment ──── Email Server               │
│  │  (document     │ ──── pipeline_complete ──► OpenClaw ──► Donna  │
│  │   parser)      │                                                │
│  └────────────────┘                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Session identity in OpenClaw

Every email maps to a Donna session keyed by `case_id`. OpenClaw resumes the existing
session whenever a new envelope arrives with the same `session_id`:

```
session_id = case_id  (e.g. "case-2026-001")
```

This means Donna remembers the full email thread history for a case across multiple
incoming emails — she doesn't start fresh for each one.

### What M2 needs to add to `agent/donna.yaml`

```yaml
channels:
  - voice
  - text
  - email    # ← add this; source: "email" inbound envelopes are now valid

tools:
  # ... existing tools ...
  - name: send_email
    description: "Draft or send an outbound email on behalf of the firm. Required: to (str), subject (str), body (str), case_id (str), email_type (adjuster_follow_up|records_request|client_update|appointment_confirmation|deposition_notice|lien_notice). Optional: reply_to_message_id (str — for thread continuity, include when replying to a specific email), requires_approval (bool, default true — always true except appointment_confirmation)."

  - name: list_email_drafts
    description: "List pending outbound email drafts awaiting lawyer approval for a case. Required: case_id (str). Returns: drafts[] with draft_id, to, subject, email_type, created_at."
```

---

## 2. Full Inbound Flow (email → Donna)

```
Adjuster sends email
        ↓
Email server receives (SMTP port 1025 or IMAP poll)
        ↓
parser.py: extracts case_id from [DONNA] subject, saves attachments
        ↓
        ├── Body text → POST localhost:8000/ipc
        │     { source:"email", session_id:"case-2026-001",
        │       text:"From: adjuster@allstate.com\nSubject: ...\n\n<body>",
        │       type:"user_input" }
        │         ↓
        │     M1 session router → OpenClaw → Donna (LLM)
        │         ↓
        │     Donna: "Got settlement offer of $125k on Smith case.
        │             Updating case file. Drafting follow-up for lawyer review."
        │         ↓
        │     Donna calls: update_case_file, then send_email (requires_approval=true)
        │
        └── Attachment → POST localhost:8765/ingest
              { source:"email", type:"document_ingest",
                text:"./documents/case-2026-001/adjuster-letter.pdf",
                metadata: { case_id, doc_type_hint:"adjuster_letter", ... } }
                  ↓
              VLM pipeline processes document
                  ↓
              POST localhost:8000/ipc
              { source:"pipeline", type:"pipeline_complete",
                text:"Processed adjuster-letter.pdf. Risk updated to 7/10." }
                  ↓
              Donna notifies lawyer dashboard
```

---

## 3. Full Outbound Flow (Donna → email)

```
Donna decides to send a follow-up email
        ↓
Donna emits tool_call:
  { type:"tool_call", text: JSON {
      tool: "send_email",
      args: {
        to: "adjuster@allstate.com",
        subject: "[DONNA] case-2026-001 - follow-up on settlement offer",
        body: "Dear Ms. Johnson,\n\nWe are following up on the settlement offer...",
        case_id: "case-2026-001",
        email_type: "adjuster_follow_up",
        reply_to_message_id: "offer-email-id@allstate.com",
        requires_approval: true
      }
  }}
        ↓
M2 tool router → tools/email_sender.py → donna/email_server/sender.py
        ↓
sender.py: requires_approval=True
  → saves draft to /gbio/donna/drafts/case-2026-001/{uuid}.json
  → POSTs to M1 dashboard:
      { type:"email_draft_pending", draft_id, case_id, to, subject, email_type }
        ↓
M1 dashboard: lawyer sees notification
  "Donna drafted a follow-up to adjuster@allstate.com — Approve / Edit / Reject"
        ↓
Lawyer clicks Approve
        ↓
M1 calls: POST /email/approve/{draft_id}  (on the email server, port 1025+1)
        ↓
sender.py: loads draft, sends via SMTP relay, marks draft as sent
  → saves sent copy to /gbio/donna/sent/case-2026-001/{uuid}.json
  → POSTs to M1: { type:"email_sent", draft_id, case_id, to, subject }
        ↓
Donna session receives email_sent confirmation
  → calls update_case_file: logs "Follow-up email sent to adjuster 2026-06-14"
```

For `requires_approval=False` (appointment confirmations), the draft step is skipped
and the email is sent immediately.

---

## 4. Who Donna Sends Email To — Full Matrix

| Email Type | Recipient | Trigger | Approval | Frequency |
|-----------|-----------|---------|----------|-----------|
| `adjuster_follow_up` | Insurance adjuster | 14 days after demand/offer with no response | Required | Every 14 days until reply |
| `records_request` | Medical provider, police dept | Donna receives case with missing records | Required first time; auto-send after template approved | Per provider |
| `lien_notice` | Medical provider | Case settles or demand package sent | Required | Once per provider per case |
| `client_update` | Client | Major case event (records received, offer received, court date set) | Required | Per event |
| `appointment_confirmation` | Client | Calendar event booked | **Auto-send** | 24h before event |
| `deposition_notice` | Opposing party / client | Deposition booked | Required | Once |
| `demand_acknowledgment` | Adjuster | Demand package sent by attorney | **Auto-send** | Once |

### Emails Donna never sends without explicit attorney instruction
- Demand letters (attorney composes and signs these)
- Settlement acceptance / rejection
- Anything to opposing counsel in active litigation
- Anything containing a specific dollar amount that wasn't first input by the lawyer

---

## 5. Subject Line Convention (outbound)

All outbound emails must use the `[DONNA]` tag so replies are auto-matched:

```
[DONNA] {case_id} - {email_type_description}
```

Examples:
```
[DONNA] case-2026-001 - follow-up on settlement offer (14-day)
[DONNA] case-2026-001 - medical records request: Dr. Smith UCLA Health
[DONNA] case-2026-002 - your deposition is confirmed for June 20
[DONNA] case-2026-002 - case update: police report received
```

When an adjuster replies to this email, the email server sees `[DONNA] case-2026-001`
in the subject and routes it back to the right case session automatically.

---

## 6. Thread Continuity

Donna maintains full thread context by chaining `Message-ID` / `In-Reply-To` headers:

```
[Inbound] Adjuster sends settlement offer
  Message-ID: <offer-001@allstate.com>
       ↓
  email server stores message_id in parsed dict
  router sends it as session_id="case-2026-001"
  Donna updates case file, drafts reply
       ↓
[Outbound] Donna's follow-up (via send_email tool)
  In-Reply-To: <offer-001@allstate.com>   ← links thread
  Message-ID: <donna-reply-uuid@lawfirm.com>
       ↓
[Inbound] Adjuster replies to Donna's follow-up
  In-Reply-To: <donna-reply-uuid@lawfirm.com>
  Subject: Re: [DONNA] case-2026-001 - follow-up on settlement offer
       ↓
  email server: parse_case_id("Re: [DONNA] case-2026-001 ...") = "case-2026-001"
  Routes back to same session — Donna has full thread context
```

---

## 7. Draft File Format

```
/gbio/donna/drafts/{case_id}/{draft_id}.json
```

```json
{
  "draft_id": "d3f1a2b4-...",
  "case_id": "case-2026-001",
  "status": "pending_approval",
  "email_type": "adjuster_follow_up",
  "to": "adjuster@allstate.com",
  "subject": "[DONNA] case-2026-001 - follow-up on settlement offer",
  "body": "Dear Ms. Johnson,\n\n...",
  "reply_to_message_id": "offer-001@allstate.com",
  "created_at": "2026-06-14T13:00:00Z",
  "session_id": "case-2026-001",
  "donna_reasoning": "Offer received 2026-05-31, no response after 14 days, standard follow-up per firm protocol"
}
```

Sent emails move to `/gbio/donna/sent/{case_id}/{draft_id}.json` with `status: "sent"` and `sent_at`.

---

## 8. M1 Dashboard Integration Points

M1 needs to handle these IPC envelope types from the email layer:

| `type` | Direction | Payload | Dashboard action |
|--------|-----------|---------|-----------------|
| `email_draft_pending` | email → M1 | `{ draft_id, case_id, to, subject, email_type, preview }` | Show "Approve / Edit / Reject" card |
| `email_sent` | email → M1 | `{ draft_id, case_id, to, subject, sent_at }` | Log in case activity feed |
| `email_rejected` | email → M1 | `{ draft_id, case_id, reason }` | Log in case activity feed |

M1 exposes these endpoints for the email server:

| Endpoint | Method | Body | Action |
|----------|--------|------|--------|
| `/email/approve/{draft_id}` | POST | `{}` | Load draft, send via SMTP, mark sent |
| `/email/reject/{draft_id}` | POST | `{ reason: str }` | Mark draft rejected, log to case |
| `/email/drafts/{case_id}` | GET | — | List pending drafts for case |

---

## 9. What Each Team Builds

| Team | What to build |
|------|--------------|
| **M4 (email)** | `sender.py`, `approval_server.py` (POST /email/approve endpoint), draft queue, tests |
| **M2 (tools)** | `tools/email_sender.py` (dispatches `send_email` tool → `sender.py`), add `send_email` + `list_email_drafts` to `donna.yaml` tool registry, add `email` to channels list |
| **M1 (dashboard)** | Approval UI cards, `/email/approve` and `/email/reject` endpoints, case activity feed for sent emails |

M4 owns `sender.py`. M2 owns the tool registration and dispatch. M1 owns the UI and approval HTTP endpoints.
