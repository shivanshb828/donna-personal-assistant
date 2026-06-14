from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TelephonyConfig:
    port: int
    public_url: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str
    telephony_db: Path
    context_db: Path
    calendar_db: Path
    dashboard_ws: str
    ollama_url: str
    ollama_model: str
    firm_name: str
    echo_mode: bool
    validate_twilio_signature: bool

    @classmethod
    def from_env(cls) -> TelephonyConfig:
        return cls(
            port=int(os.getenv("DONNA_TELEPHONY_PORT", "3002")),
            public_url=os.getenv("PUBLIC_URL", "http://localhost:3002"),
            twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
            twilio_phone_number=os.getenv("TWILIO_PHONE_NUMBER", ""),
            telephony_db=Path(os.getenv("DONNA_TELEPHONY_DB", "data/donna_telephony.sqlite")),
            context_db=Path(os.getenv("DONNA_CONTEXT_DB", "data/donna_m3_context.sqlite")),
            calendar_db=Path(os.getenv("DONNA_CALENDAR_DB", "data/donna_m3_calendar.sqlite")),
            dashboard_ws=os.getenv("DONNA_DASHBOARD_WS", "ws://localhost:3001"),
            ollama_url=os.getenv("DONNA_OLLAMA_URL", "http://localhost:11434"),
            ollama_model=os.getenv("DONNA_MODEL", "nemotron-3-nano"),
            firm_name=os.getenv("DONNA_FIRM_NAME", "Donna Legal"),
            echo_mode=os.getenv("DONNA_TELEPHONY_ECHO", "").lower() in {"1", "true", "yes"},
            validate_twilio_signature=os.getenv("DONNA_VALIDATE_TWILIO", "true").lower()
            not in {"0", "false", "no"},
        )

    @property
    def media_stream_ws_url(self) -> str:
        return self.public_url.replace("https://", "wss://").replace("http://", "ws://") + "/media-stream"

    @property
    def twilio_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_phone_number)
