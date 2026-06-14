# DONNA — The AI Legal Secretary

**The Donna they never had.**

Local-first AI legal secretary for personal injury law firms. Runs entirely on Dell GBIO (GB10). Zero data leaves the machine. Attorney-client privilege enforced at the OS level.

## Quick Start (on Dell GBIO)

```bash
# 1. Install NemoClaw (installs OpenClaw + OpenShell + Ollama)
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash

# 2. Pull the model (~87GB — start this first)
ollama pull nemotron:120b

# 3. Install Python deps
cd donna && pip install -r requirements.txt

# 4. Start everything
bash scripts/start-donna.sh
```

Then say **"Hey Donna"** and start talking.

## Architecture

```
Microphone → Wake Word → Whisper STT → Nemotron 120B (Ollama) → Kokoro TTS → Speaker
                                              ↓ tool calls
                                     SQLite + ChromaDB
                                              ↓
                                     React Dashboard :3000
```

All processing local. OpenShell blocks all outbound network.

## Team

| Person | Role |
|--------|------|
| Dhruva | Knowledge DB + Integration + Demo |
| Shivansh | NemoClaw DevOps + OpenClaw setup |
| Aayush | OpenClaw Agent brain + Tools |
| Anish | Voice Pipeline (STT + TTS + Wake Word) |

## Stack

- **LLM**: Nemotron 3 Super 120B via Ollama
- **STT**: Faster-Whisper (large-v3-turbo)
- **TTS**: Kokoro-FastAPI
- **VAD**: silero-vad
- **Wake Word**: openwakeword
- **Agent**: OpenClaw
- **Security**: NVIDIA OpenShell
- **DB**: SQLite + ChromaDB
- **Dashboard**: React + Vite

Built with NVIDIA NemoClaw + OpenClaw + Dell GBIO
