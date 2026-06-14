# Optional GBrain + OpenClaw for Donna

Donna's **M2 agent memory** currently runs on [OpenClaw's built-in SQLite index](https://docs.openclaw.ai/concepts/memory-builtin). [GBrain](https://github.com/garrytan/gbrain) is an optional later-phase add-on for synthesis and graph skills, not a required part of the current stack. See [storage-architecture.md](storage-architecture.md) for how the SQLite layers fit together.

## Architecture

```
Voice / iMessage
       ↓
M3 SQLite tools (case rows, calendar CRUD)
       ↓ export → MEMORY.md + memory/*.md
M2 OpenClaw (`openclaw run donna`) → ~/.openclaw/memory/donna.sqlite
       ↓ optional MCP
GBrain (PGLite at ~/.gbrain/) — synthesis, dream cycle
       ↓
Ollama / Nemotron (local on Dell GB10)
```

| Layer | Engine | Role |
|-------|--------|------|
| **M3 glue** | SQLite | Structured case/calendar data + tool CLIs |
| **OpenClaw memory** | SQLite (FTS5 + sqlite-vec) | Indexes workspace markdown for RAG |
| **GBrain** | PGLite (Postgres WASM, not SQLite) | Optional background brain via MCP skills |
| **Voice context bridge** | Reads M3 SQLite | Fallback when OpenClaw is unavailable |

If we enable it later, GBrain can replace the original **ChromaDB** plan in `m3-glue-layer-plan.md` for `memory.search` / `memory.write`. Structured tools (calendar, intake forms) stay in M3 Python glue.

## Dell GB10 setup (optional, later phase)

Only do this if you explicitly want the optional GBrain layer on top of the baseline OpenClaw + SQLite setup.

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

The voice pipeline in this branch does not call OpenClaw yet. It uses the local SQLite
context bridge and then posts directly to Ollama. Treat `openclaw run donna` as a separate
agent path until voice-agent routing is implemented.

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

For synthesis and graph skills beyond OpenClaw's SQLite RAG index:

```bash
gbrain sync --repo ~/donna-brain && gbrain embed
```

### 6. Bridge M3 SQLite → OpenClaw memory

OpenClaw already indexes markdown into its own SQLite file. Export our seed DB first:

```bash
python3 scripts/init_m3_test_db.py
python3 scripts/export_openclaw_memory.py --output openclaw/workspace
# Copy openclaw/workspace/ into your OpenClaw repo, then:
openclaw memory index --force
```

See [storage-architecture.md](storage-architecture.md).

### 7. Optional GBrain layer

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
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

# Voice loop (separate direct-Ollama path in this branch)
cd donna && python3 -m voice.pipeline

# Services on Dell
bash scripts/check_services.sh
```

## Related docs

- [Storage architecture](storage-architecture.md) — SQLite vs PGLite roles
- [M3 glue layer plan](m3-glue-layer-plan.md)
- [Dell GBIO access](dell-gbio-access.md)
- [GBrain INSTALL_FOR_AGENTS.md](https://github.com/garrytan/gbrain/blob/master/INSTALL_FOR_AGENTS.md)
