# Donna Testing Runbook

Single reference for validating Donna across M3 glue, voice, and Dell services. Run from repo root unless noted.

## Quick smoke (no hardware, ~15s)

```bash
python3 -m unittest discover -s tests -v
cd donna && python3 -m pytest voice/tests/ -v
```

Expected: **4** unittest cases, **30** pytest cases (all mocked — no mic/STT server required).

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

## Voice pipeline (local Mac or Dell)

Install deps once:

```bash
cd donna
pip install -r requirements.txt
brew install portaudio   # macOS only
```

Unit tests:

```bash
cd donna && python3 -m pytest voice/tests/ -v
```

Hardware / integration smoke:

```bash
cd donna
python3 -m voice.pipeline --test-mic    # 3s record + playback
python3 -m voice.tts                    # speaks test phrase
python3 -m voice.stt                    # 5s record → STT (needs :9000)
python3 fake_dashboard.py                 # terminal WS listener on :3001
python3 -m voice.pipeline               # full push-to-talk loop
```

With M3 context injection (from repo root, seed DB present):

```bash
# Say something like "How is Maria doing?" — pipeline loads case context
cd donna && python3 -m voice.pipeline
```

## Dell service health

On the Dell (or via SSH):

```bash
bash scripts/check_services.sh
```

All checks should print `OK`. Any `FAIL` means that layer of the demo stack is down.

## End-to-end demo checklist

Use before pitching or recording a demo:

- [ ] `check_services.sh` — STT, TTS, Ollama, dashboard ports up
- [ ] `context_lookup.py Maria` — returns case hits
- [ ] `fake_dashboard.py` or React dashboard on :3001
- [ ] `python3 -m voice.pipeline` — push-to-talk full loop
- [ ] Dashboard shows `user_speech` / `donna_speech` events
- [ ] Mentioning "Maria" triggers `[Loaded case context from local DB]` in pipeline output

## CI / future automation

There is no GitHub Actions workflow yet. Minimum bar before merge:

```bash
python3 -m unittest discover -s tests
cd donna && python3 -m pytest voice/tests/ -q
```

Optional on Dell with services running:

```bash
bash scripts/check_services.sh
```

## Related docs

- [M2 testing tools](m2-testing-tools.md) — JSON CLI shapes for OpenClaw stubs
- [GBrain + OpenClaw setup](gbrain-openclaw-setup.md) — optional synthesis layer
- [Storage architecture](storage-architecture.md) — SQLite roles (M3, OpenClaw, GBrain)
- [Dell GBIO access](dell-gbio-access.md) — SSH and port forwarding
- [Hackathon quickstart](hackathon-quickstart.md) — team roles and module map
- [Voice pipeline](../donna/VOICE_PIPELINE.md) — architecture and env vars
