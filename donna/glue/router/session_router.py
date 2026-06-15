from __future__ import annotations

import json
import inspect
import os
import re
import time

from dataclasses import dataclass, field
from typing import Awaitable, Callable

from donna.glue.context_bridge import lookup_context_block
from donna.glue.prompts.inbound_intake import build_inbound_prompt
from donna.glue.prompts.local_assistant import build_local_assistant_prompt
from donna.glue.prompts.outbound_lead import build_outbound_prompt
from donna.glue.tools.registry import TOOL_DEFINITIONS, ToolRegistry
from donna.telephony import db as telephony_db
from donna.telephony.llm import ChatMessage, DonnaLLM


@dataclass
class RouterResult:
    reply: str
    tool_results: list[dict] = field(default_factory=list)
    phase: str = "DISCLOSURE"


@dataclass
class RouterStreamOutcome:
    result: RouterResult
    first_token_seconds: float | None = None
    first_sentence_seconds: float | None = None


SentenceHandler = Callable[[str], Awaitable[None] | None]
LOCAL_ASSISTANT_SENTENCE_LIMIT = max(1, int(os.getenv("DONNA_LOCAL_SENTENCE_LIMIT", "1")))


PHASE_TOOL_NAMES: dict[str, list[str]] = {
    "DISCLOSURE": ["record_consent", "intake.start", "intake.update", "notify.dashboard"],
    "INTAKE": ["intake.start", "intake.update", "case.qualify", "notify.dashboard"],
    "QUALIFICATION": ["intake.update", "case.qualify", "case.create", "case.decline", "notify.dashboard"],
    "BOOKING": ["intake.update", "case.create", "calendar.create_event", "notify.dashboard"],
    "CLOSE": ["notify.dashboard"],
}

LOCAL_ASSISTANT_PHASE_TOOL_NAMES: dict[str, list[str]] = {
    "DISCLOSURE": ["record_consent", "intake.start", "intake.update", "case.qualify", "notify.dashboard"],
    "INTAKE": ["intake.start", "intake.update", "case.qualify", "notify.dashboard"],
    "QUALIFICATION": ["intake.update", "case.qualify", "case.create", "case.decline", "notify.dashboard"],
    "BOOKING": ["intake.update", "case.create", "calendar.create_event", "notify.dashboard"],
    "CLOSE": ["intake.update", "notify.dashboard"],
}

TOOL_DEFINITION_BY_NAME = {
    item["function"]["name"]: item
    for item in TOOL_DEFINITIONS
}


