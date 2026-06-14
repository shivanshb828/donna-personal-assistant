# Donna Voice Pipeline

Local, zero-cloud voice interface for Donna — PI attorney AI assistant.
Built for Dell x NVIDIA Hackathon, June 14 2026.

## Architecture

```
[Enter key]
    ↓
Microphone (PyAudio, 16kHz mono PCM16)
    ↓
VAD — Silero-VAD (energy fallback) — auto-stops on 800ms silence
    ↓
STT — faster-whisper-server (localhost:9000, OpenAI-compatible)
    ↓
M3 context lookup — optional SQLite seed DB (data/donna_m3_context.sqlite)
    ↓
Ollama (nemotron-3-super on Dell GB10)
    ↓
TTS — Kokoro-FastAPI (localhost:8880) → Piper fallback
    ↓
Speaker (PyAudio playback)
    ↓
Dashboard WebSocket (localhost:3001) — status + transcript events
```

## Files

| File | Role |
|------|------|
| `voice/vad.py` | Voice activity detection — Silero-VAD + energy fallback |
| `voice/stt.py` | Speech-to-text via faster-whisper-server |
| `voice/tts.py` | Text-to-speech — Kokoro primary, Piper fallback |
| `voice/wake_word.py` | Push-to-talk (keyboard) now; openwakeword stub for later |
| `voice/pipeline.py` | Main async loop — push-to-talk mode |
| `voice/dashboard_bridge.py` | WebSocket event emitter |
| `fake_dashboard.py` | Dev tool — prints pipeline events in terminal |

## Setup

**Ubuntu / Dell GB10 (required — system pip is blocked on 24.04):**

```bash
cd ~/dell-hack
git pull
bash scripts/setup_venv.sh
source .venv/bin/activate
```

Or use wrapper scripts (auto-activate venv):

```bash
bash scripts/run_fake_dashboard.sh   # terminal 1
bash scripts/run_voice.sh              # terminal 2
```

**macOS:**

```bash
brew install portaudio
python3 -m venv .venv && source .venv/bin/activate
pip install -r donna/requirements.txt
```

Optional services:

```bash
# Kokoro TTS (usually already running in Docker on Dell)
docker pull ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.2
docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.2

# Piper binary fallback
pip install piper-tts
piper --update-voices --model en_US-amy-medium
```

## Run

**Dell / Ubuntu — use venv wrappers from repo root:**

```bash
bash scripts/run_fake_dashboard.sh   # terminal 1 (optional)
bash scripts/run_voice.sh            # terminal 2
```

**Or with venv activated (`source .venv/bin/activate`):**

**Terminal 1 — fake dashboard (dev only):**
```bash
python donna/fake_dashboard.py
```

**Terminal 2 — voice pipeline:**
```bash
cd donna && python -m voice.pipeline
```

Press **ENTER** to speak. Donna auto-stops when you go silent (~800ms).

## Env Vars

| Variable | Default | Description |
|----------|---------|-------------|
| `DONNA_STT_URL` | `http://localhost:9000/v1/audio/transcriptions` | STT server |
| `DONNA_STT_MODEL` | `Systran/faster-distil-whisper-large-v3` | Whisper model |
| `DONNA_KOKORO_URL` | `http://localhost:8880/v1/audio/speech` | Kokoro TTS |
| `DONNA_KOKORO_VOICE` | `af_heart` | Kokoro voice |
| `DONNA_PIPER_MODEL` | `en_US-amy-medium` | Piper voice model |
| `DONNA_OLLAMA_URL` | `http://localhost:11434/api/generate` | Ollama endpoint |
| `DONNA_MODEL` | `nemotron-3-super` on Dell GB10; `nemotron` elsewhere | Ollama model name |
| `DONNA_CONTEXT_DB` | `data/donna_m3_context.sqlite` | Local SQLite DB for case context lookup |
| `DONNA_DASHBOARD_WS` | `ws://localhost:3001` | Dashboard WebSocket |
| `DONNA_WAKEWORD_MODEL` | *(unset)* | Custom ONNX wake word model path |

## Smoke Tests

```bash
# Unit tests (no hardware needed — all mocked)
python -m pytest donna/voice/tests/ -v   # 30/30

# Hardware smoke tests
python -m voice.pipeline --test-mic  # record 3s → play back
python -m voice.tts                  # speaks "Hello, I'm Donna"
python -m voice.stt                  # records 5s → transcribes (needs STT server)

# Full loop (push-to-talk)
python -m voice.pipeline
```

## Wake Word (deferred)

Wake word is not yet connected. Current mode: **push-to-talk (Enter key)**.

To enable audio wake word when ready:
```bash
pip install openwakeword
export DONNA_WAKEWORD_MODEL=/path/to/hey_donna.onnx
# Then in pipeline.py: replace input() with wake_word detection loop
```

Built-in fallback model: `hey_jarvis` (closest phoneme match to "Hey Donna").

## Dashboard Events

Events emitted to `ws://localhost:3001`:

```json
{"type": "pipeline_status", "status": "ready|listening|processing|speaking", "ts": 1234}
{"type": "user_speech", "text": "I was in an accident last week", "ts": 1234}
{"type": "donna_speech", "text": "I can help with that. What date did the accident occur?", "ts": 1234}
```

## Service Dependencies

| Service | Port | Who starts it |
|---------|------|---------------|
| faster-whisper-server | 9000 | Shivansh (Docker on Dell GBIO) |
| Kokoro-FastAPI | 8880 | Shivansh (Docker) |
| Ollama + Nemotron 120B | 11434 | Shivansh (after `ollama pull nemotron`) |
| React dashboard | 3001 | Dhruva (`npm run dev`) |
