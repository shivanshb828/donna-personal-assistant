from __future__ import annotations

import json

from dataclasses import dataclass, field

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
        tools_for_turn = self._tools_for_turn(agent_mode=agent_mode, phase=phase)
        enforce_consent = agent_mode != "local_assistant"

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
                    tools=self._tools_for_turn(agent_mode=agent_mode, phase=updated_phase),
                )
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
        return "Thanks - I've noted that. What else can you tell me about the incident?"

    @staticmethod
    def _immediate_tool_reply(tool_results: list[dict]) -> str | None:
        for item in tool_results:
            if not item.get("ok"):
                return None
            data = item.get("data") or {}
            if item.get("tool") == "calendar.create_event" and data.get("formatted_confirmation"):
                return data["formatted_confirmation"]
            if item.get("tool") == "case.decline":
                return "Thank you for sharing your situation. We aren't able to take this case, but I wish you the best."
        return None

    @staticmethod
    def _tools_for_turn(*, agent_mode: str, phase: str) -> list[dict]:
        mapping = LOCAL_ASSISTANT_PHASE_TOOL_NAMES if agent_mode == "local_assistant" else PHASE_TOOL_NAMES
        tool_names = mapping.get(phase, mapping["INTAKE"])
        return [
            TOOL_DEFINITION_BY_NAME[name]
            for name in tool_names
            if name in TOOL_DEFINITION_BY_NAME
        ]

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
