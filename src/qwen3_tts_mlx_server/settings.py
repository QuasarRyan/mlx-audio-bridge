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
DEFAULT_TEMPERATURE = 0.6
DEFAULT_TOP_P = 0.9
DEFAULT_TOP_K = 30
DEFAULT_REPETITION_PENALTY = 1.05
DEFAULT_TTS_MODEL_NAME = "Qwen3-TTS-12Hz-1.7B-Base-bf16"
DEFAULT_ASR_MODEL_NAME = "Qwen3-ASR-0.6B-8bit"
LEGACY_DEFAULT_BASE_0_6B_TTS_MODEL = "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16"
LEGACY_DEFAULT_BASE_1_7B_TTS_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16"
LEGACY_DEFAULT_ASR_MODEL = "mlx-community/Qwen3-ASR-0.6B-8bit"
TTS_QUANTIZATION_PREFERENCE = ("8bit", "6bit", "5bit", "4bit", "bf16")
OPENAI_TTS_ALIASES = ("gpt-4o-mini-tts", "tts-1", "tts-1-hd")
OPENAI_STT_ALIASES = ("gpt-4o-mini-transcribe", "gpt-4o-transcribe", "whisper-1")

VoiceConfigValue: TypeAlias = str | int | float
VoiceConfig: TypeAlias = dict[str, VoiceConfigValue]
VoicesConfig: TypeAlias = dict[str, VoiceConfig]
_VOICE_NUMERIC_FIELDS = {"temperature", "top_p", "top_k", "repetition_penalty"}

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
class TTSFamilySpec:
    public_id: str
    legacy_model: str
    required_tokens: tuple[str, ...]


DEFAULT_TTS_FAMILY = TTSFamilySpec(
    public_id="Qwen3-TTS-12Hz-0.6B-Base",
    legacy_model=LEGACY_DEFAULT_BASE_0_6B_TTS_MODEL,
    required_tokens=("Qwen3-TTS-12Hz", "0.6B", "Base"),
)
LARGE_BASE_TTS_FAMILY = TTSFamilySpec(
    public_id="Qwen3-TTS-12Hz-1.7B-Base",
    legacy_model=LEGACY_DEFAULT_BASE_1_7B_TTS_MODEL,
    required_tokens=("Qwen3-TTS-12Hz", "1.7B", "Base"),
)
CUSTOM_VOICE_TTS_FAMILY = TTSFamilySpec(
    public_id="Qwen3-TTS-12Hz-0.6B-CustomVoice",
    legacy_model="mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-bf16",
    required_tokens=("Qwen3-TTS-12Hz", "0.6B", "CustomVoice"),
)
VOICE_DESIGN_TTS_FAMILY = TTSFamilySpec(
    public_id="Qwen3-TTS-12Hz-1.7B-VoiceDesign",
    legacy_model="mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16",
    required_tokens=("Qwen3-TTS-12Hz", "1.7B", "VoiceDesign"),
)
LARGE_CUSTOM_VOICE_TTS_FAMILY = TTSFamilySpec(
    public_id="Qwen3-TTS-12Hz-1.7B-CustomVoice",
    legacy_model="mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-bf16",
    required_tokens=("Qwen3-TTS-12Hz", "1.7B", "CustomVoice"),
)


