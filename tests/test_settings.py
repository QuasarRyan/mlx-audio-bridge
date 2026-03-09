from __future__ import annotations

import json

import qwen3_tts_mlx_server.settings as settings_module
from qwen3_tts_mlx_server.settings import DEFAULT_VOICE_DESIGN_SPEAKER, Settings, load_settings


def test_load_settings_builds_model_paths_from_shared_model_dir(monkeypatch) -> None:
    monkeypatch.delenv("QWEN_TTS_MODEL", raising=False)
    monkeypatch.delenv("QWEN_ASR_MODEL", raising=False)
    monkeypatch.setenv("QWEN_MODEL_DIR", "/opt/mlx-audio-bridge/models")
    monkeypatch.setenv("QWEN_TTS_MODEL_NAME", "tts-model")
    monkeypatch.setenv("QWEN_ASR_MODEL_NAME", "asr-model")

    settings = load_settings()

    assert settings.default_tts_model == "/opt/mlx-audio-bridge/models/tts-model"
    assert settings.default_asr_model == "/opt/mlx-audio-bridge/models/asr-model"


def test_load_settings_keeps_legacy_direct_model_overrides(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_MODEL_DIR", "/opt/mlx-audio-bridge/models")
    monkeypatch.setenv("QWEN_TTS_MODEL", "mlx-community/custom-tts")
    monkeypatch.setenv("QWEN_ASR_MODEL", "/tmp/custom-asr")

    settings = load_settings()

    assert settings.default_tts_model == "mlx-community/custom-tts"
    assert settings.default_asr_model == "/tmp/custom-asr"


def test_load_settings_reads_voice_overrides_from_file(monkeypatch, tmp_path) -> None:
    voices_file = tmp_path / "voices.json"
    voices_file.write_text(json.dumps({"alloy": {"mode": "voice_design", "voice_description": "Calm and bright."}}), encoding="utf-8")

    monkeypatch.setattr(settings_module, "DEFAULT_VOICES_FILE", str(voices_file))

    settings = load_settings()

    assert settings.voices["alloy"]["mode"] == "voice_design"
    assert settings.voices["alloy"]["voice_description"] == "Calm and bright."


def test_missing_voices_file_keeps_defaults(monkeypatch, tmp_path) -> None:
    missing_file = tmp_path / "missing-voices.json"
    monkeypatch.setattr(settings_module, "DEFAULT_VOICES_FILE", str(missing_file))

    settings = load_settings()

    assert settings.voices["alloy"]["mode"] == "voice_design"
    assert settings.resolve_voice("alloy") == DEFAULT_VOICE_DESIGN_SPEAKER


def test_voice_modes_resolve_backend_voice_and_prompt_fields() -> None:
    settings = Settings(
        api_key=None,
        default_tts_model="tts-model",
        default_asr_model="asr-model",
        forced_language=None,
        voices={
            "maid": {
                "mode": "voice_design",
                "voice_description": "A calm maid voice.",
            },
            "serena": {
                "mode": "custom_voice",
                "speaker": "Serena",
            },
            "assistant": {
                "mode": "voice_clone",
                "prompt_audio_path": "/tmp/reference.wav",
                "prompt_text": "Reference prompt text.",
            }
        },
    )

    assert settings.resolve_voice("maid") == DEFAULT_VOICE_DESIGN_SPEAKER
    assert settings.resolve_voice("serena") == "Serena"
    assert settings.resolve_voice_mode("assistant") == "voice_clone"
    assert settings.resolve_prompt_audio_path("assistant") == "/tmp/reference.wav"
    assert settings.resolve_prompt_text("assistant") == "Reference prompt text."
    assert settings.compose_instructions("maid", "Speak a little slower.") == (
        "Voice design: A calm maid voice.\n"
        "Additional instructions: Speak a little slower."
    )
