# Donna — AI OS Extension

**Dell x NVIDIA Hackathon, June 14 2026**

Donna is a voice-native AI layer that sits at the OS level and orchestrates any workflow on the machine. All compute runs locally on Dell GB10 hardware — no cloud, no data leaves the device.

**Demo vertical: legal client intake.** A prospective client calls a law firm. Donna answers, handles the full intake autonomously — collects case details via voice, OCR-scans documents the client sends, estimates legal fees, books an appointment, and emails a structured intake summary to the lawyer. The lawyer never picks up the phone.

This is not a chatbot. Donna is an AI that uses OS-level tools (voice, file I/O, email, calendar, browser) to complete real workflows end-to-end.

---

## Architecture

```
[Inbound call / Push-to-talk]
    ↓
Twilio Media Streams OR Enter key (push-to-talk)
    ↓
Microphone → VAD (Silero + energy fallback, 800ms silence)
    ↓
STT — faster-whisper-server (localhost:9000)
    ↓
Agent — OpenClaw CLI → Ollama/nemotron 120B fallback
    ↓                    ↑
    └── Tools ───────────┘
         • schedule_appointment(date, time)
         • send_email(to, subject, body)
         • ocr_document(file_path)          ← new
         • estimate_case_cost(case_type)    ← new
         • lookup_case_law(query)
    ↓
TTS — Kokoro-FastAPI (localhost:8880, GB10 GPU) → Piper fallback
    ↓
Speaker / Twilio audio stream
    ↓
Dashboard WebSocket (localhost:3001) — live status + transcript
```

---

## Repo Structure

```
donna/
  voice/
    pipeline.py          # Main async loop (push-to-talk + Twilio modes)
    vad.py               # Voice activity detection
    stt.py               # Speech-to-text
    tts.py               # Text-to-speech
    wake_word.py         # Push-to-talk now; openwakeword stub for later
    dashboard_bridge.py  # WebSocket event emitter
    twilio_handler.py    # Inbound call handling (Twilio Media Streams)
    tools/
      scheduler.py       # Calendar booking
      emailer.py         # Send intake summary to lawyer
      ocr.py             # Document OCR scan          ← new
      cost_estimator.py  # Legal fee estimation       ← new
  agent/
    donna.yaml           # OpenClaw agent config (Aayush)
  fake_dashboard.py      # Dev tool — terminal WS server
  VOICE_PIPELINE.md      # Full voice pipeline docs
```

---

## Demo Script (90 seconds)

1. Prospective client calls Donna's Twilio number
2. Donna answers: "Law Office of [Firm], how can I help you today?"
3. Client describes accident — Donna asks structured intake questions
4. Client says "I'm sending you a photo of the police report"
5. Donna OCR-scans → extracts key facts → confirms aloud
6. Donna estimates fee range: "Contingency cases like this typically run 33%..."
7. Donna books appointment: "I have Thursday at 2pm available for Attorney Smith"
8. Donna emails intake summary to lawyer — confirms: "You're all set. Check your email."
9. Show OpenShell: zero outbound network calls. Everything ran locally on Dell GB10.

---

## Team

| Person | Owns |
|--------|------|
| Dhruva | Voice pipeline, integration, demo |
| Shivansh | DevOps — all services on Dell GBIO |
| Aayush | Agent brain (`donna.yaml`), tools |
| Anish | Voice pipeline (co-owner) |

---

## Services (Shivansh starts these on Dell GBIO)

| Service | Port | Command |
|---------|------|---------|
| faster-whisper-server | 9000 | Docker |
| Kokoro-FastAPI | 8880 | Docker |
| Ollama + Nemotron 120B | 11434 | `ollama pull nemotron` |
| OpenClaw agent | — | `openclaw run donna` (Aayush) |
| React dashboard | 3001 | `npm run dev` (Dhruva) |

---

## Current State (as of June 14 11:33 PDT)

Voice pipeline: **done and committed** (`c5995f5` on `origin/main`).
- 7 source files + 5 test files
- 30/30 unit tests pass (no hardware needed)
- Push-to-talk mode working end-to-end

**Remaining:**
1. OCR tool (`donna/voice/tools/ocr.py`)
2. Cost estimator tool (`donna/voice/tools/cost_estimator.py`)
3. Email tool (`donna/voice/tools/emailer.py`)
4. Twilio handler wire-up (stub exists at `voice/twilio_handler.py`)
5. Update `donna.yaml` system prompt → legal intake persona
6. Demo rehearsal — 90s flow
7. Latency check — target <4s round-trip on GB10
8. Services confirm with Shivansh (ports 9000, 8880, 11434)

---

## Quick Start

```bash
cd donna/

# Unit tests (no hardware)
python -m pytest voice/tests/ -v

# Dev mode (push-to-talk)
python fake_dashboard.py &   # terminal dashboard
python -m voice.pipeline     # press Enter to speak
```

See `donna/VOICE_PIPELINE.md` for full env vars, service deps, and smoke tests.
