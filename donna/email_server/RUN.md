# Donna Email Server — Run Guide for GBIO

> **Who this is for:** The agent or engineer deploying the email inbound channel on the
> Dell GBIO (GB10 Grace Blackwell). M2's `deploy.sh` must have already run successfully
> before you start here.

---

## Prerequisites (confirm before proceeding)

| Check | How to verify |
|-------|--------------|
| M2 deploy.sh ran | `ls /gbio/donna/.venv` — must exist |
| Ollama is up | `curl http://localhost:11434/api/tags` — returns JSON |
| GBrain is up | `psql postgresql://donna@localhost:7700/donna -c "SELECT 1"` |
| OpenClaw agent registered | `openclaw list` — shows `donna` |
| M1's session router is up | `curl -s http://localhost:8000/ipc` — any response (not connection refused) |
| VLM pipeline is up | `curl -s http://localhost:8765/ingest` — any response |

If M1 or the VLM pipeline aren't up yet, proceed anyway — the email server retries
failed POSTs 3× with 2s backoff and logs errors rather than crashing.

---

## Step 1 — Configure credentials

```bash
cp /gbio/donna/.env.example /gbio/donna/.env   # skip if .env already exists
nano /gbio/donna/.env
```

Fill in at minimum:

```env
# Which email to poll (imap mode) or leave blank for smtp mode
DONNA_EMAIL_USER=intake@lawfirm.com
DONNA_EMAIL_PASS=<gmail-app-password-or-outlook-password>

# M1's confirmed endpoint (update once M1 tells you the real port/path)
DONNA_SESSION_ROUTER_URL=http://localhost:8000/ipc

# VLM pipeline endpoint
DONNA_PIPELINE_INGEST_URL=http://localhost:8765/ingest

# Where attachments are saved — must match what VLM pipeline expects
DONNA_ATTACHMENT_DIR=/gbio/donna/documents
```

**Gmail app password:** Google account → Security → 2-Step Verification → App passwords →
select "Mail" → copy the 16-char password.

---

## Step 2 — Choose a mode

| Mode | Use when | How emails arrive |
|------|----------|-------------------|
| `smtp` (default) | You control the mail server / MX | Forwarded to port 1025 on this machine |
| `imap` | Firm already has Gmail or Outlook | Polled every 30s via IMAP |

Set the mode in `.env`:

```env
DONNA_EMAIL_MODE=imap   # or smtp
```

### SMTP mode — one extra step

The SMTP listener binds to `localhost:1025`. You need your email gateway to forward
inbound mail to this port. Options:

- **Postfix relay** (firm has their own mail server):
  ```
  # /etc/postfix/main.cf
  transport_maps = hash:/etc/postfix/transport
  # /etc/postfix/transport
  lawfirm.local   smtp:[127.0.0.1]:1025
  ```
- **Gmail/Outlook forward**: set up a filter that forwards all mail matching
  `[DONNA]` in the subject to a local mailbox, then relay with Postfix.
- **Dev / testing**: use `swaks` (see Step 5).

---

## Step 3 — Deploy

```bash
cd /path/to/dell-hack
bash donna/email_server/deploy.sh
```

The script:
1. Installs dependencies into the existing `/gbio/donna/.venv`
2. Creates `/gbio/donna/documents/` and `unmatched/` subdirectory
3. Installs and enables a systemd service (`donna-email`)
4. Runs the full test suite (31 tests) — must pass before starting
5. Starts the service

Expected output ends with:
```
✓ Donna email server deployed.
   Mode      : smtp
   SMTP listener on localhost:1025
```

---

## Step 4 — Verify it's running

```bash
systemctl status donna-email          # should show "active (running)"
journalctl -u donna-email -f          # live logs
```

Expected log line on startup (SMTP mode):
```
Donna SMTP listener on 127.0.0.1:1025 → session router http://localhost:8000/ipc
```

Expected log line on startup (IMAP mode):
```
IMAP poller started | host=imap.gmail.com user=intake@lawfirm.com interval=30s
```

---

## Step 5 — End-to-end smoke test

### SMTP mode

Install `swaks` if not present: `apt install swaks`

