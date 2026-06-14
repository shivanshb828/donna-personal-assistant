# Donna — AI OS Extension

**Dell x NVIDIA Hackathon, June 14, 2026**

Donna is a local-first AI legal secretary for personal injury lawyers. The broader pitch is an
OS-level AI layer that can orchestrate real workflows on-device; legal intake is the demo proof.
All hot-path compute is intended to run locally on the Dell GB10 box.

## Start Here

If you are new to this repo or opening a fresh Conductor workspace, read these first:

- [docs/hackathon-quickstart.md](docs/hackathon-quickstart.md)
- [docs/storage-architecture.md](docs/storage-architecture.md)
- [docs/testing-runbook.md](docs/testing-runbook.md)
- [docs/dell-gbio-access.md](docs/dell-gbio-access.md)

## Current Repo Shape

There are two distinct paths in the repo today:

- Voice demo path: push-to-talk voice pipeline with STT, SQLite context injection, direct Ollama,
  and TTS. See [donna/VOICE_PIPELINE.md](donna/VOICE_PIPELINE.md).
- M2 agent path: OpenClaw + optional GBrain docs, schemas, and tool wiring for a fuller Donna
  agent stack. See [docs/gbrain-openclaw-setup.md](docs/gbrain-openclaw-setup.md) and
  [openclaw/README.md](openclaw/README.md).

Important current-state note: in this branch, the voice pipeline does **not** route through
OpenClaw yet. `donna/voice/pipeline.py` loads local SQLite context and then calls Ollama directly.

## Voice Pipeline

Run from the repo root on Dell or Mac after dependencies are installed:

```bash
bash scripts/run_voice.sh
```

Or manually:

```bash
cd donna
pip install -r requirements.txt
python3 -m voice.pipeline
```

On Ubuntu 24.04 / Dell, use the venv bootstrap first:

```bash
bash scripts/setup_venv.sh
```

When the M3 seed DB is present, voice queries inject matching case context from
`data/donna_m3_context.sqlite` before calling Ollama.

## M3 Glue + Seed Data

Create the local seed databases:

```bash
python3 scripts/init_m3_test_db.py
```

Try a sample context lookup:

```bash
python3 scripts/context_lookup.py Maria
```

Export seed data into OpenClaw memory markdown:

```bash
python3 scripts/export_openclaw_memory.py --output openclaw/workspace
```

Related docs:

- [docs/m3-glue-layer-plan.md](docs/m3-glue-layer-plan.md)
- [docs/m2-testing-tools.md](docs/m2-testing-tools.md)
- [docs/donna-brain-schema.md](docs/donna-brain-schema.md)

## Dell GBIO

- SSH and port forwarding: [docs/dell-gbio-access.md](docs/dell-gbio-access.md)
- Health check: `bash scripts/check_services.sh`
- Machine discovery on Dell: `bash scripts/dell_discovery.sh`

Primary observed host:

```bash
ssh dell@10.104.77.67
```

## Tests

```bash
python3 -m unittest discover -s tests
cd donna && python3 -m pytest voice/tests/ -v
bash scripts/check_services.sh
```

See [docs/testing-runbook.md](docs/testing-runbook.md) for the full checklist.
