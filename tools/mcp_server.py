"""
Thin MCP server wrapping Donna's tool layer.
OpenClaw connects to this via stdio (command/args in openclaw.json).
Uses the `mcp` SDK (pip install mcp).
"""

from __future__ import annotations

import json
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from tools.calendar import book_calendar, check_calendar_conflicts, get_upcoming_events
from tools.case_files import (
    create_case_file, get_case_file, update_case_file,
    list_cases, search_context, log_payment, get_payment_summary, log_court_date,
)
from tools.case_law import search_case_law, analyze_case_weaknesses, profile_adverse_adjuster
from tools import ALL_TOOL_DEFINITIONS

server = Server("donna-tools")

# ── Tool listing ──────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    tools = []
    for defn in ALL_TOOL_DEFINITIONS:
        fn = defn["function"]
        tools.append(types.Tool(
            name=fn["name"],
            description=fn["description"],
            inputSchema=fn["parameters"],
        ))
    return tools


# ── Tool dispatch ─────────────────────────────────────────────────────────────

_DISPATCH = {
    "check_calendar_conflicts": check_calendar_conflicts,
    "book_calendar":            book_calendar,
    "get_upcoming_events":      get_upcoming_events,
    "create_case_file":         create_case_file,
    "get_case_file":            get_case_file,
    "update_case_file":         update_case_file,
    "list_cases":               list_cases,
    "search_context":           search_context,
    "log_payment":              log_payment,
    "get_payment_summary":      get_payment_summary,
    "log_court_date":           log_court_date,
    "search_case_law":          search_case_law,
    "analyze_case_weaknesses":  analyze_case_weaknesses,
    "profile_adverse_adjuster": profile_adverse_adjuster,
}


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    fn = _DISPATCH.get(name)
    if fn is None:
        return [types.TextContent(type="text", text=json.dumps({
            "status": "error", "message": f"Unknown tool: {name}"
        }))]
    try:
        result = fn(**arguments)
        return [types.TextContent(type="text", text=json.dumps(result))]
    except Exception as exc:
        return [types.TextContent(type="text", text=json.dumps({
            "status": "error", "message": str(exc)
        }))]


if __name__ == "__main__":
    import asyncio
    asyncio.run(stdio_server(server))
