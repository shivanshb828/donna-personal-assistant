# Dell GBIO / Pro Max Access

Donna runs locally on the **Dell Pro Max with GB10** provided at the Dell x NVIDIA hackathon (June 14, 2026). Use this doc to SSH in, sync the repo, and verify services.

## SSH connection

Observed active session (June 14, 2026):

```bash
ssh dell@10.104.77.67
```

Other host entries seen in `~/.ssh/known_hosts` (may be the same machine on a different network):

| Host | Notes |
|------|-------|
| `10.104.77.67` | Primary — used for hackathon SSH |
| `10.0.0.31` | Likely LAN address |
| `100.119.229.11` | Likely Tailscale / alternate route |

**User:** `dell`

**Hostname (confirmed):** `promaxgb10-887e`  
**Repo path:** `/home/dell/dell-hack`

Auth is key- or password-based on the event network. If non-interactive SSH fails with `Permission denied (publickey,password)`, use an interactive terminal or load the correct key into your agent first.

### Recommended local SSH config

Add to `~/.ssh/config` (adjust key path):

```sshconfig
Host dell-gbio dell-hack
    HostName 10.104.77.67
    User dell
    IdentityFile ~/.ssh/id_ed25519
```

Then connect with:

```bash
ssh dell-gbio
```

## Repo on the Dell

The repo is **not** pre-installed on the GB10 box. Clone it first (from your home directory):

```bash
cd ~
git clone https://github.com/shivanshb828/dell-hack.git
cd dell-hack
git fetch origin
git checkout integrate-dafely-from-pr   # or main after merge
```

If `cd dell-hack` fails with "No such file or directory", you have not cloned yet — run the `git clone` block above.

Seed databases (after clone):

```bash
python3 scripts/init_m3_test_db.py
```

Copy seed DBs to the GBIO path used in fixtures when needed:

```bash
mkdir -p /gbio/donna/cases
cp data/donna_m3_context.sqlite data/donna_m3_calendar.sqlite /gbio/donna/ 2>/dev/null || true
```

## Service ports (localhost on Dell)

Confirmed on `promaxgb10-887e` (2026-06-14):

| Service | Port | Bind | Docker | Env var | Owner | Status |
|---------|------|------|--------|---------|-------|--------|
| faster-whisper STT | 9000 | 0.0.0.0 | `whisper` (→8000) | `DONNA_STT_URL` | Shivansh | Up |
| Kokoro TTS | 8880 | 0.0.0.0 | `kokoro` | `DONNA_KOKORO_URL` | Shivansh | Up |
| Ollama | 11434 | 127.0.0.1 | native | `DONNA_OLLAMA_URL`, `DONNA_MODEL` | Shivansh | Up |
| React dashboard WS | 3001 | — | — | `DONNA_DASHBOARD_WS` | Dhruva | Down |
| OpenClaw | CLI | — | — | `DONNA_OPENCLAW_BIN` | Aayush | Installed |
| GBrain | MCP | — | — | — | Aayush | Not installed |

Ollama model on box (June 14):

```bash
export DONNA_MODEL=nemotron-3-super
```

Quick health check on the Dell:

```bash
bash scripts/check_services.sh
```

## Discover machine state (run on Dell)

While SSH'd into the Dell, capture hardware and service info:

```bash
cd dell-hack
bash scripts/dell_discovery.sh | tee dell-discovery.txt
```

Paste `dell-discovery.txt` into `.context/dell-machine.md` in your Conductor workspace so other agents see live state. Committed docs stay generic; `.context/` holds session-specific output.

## SSH port forwarding (dev from Mac)

If services only listen on the Dell localhost, forward ports to your Mac:

```bash
ssh -L 9000:localhost:9000 \
    -L 8880:localhost:8880 \
    -L 11434:localhost:11434 \
    -L 3001:localhost:3001 \
    dell@10.104.77.67
```

Then run voice pipeline on your Mac with defaults unchanged, or run everything on the Dell over SSH.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| `cd dell-hack: No such file or directory` | Run `git clone https://github.com/shivanshb828/dell-hack.git` from `~` first |
| SSH refused | Confirm you're on event Wi‑Fi / VPN; try alternate IP from table above |
| STT 9000 down | `curl -s -o /dev/null -w '%{http_code}' localhost:9000` on Dell |
| Ollama empty | `curl localhost:11434/api/tags` — run `ollama pull nemotron` |
| Voice no context | `python3 scripts/context_lookup.py Maria` — re-run `init_m3_test_db.py` |
| OpenClaw missing | `which openclaw` — M2 agent not installed yet; pipeline falls back to Ollama |
