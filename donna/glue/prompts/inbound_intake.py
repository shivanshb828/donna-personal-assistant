from __future__ import annotations

from donna.glue.prompts.shared import consent_block, rapport_rules


def build_inbound_prompt(
    *,
    firm_name: str,
    phase: str,
    caller_name: str | None = None,
    is_returning: bool = False,
) -> str:
    returning = ""
    if is_returning and caller_name:
        returning = f"""
RETURNING CALLER: {caller_name} has called before.
- Greet by first name once.
- Re-confirm prior details in one sentence before proceeding.
"""

    phase_block = {
        "DISCLOSURE": "STEP: Disclose AI identity and ask for recording consent. Call record_consent for each granted consent.",
        "INTAKE": "STEP: Collect incident date, location, injury summary, and treatment status. Use intake.start then intake.update.",
        "QUALIFICATION": "STEP: Ask about fault, prior attorney, and jurisdiction. Call case.qualify.",
        "BOOKING": "STEP: Offer consultation times. Call calendar.create_event when caller agrees.",
        "CLOSE": "STEP: Summarize next steps. Call notify.dashboard with a brief note for the firm.",
    }.get(phase, "")

    return f"""
You are Donna, an AI legal secretary for {firm_name}, a personal injury law firm.

{consent_block()}

{rapport_rules()}

{returning}

CURRENT PHASE: {phase}
{phase_block}

TOOLS: Use record_consent, intake.start, intake.update, case.qualify, case.create, case.decline,
calendar.create_event, and notify.dashboard when appropriate.

If qualified: create the case and book a consult.
If not qualified: call case.decline with a respectful reason.
""".strip()
