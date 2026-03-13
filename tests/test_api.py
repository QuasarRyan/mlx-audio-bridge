from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from qwen3_tts_mlx_server.app import create_app
from qwen3_tts_mlx_server.backends import SpeechSynthesisRequest, SynthesizedAudio, TTSBackend
from qwen3_tts_mlx_server.backends.qwen_tts import QwenMLXTTSBackend
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
        default_tts_model="mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16",
        small_base_tts_model="mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16",
        large_base_tts_model="mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16",
        custom_voice_tts_model="mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-bf16",
        voice_design_tts_model="mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16",
        large_custom_voice_tts_model="mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-bf16",
        default_asr_model="mlx-community/Qwen3-ASR-0.6B-8bit",
        forced_language=None,
        voices={
            "alloy": {
                "mode": "voice_design",
                "voice_description": "Neutral and polished.",
                "temperature": 0.72,
                "top_p": 0.86,
                "top_k": 42,
                "repetition_penalty": 1.18,
            },
            "assistant": {
                "mode": "voice_clone",
                "prompt_audio_path": "/tmp/reference.wav",
                "prompt_text": "Reference prompt text.",
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
    assert backend_call.backend_model == "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16"
    assert backend_call.voice == "Chelsie"
    assert backend_call.language == "English"
    assert "Neutral and polished." in (backend_call.instructions or "")
    assert "Speak slowly." in (backend_call.instructions or "")
    assert backend_call.temperature == 0.72
    assert backend_call.top_p == 0.86
    assert backend_call.top_k == 42
    assert backend_call.repetition_penalty == 1.18


def test_speech_endpoint_supports_voice_clone_config() -> None:
    client, backend = build_client()

    response = client.post(
        "/v1/audio/speech",
        json={
            "model": "gpt-4o-mini-tts",
            "input": "Use the assistant reference.",
            "voice": "assistant",
            "response_format": "wav",
        },
    )

    assert response.status_code == 200
    backend_call = backend.calls[0]
    assert backend_call.voice == ""
    assert backend_call.prompt_audio_path == "/tmp/reference.wav"
    assert backend_call.prompt_text == "Reference prompt text."
    assert backend_call.temperature == 0.6
    assert backend_call.top_p == 0.9
    assert backend_call.top_k == 30
    assert backend_call.repetition_penalty == 1.05


def test_speech_endpoint_selects_model_family_from_voice_mode() -> None:
    client, backend = build_client()

    response = client.post(
        "/v1/audio/speech",
        json={
            "model": "gpt-4o-mini-tts",
            "input": "Tell a story.",
            "voice": "alloy",
            "response_format": "wav",
        },
    )

    assert response.status_code == 200
    assert backend.calls[-1].backend_model == "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16"


def test_speech_endpoint_forwards_repetition_penalty() -> None:
    client, backend = build_client()

    response = client.post(
        "/v1/audio/speech",
        json={
            "model": "gpt-4o-mini-tts",
            "input": "Repeat-safe text.",
            "voice": "alloy",
            "response_format": "wav",
            "repetition_penalty": 1.35,
        },
    )

    assert response.status_code == 200
    assert backend.calls[-1].repetition_penalty == 1.35


def test_backend_enforces_repetition_penalty_floor_for_voice_clone() -> None:
    backend = QwenMLXTTSBackend()
    captured: dict[str, float] = {}

    class DummyModel:
        def generate(
            self,
            *,
            text: str,
            speed: float,
            temperature: float,
            top_p: float,
            top_k: int,
            repetition_penalty: float,
            **kwargs,
        ):
            _ = (text, speed, temperature, top_p, top_k, kwargs)
            captured["repetition_penalty"] = repetition_penalty
            return np.zeros(10, dtype=np.float32), 24_000

    request = SpeechSynthesisRequest(
        public_model="gpt-4o-mini-tts",
        backend_model="mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16",
        text="Clone this voice.",
        voice_mode="voice_clone",
        voice="",
        instructions=None,
        prompt_audio_path="/tmp/reference.wav",
        prompt_text="Reference prompt text.",
        language="English",
        speed=1.0,
        temperature=None,
        top_p=None,
        top_k=None,
        repetition_penalty=1.1,
        response_format="wav",
    )

    audio, sample_rate = backend._generate(DummyModel(), request)

    assert sample_rate == 24_000
    assert len(audio) == 10
    assert captured["repetition_penalty"] == 1.5


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
    assert "Qwen3-TTS-12Hz-1.7B-Base" in model_ids
    assert "Qwen3-TTS-12Hz-0.6B-CustomVoice" in model_ids
    assert "Qwen3-TTS-12Hz-1.7B-VoiceDesign" in model_ids
    assert "Qwen3-TTS-12Hz-1.7B-CustomVoice" in model_ids


def test_backend_refreshes_tokenizer_with_fixed_mistral_regex(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    class DummyTokenizer:
        pass

    class DummyAutoTokenizer:
        @staticmethod
        def from_pretrained(path: str, **kwargs):
            recorded["path"] = path
            recorded["kwargs"] = kwargs
            return DummyTokenizer()

    dummy_model = type(
        "DummyModel",
        (),
        {
            "tokenizer": object(),
            "config": type("DummyConfig", (), {"model_path": "/opt/mlx-audio-bridge/models/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit"})(),
        },
    )()

    import qwen3_tts_mlx_server.backends.qwen_tts as backend_module

    monkeypatch.setattr(backend_module, "AutoTokenizer", DummyAutoTokenizer, raising=False)
    monkeypatch.setitem(__import__("sys").modules, "transformers", type("DummyTransformers", (), {"AutoTokenizer": DummyAutoTokenizer})())

    backend = QwenMLXTTSBackend()
    backend._refresh_tokenizer(dummy_model, "ignored-model-id")

    assert isinstance(dummy_model.tokenizer, DummyTokenizer)
    assert recorded["path"] == "/opt/mlx-audio-bridge/models/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit"
    assert recorded["kwargs"] == {"fix_mistral_regex": True}
