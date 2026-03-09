from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from qwen3_tts_mlx_server.app import create_app
from qwen3_tts_mlx_server.backends import SpeechSynthesisRequest, SynthesizedAudio, TTSBackend
from qwen3_tts_mlx_server.settings import Settings


class StubTTSBackend(TTSBackend):
    def __init__(self) -> None:
        self.calls: list[SpeechSynthesisRequest] = []

    def synthesize(self, request: SpeechSynthesisRequest) -> SynthesizedAudio:
        self.calls.append(request)
        samples = np.linspace(-0.2, 0.2, 512, dtype=np.float32)
        return SynthesizedAudio(
            audio=samples,
            sample_rate=24_000,
            backend_model=request.backend_model,
            resolved_voice=request.voice,
            resolved_language=request.language,
        )


def build_client() -> tuple[TestClient, StubTTSBackend]:
    backend = StubTTSBackend()
    settings = Settings(
        api_key=None,
        default_tts_model="mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16",
        default_asr_model="mlx-community/Qwen3-ASR-0.6B-8bit",
        forced_language=None,
        voice_style_map={
            "alloy": {
                "voice": "Chelsie",
                "instructions": "Neutral and polished.",
            }
        },
    )
    app = create_app(settings=settings, tts_backend=backend)
    return TestClient(app), backend


def test_speech_endpoint_maps_openai_fields_to_backend() -> None:
    client, backend = build_client()

    response = client.post(
        "/v1/audio/speech",
        json={
            "model": "gpt-4o-mini-tts",
            "input": "Hello from tests.",
            "voice": "alloy",
            "instructions": "Speak slowly.",
            "response_format": "wav",
            "speed": 1.25,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content.startswith(b"RIFF")

    backend_call = backend.calls[0]
    assert backend_call.backend_model == "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16"
    assert backend_call.voice == "Chelsie"
    assert backend_call.language == "English"
    assert "Neutral and polished." in (backend_call.instructions or "")
    assert "Speak slowly." in (backend_call.instructions or "")


def test_speech_endpoint_supports_sse_streaming() -> None:
    client, _ = build_client()

    response = client.post(
        "/v1/audio/speech",
        json={
            "model": "gpt-4o-mini-tts",
            "input": "Stream this.",
            "voice": "alloy",
            "response_format": "pcm",
            "stream_format": "sse",
        },
    )

    body = response.text
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"type":"speech.audio.delta"' in body
    assert '"type":"speech.audio.done"' in body


def test_reserved_transcription_endpoint_returns_openai_shape() -> None:
    client, _ = build_client()

    response = client.post(
        "/v1/audio/transcriptions",
        data={"model": "whisper-1"},
        files={"file": ("audio.wav", b"RIFF....", "audio/wav")},
    )

    assert response.status_code == 501
    payload = response.json()
    assert payload["error"]["code"] == "not_implemented"
    assert "Qwen-ASR" in payload["error"]["message"]


def test_models_endpoint_lists_openai_aliases() -> None:
    client, _ = build_client()

    response = client.get("/v1/models")

    assert response.status_code == 200
    payload = response.json()
    model_ids = {item["id"] for item in payload["data"]}
    assert "gpt-4o-mini-tts" in model_ids
    assert "tts-1" in model_ids
    assert "tts-1-hd" in model_ids
