# Donna storage architecture

Donna uses **local embedded databases** at every layer. They are not duplicates — each SQLite (or PGLite) file has a different job.

## Three stores

| Store | Engine | Location | Purpose |
|-------|--------|----------|---------|
| **M3 glue** | SQLite | `data/donna_m3_context.sqlite`, `data/donna_m3_calendar.sqlite` | Structured case/calendar data for M3 tool CLIs and tests |
| **OpenClaw builtin memory** | SQLite (+ FTS5, sqlite-vec) | `~/.openclaw/memory/donna.sqlite` | RAG index over `MEMORY.md` and `memory/*.md` in the agent workspace |
| **GBrain** (optional) | **PGLite** (embedded Postgres, not SQLite) | `~/.gbrain/` + markdown brain repo | Synthesis, knowledge graph, dream cycle — sits behind OpenClaw via MCP |

OpenClaw’s built-in memory is documented at [OpenClaw memory](https://docs.openclaw.ai/concepts/memory-builtin). It chunks markdown into ~400-token pieces and stores embeddings in a **per-agent SQLite file**. That is separate from our M3 seed DB.

GBrain uses **PGLite** (Postgres-compatible WASM), not SQLite. It complements OpenClaw: OpenClaw indexes workspace markdown locally; GBrain adds graph traversal and overnight consolidation when you run `gbrain serve`.

## Data flow (hackathon path)

```text
python3 scripts/init_m3_test_db.py
        ↓
data/donna_m3_*.sqlite          ← M3 tools + voice context_bridge fallback
        ↓
python3 scripts/export_openclaw_memory.py
        ↓
openclaw/workspace/MEMORY.md
openclaw/workspace/memory/**/*.md
        ↓  (OpenClaw file watcher, ~1.5s debounce)
~/.openclaw/memory/donna.sqlite ← hybrid keyword + vector search
        ↓
openclaw run donna              ← M2 agent reads indexed memory
        ↓  (optional)
gbrain serve                    ← richer synthesis via MCP skills
```

## When to use which

| Need | Use |
|------|-----|
| Calendar create/search JSON tools | M3 `data/donna_m3_calendar.sqlite` |
| Quick voice fallback without OpenClaw | M3 `context_bridge` → context SQLite |
| Agent remembers case facts across turns | Export to OpenClaw workspace → OpenClaw SQLite index |
| “What do I need to know before meeting Maria?” synthesis | GBrain query skills (optional) |

## Export seed data into OpenClaw memory

```bash
python3 scripts/init_m3_test_db.py
python3 scripts/export_openclaw_memory.py --output openclaw/workspace
openclaw memory index --force    # rebuild ~/.openclaw/memory/donna.sqlite
openclaw run donna --input "Summarize Maria Lopez case-2026-001"
```

Copy `openclaw/workspace/` into your real OpenClaw repo on the Dell (e.g. `~/donna-openclaw/`).

## Why keep M3 SQLite if OpenClaw has SQLite?

- **M3 tools** need typed tables (calendar events, intake fields, foreign keys) — not just markdown chunks.
- **OpenClaw SQLite** is a search index, not a transactional case database.
- **Same local-first philosophy:** stdlib SQLite for glue; OpenClaw’s SQLite for agent RAG; GBrain PGLite for advanced brain ops.

Long term, M3 `memory.write` can append markdown to the OpenClaw workspace (triggering reindex) while structured updates stay in M3 SQLite or calendar DB.

## Related docs

- [GBrain + OpenClaw setup](gbrain-openclaw-setup.md)
- [M2 testing tools](m2-testing-tools.md)
- [openclaw/README.md](../openclaw/README.md)