@dataclass(slots=True, frozen=True)
class Settings:
    api_key: str | None
    default_tts_model: str
    small_base_tts_model: str
    large_base_tts_model: str
    custom_voice_tts_model: str
    voice_design_tts_model: str
    large_custom_voice_tts_model: str
    default_asr_model: str
    forced_language: str | None
    voices: VoicesConfig

    def resolve_tts_model(self, public_model: str, voice_mode: str = "voice_clone") -> str:
        if public_model in OPENAI_TTS_ALIASES:
            if voice_mode == "voice_design":
                return self.voice_design_tts_model
            if voice_mode == "custom_voice":
                return self.custom_voice_tts_model
            return self.default_tts_model
        return self.public_model_roots().get(public_model, public_model)

    def public_model_roots(self) -> dict[str, str]:
        public_models = {alias: self.default_tts_model for alias in OPENAI_TTS_ALIASES}
        public_models[DEFAULT_TTS_FAMILY.public_id] = self.small_base_tts_model
        public_models[LARGE_BASE_TTS_FAMILY.public_id] = self.large_base_tts_model
        public_models[CUSTOM_VOICE_TTS_FAMILY.public_id] = self.custom_voice_tts_model
        public_models[VOICE_DESIGN_TTS_FAMILY.public_id] = self.voice_design_tts_model
        public_models[LARGE_CUSTOM_VOICE_TTS_FAMILY.public_id] = self.large_custom_voice_tts_model
        public_models[self.default_tts_model] = self.default_tts_model
        public_models[self.small_base_tts_model] = self.small_base_tts_model
        public_models[self.large_base_tts_model] = self.large_base_tts_model
        public_models[self.custom_voice_tts_model] = self.custom_voice_tts_model
        public_models[self.voice_design_tts_model] = self.voice_design_tts_model
        public_models[self.large_custom_voice_tts_model] = self.large_custom_voice_tts_model
        return public_models

    def resolve_voice_config(self, requested_voice: str) -> VoiceConfig:
        return self.voices.get(requested_voice, {"mode": "custom_voice", "speaker": requested_voice})

    def resolve_voice_mode(self, requested_voice: str) -> str:
        return _read_voice_string(self.resolve_voice_config(requested_voice), "mode") or "custom_voice"

    def resolve_voice(self, requested_voice: str) -> str:
        config = self.resolve_voice_config(requested_voice)
        mode = _read_voice_string(config, "mode") or "custom_voice"
        if mode == "custom_voice":
            return _read_voice_string(config, "speaker") or requested_voice
        if mode == "voice_design":
            return _read_voice_string(config, "speaker") or DEFAULT_VOICE_DESIGN_SPEAKER
        return ""

    def resolve_prompt_audio_path(self, requested_voice: str) -> str | None:
        config = self.resolve_voice_config(requested_voice)
        if _read_voice_string(config, "mode") != "voice_clone":
            return None
        return _read_voice_string(config, "prompt_audio_path")

    def resolve_prompt_text(self, requested_voice: str) -> str | None:
        config = self.resolve_voice_config(requested_voice)
        if _read_voice_string(config, "mode") != "voice_clone":
            return None
        return _read_voice_string(config, "prompt_text")

    def compose_instructions(self, requested_voice: str, instructions: str | None) -> str | None:
        config = self.resolve_voice_config(requested_voice)
        base_instruction = None
        if _read_voice_string(config, "mode") == "voice_design":
            base_instruction = _read_voice_string(config, "voice_description")
        elif _read_voice_string(config, "mode") == "custom_voice":
            base_instruction = _read_voice_string(config, "instructions")

        if base_instruction and instructions:
            return f"Voice design: {base_instruction}\nAdditional instructions: {instructions}"
        if instructions:
            return instructions
        if base_instruction:
            return f"Voice design: {base_instruction}"
        return None

    def resolve_temperature(self, requested_voice: str) -> float:
        return _read_voice_float(self.resolve_voice_config(requested_voice), "temperature", DEFAULT_TEMPERATURE)

    def resolve_top_p(self, requested_voice: str) -> float:
        return _read_voice_float(self.resolve_voice_config(requested_voice), "top_p", DEFAULT_TOP_P)

    def resolve_top_k(self, requested_voice: str) -> int:
        return _read_voice_int(self.resolve_voice_config(requested_voice), "top_k", DEFAULT_TOP_K)

    def resolve_repetition_penalty(self, requested_voice: str) -> float:
        return _read_voice_float(
            self.resolve_voice_config(requested_voice),
            "repetition_penalty",
            DEFAULT_REPETITION_PENALTY,
        )

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


def _read_voice_string(config: VoiceConfig, field: str) -> str | None:
    value = config.get(field)
    if isinstance(value, str):
        return value
    return None


def _read_voice_float(config: VoiceConfig, field: str, default: float) -> float:
    value = config.get(field)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def _read_voice_int(config: VoiceConfig, field: str, default: int) -> int:
    value = config.get(field)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        if numeric.is_integer():
            return int(numeric)
    return default


def _validate_voice_numeric_field(*, source: str, voice_name: str, field: str, value: object) -> int | float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{source} voice '{voice_name}' field '{field}' must be numeric.")

    numeric = float(value)
    if field == "temperature":
        if numeric <= 0:
            raise ValueError(f"{source} voice '{voice_name}' field 'temperature' must be > 0.")
        return numeric
    if field == "top_p":
        if numeric <= 0 or numeric > 1:
            raise ValueError(f"{source} voice '{voice_name}' field 'top_p' must be in (0, 1].")
        return numeric
    if field == "top_k":
        if numeric < 1 or not numeric.is_integer():
            raise ValueError(f"{source} voice '{voice_name}' field 'top_k' must be an integer >= 1.")
        return int(numeric)
    if field == "repetition_penalty":
        if numeric < 1.0:
            raise ValueError(f"{source} voice '{voice_name}' field 'repetition_penalty' must be >= 1.0.")
        return numeric
    raise ValueError(f"{source} voice '{voice_name}' has unsupported numeric field '{field}'.")


