from __future__ import annotations

import base64
import io
import json
import math
import shutil
import subprocess
import wave
from typing import Iterable

import numpy as np

from .errors import OpenAIHTTPException


MEDIA_TYPES = {
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/pcm",
}


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    return clipped.reshape(-1)


def float_audio_to_int16(audio: np.ndarray) -> np.ndarray:
    normalized = normalize_audio(audio)
    return np.asarray(normalized * 32767.0, dtype=np.int16)


def encode_wav(audio: np.ndarray, sample_rate: int) -> bytes:
    pcm = float_audio_to_int16(audio)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())
    return buffer.getvalue()


def encode_pcm(audio: np.ndarray) -> bytes:
    return float_audio_to_int16(audio).tobytes()


def _encode_with_ffmpeg(wav_bytes: bytes, response_format: str) -> bytes:
    if shutil.which("ffmpeg") is None:
        raise OpenAIHTTPException(
            status_code=500,
            message=f"ffmpeg is required to generate {response_format} output.",
            error_type="server_error",
            code="ffmpeg_missing",
        )

    format_args = {
        "mp3": ["-f", "mp3"],
        "opus": ["-c:a", "libopus", "-f", "opus"],
        "aac": ["-c:a", "aac", "-f", "adts"],
        "flac": ["-f", "flac"],
    }
    args = format_args[response_format]
    process = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", "pipe:0", *args, "pipe:1"],
        input=wav_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        raise OpenAIHTTPException(
            status_code=500,
            message=f"ffmpeg failed while encoding {response_format}: {process.stderr.decode('utf-8', errors='ignore')}",
            error_type="server_error",
            code="audio_encode_failed",
        )
    return process.stdout


def encode_audio(audio: np.ndarray, sample_rate: int, response_format: str) -> bytes:
    if response_format == "wav":
        return encode_wav(audio, sample_rate)
    if response_format == "pcm":
        return encode_pcm(audio)
    wav_bytes = encode_wav(audio, sample_rate)
    return _encode_with_ffmpeg(wav_bytes, response_format)


def media_type_for_format(response_format: str) -> str:
    return MEDIA_TYPES[response_format]


def estimate_usage(input_text: str, audio_bytes: bytes) -> dict[str, int]:
    input_tokens = max(1, math.ceil(len(input_text) / 4))
    output_tokens = max(1, math.ceil(len(audio_bytes) / 512))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def sse_audio_events(audio_bytes: bytes, input_text: str, chunk_size: int = 16384) -> Iterable[str]:
    for offset in range(0, len(audio_bytes), chunk_size):
        chunk = audio_bytes[offset : offset + chunk_size]
        payload = {
            "type": "speech.audio.delta",
            "audio": base64.b64encode(chunk).decode("ascii"),
        }
        yield f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"

    done_payload = {
        "type": "speech.audio.done",
        "usage": estimate_usage(input_text=input_text, audio_bytes=audio_bytes),
    }
    yield f"data: {json.dumps(done_payload, separators=(',', ':'))}\n\n"

