"""Bridge between voice pipeline and Donna's LLM brain.

Handles: conversation history, tool calling, system prompt injection.
Tries OpenClaw CLI first, falls back to direct Ollama API.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.intake import intake_client, create_case_file, TOOL_DEFINITIONS as INTAKE_TOOLS
from tools.calendar import book_calendar, get_upcoming, TOOL_DEFINITIONS as CALENDAR_TOOLS
from tools.cases import get_status, check_deadline, get_deadlines, TOOL_DEFINITIONS as CASES_TOOLS
from tools.search import search_cases, summarize_document, TOOL_DEFINITIONS as SEARCH_TOOLS

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL = os.environ.get("DONNA_LLM_MODEL", "qwen2.5:14b")

ALL_TOOLS = INTAKE_TOOLS + CALENDAR_TOOLS + CASES_TOOLS + SEARCH_TOOLS

TOOL_DISPATCH = {
    "intake_client": intake_client,
    "create_case_file": create_case_file,
    "book_calendar": book_calendar,
    "get_upcoming_events": get_upcoming,
    "get_case_status": get_status,
    "check_sol_deadline": check_deadline,
    "get_upcoming_deadlines": get_deadlines,
    "search_cases": search_cases,
    "summarize_document": summarize_document,
}


def load_system_prompt() -> str:
    config_path = Path(__file__).parent.parent / "agent" / "donna.yaml"
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
            return config.get("system_prompt", "")
    return "You are Donna, an AI legal secretary for a personal injury law firm."


class DonnaAgent:
    """Manages conversation state and tool execution for Donna."""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.system_prompt = load_system_prompt()
        self.history = [{"role": "system", "content": self.system_prompt}]

    async def chat(self, user_text: str) -> str:
        """Send user message to Donna and return her response. Handles tool calls."""
        self.history.append({"role": "user", "content": user_text})

        async with httpx.AsyncClient(timeout=60.0) as client:
            # First call — may include tool calls
            resp = await client.post(
                f"{OLLAMA_URL}/v1/chat/completions",
                json={
                    "model": MODEL,
                    "messages": self.history,
                    "tools": ALL_TOOLS,
                    "temperature": 0.3,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            message = choice["message"]

            # Handle tool calls (up to 3 rounds)
            rounds = 0
            while message.get("tool_calls") and rounds < 3:
                self.history.append(message)

                for tc in message["tool_calls"]:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]

                    fn = TOOL_DISPATCH.get(fn_name)
                    if fn:
                        try:
                            result = fn(**fn_args)
                        except Exception as e:
                            result = {"error": str(e)}
                    else:
                        result = {"error": f"Unknown tool: {fn_name}"}

                    self.history.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result),
                    })

                # Continue conversation after tool results
                resp = await client.post(
                    f"{OLLAMA_URL}/v1/chat/completions",
                    json={
                        "model": MODEL,
                        "messages": self.history,
                        "tools": ALL_TOOLS,
                        "temperature": 0.3,
                        "max_tokens": 300,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                choice = data["choices"][0]
                message = choice["message"]
                rounds += 1

            # Final text response
            donna_text = message.get("content", "I'm sorry, I didn't catch that.")
            self.history.append({"role": "assistant", "content": donna_text})

            # Keep history manageable (last 20 turns)
            if len(self.history) > 40:
                self.history = [self.history[0]] + self.history[-20:]

            return donna_text


async def test():
    agent = DonnaAgent()
    test_messages = [
        "Hey Donna, I have a new client. Sarah Chen, she slipped and fell at Westfield mall on March 3rd.",
        "What does the police report say?",
        "Book a follow-up call with Sarah for next Tuesday at 2pm.",
    ]
    for msg in test_messages:
        print(f"\nUser: {msg}")
        response = await agent.chat(msg)
        print(f"Donna: {response}")


if __name__ == "__main__":
    asyncio.run(test())