class SessionRouter:
    def __init__(
        self,
        *,
        telephony_db_path,
        context_db_path,
        calendar_db_path,
        llm: DonnaLLM,
        tools: ToolRegistry,
        firm_name: str = "Donna Legal",
    ) -> None:
        self.telephony_db_path = telephony_db_path
        self.context_db_path = context_db_path
        self.calendar_db_path = calendar_db_path
        self.llm = llm
        self.tools = tools
        self.firm_name = firm_name
        self._histories: dict[str, list[ChatMessage]] = {}
        self._greeted: set[str] = set()

    def greeting(self, *, call_sid: str, agent_mode: str, caller_name: str | None = None) -> str:
        if agent_mode == "outbound_lead":
            name = caller_name or "there"
            return (
                f"Hi {name}, this is Donna with {self.firm_name}. "
                "I'm reaching out because we help people who've been injured in accidents. "
                "Do you have a quick minute?"
            )
        return (
            f"Thank you for calling {self.firm_name}. I'm Donna, an AI legal assistant. "
            "This call may be recorded. May I ask what happened?"
        )

    def handle_turn(
        self,
        *,
        call_sid: str,
        user_text: str,
        agent_mode: str = "inbound_intake",
        caller_name: str | None = None,
        is_returning: bool = False,
    ) -> RouterResult:
        session = telephony_db.get_call_session(self.telephony_db_path, call_sid)
        phase = session.phase if session else "DISCLOSURE"

        system_prompt = self._build_prompt(
            agent_mode=agent_mode,
            phase=phase,
            caller_name=caller_name,
            is_returning=is_returning,
            user_text=user_text,
        )

        history = self._histories.setdefault(call_sid, [])
        history.append(ChatMessage(role="user", content=user_text))
        tools_for_turn = self._tools_for_turn(agent_mode=agent_mode, phase=phase, user_text=user_text)
        enforce_consent = agent_mode != "local_assistant"
        max_sentences = self._reply_sentence_limit(agent_mode=agent_mode, tools_for_turn=tools_for_turn)
        first_token_seconds: float | None = None
        first_sentence_seconds: float | None = None
        fast_reply = self._fast_reply(
            agent_mode=agent_mode,
            phase=phase,
            user_text=user_text,
            tools_for_turn=tools_for_turn,
        )
        if fast_reply:
            history.append(ChatMessage(role="assistant", content=fast_reply))
            return RouterResult(reply=fast_reply, phase=phase)

        try:
            result = self.llm.chat(
                system_prompt=system_prompt,
                messages=history,
                tools=tools_for_turn,
            )
        except Exception:
            fallback = self.llm.generate_simple(system_prompt=system_prompt, user_text=user_text)
            history.append(ChatMessage(role="assistant", content=fallback))
            return RouterResult(reply=fallback, phase=phase)

        tool_results: list[dict] = []
        reply = result.text
        if max_sentences is not None and reply:
            reply = self._truncate_sentences(reply, max_sentences)

        for call in result.tool_calls:
            fn = call.get("function", {})
            tool_name = fn.get("name", "")
            args = self.llm.parse_tool_args(fn.get("arguments"))
            tool_result = self.tools.execute(
                call_sid=call_sid,
                tool_name=tool_name,
                args=args,
                enforce_consent=enforce_consent,
            )
            tool_results.append({"tool": tool_name, "ok": tool_result.ok, "data": tool_result.data, "error": tool_result.error})
            history.append(
                ChatMessage(
                    role="tool",
                    content=json.dumps({"tool": tool_name, "ok": tool_result.ok, "data": tool_result.data, "error": tool_result.error}),
                )
            )

        if result.tool_calls:
            immediate_reply = self._immediate_tool_reply(tool_results)
            if immediate_reply:
                reply = immediate_reply
            else:
                updated = telephony_db.get_call_session(self.telephony_db_path, call_sid)
                updated_phase = updated.phase if updated else phase
                follow_up_prompt = self._build_prompt(
                    agent_mode=agent_mode,
                    phase=updated_phase,
                    caller_name=caller_name,
                    is_returning=is_returning,
                    user_text=user_text,
                )
                follow_up = self.llm.chat(
                    system_prompt=follow_up_prompt,
                    messages=history,
                    tools=self._tools_for_turn(agent_mode=agent_mode, phase=updated_phase, user_text=user_text),
                )
                if follow_up.text:
                    reply = follow_up.text
                elif not reply:
                    reply = self._tool_fallback(tool_results)
        elif not reply:
            reply = "Got that. What else can you tell me about the incident?"

        if not reply:
            reply = self._tool_fallback(tool_results)

        history.append(ChatMessage(role="assistant", content=reply))
        updated = telephony_db.get_call_session(self.telephony_db_path, call_sid)
        return RouterResult(reply=reply, tool_results=tool_results, phase=updated.phase if updated else phase)

    async def stream_turn(
        self,
        *,
        call_sid: str,
        user_text: str,
        agent_mode: str = "inbound_intake",
        caller_name: str | None = None,
        is_returning: bool = False,
        on_sentence: SentenceHandler | None = None,
    ) -> RouterStreamOutcome:
        started = time.perf_counter()
        session = telephony_db.get_call_session(self.telephony_db_path, call_sid)
        phase = session.phase if session else "DISCLOSURE"

        system_prompt = self._build_prompt(
            agent_mode=agent_mode,
            phase=phase,
            caller_name=caller_name,
            is_returning=is_returning,
            user_text=user_text,
        )

        history = self._histories.setdefault(call_sid, [])
        history.append(ChatMessage(role="user", content=user_text))
        tools_for_turn = self._tools_for_turn(agent_mode=agent_mode, phase=phase, user_text=user_text)
        enforce_consent = agent_mode != "local_assistant"
        max_sentences = self._reply_sentence_limit(agent_mode=agent_mode, tools_for_turn=tools_for_turn)
        first_token_seconds: float | None = None
        first_sentence_seconds: float | None = None
        fast_reply = self._fast_reply(
            agent_mode=agent_mode,
            phase=phase,
            user_text=user_text,
            tools_for_turn=tools_for_turn,
        )
        if fast_reply:
            first_sentence_seconds = await self._emit_reply_text(
                fast_reply,
                on_sentence=on_sentence,
                started=started,
                first_sentence_seconds=first_sentence_seconds,
            )
            history.append(ChatMessage(role="assistant", content=fast_reply))
            return RouterStreamOutcome(
                result=RouterResult(reply=fast_reply, phase=phase),
                first_token_seconds=0.0,
                first_sentence_seconds=first_sentence_seconds,
            )

        try:
            streamed = await self._stream_reply(
                system_prompt=system_prompt,
                messages=history,
                tools=tools_for_turn,
                started=started,
                on_sentence=on_sentence,
                first_sentence_seconds=first_sentence_seconds,
                max_sentences=max_sentences,
            )
            reply = streamed["text"]
            tool_calls = streamed["tool_calls"]
            first_token_seconds = streamed["first_token_seconds"]
            first_sentence_seconds = streamed["first_sentence_seconds"]
        except Exception:
            fallback = self.llm.generate_simple(system_prompt=system_prompt, user_text=user_text)
            first_sentence_seconds = await self._emit_reply_text(
                fallback,
                on_sentence=on_sentence,
                started=started,
                first_sentence_seconds=first_sentence_seconds,
            )
            history.append(ChatMessage(role="assistant", content=fallback))
            return RouterStreamOutcome(
                result=RouterResult(reply=fallback, phase=phase),
                first_token_seconds=first_token_seconds,
                first_sentence_seconds=first_sentence_seconds,
            )

        tool_results: list[dict] = []
        for call in tool_calls:
            fn = call.get("function", {})
            tool_name = fn.get("name", "")
            args = self.llm.parse_tool_args(fn.get("arguments"))
            tool_result = self.tools.execute(
                call_sid=call_sid,
                tool_name=tool_name,
                args=args,
                enforce_consent=enforce_consent,
            )
            tool_results.append({"tool": tool_name, "ok": tool_result.ok, "data": tool_result.data, "error": tool_result.error})
            history.append(
                ChatMessage(
                    role="tool",
                    content=json.dumps({"tool": tool_name, "ok": tool_result.ok, "data": tool_result.data, "error": tool_result.error}),
                )
            )

        if tool_calls:
            immediate_reply = self._immediate_tool_reply(tool_results)
            if immediate_reply:
                reply = immediate_reply
                first_sentence_seconds = await self._emit_reply_text(
                    reply,
                    on_sentence=on_sentence,
                    started=started,
                    first_sentence_seconds=first_sentence_seconds,
                )
            else:
                updated = telephony_db.get_call_session(self.telephony_db_path, call_sid)
                updated_phase = updated.phase if updated else phase
                follow_up_prompt = self._build_prompt(
                    agent_mode=agent_mode,
                    phase=updated_phase,
                    caller_name=caller_name,
                    is_returning=is_returning,
                    user_text=user_text,
                )
                try:
                    follow_up = await self._stream_reply(
                        system_prompt=follow_up_prompt,
                        messages=history,
                        tools=self._tools_for_turn(agent_mode=agent_mode, phase=updated_phase, user_text=user_text),
                        started=started,
                        on_sentence=on_sentence,
                        first_sentence_seconds=first_sentence_seconds,
                        max_sentences=max_sentences,
                    )
                    if follow_up["text"]:
                        reply = follow_up["text"]
                    elif not reply:
                        reply = self._tool_fallback(tool_results)
                    if first_token_seconds is None:
                        first_token_seconds = follow_up["first_token_seconds"]
                    first_sentence_seconds = follow_up["first_sentence_seconds"]
                except Exception:
                    if not reply:
                        reply = self._tool_fallback(tool_results)
                        first_sentence_seconds = await self._emit_reply_text(
                            reply,
                            on_sentence=on_sentence,
                            started=started,
                            first_sentence_seconds=first_sentence_seconds,
                        )
        elif not reply:
            reply = "Got that. What else can you tell me about the incident?"
            first_sentence_seconds = await self._emit_reply_text(
                reply,
                on_sentence=on_sentence,
                started=started,
                first_sentence_seconds=first_sentence_seconds,
            )

        if not reply:
            reply = self._tool_fallback(tool_results)
            first_sentence_seconds = await self._emit_reply_text(
                reply,
                on_sentence=on_sentence,
                started=started,
                first_sentence_seconds=first_sentence_seconds,
            )

        history.append(ChatMessage(role="assistant", content=reply))
        updated = telephony_db.get_call_session(self.telephony_db_path, call_sid)
        return RouterStreamOutcome(
            result=RouterResult(reply=reply, tool_results=tool_results, phase=updated.phase if updated else phase),
            first_token_seconds=first_token_seconds,
            first_sentence_seconds=first_sentence_seconds,
        )

    @staticmethod
    def _tool_fallback(tool_results: list[dict]) -> str:
        for item in tool_results:
            if not item.get("ok"):
                error = item.get("error") or ""
                if "Missing required consent" in error:
                    return "I need your permission before we continue. May I record this call and proceed with intake?"
                return "I hit a snag saving that detail. Could you repeat the key information one more time?"
            if item.get("tool") == "calendar.create_event":
                data = item.get("data") or {}
                return data.get("formatted_confirmation", "Your consultation is booked.")
            if item.get("tool") == "case.decline":
                return "Thank you for sharing your situation. We aren't able to take this case, but I wish you the best."
            if item.get("tool") == "case.create":
                return "I've opened the case details. If you'd like, we can book the next step now."
        return "Noted. What else should I know about the incident?"

    @staticmethod
    def _immediate_tool_reply(tool_results: list[dict]) -> str | None:
        has_recorded_consent = False
        for item in tool_results:
            if not item.get("ok"):
                return None
            data = item.get("data") or {}
            if item.get("tool") == "calendar.create_event" and data.get("formatted_confirmation"):
                return data["formatted_confirmation"]
            if item.get("tool") == "case.decline":
                return "Thank you for sharing your situation. We aren't able to take this case, but I wish you the best."
            if item.get("tool") == "case.create":
                return "I've opened the case details. If you'd like, we can book the next step now."
            if item.get("tool") == "record_consent":
                has_recorded_consent = True
        if has_recorded_consent:
            return "Thanks. I've noted your consent. Please tell me what happened."
        return None

    async def _stream_reply(
        self,
        *,
        system_prompt: str,
        messages: list[ChatMessage],
        tools: list[dict],
        started: float,
        on_sentence: SentenceHandler | None,
        first_sentence_seconds: float | None,
        max_sentences: int | None,
    ) -> dict:
        full_text = ""
        buffer = ""
        tool_calls: list[dict] = []
        first_token_seconds: float | None = None
        emitted_sentences: list[str] = []
        async for chunk in self.llm.chat_stream(
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
        ):
            full_text = chunk.text.strip()
            if first_token_seconds is None and chunk.first_token_seconds is not None:
                first_token_seconds = chunk.first_token_seconds
            if chunk.tool_calls:
                tool_calls = list(chunk.tool_calls)
            if not chunk.text_delta:
                continue
            buffer += chunk.text_delta
            sentences, buffer = self._split_complete_sentences(buffer)
            for sentence in sentences:
                first_sentence_seconds = await self._emit_sentence(
                    sentence,
                    on_sentence=on_sentence,
                    started=started,
                    first_sentence_seconds=first_sentence_seconds,
                )
                emitted_sentences.append(sentence.strip())
                if max_sentences is not None and len(emitted_sentences) >= max_sentences:
                    full_text = " ".join(emitted_sentences)
                    buffer = ""
                    return {
                        "text": full_text,
                        "tool_calls": tool_calls,
                        "first_token_seconds": first_token_seconds,
                        "first_sentence_seconds": first_sentence_seconds,
                    }

        if buffer.strip():
            if max_sentences is not None and len(emitted_sentences) >= max_sentences:
                buffer = ""
            else:
                sentence = buffer.strip()
                emitted_sentences.append(sentence)
                full_text = " ".join(emitted_sentences)
                buffer = ""
            first_sentence_seconds = await self._emit_sentence(
                emitted_sentences[-1],
                on_sentence=on_sentence,
                started=started,
                first_sentence_seconds=first_sentence_seconds,
            )
        elif emitted_sentences:
            full_text = " ".join(emitted_sentences)

        return {
            "text": full_text,
            "tool_calls": tool_calls,
            "first_token_seconds": first_token_seconds,
            "first_sentence_seconds": first_sentence_seconds,
        }

    async def _emit_reply_text(
        self,
        text: str,
        *,
        on_sentence: SentenceHandler | None,
        started: float,
        first_sentence_seconds: float | None,
    ) -> float | None:
        for sentence in self._split_fallback_sentences(text):
            first_sentence_seconds = await self._emit_sentence(
                sentence,
                on_sentence=on_sentence,
                started=started,
                first_sentence_seconds=first_sentence_seconds,
            )
        return first_sentence_seconds

    @staticmethod
    async def _emit_sentence(
        sentence: str,
        *,
        on_sentence: SentenceHandler | None,
        started: float,
        first_sentence_seconds: float | None,
    ) -> float | None:
        text = sentence.strip()
        if not text:
            return first_sentence_seconds
        if first_sentence_seconds is None:
            first_sentence_seconds = round(time.perf_counter() - started, 3)
        if on_sentence is not None:
            maybe_awaitable = on_sentence(text)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
        return first_sentence_seconds

    @staticmethod
    def _split_complete_sentences(buffer: str) -> tuple[list[str], str]:
        sentences: list[str] = []
        last_end = 0
        for match in re.finditer(r".+?[.!?](?:['\")\]]+)?(?:\s+|$)", buffer, flags=re.S):
            sentences.append(match.group(0).strip())
            last_end = match.end()
        return sentences, buffer[last_end:]

    @classmethod
    def _split_fallback_sentences(cls, text: str) -> list[str]:
        sentences, remainder = cls._split_complete_sentences(text)
        if remainder.strip():
            sentences.append(remainder.strip())
        return sentences

    @staticmethod
    def _tools_for_turn(*, agent_mode: str, phase: str, user_text: str = "") -> list[dict]:
        mapping = LOCAL_ASSISTANT_PHASE_TOOL_NAMES if agent_mode == "local_assistant" else PHASE_TOOL_NAMES
        tool_names = mapping.get(phase, mapping["INTAKE"])
        return [
            TOOL_DEFINITION_BY_NAME[name]
            for name in tool_names
            if name in TOOL_DEFINITION_BY_NAME
        ]

    @staticmethod
    def _local_assistant_needs_tools(user_text: str, phase: str) -> bool:
        text = user_text.lower()
        if phase in {"BOOKING", "CLOSE"}:
            return True
        tool_keywords = (
            "intake",
            "start",
            "update",
            "book",
            "schedule",
            "calendar",
            "consult",
            "appointment",
            "create case",
            "open case",
            "decline",
            "consent",
            "record",
            "dashboard",
        )
        return any(keyword in text for keyword in tool_keywords)

    @staticmethod
    def _reply_sentence_limit(*, agent_mode: str, tools_for_turn: list[dict]) -> int | None:
        if agent_mode == "local_assistant" and not tools_for_turn:
            return LOCAL_ASSISTANT_SENTENCE_LIMIT
        return None

    @staticmethod
    def _fast_reply(
        *,
        agent_mode: str,
        phase: str,
        user_text: str,
        tools_for_turn: list[dict],
    ) -> str | None:
        if agent_mode != "local_assistant" or phase != "DISCLOSURE" or tools_for_turn:
            return None
        normalized = re.sub(r"[^a-z0-9\s']", " ", user_text.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized:
            return None
        greeting_patterns = {
            "hi",
            "hello",
            "hey",
            "yo",
            "sup",
            "what's up",
            "whats up",
            "hey what's up",
            "hello what's up",
            "yo what's up",
        }
        if normalized in greeting_patterns:
            return "Hi there!"
        if any(term in normalized for term in ("injury", "attorney", "lawyer", "case", "claim")):
            return "Sure thing. Tell me what happened."
        return None

    @classmethod
    def _truncate_sentences(cls, text: str, sentence_limit: int) -> str:
        sentences = cls._split_fallback_sentences(text)
        if not sentences:
            return text.strip()
        return " ".join(sentences[:sentence_limit]).strip()

    def _build_prompt(
        self,
        *,
        agent_mode: str,
        phase: str,
        caller_name: str | None,
        is_returning: bool,
        user_text: str,
    ) -> str:
        context_block = lookup_context_block(user_text, db_path=self.context_db_path)
        if agent_mode == "local_assistant":
            return build_local_assistant_prompt(
                firm_name=self.firm_name,
                phase=phase,
                context_block=context_block,
            )
        if agent_mode == "outbound_lead":
            prompt = build_outbound_prompt(firm_name=self.firm_name, phase=phase, caller_name=caller_name)
        else:
            prompt = build_inbound_prompt(
                firm_name=self.firm_name,
                phase=phase,
                caller_name=caller_name,
                is_returning=is_returning,
            )
        if context_block:
            prompt = f"{prompt}\n\n{context_block}\nUse relevant case context when it helps answer directly."
        return prompt
