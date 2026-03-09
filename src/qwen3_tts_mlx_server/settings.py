from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass


DEFAULT_TTS_MODEL = "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16"
DEFAULT_ASR_MODEL = "mlx-community/Qwen3-ASR-0.6B-8bit"
OPENAI_TTS_ALIASES = ("gpt-4o-mini-tts", "tts-1", "tts-1-hd")
OPENAI_STT_ALIASES = ("gpt-4o-mini-transcribe", "gpt-4o-transcribe", "whisper-1")

DEFAULT_VOICE_MAP = {
    "alloy": "Chelsie",
    "ash": "Chelsie",
    "ballad": "Chelsie",
    "coral": "Chelsie",
    "echo": "Chelsie",
    "fable": "Chelsie",
    "nova": "Chelsie",
    "onyx": "Chelsie",
    "sage": "Chelsie",
    "shimmer": "Chelsie",
    "verse": "Chelsie",
}

DEFAULT_VOICE_STYLE_MAP = {
    "alloy": "Neutral, balanced, clear, and professional.",
    "ash": "Measured, grounded, and slightly deeper in tone.",
    "ballad": "Warm, narrative, and expressive.",
    "coral": "Friendly, bright, and conversational.",
    "echo": "Crisp, direct, and confident.",
    "fable": "Gentle, story-like, and soft.",
    "nova": "Modern, energetic, and upbeat.",
    "onyx": "Low, calm, and authoritative.",
    "sage": "Thoughtful, composed, and reassuring.",
    "shimmer": "Light, polished, and airy.",
    "verse": "Smooth, rhythmic, and presentational.",
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
    voice_map: dict[str, str]
    voice_style_map: dict[str, str]

    def resolve_tts_model(self, public_model: str) -> str:
        return self.public_model_roots().get(public_model, public_model)

    def public_model_roots(self) -> dict[str, str]:
        public_models = {alias: self.default_tts_model for alias in OPENAI_TTS_ALIASES}
        public_models[self.default_tts_model] = self.default_tts_model
        return public_models

    def resolve_voice(self, requested_voice: str) -> str:
        return self.voice_map.get(requested_voice, requested_voice)

    def compose_instructions(self, requested_voice: str, instructions: str | None) -> str | None:
        style_hint = self.voice_style_map.get(requested_voice)
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


def _load_json_mapping(env_name: str, fallback: dict[str, str]) -> dict[str, str]:
    raw_value = os.getenv(env_name)
    if not raw_value:
        return fallback
    return json.loads(raw_value)


def load_settings() -> Settings:
    return Settings(
        api_key=os.getenv("API_KEY"),
        default_tts_model=os.getenv("QWEN_TTS_MODEL", DEFAULT_TTS_MODEL),
        default_asr_model=os.getenv("QWEN_ASR_MODEL", DEFAULT_ASR_MODEL),
        forced_language=os.getenv("QWEN_TTS_LANGUAGE") or None,
        voice_map=_load_json_mapping("OPENAI_VOICE_MAP", DEFAULT_VOICE_MAP),
        voice_style_map=_load_json_mapping("OPENAI_VOICE_STYLE_MAP", DEFAULT_VOICE_STYLE_MAP),
    )

