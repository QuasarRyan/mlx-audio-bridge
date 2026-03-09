from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .audio import encode_audio, media_type_for_format, sse_audio_events
from .backends import QwenMLXTTSBackend, SpeechSynthesisRequest, TTSBackend
from .errors import (
    OpenAIHTTPException,
    openai_http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from .models import available_models_payload, make_model_object
from .schemas import SpeechRequest
from .settings import OPENAI_STT_ALIASES, Settings, load_settings


def _authorization_dependency(settings: Settings):
    async def require_api_key(authorization: Annotated[str | None, Header()] = None) -> None:
        if not settings.api_key:
            return
        expected = f"Bearer {settings.api_key}"
        if authorization != expected:
            raise OpenAIHTTPException(
                status_code=401,
                message="Invalid authentication credentials.",
                error_type="invalid_request_error",
                code="invalid_api_key",
            )

    return require_api_key


def create_app(settings: Settings | None = None, tts_backend: TTSBackend | None = None) -> FastAPI:
    resolved_settings = settings or load_settings()
    resolved_backend = tts_backend or QwenMLXTTSBackend()
    auth_dependency = _authorization_dependency(resolved_settings)

    app = FastAPI(title="Qwen3-TTS MLX OpenAI-Compatible API", version="0.1.0")
    app.add_exception_handler(OpenAIHTTPException, openai_http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models", dependencies=[Depends(auth_dependency)])
    async def list_models() -> dict[str, object]:
        return available_models_payload(resolved_settings)

    @app.get("/v1/models/{model_id}", dependencies=[Depends(auth_dependency)])
    async def retrieve_model(model_id: str) -> dict[str, object]:
        public_models = resolved_settings.public_model_roots()
        if model_id not in public_models:
            raise OpenAIHTTPException(
                status_code=404,
                message=f"The model '{model_id}' does not exist.",
                error_type="invalid_request_error",
                code="model_not_found",
            )
        return make_model_object(model_id=model_id, root=public_models[model_id])

    @app.post("/v1/audio/speech", dependencies=[Depends(auth_dependency)])
    async def create_speech(request: SpeechRequest) -> Response:
        if request.model in {"tts-1", "tts-1-hd"} and request.stream_format == "sse":
            raise OpenAIHTTPException(
                status_code=400,
                message=f"stream_format='sse' is not supported for model '{request.model}'.",
                error_type="invalid_request_error",
                param="stream_format",
                code="unsupported_stream_format",
            )

        synthesis_request = SpeechSynthesisRequest(
            public_model=request.model,
            backend_model=resolved_settings.resolve_tts_model(request.model),
            text=request.input,
            voice=resolved_settings.resolve_voice(request.voice),
            instructions=resolved_settings.compose_instructions(request.voice, request.instructions),
            language=resolved_settings.infer_language(request.input),
            speed=request.speed,
            response_format=request.response_format,
        )
        synthesized = await run_in_threadpool(resolved_backend.synthesize, synthesis_request)
        audio_bytes = await run_in_threadpool(
            encode_audio,
            synthesized.audio,
            synthesized.sample_rate,
            request.response_format,
        )

        if request.stream_format == "sse":
            return StreamingResponse(
                sse_audio_events(audio_bytes=audio_bytes, input_text=request.input),
                media_type="text/event-stream",
            )

        return Response(
            content=audio_bytes,
            media_type=media_type_for_format(request.response_format),
            headers={
                "Content-Disposition": f'attachment; filename="speech.{request.response_format}"',
            },
        )

    @app.post("/v1/audio/transcriptions", dependencies=[Depends(auth_dependency)])
    async def create_transcription(
        file: UploadFile = File(...),
        model: str = Form(...),
        response_format: str = Form(default="json"),
        language: str | None = Form(default=None),
        prompt: str | None = Form(default=None),
        temperature: float | None = Form(default=None),
    ) -> JSONResponse:
        _ = (file, model, response_format, language, prompt, temperature)
        raise OpenAIHTTPException(
            status_code=501,
            message=(
                "The transcription endpoint is reserved for future Qwen-ASR integration. "
                f"Configured ASR target aliases: {', '.join(OPENAI_STT_ALIASES)}."
            ),
            error_type="server_error",
            code="not_implemented",
        )

    @app.post("/v1/audio/translations", dependencies=[Depends(auth_dependency)])
    async def create_translation(
        file: UploadFile = File(...),
        model: str = Form(...),
        response_format: str = Form(default="json"),
        prompt: str | None = Form(default=None),
        temperature: float | None = Form(default=None),
    ) -> JSONResponse:
        _ = (file, model, response_format, prompt, temperature)
        raise OpenAIHTTPException(
            status_code=501,
            message="The translation endpoint is reserved for future Qwen-ASR integration.",
            error_type="server_error",
            code="not_implemented",
        )

    return app
