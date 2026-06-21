# Donna — Local-First AI Legal Secretary

Donna is a voice-native AI layer that runs entirely on local hardware. Built for the Dell × NVIDIA hackathon, the demo vertical is **legal client intake**: a prospective client calls → Donna answers autonomously → collects case info via voice → OCR-scans documents → estimates fees → books appointment → emails intake summary to the lawyer. Zero cloud. All runs locally on a Dell GB10.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [System Requirements](#system-requirements)
- [Quick Start (Dell GB10)](#quick-start-dell-gb10)
- [Quick Start (Mac Dev)](#quick-start-mac-dev)
- [Services & Ports](#services--ports)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Voice Pipeline](#voice-pipeline)
- [Telephony (Twilio)](#telephony-twilio)
- [Agent Brain](#agent-brain)
- [Dashboard](#dashboard)
- [Email Server](#email-server)
- [Data Layer](#data-layer)
- [Testing](#testing)
- [Team Ownership](#team-ownership)
- [Remaining Work](#remaining-work)
- [Demo Script (90s)](#demo-script-90s)
- [Docs Index](#docs-index)

---

## Architecture Overview

```
Inbound call (PSTN)
        │
        ▼
  Twilio Media Streams
        │  μ-law audio
        ▼
  donna/telephony/server.py  (FastAPI :3002)
        │
        ├─── STT ──► faster-whisper-server (:9000)
        │
        ├─── LLM ──► Ollama HTTP (:11434)  [nemotron-3-nano / qwen2.5:14b]
        │               │
        │               ├── Tool calls ──► ToolRegistry (SQLite)
        │               └── Session phases: DISCLOSURE → INTAKE → QUALIFICATION → BOOKING → CLOSE
        │
        ├─── TTS ──► Kokoro-FastAPI GPU (:8880) → Piper fallback
        │
        └─── Events ──► WebSocket (:3001) ──► React Dashboard (:7777)


Push-to-talk (local mic)
        │
        ▼
  donna/voice/pipeline.py
        │
        ├── VAD: Silero-VAD + EnergyVAD fallback (800ms silence threshold)
        ├── STT → Ollama → TTS  (same services as above)
        └── Events ──► WebSocket dashboard
```

All inference is local. No cloud API keys required on the hot path.

---

## System Requirements

| Component | Requirement |
|-----------|-------------|
| Hardware | Dell GB10 (`promaxgb10-887e`) or Apple M2/M3 for dev |
| OS | Ubuntu 22.04 (GB10) or macOS 14+ (dev) |
| GPU | NVIDIA (GB10) for Whisper + Kokoro CUDA images |
| Mic | **USB headset required** — stock GB10 has no built-in mic |
| Python | 3.11+ |
| Node.js | 18+ (dashboard only) |
| Docker | 24+ with NVIDIA container toolkit (GB10) |
| Ollama | Running natively at `localhost:11434` (not in Docker) |

---

## Quick Start (Dell GB10)

```bash
# 1. SSH into the box
ssh dell@10.104.77.67
# password: 123456

# 2. Pull latest
cd ~/dell-hack && git pull

# 3. Set up Python venv (first time only)
bash scripts/setup_venv.sh

# 4. Start Docker services (STT, TTS, ChromaDB)
bash scripts/run_dashboard_stack.sh

# 5. Seed demo clients and cases
python3 scripts/seed_demo_unified.py

# 6. Terminal A — push-to-talk voice pipeline
bash scripts/run_voice.sh

# 7. Terminal B — Twilio inbound call server
bash scripts/run_telephony.sh

# 8. Terminal C — React dashboard
cd donna/dashboard && npm install && npm run dev
```

Verify all services are healthy before the demo:

```bash
bash scripts/check_services.sh
```

Full setup and troubleshooting: [docs/dell-gbio-runbook.md](docs/dell-gbio-runbook.md)

---

## Quick Start (Mac Dev)

```bash
# Clone and install
cd donna/
pip install -r requirements.txt

# Run unit tests (all mocked, no services needed)
python -m pytest voice/tests/ -v           # 30/30
python -m pytest telephony/tests/ -v
python -m pytest email_server/tests/ -v

# Run voice pipeline (requires STT + Ollama + TTS running)
python -m donna.voice.pipeline
```

---

## Services & Ports

| Service | Port | How it runs | Notes |
|---------|------|-------------|-------|
| faster-whisper STT | 9000 | Docker (CUDA) | Primary STT |
| speaches STT | 9001 | Docker (CUDA) | Fallback STT |
| Kokoro TTS | 8880 | Docker (CUDA) | GPU TTS |
| Ollama LLM | 11434 | Native binary | Must run outside Docker |
| ChromaDB | 8001 | Docker | Vector search |
| Telephony server | 3002 | FastAPI / uvicorn | Twilio webhook target |
| Dashboard WebSocket | 3001 | Built into telephony server | Silent no-op if down |
| Dashboard UI | 7777 | Vite dev server | React frontend |

Start all Docker services:

```bash
bash scripts/run_dashboard_stack.sh   # start
bash scripts/stop_dashboard_stack.sh  # stop
```

---

## Environment Variables

Copy `.env.example` to `.env` in the repo root and fill in values:

```bash
cp donna/.env.example donna/.env
```

Key variables:

```bash
# LLM
DONNA_OLLAMA_URL=http://localhost:11434
DONNA_MODEL=qwen2.5:14b

# STT
DONNA_STT_URL=http://localhost:9000/v1/audio/transcriptions
DONNA_STT_MODEL=Systran/faster-distil-whisper-large-v3

# TTS
DONNA_KOKORO_URL=http://localhost:8880/v1/audio/speech
DONNA_KOKORO_VOICE=af_heart

# Telephony (Twilio + ngrok)
DONNA_TELEPHONY_PORT=3002
PUBLIC_URL=https://YOUR-NGROK-ID.ngrok-free.app
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx

# Email (inbound IMAP + outbound SMTP)
DONNA_EMAIL_USER=intake@lawfirm.com
DONNA_EMAIL_PASS=app-specific-password
DONNA_SMTP_HOST=smtp.gmail.com
DONNA_SMTP_PORT=587

# Database paths
DONNA_TELEPHONY_DB=data/donna_telephony.sqlite
DONNA_CONTEXT_DB=data/donna_m3_context.sqlite
DONNA_CALENDAR_DB=data/donna_m3_calendar.sqlite
```

Full variable reference: `donna/.env.example` (77 variables).

---

## Project Structure

```
des-moines/
├── donna/                     # All Python source
│   ├── voice/                 # Push-to-talk pipeline
│   ├── telephony/             # Twilio inbound/outbound
│   ├── glue/                  # Shared session router + tool registry
│   ├── tools/                 # Domain tools (intake, calendar, email, cases)
│   ├── email_server/          # IMAP polling + SMTP sending
│   ├── knowledge/             # SQLite queries + ChromaDB vector search
│   ├── vlm/                   # Document ingestion + OCR pipeline
│   ├── dashboard/             # React frontend (Vite + Tailwind)
│   ├── config/                # Security policies
│   ├── docker-compose.yml     # STT, TTS, ChromaDB services
│   ├── requirements.txt       # Python deps
│   └── .env.example           # All env var templates
│
├── agent/                     # Agent brain
│   ├── donna.yaml             # Tool definitions + phase config
│   ├── system_prompt.md       # PI law knowledge base
│   └── Modelfile              # Ollama model definition
│
├── scripts/                   # Utility scripts
│   ├── setup_venv.sh
│   ├── run_voice.sh
│   ├── run_telephony.sh
│   ├── run_dashboard_stack.sh
│   ├── check_services.sh
│   ├── seed_demo_unified.py
│   └── ...
│
├── docs/                      # Architecture + ops guides
├── data/                      # SQLite databases + demo docs
├── gbrain/                    # Optional PGLite vector brain
├── deploy.sh                  # One-shot GB10 deployment
└── README.md
```

---

## Voice Pipeline

Entry point: `donna/voice/pipeline.py`

**Flow:** PyAudio capture → Silero-VAD → faster-whisper STT → Ollama LLM → Kokoro TTS

```
User presses ENTER → PyAudio records 16kHz mono PCM16
                  → Silero-VAD detects end of speech (800ms silence)
                  → STT: faster-whisper at localhost:9000
                  → LLM: Ollama HTTP with streaming
                      → Tool calls dispatched via ToolRegistry
                  → TTS: streamed sentence-by-sentence to Kokoro
                  → Dashboard event emitted over WebSocket
```

Key parameters:
- Sample rate: 16kHz mono PCM16
- Silence threshold: 800ms
- VAD fallback: EnergyVAD (no torch required)
- Interrupt detection: confidence + RMS thresholds

Latency target: **< 4s** round-trip (STT + agent + TTS). GB10 achieves ~3.2s.

Detailed docs: [donna/VOICE_PIPELINE.md](donna/VOICE_PIPELINE.md)

---

## Telephony (Twilio)

Entry point: `bash scripts/run_telephony.sh` → FastAPI server at `:3002`

**Flow:** PSTN call → Twilio Media Streams → WebSocket → FastAPI → STT/LLM/TTS → μ-law audio back to caller

```
Incoming call
    │
    ▼ TwiML: <Connect><Stream url="wss://YOUR_NGROK/media-stream"/>
Twilio sends μ-law audio chunks over WebSocket
    │
    ▼ donna/telephony/local_provider.py
       - Decodes μ-law → PCM16
       - Buffers until STT returns transcript
    │
    ▼ donna/telephony/llm.py  (Ollama chat)
       - Phase-gated tool calls
       - Consent enforcement
    │
    ▼ donna/telephony/server.py
       - Encodes TTS output → μ-law
       - Streams back to Twilio
```

Session phases managed by `donna/glue/router/session_router.py`:

| Phase | Goal | Tools available |
|-------|------|----------------|
| DISCLOSURE | AI & recording consent | `record_consent` |
| INTAKE | Collect caller info | `intake.start`, `intake.update` |
| QUALIFICATION | Assess case viability | `case.qualify` |
| BOOKING | Schedule consultation | `check_calendar_conflicts`, `book_calendar` |
| CLOSE | Confirm + notify lawyer | `notify.dashboard`, email tools |

Setup guide: [docs/twilio-setup.md](docs/twilio-setup.md)  
Architecture deep-dive: [docs/voice-telephony-architecture.md](docs/voice-telephony-architecture.md)

---

## Agent Brain

Configuration: `agent/donna.yaml`

- **Model:** `qwen2.5:14b` (Dell GB10) or `nemotron-3-nano`
- **Temperature:** 0.3
- **Persona:** calm, professional PI law secretary — no filler words, no hallucinated case citations

**Tool categories:**

| Category | Tools |
|----------|-------|
| Consent | `record_consent` |
| Intake | `intake.start`, `intake.update` |
| Case management | `case.qualify`, `case.create`, `case.decline` |
| Calendar | `check_calendar_conflicts`, `book_calendar`, `get_upcoming_events` |
| Case law | `search_case_law`, `analyze_case_weaknesses`, `profile_adverse_adjuster` |
| Context search | `search_context`, `get_case_file`, `list_cases` |
| Paralegal analysis | `check_narrative_consistency`, `score_litigation_risk` |

System prompt includes a 100-line PI law knowledge base covering torts, damages, statute of limitations, key documents, and court terminology.

To customize the Modelfile:

```bash
ollama create donna -f agent/Modelfile
ollama run donna
```

---

## Dashboard

Entry point: `cd donna/dashboard && npm run dev` → `http://localhost:7777`

React 18 + Vite + Tailwind. Connects to the WebSocket at `ws://localhost:3001` and displays:
- Live call status and active phase
- Caller intake data as it's collected
- Case qualification result
- Upcoming calendar events
- Lead pipeline

The WebSocket connection is silent no-op if the server is down — the voice pipeline and telephony server work without it.

---

## Email Server

Entry point: `donna/email_server/server.py` (FastAPI)

**Inbound:** IMAP poller watches `intake@lawfirm.com` for new emails, parses attachments (PDFs, images), routes to the agent for processing.

**Outbound:** After a call completes, `donna/tools/email_sender.py` composes an intake summary and sends it to the lawyer via SMTP.

```
Intake call ends
    │
    ▼ intake summary generated by LLM
    ▼ donna/email_server/sender.py
       → strips tool artifacts from output
       → formats structured intake report
       → sends via SMTP (Gmail app password)
    ▼ Lawyer receives email with: caller name, incident, injuries, case type, booked appointment
```

Approval workflow: `donna/email_server/approval_server.py` — optional human review before sending.

Setup: [donna/email_server/RUN.md](donna/email_server/RUN.md)

---

## Data Layer

### SQLite Databases

| Database | Path | Tables |
|----------|------|--------|
| Context | `data/donna_m3_context.sqlite` | clients, cases, case_notes, documents, facts |
| Calendar | `data/donna_m3_calendar.sqlite` | events, attendees |
| Telephony | `data/donna_telephony.sqlite` | call_sessions, intake_state, leads, messages |

Seed demo data:

```bash
python3 scripts/seed_demo_unified.py
```

### Vector Search (ChromaDB)

Optional — enables semantic case file search. Runs at `:8001` via Docker.

### GBrain (Optional)

Advanced PGLite-backed vector brain for persistent cross-session context. Config: `gbrain/`. Not required for the core demo.

Architecture: [docs/storage-architecture.md](docs/storage-architecture.md)

---

## Testing

All tests are mocked — no live services required.

```bash
# Voice pipeline (30/30)
python3 -m pytest donna/voice/tests/ -v

# Telephony (8 tests)
python3 -m pytest donna/telephony/tests/ -v

# Email server (5 tests)
python3 -m pytest donna/email_server/tests/ -v

# Hardware smoke tests (requires physical setup)
python3 -m donna.voice.pipeline --test-mic    # Record + playback 3s
python3 -m donna.voice.tts                    # Speak "Hello, I'm Donna"
```

Full test matrix and mocking strategy: [docs/testing-runbook.md](docs/testing-runbook.md)

---

## Team Ownership

| Person | Module |
|--------|--------|
| Dhruva | Voice pipeline (`donna/voice/`) |
| Anish | Voice pipeline co-owner |
| Shivansh | DevOps — Docker, Ollama, Dell GB10 infra |
| Aayush | Agent brain (`agent/donna.yaml`, system prompts) |

---

## Remaining Work

| Item | File | Owner |
|------|------|-------|
| OCR document scan | `donna/voice/tools/ocr.py` | — |
| Legal fee estimator | `donna/voice/tools/cost_estimator.py` | — |
| Emailer tool | `donna/voice/tools/emailer.py` | — |
| Wire Twilio handler | `donna/voice/twilio_handler.py` (stub exists) | — |
| Update system prompt | `donna/agent/donna.yaml` | Aayush |
| Demo rehearsal | Full 90s flow end-to-end | Team |
| Latency check | Verify < 4s round-trip on GB10 | Dhruva |
| Service confirmation | Ports 9000, 8880, 11434 on GB10 | Shivansh |

---

## Demo Script (90s)

```bash
# Pre-demo: seed data and verify services
python3 scripts/seed_demo_unified.py
bash scripts/check_services.sh

# Terminal 1: start voice pipeline
bash scripts/run_voice.sh
# → "Press ENTER to speak"

# Terminal 2: start Twilio server (for call demo)
bash scripts/run_telephony.sh

# Terminal 3: dashboard
cd donna/dashboard && npm run dev
# → open http://localhost:7777

# Demo flow:
# 1. Call the Twilio number
# 2. Donna answers, delivers AI disclosure, gets consent
# 3. Donna collects: name, incident date, injury summary
# 4. Donna qualifies the case (PI check)
# 5. Donna books a consultation slot
# 6. Lawyer receives intake summary email
# 7. Dashboard shows live call state throughout

# Key demo point: ALL LOCAL — no cloud keys, no data leaves GB10
```

---

## Docs Index

| Doc | Purpose |
|-----|---------|
| [docs/dell-gbio-runbook.md](docs/dell-gbio-runbook.md) | **START HERE** — SSH, venv, audio, confirmed GB10 state |
| [docs/dell-gbio-access.md](docs/dell-gbio-access.md) | SSH ports, firewall, troubleshooting |
| [docs/hackathon-quickstart.md](docs/hackathon-quickstart.md) | Module map, day-of startup order |
| [docs/testing-runbook.md](docs/testing-runbook.md) | All test commands and mocking strategy |
| [docs/voice-telephony-architecture.md](docs/voice-telephony-architecture.md) | Dataflow: PSTN → WebSocket → Ollama |
| [docs/twilio-setup.md](docs/twilio-setup.md) | Twilio account + ngrok + `.env` config |
| [docs/storage-architecture.md](docs/storage-architecture.md) | SQLite vs. OpenClaw vs. GBrain |
| [docs/donna-brain-schema.md](docs/donna-brain-schema.md) | GBrain markdown layout |
| [docs/email-server-context.md](docs/email-server-context.md) | IMAP inbound + SMTP outbound architecture |
| [docs/m3-glue-layer-plan.md](docs/m3-glue-layer-plan.md) | Tool registry, context bridge, session router |
| [docs/dell-ssh-agent-prompt.md](docs/dell-ssh-agent-prompt.md) | Copy-paste system prompt for SSH agent on GB10 |
| [donna/VOICE_PIPELINE.md](donna/VOICE_PIPELINE.md) | Detailed voice pipeline documentation |
| [donna/telephony/README.md](donna/telephony/README.md) | Telephony architecture and setup |
