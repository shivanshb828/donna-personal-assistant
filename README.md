# dell-hack

Donna — local-first AI legal secretary / voice intake for the Dell x NVIDIA hackathon.

## New workspace?

**Start here:** [docs/dell-gbio-runbook.md](docs/dell-gbio-runbook.md) (SSH, venv, audio, confirmed GB10 state)

Then: [docs/hackathon-quickstart.md](docs/hackathon-quickstart.md) · [docs/testing-runbook.md](docs/testing-runbook.md)

## Quick run on Dell GB10

```bash
ssh dell@10.104.77.67
cd ~/dell-hack && git pull
bash scripts/setup_venv.sh    # once
bash scripts/run_voice.sh
```

**Note:** stock GB10 has **no built-in mic** — plug a USB headset or use Mac + SSH port forward. See runbook.

## Voice pipeline

[donna/VOICE_PIPELINE.md](donna/VOICE_PIPELINE.md) — STT → SQLite context → Ollama → TTS

## Docs index

| Doc | Purpose |
|-----|---------|
| [dell-gbio-runbook.md](docs/dell-gbio-runbook.md) | **Confirmed Dell setup** — read first |
| [dell-gbio-access.md](docs/dell-gbio-access.md) | SSH, ports, troubleshooting |
| [testing-runbook.md](docs/testing-runbook.md) | All test commands |
| [hackathon-quickstart.md](docs/hackathon-quickstart.md) | Team, modules, demo |
| [storage-architecture.md](docs/storage-architecture.md) | SQLite / OpenClaw / GBrain |
