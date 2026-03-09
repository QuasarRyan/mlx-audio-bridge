from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias


DEFAULT_MODEL_DIR = "/opt/mlx-audio-bridge/models"
DEFAULT_VOICE_STYLE_FILE = "/opt/mlx-audio-bridge/config/voice-style.json"
DEFAULT_TTS_MODEL_NAME = "Qwen3-TTS-12Hz-0.6B-Base-bf16"
DEFAULT_ASR_MODEL_NAME = "Qwen3-ASR-0.6B-8bit"
LEGACY_DEFAULT_TTS_MODEL = "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16"
LEGACY_DEFAULT_ASR_MODEL = "mlx-community/Qwen3-ASR-0.6B-8bit"
OPENAI_TTS_ALIASES = ("gpt-4o-mini-tts", "tts-1", "tts-1-hd")
OPENAI_STT_ALIASES = ("gpt-4o-mini-transcribe", "gpt-4o-transcribe", "whisper-1")

VoiceStylePreset: TypeAlias = dict[str, str]
VoiceStyleMapping: TypeAlias = dict[str, str | VoiceStylePreset]

DEFAULT_VOICE_STYLE_MAP: VoiceStyleMapping = {
    "alloy": {
        "voice": "Chelsie",
        "instructions": (
            "Use a balanced, neutral, polished assistant voice with medium pitch, clean articulation, "
            "steady pacing, restrained emotion, and consistent professional delivery. Keep the timbre "
            "stable across the entire utterance and avoid sounding theatrical, overly bright, or overly soft."
        ),
    },
    "ash": {
        "voice": "Chelsie",
        "instructions": (
            "Use a dry, grounded, lower-energy voice with a slightly deeper color, calm control, crisp consonants, "
            "and measured pacing. Keep the delivery understated, stable, and matter-of-fact without sounding sleepy."
        ),
    },
    "ballad": {
        "voice": "Chelsie",
        "instructions": (
            "Use a warm, lyrical, storytelling voice with gentle expressiveness, flowing phrasing, softer edges, "
            "and a slightly slower pace. Keep the tone emotionally rich but stable, avoiding exaggerated drama."
        ),
    },
    "coral": {
        "voice": "Chelsie",
        "instructions": (
            "Use a friendly, bright, welcoming conversational voice with natural smiles in the tone, clear diction, "
            "and easy medium pacing. Keep the timbre stable and approachable without becoming childish or overly excited."
        ),
    },
    "echo": {
        "voice": "Chelsie",
        "instructions": (
            "Use a crisp, direct, highly articulate voice with fast response energy, strong clarity, and confident "
            "forward momentum. Keep the sound clean and stable, avoiding warmth-heavy or theatrical expression."
        ),
    },
    "fable": {
        "voice": "Chelsie",
        "instructions": (
            "Use a soft, gentle, storybook-like voice with airy warmth, smooth phrasing, and calm, patient pacing. "
            "Keep the timbre stable and soothing while preserving clear intelligibility."
        ),
    },
    "nova": {
        "voice": "Chelsie",
        "instructions": (
            "Use a bright, modern, energetic voice with upbeat momentum, clean projection, and lively but controlled "
            "expression. Keep the timbre stable across the whole line and avoid drifting into shouty or overly playful delivery."
        ),
    },
    "onyx": {
        "voice": "Chelsie",
        "instructions": (
            "Use a low, steady, authoritative voice with calm gravity, deliberate pacing, and confident resonance. "
            "Keep the timbre stable and serious, avoiding excessive softness, cheerfulness, or dramatic flourishes."
        ),
    },
    "sage": {
        "voice": "Chelsie",
        "instructions": (
            "Use a thoughtful, composed, reassuring voice with measured pacing, calm confidence, and reflective warmth. "
            "Keep the delivery stable, clear, and trustworthy without sounding overly formal or detached."
        ),
    },
    "shimmer": {
        "voice": "Chelsie",
        "instructions": (
            "Use a light, airy, polished voice with soft brightness, delicate phrasing, and graceful smoothness. "
            "Keep the timbre stable and refined without becoming whispery, weak, or breathy."
        ),
    },
    "verse": {
        "voice": "Chelsie",
        "instructions": (
            "Use a smooth, rhythmic, presenter-like voice with clear structure, confident flow, and elegant pacing. "
            "Keep the timbre stable and expressive enough for narration, but avoid sounding theatrical or sing-song."
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
    voice_style_map: VoiceStyleMapping

    def resolve_tts_model(self, public_model: str) -> str:
        return self.public_model_roots().get(public_model, public_model)

    def public_model_roots(self) -> dict[str, str]:
        public_models = {alias: self.default_tts_model for alias in OPENAI_TTS_ALIASES}
        public_models[self.default_tts_model] = self.default_tts_model
        return public_models

    def _resolve_voice_preset(self, requested_voice: str) -> tuple[str, str | None]:
        preset = self.voice_style_map.get(requested_voice)
        if isinstance(preset, dict):
            backend_voice = preset.get("voice") or requested_voice
            style_hint = preset.get("instructions") or preset.get("style")
            return backend_voice, style_hint
        if isinstance(preset, str):
            return requested_voice, preset
        return requested_voice, None

    def resolve_voice(self, requested_voice: str) -> str:
        resolved_voice, _ = self._resolve_voice_preset(requested_voice)
        return resolved_voice

    def compose_instructions(self, requested_voice: str, instructions: str | None) -> str | None:
        _, style_hint = self._resolve_voice_preset(requested_voice)
        if style_hint and instructions:
            return f"Voice style: {style_hint}\nAdditional instructions: {instructions}"
        if instructions:
            return instructions
        if style_hint:
            return f"Voice style: {style_hint}"
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


def _validate_voice_style_mapping(raw_mapping: object, *, source: str) -> VoiceStyleMapping:
    if not isinstance(raw_mapping, dict):
        raise ValueError(f"{source} must resolve to a JSON object.")
    validated: VoiceStyleMapping = {}
    for key, value in raw_mapping.items():
        if not isinstance(key, str):
            raise ValueError(f"{source} must contain only string keys.")
        if isinstance(value, str):
            validated[key] = value
            continue
        if not isinstance(value, dict):
            raise ValueError(f"{source} values must be either strings or JSON objects.")
        invalid_items = [
            (nested_key, nested_value)
            for nested_key, nested_value in value.items()
            if not isinstance(nested_key, str) or not isinstance(nested_value, str)
        ]
        if invalid_items:
            raise ValueError(f"{source} preset objects must contain only string-to-string fields.")
        validated[key] = dict(value)
    return validated


def _merge_voice_style_mappings(
    base: VoiceStyleMapping,
    overrides: VoiceStyleMapping,
) -> VoiceStyleMapping:
    merged: VoiceStyleMapping = {
        key: dict(value) if isinstance(value, dict) else value
        for key, value in base.items()
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = dict(value) if isinstance(value, dict) else value
    return merged


def _load_voice_style_mapping(fallback: VoiceStyleMapping) -> VoiceStyleMapping:
    file_path = Path(DEFAULT_VOICE_STYLE_FILE)
    if not file_path.exists():
        return fallback
    with file_path.open("r", encoding="utf-8") as handle:
        overrides = _validate_voice_style_mapping(json.load(handle), source=DEFAULT_VOICE_STYLE_FILE)
    return _merge_voice_style_mappings(fallback, overrides)


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
        voice_style_map=_load_voice_style_mapping(DEFAULT_VOICE_STYLE_MAP),
    )
