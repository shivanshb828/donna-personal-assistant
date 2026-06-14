# Donna Testing Runbook

Single reference for validating Donna across M3 glue, voice, and Dell services. Run from repo root unless noted.

## Quick smoke (no hardware, ~15s)

```bash
python3 -m unittest discover -s tests -v
cd donna && python3 -m pytest voice/tests/ telephony/tests/ -v
```

Expected: **5** unittest cases, **54** pytest cases (voice + telephony mocked — no mic/STT/Twilio required).

## M3 glue layer

Initialize seed SQLite DBs:

```bash
python3 scripts/init_m3_test_db.py
```

Context lookup:

```bash
python3 scripts/context_lookup.py Maria
python3 scripts/context_lookup.py Andre
```

Calendar tool:

```bash
python3 scripts/calendar_tool.py search_events --input '{"case_id":"case-2026-001"}'

python3 scripts/calendar_tool.py create_event --input '{
  "title": "Client follow-up",
  "start": "2026-06-19T10:00:00-07:00",
  "end": "2026-06-19T10:30:00-07:00",
  "attendee": "Maria Lopez",
  "case_id": "case-2026-001",
  "notes": "Ask for insurance claim number."
}'
```

## Voice pipeline (Mac or Dell)

**Dell GB10:** use [dell-gbio-runbook.md](dell-gbio-runbook.md) — `setup_venv.sh` + `run_voice.sh` from repo root. Stock box has **no mic**.

**macOS:**

```bash
brew install portaudio
python3 -m venv .venv && source .venv/bin/activate
pip install -r donna/requirements.txt
```

Unit tests:

```bash
cd donna && python3 -m pytest voice/tests/ -v
```

Hardware / integration smoke (Dell — from repo root, venv active):

```bash
bash scripts/run_voice.sh
python -m donna.voice.pipeline --test-mic
```

Hardware / integration smoke (macOS — from `donna/`):

```bash
cd donna
python3 -m voice.pipeline --test-mic
python3 -m voice.tts
python3 -m voice.stt
python3 fake_dashboard.py
python3 -m voice.pipeline
```

With M3 context injection (repo root, seed DB present):

```bash
bash scripts/run_voice.sh
# Say "How is Maria doing?" — expect [Loaded case context from local DB]
```

## Telephony (Twilio bridge)

Unit tests (no Twilio/ngrok):

```bash
cd donna && python3 -m pytest telephony/tests/ -v
```

Local server smoke:

```bash
bash scripts/run_telephony.sh
curl http://localhost:3002/health
```

Echo mode (Twilio loopback, no STT/LLM):

```bash
DONNA_TELEPHONY_ECHO=true bash scripts/run_telephony.sh
```

See [twilio-setup.md](twilio-setup.md) for ngrok + Twilio console wiring.

## Dell service health

On the Dell (or via SSH):

```bash
bash scripts/check_services.sh
```

All checks should print `OK`. Any `FAIL` means that layer of the demo stack is down.

## End-to-end demo checklist

Use before pitching or recording a demo:

- [ ] `check_services.sh` — STT, TTS, Ollama OK (dashboard :3001 optional)
- [ ] `arecord -l` lists a device if demo needs on-box mic (stock GB10: empty)
- [ ] `context_lookup.py Maria` — returns case hits
- [ ] `bash scripts/run_voice.sh` — full push-to-talk loop
- [ ] Mentioning "Maria" triggers `[Loaded case context from local DB]`

## CI / future automation

There is no GitHub Actions workflow yet. Minimum bar before merge:

```bash
python3 -m unittest discover -s tests
cd donna && python3 -m pytest voice/tests/ telephony/tests/ -q
```

Optional on Dell with services running:

```bash
bash scripts/check_services.sh
```

## Related docs

- [M2 testing tools](m2-testing-tools.md) — JSON CLI shapes for OpenClaw stubs
- [GBrain + OpenClaw setup](gbrain-openclaw-setup.md) — optional synthesis layer
- [Storage architecture](storage-architecture.md) — SQLite roles (M3, OpenClaw, GBrain)
- [Dell GB10 runbook](dell-gbio-runbook.md) — **start here for new workspaces**
- [Dell GBIO access](dell-gbio-access.md) — SSH and port forwarding
- [Hackathon quickstart](hackathon-quickstart.md) — team roles and module map
- [Voice pipeline](../donna/VOICE_PIPELINE.md) — architecture and env vars
- [Telephony](../donna/telephony/README.md) — Twilio phone agent
- [Twilio setup](twilio-setup.md)
