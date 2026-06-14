from __future__ import annotations

import secrets
import time
from dataclasses import dataclass


@dataclass
class StreamTokenEntry:
    call_sid: str
    expires_at: float


class StreamTokenStore:
    def __init__(self, ttl_seconds: float = 120.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._tokens: dict[str, StreamTokenEntry] = {}

    def issue(self, call_sid: str) -> str:
        self._purge_expired()
        token = secrets.token_hex(32)
        self._tokens[token] = StreamTokenEntry(call_sid=call_sid, expires_at=time.time() + self.ttl_seconds)
        return token

    def consume(self, call_sid: str, token: str | None) -> bool:
        if not token:
            return False
        self._purge_expired()
        entry = self._tokens.get(token)
        if not entry or entry.call_sid != call_sid or time.time() > entry.expires_at:
            return False
        del self._tokens[token]
        return True

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [token for token, entry in self._tokens.items() if now > entry.expires_at]
        for token in expired:
            del self._tokens[token]
