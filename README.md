# dell-hack

Donna — local-first AI legal secretary / voice intake for the Dell x NVIDIA hackathon.

## New workspace?

**Start here:** [docs/dell-gbio-runbook.md](docs/dell-gbio-runbook.md) (SSH, venv, audio, confirmed GB10 state)

Then: [docs/hackathon-quickstart.md](docs/hackathon-quickstart.md) · [docs/testing-runbook.md](docs/testing-runbook.md)

## Quick run on Dell GB10

```bash
ssh dell@10.104.77.67
# password: 123456
cd ~/dell-hack && git pull
bash scripts/setup_venv.sh    # once
bash scripts/run_voice.sh
```

**Note:** stock GB10 has **no built-in mic** — plug a USB headset or use Mac + SSH port forward. See runbook.

## Voice pipeline

[donna/VOICE_PIPELINE.md](donna/VOICE_PIPELINE.md) — STT → SQLite context → Ollama → TTS (local push-to-talk)

**Twilio telephony** (inbound intake + outbound lead capture): [donna/telephony/README.md](donna/telephony/README.md) · setup [docs/twilio-setup.md](docs/twilio-setup.md)

```bash
bash scripts/run_voice.sh           # push-to-talk on :n/a
bash scripts/run_telephony.sh       # Twilio agent on :3002
```

## Docs index

| Doc | Purpose |
|-----|---------|
| [dell-gbio-runbook.md](docs/dell-gbio-runbook.md) | **Confirmed Dell setup** — read first |
| [dell-gbio-access.md](docs/dell-gbio-access.md) | SSH, ports, troubleshooting |
| [twilio-setup.md](docs/twilio-setup.md) | Twilio + ngrok telephony setup |
| [voice-telephony-architecture.md](docs/voice-telephony-architecture.md) | Phone agent architecture |
| [dell-ssh-agent-prompt.md](docs/dell-ssh-agent-prompt.md) | **Copy-paste system prompt for SSH agent on GB10** |
| [testing-runbook.md](docs/testing-runbook.md) | All test commands |
| [hackathon-quickstart.md](docs/hackathon-quickstart.md) | Team, modules, demo |
| [storage-architecture.md](docs/storage-architecture.md) | SQLite / OpenClaw / GBrain |
