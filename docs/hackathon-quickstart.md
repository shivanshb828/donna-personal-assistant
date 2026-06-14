# Hackathon Quickstart

**Event:** Dell x NVIDIA Hackathon — Local AI on Dell Pro Max with GB10  
**Date:** Sunday, June 14, 2026  
**Location:** Entrepreneurs First, 501 Folsom St, San Francisco  
**Repo:** [shivanshb828/dell-hack](https://github.com/shivanshb828/dell-hack)

## What we're building

**Donna** — a local-first AI legal secretary for personal injury attorneys. Runs entirely on the Dell GB10 box: voice intake, case context, calendar scheduling, and agent responses with no cloud dependency for the demo.

## Module map

| Module | Owns | Status in repo |
|--------|------|----------------|
| **M1** | IPC envelope, iMessage bridge | Planned |
| **M2** | OpenClaw agent + SQLite memory index | `openclaw run donna` — see [storage-architecture.md](storage-architecture.md) |
| **M3** | Glue tools, SQLite context/calendar | Partial — seed DBs + CLIs + context bridge |
| **M4** | Voice pipeline (STT/VAD/TTS) | Implemented — push-to-talk |

## Team service ownership

| Person | Responsibility |
|--------|----------------|
| **Shivansh** | Docker: faster-whisper (:9000), Kokoro TTS (:8880), Ollama/Nemotron (:11434) on Dell |
| **Aayush** | OpenClaw agent, **GBrain** brain, M3 tool wiring |
| **Dhruva** | React dashboard WebSocket (:3001) |

## Day-of startup order

1. SSH to Dell — [dell-gbio-runbook.md](dell-gbio-runbook.md) · `ssh dell@10.104.77.67`
2. Clone repo if needed: `git clone … && cd dell-hack && git checkout integrate-dafely-from-pr`
3. Inference stack should already be up (Shivansh): STT :9000, TTS :8880, Ollama :11434
4. `bash scripts/setup_venv.sh` then `bash scripts/run_voice.sh` (from `~/dell-hack`)
5. **Plug USB mic** — stock GB10 has no built-in capture device
6. Optional: `bash scripts/run_fake_dashboard.sh` (dashboard :3001 not running)
7. `bash scripts/check_services.sh` — STT/TTS/Ollama should be OK
8. Seed DBs if needed: `python3 scripts/init_m3_test_db.py`

Voice path: **SQLite context → Ollama direct** (no OpenClaw hop). Energy VAD without torch is expected.

## Branches (June 14, 2026)

| Branch | Contents |
|--------|----------|
| `main` | Voice pipeline baseline |
| `integrate-dafely-from-pr` | M3 scaffold merged + voice context bridge |
| `codex/m3-test-db-calendar` | Original M3 PR (superseded by integration branch) |

Target merge: `integrate-dafely-from-pr` → `main`.

## New Conductor workspace?

1. **[dell-gbio-runbook.md](dell-gbio-runbook.md)** — confirmed GB10 setup (read first)
2. This file and [testing-runbook.md](testing-runbook.md)
3. `.context/README.md` if present for workspace-specific notes
4. `bash scripts/check_services.sh` on Dell after SSH

## Demo script (2 min)

1. "Donna, how is Maria Lopez doing?" — context from seed DB informs response
2. Show dashboard transcript events
3. Run `python3 scripts/calendar_tool.py search_events --input '{"case_id":"case-2026-001"}'`
4. Emphasize: all local, no cloud API keys in the hot path
