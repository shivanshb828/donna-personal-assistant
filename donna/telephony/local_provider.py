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
from donna.voice.tts import SentenceSynthesisQueue, synthesize
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
    vad: EnergyVAD = field(default_factory=lambda: EnergyVAD(profile="telephony"))
    greeting_sent: bool = False
    speaking_until: float = 0.0
    speaking: bool = False
    turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    outbound_frames: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    turn_task: asyncio.Task[None] | None = None
    active_tts: SentenceSynthesisQueue | None = None
    turn_interrupted: bool = False

    async def handle_mulaw_frame(self, payload_b64: str) -> list[str]:
        if self.echo_mode:
            return [payload_b64]

        pcm16 = twilio_payload_to_pcm16_16k(payload_b64)
        combined = self.pcm_buffer + pcm16
        self.pcm_buffer = b""
        responses = self._drain_outbound_frames()

        offset = 0
        while offset + CHUNK_BYTES_16K <= len(combined):
            chunk = combined[offset : offset + CHUNK_BYTES_16K]
            offset += CHUNK_BYTES_16K
            result = self.vad.process(chunk)
            if self.speaking and result["is_speaking"]:
                self._interrupt_current_turn()
            if result["speech_ended"]:
                self._start_turn(result["audio"])

        if offset < len(combined):
            self.pcm_buffer = combined[offset:]

        responses.extend(self._drain_outbound_frames())
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
            total_started = time.perf_counter()
            frames: list[str] = []
            self.turn_interrupted = False
            try:
                stt_started = time.perf_counter()
                text = await asyncio.to_thread(transcribe_audio, audio)
                stt_seconds = time.perf_counter() - stt_started
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

                llm_started = time.perf_counter()
                tts_queue = SentenceSynthesisQueue(
                    audio_handler=lambda sentence, wav, stop_event: self._queue_audio_frames(
                        sentence=sentence,
                        audio=wav,
                        stop_event=stop_event,
                        frames=frames,
                    ),
                    started_at=total_started,
                )
                self.active_tts = tts_queue

                async def _on_sentence(sentence: str) -> None:
                    await broadcast_event(self.dashboard_ws, {
                        "type": "donna_speech",
                        "callSid": self.call_sid,
                        "text": sentence,
                    })
                    await tts_queue.enqueue(sentence)

                outcome = await self.router.stream_turn(
                    call_sid=self.call_sid,
                    user_text=text,
                    agent_mode=self.agent_mode,
                    caller_name=self.caller_name,
                    is_returning=self.is_returning,
                    on_sentence=_on_sentence,
                )
                llm_seconds = time.perf_counter() - llm_started
                self.transcript_lines.append(f"Donna: {outcome.result.reply}")
                for tool_result in outcome.result.tool_results:
                    await broadcast_event(self.dashboard_ws, {
                        "type": "tool_result",
                        "callSid": self.call_sid,
                        **tool_result,
                    })
                tts_stats = await tts_queue.finish()
                self.active_tts = None
                self.speaking = False
                await broadcast_event(self.dashboard_ws, {
                    "type": "pipeline_status",
                    "status": "listening",
                    "callSid": self.call_sid,
                })
                timing = {
                    "type": "turn_timing",
                    "callSid": self.call_sid,
                    "stt_seconds": round(stt_seconds, 3),
                    "llm_seconds": round(llm_seconds, 3),
                    "first_token_seconds": outcome.first_token_seconds,
                    "first_sentence_seconds": outcome.first_sentence_seconds,
                    "first_audio_seconds": tts_stats.first_audio_seconds,
                    "tts_total_seconds": round(tts_stats.total_seconds, 3),
                    "interrupted": self.turn_interrupted,
                    "total_seconds": round(time.perf_counter() - total_started, 3),
                }
                print(
                    "[Timing] "
                    f"callSid={self.call_sid} "
                    f"stt_seconds={timing['stt_seconds']:.3f}s "
                    f"llm_seconds={timing['llm_seconds']:.3f}s "
                    f"first_audio_seconds={timing['first_audio_seconds'] or 0.0:.3f}s "
                    f"tts_total_seconds={timing['tts_total_seconds']:.3f}s "
                    f"total_seconds={timing['total_seconds']:.3f}s"
                )
                await broadcast_event(self.dashboard_ws, timing)
                return frames
            except asyncio.CancelledError:
                self.turn_interrupted = True
                if self.active_tts is not None:
                    self.active_tts.cancel()
                    self.active_tts = None
                self.speaking = False
                await broadcast_event(self.dashboard_ws, {
                    "type": "turn_timing",
                    "callSid": self.call_sid,
                    "interrupted": True,
                    "total_seconds": round(time.perf_counter() - total_started, 3),
                })
                await broadcast_event(self.dashboard_ws, {
                    "type": "pipeline_status",
                    "status": "listening",
                    "callSid": self.call_sid,
                    "interrupted": True,
                })
                raise
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
        self._interrupt_current_turn()
        self.speaking_until = 0.0

    @property
    def transcript(self) -> str:
        return "\n".join(self.transcript_lines)

    def _start_turn(self, audio: bytes) -> None:
        if not audio:
            return
        if self.turn_task is not None and not self.turn_task.done():
            return
        self.turn_task = asyncio.create_task(self._run_turn(audio))

    async def _run_turn(self, audio: bytes) -> None:
        try:
            await self._on_speech(audio)
        except asyncio.CancelledError:
            return
        finally:
            self.turn_task = None

    def _interrupt_current_turn(self) -> None:
        if self.active_tts is not None:
            self.active_tts.cancel()
        if self.turn_task is not None and not self.turn_task.done():
            self.turn_interrupted = True
            self.turn_task.cancel()
        self.speaking = False
        while True:
            try:
                self.outbound_frames.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _queue_audio_frames(
        self,
        *,
        sentence: str,
        audio: bytes,
        stop_event,
        frames: list[str],
    ) -> None:
        if not self.speaking:
            self.speaking = True
            await broadcast_event(self.dashboard_ws, {
                "type": "pipeline_status",
                "status": "speaking",
                "callSid": self.call_sid,
            })
        payload = wav_to_twilio_payload(audio)
        mulaw = base64.b64decode(payload)
        self.speaking_until = time.time() + max(0.5, len(mulaw) / 8000.0)
        for i in range(0, len(mulaw), TWILIO_FRAME_BYTES):
            if stop_event.is_set():
                return
            frame = base64.b64encode(mulaw[i : i + TWILIO_FRAME_BYTES]).decode("ascii")
            frames.append(frame)
            await self.outbound_frames.put(frame)

    def _drain_outbound_frames(self) -> list[str]:
        frames: list[str] = []
        while True:
            try:
                frames.append(self.outbound_frames.get_nowait())
            except asyncio.QueueEmpty:
                break
        return frames


def build_media_message(*, stream_sid: str, payload_b64: str) -> str:
    return json.dumps({"event": "media", "streamSid": stream_sid, "media": {"payload": payload_b64}})
