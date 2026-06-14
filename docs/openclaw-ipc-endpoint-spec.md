# OpenClaw IPC Endpoint — Spec for M1

> **Owner:** M1 (session router + frontend)
> **Consumer:** Email server (M4), Voice pipeline (M4), Dashboard (M1 self)
> **Reference:** `agent/donna.yaml` (M2), `tools/router.py` (M2)

---

## What M1 needs to build

A single HTTP endpoint that:
1. Accepts inbound IPC envelopes from all three channels (voice, email, dashboard)
2. Forwards them to Donna's OpenClaw agent runtime
3. Dispatches `tool_call` responses from Donna to the M2 tool layer
4. Returns HTTP 2xx immediately — never blocks the caller waiting for Donna's reply

---

## Endpoint

```
POST /ipc
Content-Type: application/json
```

Bind to `localhost` or local LAN only. Never expose to the public internet.

---

## Inbound envelope (what the email server sends)

```json
{
  "source":     "email",
  "session_id": "<string>",
  "text":       "<string>",
  "type":       "user_input"
}
```

### Field contract

| Field | Type | Notes |
|-------|------|-------|
| `source` | string | `"voice"` \| `"email"` \| `"dashboard"`. The email server always sends `"email"`. |
| `session_id` | string | Thread continuity key. For email: derived from `Message-ID` / `In-Reply-To` so replies to the same email chain share a session. For voice: new UUID per call. M1 must **not** reset an existing Donna session when the same `session_id` arrives — always resume. |
| `text` | string | Full email text Donna's LLM reads. See format below. |
| `type` | string | Always `"user_input"` for inbound messages. |

### Email `text` format

```
From: adjuster@insurance.com
Subject: Re: Smith v. General Motors — Demand Package

We are prepared to settle the above-captioned matter for $125,000.
Please respond within 30 days.

[Attachment saved: /gbio/donna/documents/incoming/smith-settlement-letter.pdf]
```

Donna reads the full text. Any `[Attachment saved: <path>]` line triggers a
`summarize_document` tool call (see tool dispatch below).

---

## What M1 does with it

```
email server → POST /ipc → M1 session router → OpenClaw (Donna LLM)
                                                      ↓
                                              Donna emits tool_call
                                                      ↓
                                M1 dispatches to M2 tools/router.py handle_envelope()
                                                      ↓
                                              tool_result back to Donna
                                                      ↓
                                         Donna emits agent_response
                                                      ↓
                                        M1 pushes to lawyer dashboard
```

**M1 returns HTTP 200 immediately** after queuing the envelope — before Donna responds.
The email server does not wait for Donna's reply. The reply goes to the dashboard only.

---

## Tool call dispatch (Donna → M2)

When Donna decides to act on an email, she emits an envelope with `type: "tool_call"`:

```json
{
  "source":     "agent",
  "session_id": "<same session_id>",
  "text":       "{\"tool\": \"summarize_document\", \"args\": {\"document_path\": \"/gbio/donna/documents/incoming/smith-settlement-letter.pdf\", \"case_id\": \"case-abc-123\"}}",
  "type":       "tool_call"
}
```

M1 intercepts this and calls `tools/router.py handle_envelope(envelope)` (M2's tool layer).
The tool layer returns a `tool_result` envelope which M1 feeds back to Donna.

### Tool calls triggered by email attachments

| Tool | When triggered | Required args |
|------|---------------|---------------|
| `summarize_document` | Any `[Attachment saved: <path>]` line in email text | `document_path`, `case_id` |
| `search_context` | Donna matching email to existing case | `query` |
| `update_case_file` | Donna logging adjuster communication | `case_id`, `field`, `value` |
| `book_calendar` | Email contains deposition notice / court date | `client_id`, `event_type`, `title`, `scheduled_at` |
| `score_litigation_risk` | Settlement offer received | `case_id` |

> `summarize_document` is currently a stub in M2's router (returns `not_implemented`).
> The VLM document parser will replace this stub — M1 does not need to change anything,
> just let the tool_call dispatch flow through as usual.

---

## Agent response (Donna → dashboard)

After processing the email, Donna emits:

```json
{
  "source":     "agent",
  "session_id": "<same session_id>",
  "text":       "I've logged the settlement offer from Liberty Mutual on the Smith case and flagged it as urgent. Attachment summarized and saved to the case file.",
  "type":       "agent_response"
}
```

M1 pushes this to the **lawyer's dashboard** (WebSocket or SSE). Donna does **not**
reply to the email sender — the email server has no outbound send capability.

---

## `source: "email"` registration

M2's `donna.yaml` currently lists `channels: [voice, text]`. M1 needs to register
`"email"` as a valid source so the session router doesn't reject it:

```yaml
# agent/donna.yaml — add to channels list
channels:
  - voice
  - text
  - email        # ← add this
```

Donna's LLM already handles any `source` value — she reads only the `text` field.
This change is just for M1's router validation layer.

---

## Expected HTTP response

```json
{ "status": "accepted" }
```

HTTP `200`. The email server checks only for 2xx — it does not parse the body.
Any 4xx/5xx triggers up to 3 retries with 2s backoff.

---

## Auth (dev vs. production)

| Environment | Auth mechanism |
|-------------|---------------|
| Local dev | None — localhost only |
| ngrok tunnel (dev) | Set `DONNA_IPC_SECRET` in `.env`; email server sends `X-Donna-Secret: <token>` header |
| Production GBIO | mTLS between co-located processes (TBD) |

---

## Quick smoke test

Once M1's endpoint is up:

```bash
curl -X POST http://localhost:8000/ipc \
  -H "Content-Type: application/json" \
  -d '{
    "source": "email",
    "session_id": "smoke-test-001",
    "text": "From: test@carrier.com\nSubject: Test\n\nHello Donna.",
    "type": "user_input"
  }'
# Expected: HTTP 200, {"status": "accepted"}
```

Then send a real email to the SMTP listener:

```bash
# Start email server first:
python -m donna.email_server.server

# Send test email (requires swaks):
swaks --to donna@lawfirm.local --server localhost:1025 \
  --from adjuster@carrier.com \
  --header "Subject: Settlement Offer" \
  --body "We are prepared to offer $50,000."
```

---

## Open questions for M1

1. **Port/path**: Is `/ipc` on port `8000` correct, or different? Email team updates `DONNA_SESSION_ROUTER_URL` in `.env` — no code changes.
2. **ngrok secret**: Will M1 enforce `X-Donna-Secret` on the tunnel? Email team needs the token value.
3. **`session_id` collision policy**: If two different email threads happen to generate the same `session_id` (extremely unlikely with UUID fallback), does M1 merge or fork sessions?
4. **Dashboard notification channel**: WebSocket or SSE? Email team doesn't consume this but wants to know for end-to-end testing.
