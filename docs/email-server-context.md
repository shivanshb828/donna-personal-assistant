# Email Server — Context for Builder

## What We're Building

**Donna** is a local-first AI legal secretary for personal injury law firms running on a Dell GBIO (GB10 Grace Blackwell). No client data leaves the machine. The email server is one of several **inbound channels** that feed into Donna's brain.

---

## Where Email Fits in the Architecture

There are three inbound channels into Donna:

| Channel | Source | Who builds it |
|---------|--------|---------------|
| Voice | Client phone calls / in-office mic | M4 (voice pipeline) |
| Dashboard | Lawyer types into React UI | M1 (frontend) |
| **Email** | Adjuster emails, client emails, court notices | **You** |

All three channels funnel into the same place — Donna's LLM brain — using a shared IPC envelope:

```json
{
  "source": "email",
  "session_id": "<uuid>",
  "text": "<email body or summary>",
  "type": "user_input"
}
```

Donna reads the `text` field and decides what to do (log a note, update a case file, flag urgency, etc.). She does not care how the email arrived — that's your layer.

---

## What the Email Server Needs to Do

### 1. Receive emails locally
The firm's email (e.g. intake@lawfirm.local or a forwarded Gmail/Outlook account) routes into a local SMTP listener running on the GBIO. No email content goes to any cloud service.

**Recommended stack:**
- `aiosmtpd` (Python async SMTP server) — lightweight, runs locally
- Or: fetch via IMAP polling (imaplib / aioimaplib) if the firm uses an existing mail host

### 2. Parse and extract the relevant text
Strip HTML, remove signatures, extract plain text body. Optionally extract:
- Sender name and email
- Subject line
- Attachments (flag them — Donna's document parser handles the actual reading)

### 3. Route into the IPC envelope
Wrap the parsed email body in the IPC envelope and POST it to Donna's session router (M1's endpoint, TBD — likely `http://localhost:8000/ipc` or a local Unix socket).

```python
envelope = {
    "source": "email",
    "session_id": str(uuid4()),  # new session per email thread, or use thread-ID for continuity
    "text": f"From: {sender}\nSubject: {subject}\n\n{body}",
    "type": "user_input"
}
```

### 4. Handle attachments
If the email has PDF/DOCX attachments (medical records, adjuster letters, police reports):
- Save to `/gbio/donna/documents/incoming/<filename>`
- Include the file path in the envelope text: `"Attachment saved: /gbio/donna/documents/incoming/adjuster-letter-march.pdf"`
- Donna will call `summarize_document` on it — that triggers the LLM document parser

---

## What Donna Does With It

Once the envelope arrives, Donna's LLM reads the email text and may:
- Call `search_context` to match the email to an existing case (by client name, carrier name, case ID in subject line)
- Call `update_case_file` to log the adjuster communication
- Call `book_calendar` if the email contains a deposition notice or court date
- Call `summarize_document` if an attachment was flagged
- Flag urgency (statute of limitations proximity, settlement offer received) back to the lawyer via the dashboard

The email server does **not** need to parse legal content — Donna handles all of that. Just get the text in.

---

## Privacy Constraints

- The SMTP listener must bind to `localhost` or the local LAN only — never expose to the public internet
- No email body or attachment is forwarded to any external API
- If fetching via IMAP from an external host (Gmail, Outlook), credentials stay in a local `.env` file on the GBIO — never committed to git
- OpenShell policy blocks all outbound network traffic from Donna's agent process — the email server runs as a separate process outside the agent sandbox, which is fine

---

## Interface Contract (what you hand off)

The one thing the email server must produce per email:

```python
{
    "source": "email",
    "session_id": str,       # UUID — use email Message-ID for thread continuity
    "text": str,             # "From: ...\nSubject: ...\n\n<body>\n[Attachment: <path>]"
    "type": "user_input"
}
```

POST this to the session router. That's the full contract — everything else is your implementation choice.

---

## Suggested File Layout

```
email/
├── server.py        # SMTP listener (aiosmtpd) or IMAP poller
├── parser.py        # strip HTML, extract body + attachments
├── router.py        # wrap in IPC envelope, POST to session router
└── config.yaml      # SMTP port, IMAP credentials path, session router URL
```

---

## Questions to Resolve With M1

- What is the session router's endpoint URL / socket path?
- Does Donna respond back to the email sender, or only to the lawyer dashboard? (Current assumption: lawyer dashboard only — Donna does not send outbound email)
- Thread continuity: should emails in the same thread share a `session_id` so Donna remembers the prior context? (Recommended: yes, use email `Message-ID` / `In-Reply-To` headers)
