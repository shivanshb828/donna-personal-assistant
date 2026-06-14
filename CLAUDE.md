# Donna — Project Context for Claude

## What is this

Donna is a voice-native AI layer at the OS level. Not a chatbot, not a vertical app — an AI that sits on the OS and orchestrates real workflows using local tools (voice, file I/O, email, calendar, OCR, browser).

**Demo vertical: legal client intake.** Prospective client calls → Donna answers autonomously → collects case info via voice → OCR-scans documents → estimates fees → books appointment → emails intake summary to lawyer. Zero cloud. All runs locally on Dell GB10.

## Current state (June 14 2026)

Voice pipeline: **done**, committed at `c5995f5` on `origin/main`.
- Code in `donna/voice/`
- 30/30 unit tests pass: `python -m pytest donna/voice/tests/ -v`
- Push-to-talk mode (Enter key) working end-to-end

## Remaining work

1. `donna/voice/tools/ocr.py` — OCR document scan (Tesseract or pytesseract)
2. `donna/voice/tools/cost_estimator.py` — legal fee estimation (rule-based + LLM)
3. `donna/voice/tools/emailer.py` — send intake summary email to lawyer
4. Wire Twilio handler (`donna/voice/twilio_handler.py` stub exists) — inbound call entry point
5. Update `donna/agent/donna.yaml` system prompt → legal intake persona (Aayush owns)
6. Demo rehearsal — 90s flow (see README demo script)
7. Latency check — target <4s round-trip STT + agent + TTS on GB10
8. Services confirm with Shivansh: ports 9000 (whisper), 8880 (kokoro), 11434 (ollama)

## Key decisions already made

- Push-to-talk (Enter) now; wake word deferred
- Kokoro-FastAPI port 8880 as primary TTS (GPU); Piper fallback
- STT: faster-whisper at localhost:9000, model `Systran/faster-distil-whisper-large-v3`
- VAD: Silero-VAD + EnergyVAD fallback, 800ms silence threshold
- Agent: OpenClaw CLI first, Ollama/nemotron fallback
- Dashboard: WebSocket ws://localhost:3001, silent no-op if down
- Twilio = inbound call entry point (demo centerpiece, not stretch)
- OS extension framing: Donna runs OS-level tools locally on Dell GB10 — privacy/speed angle

## Tech stack

| Layer | Tech |
|-------|------|
| Voice capture | PyAudio 16kHz mono PCM16 |
| VAD | Silero-VAD + EnergyVAD fallback |
| STT | faster-whisper-server (OpenAI-compatible API) |
| Agent | OpenClaw CLI → Ollama nemotron 120B |
| TTS | Kokoro-FastAPI (GPU) → Piper |
| Inbound calls | Twilio Media Streams |
| Dashboard | WebSocket + React |
| OCR | pytesseract (to implement) |
| Email | smtplib or sendgrid (to implement) |

## Team split

- Dhruva: voice pipeline, integration, demo
- Shivansh: DevOps — services on Dell GBIO
- Aayush: agent brain + tools (`donna.yaml`)
- Anish: voice pipeline co-owner

## Run commands

```bash
cd donna/
python -m pytest voice/tests/ -v         # unit tests (no hardware)
python fake_dashboard.py &               # dev dashboard
python -m voice.pipeline                 # push-to-talk mode
```
