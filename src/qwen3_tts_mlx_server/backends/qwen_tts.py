from __future__ import annotations

import inspect
import logging
import threading
import warnings
from collections.abc import Iterable
from typing import Any

import numpy as np

from ..errors import OpenAIHTTPException
from .base import SpeechSynthesisRequest, SynthesizedAudio, TTSBackend


class QwenMLXTTSBackend(TTSBackend):
    _DEFAULT_TEMPERATURE = 0.6
    _DEFAULT_TOP_P = 0.9
    _DEFAULT_TOP_K = 30

    def __init__(self, default_sample_rate: int = 24_000) -> None:
        self._default_sample_rate = default_sample_rate
        self._models: dict[str, Any] = {}
        self._lock = threading.Lock()

    def synthesize(self, request: SpeechSynthesisRequest) -> SynthesizedAudio:
        model = self._load_model(request.backend_model)
        audio, sample_rate = self._generate(model=model, request=request)
        return SynthesizedAudio(
            audio=audio,
            sample_rate=sample_rate,
            backend_model=request.backend_model,
            resolved_voice=request.voice,
            resolved_language=request.language,
        )

    def _load_model(self, model_id: str) -> Any:
        with self._lock:
            if model_id in self._models:
                return self._models[model_id]

            try:
                from mlx_audio.tts.utils import load_model
            except ImportError as exc:
                raise OpenAIHTTPException(
                    status_code=500,
                    message="mlx-audio is not installed. Install project dependencies before starting the server.",
                    error_type="server_error",
                    code="mlx_audio_missing",
                ) from exc

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=r"You are using a model of type qwen3_tts to instantiate a model of type .*",
                )
                model = load_model(model_id)

            self._refresh_tokenizer(model=model, model_id=model_id)
            self._models[model_id] = model
            return model

    def _refresh_tokenizer(self, model: Any, model_id: str) -> None:
        if not hasattr(model, "tokenizer"):
            return

        try:
            from transformers import AutoTokenizer
        except ImportError:
            return

        model_path = getattr(getattr(model, "config", None), "model_path", model_id)
        try:
            model.tokenizer = AutoTokenizer.from_pretrained(
                str(model_path),
                fix_mistral_regex=True,
            )
        except TypeError:
            # Older/newer transformers builds may not expose fix_mistral_regex.
            model.tokenizer = AutoTokenizer.from_pretrained(str(model_path))
        except Exception as exc:
            logging.getLogger(__name__).warning("Failed to reload tokenizer for %s: %s", model_id, exc)

    def _generate(self, model: Any, request: SpeechSynthesisRequest) -> tuple[np.ndarray, int]:
        try:
            generate_signature = inspect.signature(model.generate)
            generate_parameters = set(generate_signature.parameters)
        except (TypeError, ValueError):
            generate_parameters = set()

        generate_kwargs: dict[str, Any] = {
            "text": request.text,
            "speed": request.speed,
            "temperature": self._DEFAULT_TEMPERATURE,
            "top_p": self._DEFAULT_TOP_P,
            "top_k": self._DEFAULT_TOP_K,
        }
        if request.voice:
            generate_kwargs["voice"] = request.voice
        if request.language:
            language_param = "lang_code" if "lang_code" in generate_parameters else "language"
            generate_kwargs[language_param] = request.language
        if request.instructions:
            generate_kwargs["instruct"] = request.instructions
        if request.prompt_audio_path:
            audio_prompt_param = "ref_audio" if "ref_audio" in generate_parameters else "prompt_audio_path"
            generate_kwargs[audio_prompt_param] = request.prompt_audio_path
        if request.prompt_text:
            text_prompt_param = "ref_text" if "ref_text" in generate_parameters else "prompt_text"
            generate_kwargs[text_prompt_param] = request.prompt_text

        try:
            raw_result = model.generate(**generate_kwargs)
        except TypeError as exc:
            if request.voice_mode == "voice_clone":
                raise OpenAIHTTPException(
                    status_code=501,
                    message=(
                        "The current mlx-audio backend does not expose the reference-audio inputs required "
                        "for voice_clone mode."
                    ),
                    error_type="server_error",
                    code="voice_clone_not_supported",
                ) from exc
            if "instruct" not in generate_kwargs:
                raise
            generate_kwargs.pop("instruct", None)
            raw_result = model.generate(**generate_kwargs)
        except Exception as exc:
            raise OpenAIHTTPException(
                status_code=500,
                message=f"Qwen3-TTS generation failed: {exc}",
                error_type="server_error",
                code="tts_generation_failed",
            ) from exc

        try:
            return self._coerce_audio_result(raw_result=raw_result, model=model)
        except OpenAIHTTPException:
            raise
        except Exception as exc:
            raise OpenAIHTTPException(
                status_code=500,
                message=f"Unable to parse MLX audio output: {exc}",
                error_type="server_error",
                code="tts_output_parse_failed",
            ) from exc

    def _coerce_audio_result(self, raw_result: Any, model: Any) -> tuple[np.ndarray, int]:
        if isinstance(raw_result, tuple) and len(raw_result) == 2:
            wavs, sample_rate = raw_result
            first = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
            return self._to_numpy(first), int(sample_rate)

        if hasattr(raw_result, "audio"):
            sample_rate = self._discover_sample_rate(raw_result, model)
            return self._to_numpy(raw_result.audio), sample_rate

        if isinstance(raw_result, Iterable) and not isinstance(raw_result, (str, bytes, bytearray)):
            items = list(raw_result)
            if not items:
                raise OpenAIHTTPException(
                    status_code=500,
                    message="Qwen3-TTS returned no audio frames.",
                    error_type="server_error",
                    code="tts_empty_output",
                )
            first = items[0]
            if hasattr(first, "audio"):
                sample_rate = self._discover_sample_rate(first, model)
                return self._to_numpy(first.audio), sample_rate

        raise OpenAIHTTPException(
            status_code=500,
            message="Unsupported MLX audio output format.",
            error_type="server_error",
            code="tts_unknown_output",
        )

    def _discover_sample_rate(self, result: Any, model: Any) -> int:
        for candidate in (
            getattr(result, "sample_rate", None),
            getattr(result, "sampling_rate", None),
            getattr(model, "sample_rate", None),
            getattr(getattr(model, "config", None), "sample_rate", None),
            getattr(getattr(model, "config", None), "sampling_rate", None),
        ):
            if candidate:
                return int(candidate)
        return self._default_sample_rate

    def _to_numpy(self, value: Any) -> np.ndarray:
        if isinstance(value, np.ndarray):
            return value.astype(np.float32).reshape(-1)
        if hasattr(value, "numpy"):
            return np.asarray(value.numpy(), dtype=np.float32).reshape(-1)
        return np.asarray(value, dtype=np.float32).reshape(-1)
