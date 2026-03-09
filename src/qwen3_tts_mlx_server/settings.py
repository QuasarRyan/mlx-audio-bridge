from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias


DEFAULT_MODEL_DIR = "/opt/mlx-audio-bridge/models"
DEFAULT_VOICES_FILE = "/opt/mlx-audio-bridge/config/voices.json"
DEFAULT_VOICE_DESIGN_SPEAKER = "Chelsie"
DEFAULT_TTS_MODEL_NAME = "Qwen3-TTS-12Hz-0.6B-Base-bf16"
DEFAULT_ASR_MODEL_NAME = "Qwen3-ASR-0.6B-8bit"
LEGACY_DEFAULT_TTS_MODEL = "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16"
LEGACY_DEFAULT_ASR_MODEL = "mlx-community/Qwen3-ASR-0.6B-8bit"
OPENAI_TTS_ALIASES = ("gpt-4o-mini-tts", "tts-1", "tts-1-hd")
OPENAI_STT_ALIASES = ("gpt-4o-mini-transcribe", "gpt-4o-transcribe", "whisper-1")

VoiceConfig: TypeAlias = dict[str, str]
VoicesConfig: TypeAlias = dict[str, VoiceConfig]

DEFAULT_VOICES: VoicesConfig = {
    "alloy": {
        "mode": "voice_design",
        "voice_description": (
            "A balanced, neutral, polished assistant voice with medium pitch, clean articulation, steady pacing, "
            "restrained emotion, and consistent professional delivery. The timbre should stay stable across the "
            "entire utterance and avoid sounding theatrical, overly bright, or overly soft."
        ),
    },
    "ash": {
        "mode": "voice_design",
        "voice_description": (
            "A dry, grounded, lower-energy voice with a slightly deeper color, calm control, crisp consonants, "
            "and measured pacing. The delivery should feel understated, stable, and matter-of-fact without sounding sleepy."
        ),
    },
    "ballad": {
        "mode": "voice_design",
        "voice_description": (
            "A warm, lyrical, storytelling voice with gentle expressiveness, flowing phrasing, softer edges, and "
            "a slightly slower pace. The tone should feel emotionally rich but stable, without exaggerated drama."
        ),
    },
    "coral": {
        "mode": "voice_design",
        "voice_description": (
            "A friendly, bright, welcoming conversational voice with natural smiles in the tone, clear diction, "
            "and easy medium pacing. The timbre should stay stable and approachable without becoming childish or overly excited."
        ),
    },
    "echo": {
        "mode": "voice_design",
        "voice_description": (
            "A crisp, direct, highly articulate voice with fast response energy, strong clarity, and confident "
            "forward momentum. The sound should stay clean and stable, avoiding warmth-heavy or theatrical expression."
        ),
    },
    "fable": {
        "mode": "voice_design",
        "voice_description": (
            "A soft, gentle, storybook-like voice with airy warmth, smooth phrasing, and calm, patient pacing. "
            "The timbre should stay stable and soothing while preserving clear intelligibility."
        ),
    },
    "nova": {
        "mode": "voice_design",
        "voice_description": (
            "A bright, modern, energetic voice with upbeat momentum, clean projection, and lively but controlled "
            "expression. The timbre should stay stable across the whole line and avoid drifting into shouty or overly playful delivery."
        ),
    },
    "onyx": {
        "mode": "voice_design",
        "voice_description": (
            "A low, steady, authoritative voice with calm gravity, deliberate pacing, and confident resonance. "
            "The timbre should stay stable and serious, avoiding excessive softness, cheerfulness, or dramatic flourishes."
        ),
    },
    "sage": {
        "mode": "voice_design",
        "voice_description": (
            "A thoughtful, composed, reassuring voice with measured pacing, calm confidence, and reflective warmth. "
            "The delivery should stay stable, clear, and trustworthy without sounding overly formal or detached."
        ),
    },
    "shimmer": {
        "mode": "voice_design",
        "voice_description": (
            "A light, airy, polished voice with soft brightness, delicate phrasing, and graceful smoothness. "
            "The timbre should stay stable and refined without becoming whispery, weak, or breathy."
        ),
    },
    "verse": {
        "mode": "voice_design",
        "voice_description": (
            "A smooth, rhythmic, presenter-like voice with clear structure, confident flow, and elegant pacing. "
            "The timbre should stay stable and expressive enough for narration, but avoid sounding theatrical or sing-song."
        ),
    },
}

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_HIRAGANA_KATAKANA_RE = re.compile(r"[\u3040-\u30ff]")
_HANGUL_RE = re.compile(r"[\uac00-\ud7af]")