def _validate_voices_config(raw_mapping: object, *, source: str) -> VoicesConfig:
    if not isinstance(raw_mapping, dict):
        raise ValueError(f"{source} must resolve to a JSON object.")
    validated: VoicesConfig = {}
    for key, value in raw_mapping.items():
        if not isinstance(key, str):
            raise ValueError(f"{source} must contain only string keys.")
        if not isinstance(value, dict):
            raise ValueError(f"{source} values must be JSON objects.")
        normalized: VoiceConfig = {}
        for nested_key, nested_value in value.items():
            if not isinstance(nested_key, str):
                raise ValueError(f"{source} voice objects must contain only string keys.")
            if nested_key in _VOICE_NUMERIC_FIELDS:
                normalized[nested_key] = _validate_voice_numeric_field(
                    source=source,
                    voice_name=key,
                    field=nested_key,
                    value=nested_value,
                )
                continue
            if not isinstance(nested_value, str):
                raise ValueError(
                    f"{source} voice '{key}' field '{nested_key}' must be a string "
                    "unless it is one of temperature/top_p/top_k/repetition_penalty."
                )
            normalized[nested_key] = nested_value

        mode = _read_voice_string(normalized, "mode")
        if mode not in {"voice_design", "custom_voice", "voice_clone"}:
            raise ValueError(
                f"{source} entries must declare mode as one of voice_design, custom_voice, or voice_clone."
            )
        if mode == "voice_design" and "voice_description" not in normalized:
            raise ValueError(f"{source} voice_design entries must define voice_description.")
        if mode == "custom_voice" and "speaker" not in normalized:
            raise ValueError(f"{source} custom_voice entries must define speaker.")
        if mode == "voice_clone" and ("prompt_audio_path" not in normalized or "prompt_text" not in normalized):
            raise ValueError(f"{source} voice_clone entries must define prompt_audio_path and prompt_text.")
        validated[key] = normalized
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


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _matches_preferred_tts_model(path: Path, family: TTSFamilySpec, quantization: str) -> bool:
    name = _normalize_identifier(path.name)
    return (
        path.is_dir()
        and all(_normalize_identifier(token) in name for token in family.required_tokens)
        and _normalize_identifier(quantization) in name
    )


def _discover_preferred_tts_model(model_dir: str, family: TTSFamilySpec) -> str | None:
    root = Path(model_dir)
    if not model_dir or not root.is_dir():
        return None

    try:
        entries = sorted(root.iterdir(), key=lambda item: item.name)
    except OSError:
        return None

    for quantization in TTS_QUANTIZATION_PREFERENCE:
        for entry in entries:
            if _matches_preferred_tts_model(entry, family, quantization):
                return str(entry)
    return None


def _resolve_tts_family_location(
    family: TTSFamilySpec,
    *,
    model_dir: str,
    explicit_model_name: str | None = None,
) -> str:
    if explicit_model_name is not None:
        if not explicit_model_name:
            return family.legacy_model
        if Path(explicit_model_name).is_absolute() or "/" in explicit_model_name:
            return explicit_model_name
        return str(Path(model_dir) / explicit_model_name)

    discovered = _discover_preferred_tts_model(model_dir, family)
    if discovered:
        return discovered
    return family.legacy_model


def _resolve_tts_model_location() -> str:
    direct_value = os.getenv("QWEN_TTS_MODEL")
    if direct_value:
        return direct_value

    model_dir = os.getenv("QWEN_MODEL_DIR", DEFAULT_MODEL_DIR).strip()
    explicit_model_name = os.getenv("QWEN_TTS_MODEL_NAME")
    if explicit_model_name is None:
        discovered = _discover_preferred_tts_model(model_dir, LARGE_BASE_TTS_FAMILY)
        if discovered:
            return discovered
        discovered = _discover_preferred_tts_model(model_dir, DEFAULT_TTS_FAMILY)
        if discovered:
            return discovered
        return LARGE_BASE_TTS_FAMILY.legacy_model
    return _resolve_tts_family_location(
        LARGE_BASE_TTS_FAMILY,
        model_dir=model_dir,
        explicit_model_name=explicit_model_name.strip(),
    )


def load_settings() -> Settings:
    model_dir = os.getenv("QWEN_MODEL_DIR", DEFAULT_MODEL_DIR).strip()

    return Settings(
        api_key=os.getenv("API_KEY"),
        default_tts_model=_resolve_tts_model_location(),
        small_base_tts_model=_resolve_tts_family_location(DEFAULT_TTS_FAMILY, model_dir=model_dir),
        large_base_tts_model=_resolve_tts_family_location(LARGE_BASE_TTS_FAMILY, model_dir=model_dir),
        custom_voice_tts_model=_resolve_tts_family_location(CUSTOM_VOICE_TTS_FAMILY, model_dir=model_dir),
        voice_design_tts_model=_resolve_tts_family_location(VOICE_DESIGN_TTS_FAMILY, model_dir=model_dir),
        large_custom_voice_tts_model=_resolve_tts_family_location(LARGE_CUSTOM_VOICE_TTS_FAMILY, model_dir=model_dir),
        default_asr_model=_resolve_model_location(
            direct_env_name="QWEN_ASR_MODEL",
            name_env_name="QWEN_ASR_MODEL_NAME",
            default_model_name=DEFAULT_ASR_MODEL_NAME,
            legacy_default_model=LEGACY_DEFAULT_ASR_MODEL,
        ),
        forced_language=os.getenv("QWEN_TTS_LANGUAGE") or None,
        voices=_load_voices_config(DEFAULT_VOICES),
    )
