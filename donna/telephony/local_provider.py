from __future__ import annotations

import asyncio
import base64
import json
import time
from dataclasses import dataclass, field

from donna.glue.router.session_router import SessionRouter
from donna.telephony.audio import twilio_payload_to_pcm16_16k, wav_to_twilio_payload
from donna.telephony.events import broadcast_event
from donna.voice.stt import transcribe_audio
from donna.voice.tts import synthesize
from donna.voice.vad import EnergyVAD


CHUNK_SAMPLES_16K = 512
CHUNK_BYTES_16K = CHUNK_SAMPLES_16K * 2
TWILIO_FRAME_BYTES = 160  # 20ms at 8kHz mu-law


@dataclass
class LocalVoiceSession:
    call_sid: str
    stream_sid: str
    agent_mode: str
    caller_name: str | None
    is_returning: bool
    router: SessionRouter
    dashboard_ws: str
    echo_mode: bool
    started_at: float = field(default_factory=time.time)
    transcript_lines: list[str] = field(default_factory=list)
    pcm_buffer: bytes = b""
    vad: EnergyVAD = field(default_factory=EnergyVAD)
    greeting_sent: bool = False
    speaking_until: float = 0.0
    turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def handle_mulaw_frame(self, payload_b64: str) -> list[str]:
        if self.echo_mode:
            return [payload_b64]

        if time.time() < self.speaking_until:
            return []

        pcm16 = twilio_payload_to_pcm16_16k(payload_b64)
        combined = self.pcm_buffer + pcm16
        self.pcm_buffer = b""
        responses: list[str] = []

        offset = 0
        while offset + CHUNK_BYTES_16K <= len(combined):
            chunk = combined[offset : offset + CHUNK_BYTES_16K]
            offset += CHUNK_BYTES_16K
            result = self.vad.process(chunk)
            if result["speech_ended"]:
                spoken = await self._on_speech(result["audio"])
                responses.extend(spoken)

        if offset < len(combined):
            self.pcm_buffer = combined[offset:]

        return responses

    async def send_greeting(self) -> list[str]:
        if self.greeting_sent:
            return []
        self.greeting_sent = True
        text = self.router.greeting(
            call_sid=self.call_sid,
            agent_mode=self.agent_mode,
            caller_name=self.caller_name,
        )
        return await self._speak(text)

    async def _on_speech(self, audio: bytes) -> list[str]:
        if not audio:
            return []
        async with self.turn_lock:
            try:
                text = await asyncio.to_thread(transcribe_audio, audio)
                if not text:
                    return []
                self.transcript_lines.append(f"Caller: {text}")
                await broadcast_event(self.dashboard_ws, {
                    "type": "user_speech",
                    "callSid": self.call_sid,
                    "text": text,
                })
                await broadcast_event(self.dashboard_ws, {
                    "type": "pipeline_status",
                    "status": "processing",
                    "callSid": self.call_sid,
                })

                result = await asyncio.to_thread(
                    self.router.handle_turn,
                    call_sid=self.call_sid,
                    user_text=text,
                    agent_mode=self.agent_mode,
                    caller_name=self.caller_name,
                    is_returning=self.is_returning,
                )
                self.transcript_lines.append(f"Donna: {result.reply}")
                for tool_result in result.tool_results:
                    await broadcast_event(self.dashboard_ws, {
                        "type": "tool_result",
                        "callSid": self.call_sid,
                        **tool_result,
                    })
                return await self._speak(result.reply)
            except Exception as exc:
                fallback = "I'm sorry, I had trouble processing that. Could you repeat that?"
                self.transcript_lines.append(f"Donna: {fallback} [{exc}]")
                return await self._speak(fallback)

    async def _speak(self, text: str) -> list[str]:
        await broadcast_event(self.dashboard_ws, {
            "type": "donna_speech",
            "callSid": self.call_sid,
            "text": text,
        })
        await broadcast_event(self.dashboard_ws, {
            "type": "pipeline_status",
            "status": "speaking",
            "callSid": self.call_sid,
        })
        wav = await asyncio.to_thread(synthesize, text)
        payload = wav_to_twilio_payload(wav)
        mulaw = base64.b64decode(payload)
        frames = [
            base64.b64encode(mulaw[i : i + TWILIO_FRAME_BYTES]).decode("ascii")
            for i in range(0, len(mulaw), TWILIO_FRAME_BYTES)
        ]
        # Approximate playback duration so inbound VAD is suppressed during TTS.
        self.speaking_until = time.time() + max(0.5, len(mulaw) / 8000.0)
        await broadcast_event(self.dashboard_ws, {
            "type": "pipeline_status",
            "status": "listening",
            "callSid": self.call_sid,
        })
        return frames

    def clear_playback(self) -> None:
        self.speaking_until = 0.0

    @property
    def transcript(self) -> str:
        return "\n".join(self.transcript_lines)


def build_media_message(*, stream_sid: str, payload_b64: str) -> str:
    return json.dumps({"event": "media", "streamSid": stream_sid, "media": {"payload": payload_b64}})
