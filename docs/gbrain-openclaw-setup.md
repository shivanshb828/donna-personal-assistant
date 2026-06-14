# GBrain + OpenClaw for Donna

Donna's **M2 agent memory** runs on [GBrain](https://github.com/garrytan/gbrain) — a markdown-first knowledge graph with hybrid search, synthesis, and an OpenClaw plugin. GBrain is the background brain behind our OpenClaw instance; M3 glue tools handle structured case/calendar operations.

## Architecture

```
Voice / iMessage
       ↓
M3 session router + tools (SQLite fixtures, calendar CLIs)
       ↓
M2 OpenClaw (`openclaw run donna`)
       ↓
GBrain MCP (`gbrain serve`) — case context, client pages, intake notes
       ↓
Ollama / Nemotron (local on Dell GB10)
```

| Layer | Memory | Role |
|-------|--------|------|
| **GBrain** | Markdown brain repo + Postgres/PGLite | Long-term case knowledge, synthesis, graph queries |
| **M3 SQLite seed DB** | `data/donna_m3_*.sqlite` | Hackathon fixtures + offline M2 tool testing |
| **Voice context bridge** | Reads SQLite today | Fast path when OpenClaw unavailable; migrate to GBrain MCP later |

GBrain replaces the original **ChromaDB** plan in `m3-glue-layer-plan.md` for `memory.search` / `memory.write`. Structured tools (calendar, intake forms) stay in M3 Python glue.

## Dell GB10 setup (recommended)

Run GBrain on the same box as OpenClaw and Ollama.

### 1. Install GBrain

```bash
curl -fsSL https://bun.sh/install | bash
export PATH="$HOME/.bun/bin:$PATH"
bun install -g github:garrytan/gbrain
gbrain --version
```

Or clone for deterministic install:

```bash
git clone https://github.com/garrytan/gbrain.git ~/gbrain && cd ~/gbrain
bun install && bun link
```

### 2. API keys

Ask the operator which embedding stack to use. Minimum for Donna demo:

```bash
export OPENAI_API_KEY=sk-...          # embeddings fallback
export ANTHROPIC_API_KEY=sk-ant-...   # optional, improves query expansion
# Or ZeroEntropy (GBrain default as of v0.36+):
export ZEROENTROPY_API_KEY=ze-...
```

Persist in `~/.gbrain/config.json` or `.env` on the Dell.

### 3. Create Donna brain repo

```bash
mkdir -p ~/donna-brain && cd ~/donna-brain && git init
gbrain init --pglite
gbrain doctor --json
```

Use the Donna-specific layout in [donna-brain-schema.md](donna-brain-schema.md) (cases, clients, intake — not generic `people/`/`companies/`).

### 4. Wire OpenClaw

In your OpenClaw workspace repo, install the bundled plugin and scaffold skills:

```bash
# From OpenClaw workspace root
gbrain skillpack scaffold --target .
```

GBrain ships `openclaw.plugin.json` with MCP server config:

```json
{
  "mcpServers": {
    "gbrain": {
      "command": "./bin/gbrain",
      "args": ["serve"]
    }
  }
}
```

Point OpenClaw at the Donna agent config and ensure the GBrain plugin is enabled. Agent entrypoint:

```bash
openclaw run donna --input "How is Maria Lopez doing?"
```

Voice pipeline already calls this via `DONNA_OPENCLAW_BIN` (see `donna/voice/pipeline.py`).

### 5. Start GBrain server (background)

```bash
gbrain serve --http                    # MCP over HTTP for remote clients
# Or local MCP only:
gbrain serve
```

Optional autopilot daemon (sync + embed + dream cycle):

```bash
gbrain autopilot --install
```

For hackathon demo, at minimum run periodic sync after seeding case pages:

```bash
gbrain sync --repo ~/donna-brain && gbrain embed
```

### 6. Seed from M3 fixtures (bridge)

Copy hackathon seed data into GBrain pages once, then let the agent compound:

```bash
# From dell-hack repo on Dell
python3 scripts/init_m3_test_db.py
python3 scripts/context_lookup.py Maria   # verify SQLite seed
# Then have OpenClaw agent ingest case summaries into ~/donna-brain/cases/
```

Long term: M3 `memory.write` tool writes to GBrain via MCP instead of ChromaDB.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DONNA_OPENCLAW_BIN` | `openclaw` | OpenClaw CLI |
| `DONNA_GBRAIN_URL` | `http://localhost:8765/mcp` | GBrain MCP HTTP endpoint (when wired) |
| `DONNA_GBRAIN_TOKEN` | — | OAuth/token if using remote GBrain |
| `DONNA_BRAIN_REPO` | `~/donna-brain` | Markdown brain git repo path |

## Agent install protocol

Paste into OpenClaw (or any agent) to run full GBrain setup:

```
Retrieve and follow the instructions at:
https://raw.githubusercontent.com/garrytan/gbrain/master/INSTALL_FOR_AGENTS.md
```

Customize Step 3 brain repo layout using [donna-brain-schema.md](donna-brain-schema.md).

## Verification

```bash
# GBrain health
gbrain doctor --json

# OpenClaw + brain query
openclaw run donna --input "Summarize case-2026-001 for Maria Lopez"

# Voice loop (OpenClaw path uses GBrain internally)
cd donna && python3 -m voice.pipeline

# Services on Dell
bash scripts/check_services.sh
```

## Related docs

- [Donna brain schema](donna-brain-schema.md)
- [M3 glue layer plan](m3-glue-layer-plan.md)
- [Dell GBIO access](dell-gbio-access.md)
- [GBrain INSTALL_FOR_AGENTS.md](https://github.com/garrytan/gbrain/blob/master/INSTALL_FOR_AGENTS.md)
