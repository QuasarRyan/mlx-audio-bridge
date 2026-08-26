from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    input: str = Field(min_length=1, max_length=4096)
    model: str
    voice: str
    instructions: str | None = None
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "mp3"
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    # Match mlx-audio's server-side cap. Its Python API otherwise defaults to
    # 4096, which makes a failed EOS/degenerate clone request run far longer.
    max_tokens: int = Field(default=1200, ge=1, le=4096)
    temperature: float | None = Field(default=None, gt=0)
    top_p: float | None = Field(default=None, gt=0, le=1)
    top_k: int | None = Field(default=None, ge=1)
    repetition_penalty: float | None = Field(default=None, ge=1.0)
    stream_format: Literal["audio", "sse"] = "audio"
