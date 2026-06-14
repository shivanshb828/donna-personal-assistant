# Dell GB10 Runbook (confirmed June 14, 2026)

**Read this first** in any new Conductor workspace. Live machine: `promaxgb10-887e`.

## Machine identity

| Field | Value |
|-------|-------|
| Hostname | `promaxgb10-887e` |
| SSH | `ssh dell@10.104.77.67` |
| User | `dell` |
| OS | Ubuntu 24.04.4 LTS, aarch64, kernel 6.17.0-1018-nvidia |
| GPU | NVIDIA GB10, driver 580.159.03 |
| Repo path | `/home/dell/dell-hack` |
| Branch | `main` |
| Password | `123456` (hackathon dummy — safe to store in repo) |

```bash
ssh dell@10.104.77.67
# password: 123456
```

## First-time setup (clone → venv → run)

The repo is **not** pre-installed on the GB10.

```bash
cd ~
git clone https://github.com/shivanshb828/dell-hack.git
cd dell-hack
git checkout main
git pull

bash scripts/setup_venv.sh
bash scripts/run_voice.sh
```

Always run scripts from **`~/dell-hack`** (repo root), not `~/dell-hack/donna`.

### What `setup_venv.sh` does

Ubuntu 24.04 blocks system `pip` (PEP 668). The script:

1. Installs apt packages: `python3-pyaudio`, `python3-httpx`, `python3-websockets`, `python3-numpy`, `portaudio19-dev`
2. Creates `.venv` with `--system-site-packages`
3. Skips `pip install --upgrade pip` (event Wi‑Fi often causes PyPI `JSONDecodeError`)

Do **not** run `pip install -r requirements.txt` system-wide.

## Confirmed services (promaxgb10-887e)

| Service | Port | Status | Notes |
|---------|------|--------|-------|
| faster-whisper STT | 9000 | Up | Docker `whisper` (host 9000 → container 8000) |
| Kokoro TTS | 8880 | Up | Docker `kokoro` |
| Ollama | 11434 | Up | `127.0.0.1` only; model **`nemotron-3-nano`** |
| Dashboard WS | 3001 | Down | Use `bash scripts/run_fake_dashboard.sh` |
| OpenClaw CLI | — | Installed | Optional — voice uses Ollama direct |
| GBrain CLI | — | Not installed | Optional |

Health check:

```bash
cd ~/dell-hack && bash scripts/check_services.sh
bash scripts/verify_ollama_model.sh nemotron-3-nano
```

Discovery dump:

```bash
cd ~/dell-hack && bash scripts/dell_discovery.sh | tee dell-discovery.txt
```

## Audio hardware — critical

**Stock GB10 has no microphone.**

Verified on `promaxgb10-887e`:

```bash
arecord -l   # → empty (no CAPTURE devices)
aplay -l     # → NVIDIA HDMI output only
```

The voice pipeline can start and show `[Recording... speak now]`, but **captures silence** without an input device.

### Options

| Option | When to use |
|--------|-------------|
| **USB mic/headset** on the Dell | Best for on-box demo — replug, then `arecord -l` should list a device |
| **Mac mic + SSH port forward** | Use Dell inference, local audio I/O |

Port forward from Mac:

```bash
ssh -L 9000:localhost:9000 \
    -L 8880:localhost:8880 \
    -L 11434:localhost:11434 \
    dell@10.104.77.67
```

Then on Mac (with local venv): run voice pipeline against forwarded ports.

### Harmless noise on startup

These ALSA/JACK lines are normal and can be ignored:

```text
ALSA lib pcm_dmix.c ... unable to open slave
jack server is not running or cannot be started
```

## Voice pipeline (current architecture)

```
Enter → Mic → Energy VAD → STT :9000 → SQLite context → Ollama :11434 → TTS :8880 → Speaker
```

- **No OpenClaw hop** — direct Ollama HTTP
- **No torch on Dell** — `[VAD] Silero failed ... using energy VAD` is expected
- Default model: **`nemotron-3-nano`** (set via `DONNA_MODEL`; already pulled on GB10)
- Voice **does not use OpenClaw/NemoClaw** — direct Ollama HTTP for latency
- OpenClaw + Nemotron Nano wiring is a **separate M2 task** (known in progress / blocked)
- Context DB: `data/donna_m3_context.sqlite` (paths relative to repo root)

### Run commands

```bash
cd ~/dell-hack
bash scripts/run_voice.sh
```

Or manually:

```bash
cd ~/dell-hack
source .venv/bin/activate
python -m donna.voice.pipeline
```

Mic test:

```bash
cd ~/dell-hack && source .venv/bin/activate
python -m donna.voice.pipeline --test-mic
```

## Common errors

| Error | Fix |
|-------|-----|
| `cd dell-hack: No such file or directory` | `git clone` first (see above) |
| `scripts/run_voice.sh: No such file or directory` | `cd ~/dell-hack` — not `donna/` |
| `externally-managed-environment` | `bash scripts/setup_venv.sh` |
| pip `JSONDecodeError` | Use apt-based setup script; don't upgrade pip |
| `No module named 'donna'` | `git pull` (fix in `aff571f+`) or run from repo root |
| `No module named 'httpx'` | Re-run `bash scripts/setup_venv.sh` |
| Pipeline runs but hears nothing | **No mic** — plug USB headset or use Mac + port forward |
| HDMI only, no sound | Connect HDMI monitor/speaker or USB audio out |

## M3 seed data (no mic needed)

```bash
cd ~/dell-hack
python3 scripts/init_m3_test_db.py
python3 scripts/context_lookup.py Maria
python3 scripts/calendar_tool.py search_events --input '{"case_id":"case-2026-001"}'
```

## Related docs

- [dell-gbio-access.md](dell-gbio-access.md) — SSH config, port forwarding
- [testing-runbook.md](testing-runbook.md) — test commands
- [hackathon-quickstart.md](hackathon-quickstart.md) — team roles, demo script
- [VOICE_PIPELINE.md](../donna/VOICE_PIPELINE.md) — env vars, architecture
- [dell-ssh-agent-prompt.md](dell-ssh-agent-prompt.md) — system prompt for SSH agent with full GB10 context