```bash
# Plain text email (no attachment) — goes to session router as user_input
swaks \
  --to donna@lawfirm.local \
  --server localhost:1025 \
  --from adjuster@allstate.com \
  --header "Subject: [DONNA] case-2026-001 - settlement offer" \
  --body "We are prepared to settle for \$125,000. Please advise."

# Watch logs — should see:
#   Email received | from=adjuster@allstate.com subject='[DONNA] case-2026-001 ...'
#   Routing email text to session router | session_id=case-2026-001
```

```bash
# Email with PDF attachment — goes to pipeline as document_ingest
swaks \
  --to donna@lawfirm.local \
  --server localhost:1025 \
  --from adjuster@allstate.com \
  --header "Subject: [DONNA] case-2026-001 - police report" \
  --attach /path/to/police-report.pdf

# Watch logs — should see:
#   Attachment saved: /gbio/donna/documents/case-2026-001/police-report.pdf
#   Routing document to pipeline | case_id=case-2026-001 file=police-report.pdf type=police_report
```

### IMAP mode

Wait up to 30 seconds after sending an email to the configured inbox. Watch logs:

```bash
journalctl -u donna-email -f
# Should see: IMAP poll: processed 1 email(s)
```

### Confirm pipeline received it

```bash
# If pipeline has a status endpoint:
curl http://localhost:8765/jobs/<job_id>

# Or check the document was saved:
ls /gbio/donna/documents/case-2026-001/
```

---

## Subject line format (required for case matching)

Every email must have a `[DONNA]` tag so the server knows which case it belongs to:

```
[DONNA] {case_id} - optional description
```

Examples:
```
[DONNA] case-2026-001 - police report from SJPD
[DONNA] case-2026-001 - Allstate adjuster letter
[DONNA] case-2026-002 - urgent care records
```

Emails without a `[DONNA]` tag are still processed — body text goes to the session router,
attachments land in `/gbio/donna/documents/unmatched/` — but Donna won't be able to link
them to a case automatically.

---

## What gets routed where

| Email content | Destination | Envelope type |
|--------------|-------------|---------------|
| Body text (no attachment) | `DONNA_SESSION_ROUTER_URL/ipc` | `user_input` |
| Attachment (PDF, DOCX, etc.) | `DONNA_PIPELINE_INGEST_URL/ingest` | `document_ingest` |
| Body text + attachment | Both endpoints (concurrent) | Both types |

---

## Common issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `Address already in use` on port 1025 | Another process on 1025 | `lsof -i :1025` to find it, or change `smtp.port` in `config.yaml` |
| `IMAP login failed` | Wrong password or 2FA | For Gmail: use App Password, not account password |
| `Route attempt 1/3 failed: connection refused` | M1 or pipeline not yet up | Normal on startup — retries automatically. Check `DONNA_SESSION_ROUTER_URL` in `.env` |
| Attachments in `unmatched/` | Subject missing `[DONNA]` tag | Tell senders to include `[DONNA] {case_id} - ...` in subject |
| Service keeps restarting | Import error or config error | `journalctl -u donna-email -n 50` to see the traceback |

---

## Service management

```bash
systemctl start donna-email       # start
systemctl stop donna-email        # stop
systemctl restart donna-email     # restart (e.g., after editing .env)
systemctl status donna-email      # current state
journalctl -u donna-email -f      # live logs
journalctl -u donna-email --since "10 minutes ago"  # recent logs
```

---

## Switching modes without redeploying

Edit `/gbio/donna/.env`, change `DONNA_EMAIL_MODE`, then restart:

```bash
nano /gbio/donna/.env
# change: DONNA_EMAIL_MODE=imap  (or smtp)
systemctl restart donna-email
```

---

## Architecture reminder

```
Email (SMTP port 1025 or IMAP poll)
        ↓
donna/email_server/server.py   ← this service (runs outside OpenShell sandbox)
        ↓ parse_email()
        ↓
  ┌─────┴──────────────────────────────────┐
  │  body text present?                   │  attachment present?
  ↓                                       ↓
POST localhost:8000/ipc           POST localhost:8765/ingest
type: "user_input"                type: "document_ingest"
  ↓                                       ↓
M1 session router                 VLM document pipeline
  ↓                                       ↓
Donna (OpenClaw)          GBrain (facts, risk score, flags)
  ↓                                       ↓
Lawyer dashboard  ←─────── pipeline_complete IPC envelope
```

The email server is intentionally **outside** the OpenShell security sandbox —
it has outbound network access to reach M1 and the pipeline on localhost,
which Donna's agent process itself cannot do.
