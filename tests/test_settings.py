from __future__ import annotations

from qwen3_tts_mlx_server.settings import load_settings


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