@dataclass(slots=True, frozen=True)
class Settings:
    api_key: str | None
    default_tts_model: str
    default_asr_model: str
    forced_language: str | None
    voices: VoicesConfig

    def resolve_tts_model(self, public_model: str) -> str:
        return self.public_model_roots().get(public_model, public_model)

    def public_model_roots(self) -> dict[str, str]:
        public_models = {alias: self.default_tts_model for alias in OPENAI_TTS_ALIASES}
        public_models[self.default_tts_model] = self.default_tts_model
        return public_models

    def resolve_voice_config(self, requested_voice: str) -> VoiceConfig:
        return self.voices.get(requested_voice, {"mode": "custom_voice", "speaker": requested_voice})

    def resolve_voice_mode(self, requested_voice: str) -> str:
        return self.resolve_voice_config(requested_voice).get("mode", "custom_voice")

    def resolve_voice(self, requested_voice: str) -> str:
        config = self.resolve_voice_config(requested_voice)
        mode = config.get("mode", "custom_voice")
        if mode == "custom_voice":
            return config.get("speaker") or requested_voice
        if mode == "voice_design":
            return config.get("speaker") or DEFAULT_VOICE_DESIGN_SPEAKER
        return ""

    def resolve_prompt_audio_path(self, requested_voice: str) -> str | None:
        config = self.resolve_voice_config(requested_voice)
        if config.get("mode") != "voice_clone":
            return None
        return config.get("prompt_audio_path")

    def resolve_prompt_text(self, requested_voice: str) -> str | None:
        config = self.resolve_voice_config(requested_voice)
        if config.get("mode") != "voice_clone":
            return None
        return config.get("prompt_text")

    def compose_instructions(self, requested_voice: str, instructions: str | None) -> str | None:
        config = self.resolve_voice_config(requested_voice)
        base_instruction = None
        if config.get("mode") == "voice_design":
            base_instruction = config.get("voice_description")
        elif config.get("mode") == "custom_voice":
            base_instruction = config.get("instructions")

        if base_instruction and instructions:
            return f"Voice design: {base_instruction}\nAdditional instructions: {instructions}"
        if instructions:
            return instructions
        if base_instruction:
            return f"Voice design: {base_instruction}"
        return None

    def infer_language(self, text: str) -> str:
        if self.forced_language:
            return self.forced_language
        if _HIRAGANA_KATAKANA_RE.search(text):
            return "Japanese"
        if _HANGUL_RE.search(text):
            return "Korean"
        if _CJK_RE.search(text):
            return "Chinese"
        return "English"


def _validate_voices_config(raw_mapping: object, *, source: str) -> VoicesConfig:
    if not isinstance(raw_mapping, dict):
        raise ValueError(f"{source} must resolve to a JSON object.")
    validated: VoicesConfig = {}
    for key, value in raw_mapping.items():
        if not isinstance(key, str):
            raise ValueError(f"{source} must contain only string keys.")
        if not isinstance(value, dict):
            raise ValueError(f"{source} values must be JSON objects.")
        invalid_items = [
            (nested_key, nested_value)
            for nested_key, nested_value in value.items()
            if not isinstance(nested_key, str) or not isinstance(nested_value, str)
        ]
        if invalid_items:
            raise ValueError(f"{source} voice objects must contain only string-to-string fields.")
        mode = value.get("mode")
        if mode not in {"voice_design", "custom_voice", "voice_clone"}:
            raise ValueError(
                f"{source} entries must declare mode as one of voice_design, custom_voice, or voice_clone."
            )
        if mode == "voice_design" and "voice_description" not in value:
            raise ValueError(f"{source} voice_design entries must define voice_description.")
        if mode == "custom_voice" and "speaker" not in value:
            raise ValueError(f"{source} custom_voice entries must define speaker.")
        if mode == "voice_clone" and ("prompt_audio_path" not in value or "prompt_text" not in value):
            raise ValueError(f"{source} voice_clone entries must define prompt_audio_path and prompt_text.")
        validated[key] = dict(value)
    return validated


def _merge_voices_config(
    base: VoicesConfig,
    overrides: VoicesConfig,
) -> VoicesConfig:
    merged: VoicesConfig = {
        key: dict(value) if isinstance(value, dict) else value
        for key, value in base.items()
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = dict(value) if isinstance(value, dict) else value
    return merged


def _load_voices_config(fallback: VoicesConfig) -> VoicesConfig:
    file_path = Path(DEFAULT_VOICES_FILE)
    if not file_path.exists():
        return fallback
    with file_path.open("r", encoding="utf-8") as handle:
        overrides = _validate_voices_config(json.load(handle), source=DEFAULT_VOICES_FILE)
    return _merge_voices_config(fallback, overrides)


def _resolve_model_location(
    *,
    direct_env_name: str,
    name_env_name: str,
    default_model_name: str,
    legacy_default_model: str,
) -> str:
    direct_value = os.getenv(direct_env_name)
    if direct_value:
        return direct_value

    model_dir = os.getenv("QWEN_MODEL_DIR", DEFAULT_MODEL_DIR).strip()
    model_name = os.getenv(name_env_name, default_model_name).strip()

    if not model_dir:
        return legacy_default_model
    if not model_name:
        return model_dir
    if Path(model_name).is_absolute() or "/" in model_name:
        return model_name
    return str(Path(model_dir) / model_name)


def load_settings() -> Settings:
    return Settings(
        api_key=os.getenv("API_KEY"),
        default_tts_model=_resolve_model_location(
            direct_env_name="QWEN_TTS_MODEL",
            name_env_name="QWEN_TTS_MODEL_NAME",
            default_model_name=DEFAULT_TTS_MODEL_NAME,
            legacy_default_model=LEGACY_DEFAULT_TTS_MODEL,
        ),
        default_asr_model=_resolve_model_location(
            direct_env_name="QWEN_ASR_MODEL",
            name_env_name="QWEN_ASR_MODEL_NAME",
            default_model_name=DEFAULT_ASR_MODEL_NAME,
            legacy_default_model=LEGACY_DEFAULT_ASR_MODEL,
        ),
        forced_language=os.getenv("QWEN_TTS_LANGUAGE") or None,
        voices=_load_voices_config(DEFAULT_VOICES),
    )
