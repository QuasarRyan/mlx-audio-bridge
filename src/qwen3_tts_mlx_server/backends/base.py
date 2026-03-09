from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class SpeechSynthesisRequest:
    public_model: str
    backend_model: str
    text: str
    voice_mode: str | None
    voice: str | None
    instructions: str | None
    prompt_audio_path: str | None
    prompt_text: str | None
    language: str | None
    speed: float
    response_format: str


@dataclass(slots=True)
class SynthesizedAudio:
    audio: np.ndarray
    sample_rate: int
    backend_model: str
    resolved_voice: str | None
    resolved_language: str | None


class TTSBackend(ABC):
    @abstractmethod
    def synthesize(self, request: SpeechSynthesisRequest) -> SynthesizedAudio:
        raise NotImplementedError
