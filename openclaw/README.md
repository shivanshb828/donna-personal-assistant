# Donna OpenClaw workspace

OpenClaw agent configuration for Donna lives outside this repo (team workspace on Dell or Render). This folder documents the expected layout and GBrain integration.

## Expected layout (on Dell or agent host)

```text
~/donna-openclaw/          # OpenClaw workspace repo
├── AGENTS.md              # Agent protocol (GBrain skillpack may extend this)
├── openclaw.plugin.json   # Enable gbrain plugin (from skillpack scaffold)
├── skills/                # Scaffolded via: gbrain skillpack scaffold --target .
└── agents/
    └── donna/
        ├── SOUL.md        # Donna legal secretary persona (M2)
        └── tools.yaml     # References M3 glue tool names

~/donna-brain/             # GBrain markdown repo — see docs/donna-brain-schema.md
```

## Quick setup on Dell

```bash
# 1. GBrain + brain repo — full steps in docs/gbrain-openclaw-setup.md
gbrain init --pglite
mkdir -p ~/donna-brain && cd ~/donna-brain && git init

# 2. Scaffold skills into OpenClaw workspace
cd ~/donna-openclaw
gbrain skillpack scaffold --target .

# 3. Run agent
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
