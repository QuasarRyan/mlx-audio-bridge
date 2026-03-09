from __future__ import annotations

import json

import qwen3_tts_mlx_server.settings as settings_module
from qwen3_tts_mlx_server.settings import Settings, load_settings


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


def test_load_settings_reads_voice_style_overrides_from_file(monkeypatch, tmp_path) -> None:
    style_map_file = tmp_path / "voice-style.json"
    style_map_file.write_text(
        json.dumps({"alloy": {"instructions": "Calm and bright."}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(settings_module, "DEFAULT_VOICE_STYLE_FILE", str(style_map_file))

    settings = load_settings()

    assert settings.voice_style_map["alloy"] == {
        "voice": "Chelsie",
        "instructions": "Calm and bright.",
    }


def test_missing_voice_style_file_keeps_defaults(monkeypatch, tmp_path) -> None:
    missing_file = tmp_path / "missing-voice-style.json"
    monkeypatch.setattr(settings_module, "DEFAULT_VOICE_STYLE_FILE", str(missing_file))

    settings = load_settings()

    assert isinstance(settings.voice_style_map["alloy"], dict)
    assert settings.voice_style_map["alloy"]["voice"] == "Chelsie"


def test_preset_mapping_resolves_backend_voice_and_style() -> None:
    settings = Settings(
        api_key=None,
        default_tts_model="tts-model",
        default_asr_model="asr-model",
        forced_language=None,
        voice_style_map={
            "alloy": {
                "voice": "Chelsie",
                "instructions": "Balanced, neutral, and polished.",
            }
        },
    )

    assert settings.resolve_voice("alloy") == "Chelsie"
    assert settings.compose_instructions("alloy", "Speak a little slower.") == (
        "Voice style: Balanced, neutral, and polished.\n"
        "Additional instructions: Speak a little slower."
    )
