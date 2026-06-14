from __future__ import annotations

import base64
import io
import struct
import wave

import numpy as np


MULAW_BIAS = 0x84
MULAW_CLIP = 32635


def _linear_to_mulaw(sample: int) -> int:
    sign = 0x80 if sample < 0 else 0
    if sample < 0:
        sample = -sample
    sample = min(sample, MULAW_CLIP) + MULAW_BIAS
    exponent = 7
    mask = 0x4000
    while exponent > 0 and not (sample & mask):
        mask >>= 1
        exponent -= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def _mulaw_to_linear(byte: int) -> int:
    byte = ~byte & 0xFF
    sign = byte & 0x80
    exponent = (byte >> 4) & 0x07
    mantissa = byte & 0x0F
    sample = ((mantissa << 3) + MULAW_BIAS) << exponent
    sample -= MULAW_BIAS
    return -sample if sign else sample


def decode_mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    samples = struct.pack("<" + "h" * len(mulaw_bytes), *(_mulaw_to_linear(b) for b in mulaw_bytes))
    return samples


def encode_pcm16_to_mulaw(pcm16_bytes: bytes) -> bytes:
    samples = struct.unpack("<" + "h" * (len(pcm16_bytes) // 2), pcm16_bytes)
    return bytes(_linear_to_mulaw(s) for s in samples)


def resample_pcm16(pcm16_bytes: bytes, from_rate: int, to_rate: int) -> bytes:
    if from_rate == to_rate or not pcm16_bytes:
        return pcm16_bytes
    samples = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32)
    ratio = to_rate / from_rate
    output_len = max(1, int(len(samples) * ratio))
    src_idx = np.arange(output_len, dtype=np.float32) / ratio
    lo = np.floor(src_idx).astype(np.int64)
    hi = np.minimum(lo + 1, len(samples) - 1)
    frac = src_idx - lo
    resampled = samples[lo] * (1.0 - frac) + samples[hi] * frac
    return resampled.astype(np.int16).tobytes()


def twilio_payload_to_pcm16_16k(base64_mulaw: str) -> bytes:
    mulaw = base64.b64decode(base64_mulaw)
    pcm8k = decode_mulaw_to_pcm16(mulaw)
    return resample_pcm16(pcm8k, 8000, 16000)


def wav_bytes_to_pcm16(wav_bytes: bytes) -> tuple[bytes, int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        rate = wf.getframerate()
        pcm = wf.readframes(wf.getnframes())
    return pcm, rate


def pcm16_to_twilio_payload(pcm16_bytes: bytes, sample_rate: int) -> str:
    pcm8k = resample_pcm16(pcm16_bytes, sample_rate, 8000)
    mulaw = encode_pcm16_to_mulaw(pcm8k)
    return base64.b64encode(mulaw).decode("ascii")


def wav_to_twilio_payload(wav_bytes: bytes) -> str:
    pcm, rate = wav_bytes_to_pcm16(wav_bytes)
    return pcm16_to_twilio_payload(pcm, rate)
