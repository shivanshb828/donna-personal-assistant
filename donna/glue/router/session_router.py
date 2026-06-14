from __future__ import annotations

import json

from dataclasses import dataclass, field

from donna.glue.prompts.inbound_intake import build_inbound_prompt
from donna.glue.prompts.outbound_lead import build_outbound_prompt
from donna.glue.tools.registry import ToolRegistry
from donna.telephony import db as telephony_db
from donna.telephony.llm import ChatMessage, DonnaLLM


@dataclass
class RouterResult:
    reply: str
    tool_results: list[dict] = field(default_factory=list)
    phase: str = "DISCLOSURE"


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
        )

        history = self._histories.setdefault(call_sid, [])
        history.append(ChatMessage(role="user", content=user_text))

        from donna.glue.tools.registry import TOOL_DEFINITIONS

        try:
            result = self.llm.chat(
                system_prompt=system_prompt,
                messages=history,
                tools=TOOL_DEFINITIONS,
            )
        except Exception:
            fallback = self.llm.generate_simple(system_prompt=system_prompt, user_text=user_text)
            history.append(ChatMessage(role="assistant", content=fallback))
            return RouterResult(reply=fallback, phase=phase)

        tool_results: list[dict] = []
        reply = result.text

        for call in result.tool_calls:
            fn = call.get("function", {})
            tool_name = fn.get("name", "")
            args = self.llm.parse_tool_args(fn.get("arguments"))
            tool_result = self.tools.execute(call_sid=call_sid, tool_name=tool_name, args=args)
            tool_results.append({"tool": tool_name, "ok": tool_result.ok, "data": tool_result.data, "error": tool_result.error})
            history.append(
                ChatMessage(
                    role="tool",
                    content=json.dumps({"tool": tool_name, "ok": tool_result.ok, "data": tool_result.data, "error": tool_result.error}),
                )
            )

        if result.tool_calls:
            follow_up = self.llm.chat(system_prompt=system_prompt, messages=history, tools=TOOL_DEFINITIONS)
            if follow_up.text:
                reply = follow_up.text
            elif not reply:
                reply = self._tool_fallback(tool_results)
        elif not reply:
            reply = "I understand. Could you tell me a bit more about what happened?"

        if not reply:
            reply = self._tool_fallback(tool_results)

        history.append(ChatMessage(role="assistant", content=reply))
        updated = telephony_db.get_call_session(self.telephony_db_path, call_sid)
        return RouterResult(reply=reply, tool_results=tool_results, phase=updated.phase if updated else phase)

    @staticmethod
    def _tool_fallback(tool_results: list[dict]) -> str:
        for item in tool_results:
            if not item.get("ok"):
                return "I need your permission before we continue. May I record this call and proceed with intake?"
            if item.get("tool") == "calendar.create_event":
                data = item.get("data") or {}
                return data.get("formatted_confirmation", "Your consultation is booked.")
            if item.get("tool") == "case.decline":
                return "Thank you for sharing your situation. We aren't able to take this case, but I wish you the best."
        return "Thanks — I've noted that. What else can you tell me about the incident?"

    def _build_prompt(
        self,
        *,
        agent_mode: str,
        phase: str,
        caller_name: str | None,
        is_returning: bool,
    ) -> str:
        if agent_mode == "outbound_lead":
            return build_outbound_prompt(firm_name=self.firm_name, phase=phase, caller_name=caller_name)
        return build_inbound_prompt(
            firm_name=self.firm_name,
            phase=phase,
            caller_name=caller_name,
            is_returning=is_returning,
        )
