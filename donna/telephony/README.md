# Donna Voice Telephony

Twilio Media Streams bridge using local STT, streamed Qwen-on-Ollama turns, and Kokoro TTS.

## Architecture

```
Caller → Twilio PSTN
    → POST /voice (TwiML <Stream>)
    → WS /media-stream
        → μ-law 8kHz ↔ PCM16 16kHz
        → VAD → STT (:9000 active, :9001 Speaches sidecar)
        → Session router → Ollama qwen2.5:14b (+ tools)
        → sentence-queued Kokoro TTS → chunked μ-law back to Twilio
    → Dashboard WebSocket events (ws://localhost:3001)
    → SQLite telephony DB (call_sessions, intake, leads, messages)
```

## Quickstart

```bash
# From repo root, with venv active
bash scripts/run_telephony.sh
```

Set env vars (see `.env.example` section in docs/twilio-setup.md):

- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- `PUBLIC_URL` — ngrok HTTPS URL pointing at :3002
- `DONNA_TELEPHONY_PORT=3002`

Echo test (no STT/LLM/TTS):

```bash
DONNA_TELEPHONY_ECHO=true bash scripts/run_telephony.sh
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/voice` | Twilio inbound webhook |
| POST | `/voice/outbound` | Twilio outbound webhook |
| WS | `/media-stream` | Twilio audio stream |
| POST | `/api/calls/outbound` | Place outbound call `{ "phone": "+1..." }` |
| GET/POST | `/api/leads` | Lead list / import |
| GET | `/api/messages` | Dashboard chat messages |
| GET | `/api/calls/{callSid}` | Call session detail |

## Agent modes

- **`inbound_intake`** — missed-call handler: disclose → intake → qualify → book
- **`outbound_lead`** — lead capture dialer with yes-man rapport tactics

## Tests

```bash
python -m pytest donna/telephony/tests/ -v
```

## Related docs

- [docs/voice-telephony-architecture.md](../../docs/voice-telephony-architecture.md)
- [docs/twilio-setup.md](../../docs/twilio-setup.md)
- [donna/VOICE_PIPELINE.md](../VOICE_PIPELINE.md) — local push-to-talk pipeline
