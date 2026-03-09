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


def test_load_settings_prefers_highest_supported_local_tts_quantization(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("QWEN_TTS_MODEL", raising=False)
    monkeypatch.delenv("QWEN_TTS_MODEL_NAME", raising=False)
    monkeypatch.setenv("QWEN_MODEL_DIR", str(tmp_path))
    (tmp_path / "Qwen3-TTS-12Hz-Base-0.6B-4bit").mkdir()
    (tmp_path / "Qwen3-TTS-12Hz-Base-0.6B-8bit").mkdir()
    (tmp_path / "Qwen3-TTS-12Hz-Base-0.6B-bf16").mkdir()

    settings = load_settings()

    assert settings.default_tts_model == str(tmp_path / "Qwen3-TTS-12Hz-Base-0.6B-8bit")


def test_load_settings_falls_back_to_legacy_tts_model_when_no_local_quantization_exists(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("QWEN_TTS_MODEL", raising=False)
    monkeypatch.delenv("QWEN_TTS_MODEL_NAME", raising=False)
    monkeypatch.setenv("QWEN_MODEL_DIR", str(tmp_path))

    settings = load_settings()

    assert settings.default_tts_model == "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16"


def test_load_settings_resolves_other_supported_tts_families(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("QWEN_TTS_MODEL", raising=False)
    monkeypatch.delenv("QWEN_TTS_MODEL_NAME", raising=False)
    monkeypatch.setenv("QWEN_MODEL_DIR", str(tmp_path))
    (tmp_path / "Qwen3-TTS-12Hz-0.6B-CustomVoice-6bit").mkdir()
    (tmp_path / "Qwen3-TTS-12Hz-1.7B-VoiceDesign-5bit").mkdir()
    (tmp_path / "Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit").mkdir()

    settings = load_settings()

    assert settings.custom_voice_tts_model == str(tmp_path / "Qwen3-TTS-12Hz-0.6B-CustomVoice-6bit")
    assert settings.voice_design_tts_model == str(tmp_path / "Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit")


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
        custom_voice_tts_model="custom-voice-model",
        voice_design_tts_model="voice-design-model",
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
