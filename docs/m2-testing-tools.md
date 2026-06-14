# M2 Testing Tools

This repo includes a small M3-owned local test surface so M2 can exercise context lookup and calendar tool calls before the full M1 IPC contract is available.

## Create Seed Databases

```bash
python3 scripts/init_m3_test_db.py
```

This creates:

- `data/donna_m3_context.sqlite`
- `data/donna_m3_calendar.sqlite`

Both are local SQLite files and can be copied onto the GBIO image for offline testing.

## Context Lookup

```bash
python3 scripts/context_lookup.py Maria
```

Output shape:

```json
{
  "ok": true,
  "hits": [
    {
      "source": "case",
      "case_id": "case-2026-001",
      "title": "Maria Lopez",
      "snippet": "Potential PI matter..."
    }
  ]
}
```

## Calendar Tool

Create an event:

```bash
python3 scripts/calendar_tool.py create_event --input '{"title":"Client follow-up","start":"2026-06-19T10:00:00-07:00","end":"2026-06-19T10:30:00-07:00","attendee":"Maria Lopez","case_id":"case-2026-001","notes":"Ask for insurance claim number."}'
```

Search events:

```bash
python3 scripts/calendar_tool.py search_events --input '{"case_id":"case-2026-001"}'
```

The CLI intentionally accepts and returns JSON so M2 can plug it into an OpenClaw tool stub without depending on the final IPC transport.
