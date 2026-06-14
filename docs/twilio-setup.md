# Twilio setup for Donna telephony

## Prerequisites

- Twilio account with a voice-capable phone number
- ngrok or similar HTTPS tunnel to your telephony server (`:3002`)
- Local model services running (Whisper :9000, Kokoro :8880, Ollama :11434)

## Environment variables

```bash
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...
PUBLIC_URL=https://your-subdomain.ngrok-free.app
DONNA_TELEPHONY_PORT=3002
DONNA_VALIDATE_TWILIO=true   # set false for local TestClient-only dev
DONNA_TELEPHONY_ECHO=false   # set true to loop audio without STT/LLM/TTS
DONNA_DASHBOARD_WS=ws://localhost:3001
DONNA_FIRM_NAME="Donna Legal"
```

## Start services

```bash
# Terminal 1 — dashboard (optional)
python donna/fake_dashboard.py

# Terminal 2 — telephony
bash scripts/run_telephony.sh

# Terminal 3 — ngrok
ngrok http 3002
```

Update `PUBLIC_URL` whenever ngrok restarts.

## Configure Twilio console

1. Phone number → **Voice Configuration**
2. **A call comes in** → Webhook → `POST` → `https://<ngrok>/voice`
3. Save

For outbound calls, the server uses `POST /api/calls/outbound` which sets Twilio callback to `/voice/outbound`.

## Smoke test

1. Set `DONNA_TELEPHONY_ECHO=true` and call the number — you should hear your own voice echoed.
2. Set `DONNA_TELEPHONY_ECHO=false`, ensure STT/TTS/Ollama are up, call again — Donna greets and responds.
3. Check dashboard terminal for `call_started`, `user_speech`, `donna_speech`, `call_ended` events.

## Outbound dialer

```bash
curl -X POST http://localhost:3002/api/calls/outbound \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+14085550101","lead_id":"lead-..."}'
```

Import leads:

```bash
curl -X POST http://localhost:3002/api/leads \
  -H 'Content-Type: application/json' \
  -d '{"name":"Jane Doe","phone":"+14085550199","incident_summary":"rear-end on 101"}'
```

## Security notes

- Twilio signature validation is enabled by default on `/voice` webhooks.
- REST API endpoints (`/api/*`) are unauthenticated — use only on localhost or behind a VPN for demos.
- Never commit `.env` with real Twilio credentials.
