from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
import json
from typing import AsyncIterator

import httpx


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class LLMResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)


@dataclass
class LLMStreamChunk:
    text_delta: str = ""
    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    done: bool = False
    first_token_seconds: float | None = None


class DonnaLLM:
    def __init__(self, *, ollama_url: str, model: str) -> None:
        normalized = ollama_url.rstrip("/")
        for suffix in ("/api/generate", "/api/chat"):
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]
                break
        self.ollama_url = normalized
        self.model = model
        self.keep_alive = self._default_keep_alive()
        self.options = self._default_options()

    @staticmethod
    def _default_keep_alive() -> int | str:
        raw_value = os.getenv("DONNA_OLLAMA_KEEP_ALIVE", "-1").strip()
        if not raw_value:
            return -1
        try:
            return int(raw_value)
        except ValueError:
            return raw_value

    @staticmethod
    def _default_options() -> dict:
        options: dict[str, int | float] = {
            "num_predict": 16,
            "temperature": 0.2,
        }
        num_predict = os.getenv("DONNA_OLLAMA_NUM_PREDICT", "").strip()
        if num_predict:
            try:
                options["num_predict"] = max(1, int(num_predict))
            except ValueError:
                pass
        temperature = os.getenv("DONNA_OLLAMA_TEMPERATURE", "").strip()
        if temperature:
            try:
                options["temperature"] = float(temperature)
            except ValueError:
                pass
        return options

    def _chat_payload(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        stream: bool,
        tools: list[dict] | None = None,
    ) -> dict:
        num_ctx = int(os.getenv("DONNA_NUM_CTX", "4096"))
        payload: dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": system_prompt}, *[
                {"role": m.role, "content": m.content} for m in messages
            ]],
            "stream": stream,
            "keep_alive": self.keep_alive,
            "options": {"num_ctx": num_ctx, "num_predict": 256},
        }
        if tools:
            payload["tools"] = tools
        if self.options:
            payload["options"] = self.options
        return payload

    @staticmethod
    def _merge_tool_calls(existing: list[dict], incoming: list[dict]) -> list[dict]:
        if not incoming:
            return existing
        seen = {json.dumps(item, sort_keys=True) for item in existing}
        for item in incoming:
            key = json.dumps(item, sort_keys=True)
            if key in seen:
                continue
            existing.append(item)
            seen.add(key)
        return existing

    def chat(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
    ) -> LLMResult:
        payload = self._chat_payload(
            system_prompt=system_prompt,
            messages=messages,
            stream=False,
            tools=tools,
        )

        with httpx.Client(timeout=120.0) as client:
            resp = client.post(f"{self.ollama_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        message = data.get("message", {})
        text = (message.get("content") or "").strip()
        tool_calls = message.get("tool_calls") or []
        return LLMResult(text=text, tool_calls=tool_calls)

    async def chat_stream(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        payload = self._chat_payload(
            system_prompt=system_prompt,
            messages=messages,
            stream=True,
            tools=tools,
        )
        accumulated_text = ""
        accumulated_tool_calls: list[dict] = []
        first_token_seconds: float | None = None
        started = time.perf_counter()

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{self.ollama_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    message = data.get("message") or {}
                    text_delta = message.get("content") or ""
                    tool_calls = message.get("tool_calls") or []
                    if first_token_seconds is None and (text_delta or tool_calls):
                        first_token_seconds = round(time.perf_counter() - started, 3)
                    accumulated_text += text_delta
                    self._merge_tool_calls(accumulated_tool_calls, tool_calls)
                    yield LLMStreamChunk(
                        text_delta=text_delta,
                        text=accumulated_text,
                        tool_calls=list(accumulated_tool_calls),
                        done=bool(data.get("done")),
                        first_token_seconds=first_token_seconds,
                    )

    def generate_simple(self, *, system_prompt: str, user_text: str) -> str:
        prompt = f"{system_prompt}\n\nClient: {user_text}\nDonna:"
        with httpx.Client(timeout=120.0) as client:
            if self.options:
                resp = client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "keep_alive": self.keep_alive,
                        "options": self.options,
                    },
                )
            else:
                resp = client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "keep_alive": self.keep_alive,
                    },
                )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()

    def warm(self) -> None:
        with httpx.Client(timeout=120.0) as client:
            if self.options:
                resp = client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": "OK",
                        "stream": False,
                        "keep_alive": self.keep_alive,
                        "options": self.options,
                    },
                )
            else:
                resp = client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": "OK",
                        "stream": False,
                        "keep_alive": self.keep_alive,
                    },
                )
        resp.raise_for_status()

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
