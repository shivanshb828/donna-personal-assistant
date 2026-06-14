# Donna — Project Context for Claude

## What is this

Donna is a voice-native AI layer at the OS level. Not a chatbot, not a vertical app — an AI that sits on the OS and orchestrates real workflows using local tools (voice, file I/O, email, calendar, OCR, browser).

**Demo vertical: legal client intake.** Prospective client calls → Donna answers autonomously → collects case info via voice → OCR-scans documents → estimates fees → books appointment → emails intake summary to lawyer. Zero cloud. All runs locally on Dell GB10.

## Current state (June 14 2026)

Voice pipeline on Dell GB10 (`promaxgb10-887e`):
- Branch `integrate-dafely-from-pr` — STT → SQLite context → **Ollama direct** → TTS
- Setup: `bash scripts/setup_venv.sh` + `bash scripts/run_voice.sh` from `~/dell-hack`
- **No built-in mic** on stock GB10 — USB headset required
- Full handoff: [docs/dell-gbio-runbook.md](docs/dell-gbio-runbook.md)

Unit tests: `cd donna && python3 -m pytest voice/tests/ -v` (30/30 mocked)

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
- Agent: **Ollama direct** (`nemotron-3-super` on Dell); OpenClaw optional for M2
- Dashboard: WebSocket ws://localhost:3001, silent no-op if down
- Twilio = inbound call entry point (demo centerpiece, not stretch)
- OS extension framing: Donna runs OS-level tools locally on Dell GB10 — privacy/speed angle

## Tech stack

| Layer | Tech |
|-------|------|
| Voice capture | PyAudio 16kHz mono PCM16 |
| VAD | Silero-VAD + EnergyVAD fallback |
| STT | faster-whisper-server (OpenAI-compatible API) |
| Agent | Ollama HTTP (`nemotron-3-super` on GB10) |
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

**Dell GB10:** see [docs/dell-gbio-runbook.md](docs/dell-gbio-runbook.md)

```bash
cd ~/dell-hack
bash scripts/setup_venv.sh
bash scripts/run_voice.sh
```

**Dev / Mac:**

```bash
cd donna/
python -m pytest voice/tests/ -v
python -m donna.voice.pipeline
```
