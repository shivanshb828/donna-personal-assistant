# Donna Voice Pipeline

Local, zero-cloud voice interface for Donna — AI OS extension for legal intake.
Built for Dell x NVIDIA Hackathon, June 14 2026.

Donna answers inbound client calls autonomously (via Twilio), runs the full intake
flow over voice, and hands the lawyer a structured email summary. All compute runs
locally on Dell GB10 — no audio or case data leaves the machine.

See `README.md` for product overview and demo script.

Push-to-talk and telephony now share the same local voice brain:
`SessionRouter + ToolRegistry + SQLite state`. The only channel-specific pieces are
audio transport and user I/O.

## Architecture

```
[Enter key]
    ↓
Microphone (PyAudio, 16kHz mono PCM16)
    ↓
VAD — Silero-VAD (energy fallback) — default 10-12 silence frames, env-tunable
    ↓
STT — active runtime on `:9000`, Speaches validation sidecar on `:9001`
    ↓
SessionRouter (`local_assistant` mode)
    ↓
ToolRegistry + SQLite state (`data/donna_telephony.sqlite`)
    ↓
M3 context lookup / case context (`data/donna_m3_context.sqlite`)
    ↓
Ollama (`qwen2.5:14b` on Dell GB10, request keep-alive enabled)
    ↓
TTS — Kokoro-FastAPI GPU `v0.5.0` (localhost:8880) → Piper fallback
    ↓
Speaker (PyAudio playback)
    ↓
Dashboard WebSocket (localhost:3001) — status + transcript events
```

## Files

| File | Role |
|------|------|
| `voice/vad.py` | Voice activity detection — Silero-VAD + energy fallback |
| `voice/stt.py` | Speech-to-text batch path + streaming STT entrypoint |
| `voice/tts.py` | Text-to-speech — sentence queue over Kokoro primary, Piper fallback |
| `voice/wake_word.py` | Push-to-talk (keyboard) now; openwakeword stub for later |
| `voice/pipeline.py` | Push-to-talk adapter over the shared router/tool brain |
| `voice/dashboard_bridge.py` | WebSocket event emitter |
| `fake_dashboard.py` | Dev tool — prints pipeline events in terminal |
| `glue/router/session_router.py` | Shared local Nano brain for mic + telephony |
| `glue/tools/registry.py` | Shared intake / qualify / case / booking tools |

## Setup

**Ubuntu / Dell GB10 (required — system pip is blocked on 24.04):**

```bash
cd ~/dell-hack
git pull
bash scripts/setup_venv.sh          # minimal deps — no torch (energy VAD fallback)
bash scripts/run_voice.sh
```

Use `bash scripts/setup_venv.sh --full` only if you need Silero-VAD / torch (large download).

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
docker pull ghcr.io/remsky/kokoro-fastapi-gpu:v0.5.0
docker run --gpus all -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-gpu:v0.5.0

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
cd ~/dell-hack && bash scripts/run_voice.sh
# or: python -m donna.voice.pipeline  (from repo root, venv active)
```

Press **ENTER** to speak. Donna auto-stops when you go silent (~320-384ms by default).

## Audio on Dell GB10 (confirmed)

**No built-in microphone** on hackathon GB10 boxes (`arecord -l` empty). Playback is HDMI-only unless you add USB audio.

| Symptom | Cause / fix |
|---------|-------------|
| Pipeline starts, nothing transcribed | Plug **USB mic/headset**; verify with `arecord -l` |
| ALSA / JACK warnings | Harmless — ignore |
| `[VAD] Silero failed ... energy VAD` | Expected without torch |
| No speaker output | HDMI only — connect display/speaker or USB audio |

See [docs/dell-gbio-runbook.md](../docs/dell-gbio-runbook.md) for port-forward + Mac mic option.

## Env Vars

| Variable | Default | Description |
|----------|---------|-------------|
| `DONNA_STT_URL` | `http://localhost:9000/v1/audio/transcriptions` | STT server |
| `DONNA_STT_MODEL` | `Systran/faster-distil-whisper-large-v3` | Whisper model |
| `DONNA_KOKORO_URL` | `http://localhost:8880/v1/audio/speech` | Kokoro TTS |
| `DONNA_KOKORO_VOICE` | `af_heart` | Kokoro voice |
| `DONNA_PIPER_MODEL` | `en_US-amy-medium` | Piper voice model |
| `DONNA_OLLAMA_URL` | `http://localhost:11434` | Ollama base URL |
| `DONNA_MODEL` | `qwen2.5:14b` on Dell GB10 | Ollama model name |
| `DONNA_OLLAMA_KEEP_ALIVE` | `-1` | Request-level Ollama residency override |
| `DONNA_VAD_SILENCE_FRAMES` | `12` (`10` for push-to-talk) | End-of-turn silence threshold |
| `DONNA_ENABLE_STREAMING_LLM` | `true` | Stream Ollama chat responses |
| `DONNA_ENABLE_STREAMING_TTS` | `true` | Synthesize/play sentence chunks as they arrive |
| `DONNA_ENABLE_STREAMING_STT` | `false` | Enable streaming STT experiments |
| `DONNA_CONTEXT_DB` | `data/donna_m3_context.sqlite` | Local SQLite DB for case context lookup |
| `DONNA_TELEPHONY_DB` | `data/donna_telephony.sqlite` | Shared session/intake state for mic + phone |
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
python -m donna.voice.pipeline --text "How is Maria Lopez doing?"

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
{"type": "pipeline_status", "status": "ready|listening|processing|speaking", "callSid": "local-...", "sessionId": "local-...", "ts": 1234}
{"type": "user_speech", "text": "I was in an accident last week", "callSid": "local-...", "sessionId": "local-...", "ts": 1234}
{"type": "donna_speech", "text": "I can help with that.", "callSid": "local-...", "sessionId": "local-...", "ts": 1234}
{"type": "tool_result", "callSid": "local-...", "sessionId": "local-...", "tool": "intake.start", "ok": true}
{"type": "turn_timing", "callSid": "local-...", "first_token_seconds": 0.42, "first_sentence_seconds": 0.88, "first_audio_seconds": 1.21, "tts_total_seconds": 1.94, "interrupted": false}
{"type": "call_started", "callSid": "CA...", "callerPhone": "+1...", "agentMode": "inbound_intake"}
{"type": "tool_result", "callSid": "CA...", "tool": "intake.start", "ok": true}
{"type": "call_ended", "callSid": "CA...", "duration": 120, "outcome": "BOOKING"}
```

Telephony events are emitted by `donna/telephony/local_provider.py` via the same WebSocket bridge.

## Service Dependencies

| Service | Port | Who starts it |
|---------|------|---------------|
| Active STT runtime | 9000 | Docker on Dell GB10 |
| Speaches validation sidecar | 9001 | Docker on Dell GB10 |
| Kokoro-FastAPI | 8880 | Docker on Dell GB10 |
| Ollama + qwen2.5:14b | 11434 | `ollama pull qwen2.5:14b` |
| React dashboard | 3001 | Dhruva (`npm run dev`) |
| **Donna telephony (Twilio)** | **3002** | **`bash scripts/run_telephony.sh`** |
