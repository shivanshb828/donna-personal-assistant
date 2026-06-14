# Donna OpenClaw workspace

OpenClaw agent configuration for Donna lives outside this repo (team workspace on Dell or Render). This folder documents the expected layout and GBrain integration.

## OpenClaw workspace (on Dell)

```text
~/donna-openclaw/
├── MEMORY.md              # Case index — export from M3 SQLite
├── memory/
│   ├── cases/             # One page per matter
│   └── clients/           # Client contact + consent
├── AGENTS.md
└── agents/donna/          # Persona + tool refs
```

OpenClaw indexes `MEMORY.md` and `memory/**/*.md` into **`~/.openclaw/memory/donna.sqlite`** (built-in hybrid search).

## Quick setup on Dell

```bash
# 1. Seed M3 SQLite + export to OpenClaw markdown
cd dell-hack
python3 scripts/init_m3_test_db.py
python3 scripts/export_openclaw_memory.py --output openclaw/workspace
# Copy openclaw/workspace/* into ~/donna-openclaw/

# 2. Reindex OpenClaw memory
openclaw memory index --force

# 3. Optional GBrain — docs/gbrain-openclaw-setup.md
gbrain skillpack scaffold --target ~/donna-openclaw

# 4. Run agent
openclaw run donna --input "How is Maria Lopez doing?"
```

## Voice pipeline integration

The voice stack calls OpenClaw first; GBrain is consulted inside the agent, not from Python directly (today):

```bash
export DONNA_OPENCLAW_BIN=openclaw
cd dell-hack/donna && python3 -m voice.pipeline
```

When OpenClaw is down, pipeline falls back to Ollama with SQLite context from `donna/glue/context_bridge.py`.

## Install via agent

Paste into OpenClaw:

```
Retrieve and follow:
https://raw.githubusercontent.com/garrytan/gbrain/master/INSTALL_FOR_AGENTS.md

Use Donna brain schema from dell-hack docs/donna-brain-schema.md
```

See [docs/gbrain-openclaw-setup.md](../docs/gbrain-openclaw-setup.md).
