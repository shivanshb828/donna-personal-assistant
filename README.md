# dell-hack

Donna is a local-first AI legal secretary for personal injury lawyers.

**New workspace?** Start with [docs/hackathon-quickstart.md](docs/hackathon-quickstart.md), [docs/storage-architecture.md](docs/storage-architecture.md), and [docs/testing-runbook.md](docs/testing-runbook.md).

## Voice Pipeline

Push-to-talk voice interface with STT, agent routing, and TTS. See [donna/VOICE_PIPELINE.md](donna/VOICE_PIPELINE.md).

```bash
cd donna
pip install -r requirements.txt
python3 -m voice.pipeline
```

On **Ubuntu 24.04 / Dell**, use a venv first (`bash scripts/setup_venv.sh`) — see [donna/VOICE_PIPELINE.md](donna/VOICE_PIPELINE.md).

When the M3 seed DB is present, voice queries inject matching case context, then call **Ollama directly** (no OpenClaw hop).

## M2 Agent + GBrain (OpenClaw)

- [GBrain + OpenClaw setup](docs/gbrain-openclaw-setup.md) — background memory for `openclaw run donna`
- [Donna brain schema](docs/donna-brain-schema.md) — case/client markdown layout
- OpenClaw workspace notes: [openclaw/README.md](openclaw/README.md)

- [M3 implementation plan](docs/m3-glue-layer-plan.md)
- [M2 testing tools](docs/m2-testing-tools.md)

Create the seed context and calendar databases:

```bash
python3 scripts/init_m3_test_db.py
```

Run a sample context lookup:

```bash
python3 scripts/context_lookup.py Maria
```

Export seed data into OpenClaw memory markdown (indexed to `~/.openclaw/memory/donna.sqlite`):

```bash
python3 scripts/export_openclaw_memory.py --output openclaw/workspace
```

## Dell GBIO (hackathon box)

- [SSH access & port forwarding](docs/dell-gbio-access.md)
- Health check: `bash scripts/check_services.sh`
- Machine discovery (run on Dell): `bash scripts/dell_discovery.sh`

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
