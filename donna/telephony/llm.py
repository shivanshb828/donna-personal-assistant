from __future__ import annotations

from dataclasses import dataclass, field
import json

import httpx


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class LLMResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)


class DonnaLLM:
    def __init__(self, *, ollama_url: str, model: str) -> None:
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model

    def chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
    ) -> LLMResult:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, *[
                {"role": m.role, "content": m.content} for m in messages
            ]],
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(f"{self.ollama_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        message = data.get("message", {})
        text = (message.get("content") or "").strip()
        tool_calls = message.get("tool_calls") or []
        return LLMResult(text=text, tool_calls=tool_calls)

    def generate_simple(self, *, system_prompt: str, user_text: str) -> str:
        prompt = f"{system_prompt}\n\nClient: {user_text}\nDonna:"
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.ollama_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()

    @staticmethod
    def parse_tool_args(raw: object) -> dict:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}
        return {}
