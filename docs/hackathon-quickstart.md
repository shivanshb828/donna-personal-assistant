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

1. SSH to Dell — see [dell-gbio-access.md](dell-gbio-access.md)
2. Start inference stack (Shivansh): STT → TTS → Ollama
3. Start **GBrain + OpenClaw** (Aayush): `gbrain serve` + `openclaw run donna` — [gbrain-openclaw-setup.md](gbrain-openclaw-setup.md)
4. Pull latest repo branch with voice + M3 integration
5. Seed test DBs: `python3 scripts/init_m3_test_db.py`
6. Export to OpenClaw memory: `python3 scripts/export_openclaw_memory.py`
7. Optional GBrain (Aayush): `gbrain serve` — [gbrain-openclaw-setup.md](gbrain-openclaw-setup.md)
8. Start dashboard (Dhruva): `npm run dev` on port 3001
9. Start fake dashboard if React not ready: `python3 donna/fake_dashboard.py`
10. Run health check: `bash scripts/check_services.sh`
11. Launch voice: `cd donna && python3 -m voice.pipeline`

## Branches (June 14, 2026)

| Branch | Contents |
|--------|----------|
| `main` | Voice pipeline baseline |
| `integrate-dafely-from-pr` | M3 scaffold merged + voice context bridge |
| `codex/m3-test-db-calendar` | Original M3 PR (superseded by integration branch) |

Target merge: `integrate-dafely-from-pr` → `main`.

## New Conductor workspace?

1. Read this file and [testing-runbook.md](testing-runbook.md)
2. Check `.context/README.md` if present for workspace-specific notes
3. Run unit tests before touching voice hardware
4. SSH to Dell using [dell-gbio-access.md](dell-gbio-access.md)

## Demo script (2 min)

1. "Donna, how is Maria Lopez doing?" — context from seed DB informs response
2. Show dashboard transcript events
3. Run `python3 scripts/calendar_tool.py search_events --input '{"case_id":"case-2026-001"}'`
4. Emphasize: all local, no cloud API keys in the hot path
