from __future__ import annotations

import base64
import struct

import pytest

from donna.telephony.audio import (
    decode_mulaw_to_pcm16,
    encode_pcm16_to_mulaw,
    pcm16_to_twilio_payload,
    resample_pcm16,
    twilio_payload_to_pcm16_16k,
)


class TestAudioCodec:
    def test_mulaw_roundtrip(self):
        samples = struct.pack("<hh", -1000, 5000)
        mulaw = encode_pcm16_to_mulaw(samples)
        pcm = decode_mulaw_to_pcm16(mulaw)
        assert len(pcm) == len(samples)

    def test_resample_identity(self):
        pcm = struct.pack("<" + "h" * 100, *range(100))
        assert resample_pcm16(pcm, 16000, 16000) == pcm

    def test_twilio_payload_roundtrip(self):
        pcm16 = struct.pack("<" + "h" * 160, *([1000] * 160))
        payload = pcm16_to_twilio_payload(pcm16, 16000)
        decoded = twilio_payload_to_pcm16_16k(payload)
        assert len(decoded) > 0

    def test_payload_is_base64(self):
        pcm16 = struct.pack("<" + "h" * 80, *([500] * 80))
        payload = pcm16_to_twilio_payload(pcm16, 16000)
        base64.b64decode(payload)
