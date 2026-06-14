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

This branch does not route the voice stack through OpenClaw yet. `donna/voice/pipeline.py`
loads case context from `donna/glue/context_bridge.py` and then calls Ollama directly.
OpenClaw and GBrain are a parallel M2 path you can run separately:

```bash
openclaw run donna --input "How is Maria Lopez doing?"
cd dell-hack/donna && python3 -m voice.pipeline
```

If you want voice to use OpenClaw, that wiring still needs to be implemented.

## Install via agent

Paste into OpenClaw:

```
Retrieve and follow:
https://raw.githubusercontent.com/garrytan/gbrain/master/INSTALL_FOR_AGENTS.md

Use Donna brain schema from dell-hack docs/donna-brain-schema.md
```

See [docs/gbrain-openclaw-setup.md](../docs/gbrain-openclaw-setup.md).
