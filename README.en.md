# Qwen3-TTS MLX OpenAI-Compatible Service

This repository provides a local REST service that exposes MLX Qwen3-TTS behind OpenAI-compatible audio endpoints.

> Note: This project only runs on Apple silicon Macs. Intel Macs, Linux, and Windows are not supported.

Implemented now:

- `POST /v1/audio/speech`
- `GET /v1/models`
- `GET /v1/models/{model}`

Reserved for future Qwen-ASR integration:

- `POST /v1/audio/transcriptions`
- `POST /v1/audio/translations`

## Goals

- OpenAI-compatible request and error shapes
- MLX `mlx-audio` as the runtime backend
- Qwen3-TTS parameter mapping for `voice`, `instructions`, `speed`, and output formats
- Clean extension point for Qwen-ASR later without changing client code

## Install

Python 3.10-3.12 is required. The runtime environment must be macOS on Apple silicon.

```bash
UV_CACHE_DIR=.uv-cache UV_PROJECT_ENVIRONMENT=.venv uv sync --extra dev
```

`ffmpeg` is required for `mp3`, `opus`, `aac`, and `flac` responses.

```bash
brew install ffmpeg
```

## Run

Set the backend model first. The default is the documented MLX example model.

```bash
export QWEN_TTS_MODEL=mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16
export API_KEY=local-dev-key
qwen3-tts-mlx-server --host 0.0.0.0 --port 8000
```

## OpenAI-compatible usage

```bash
curl http://localhost:8000/v1/audio/speech \
  -H "Authorization: Bearer local-dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini-tts",
    "input": "你好，这里是本地 Qwen3-TTS 服务。",
    "voice": "alloy",
    "response_format": "wav",
    "instructions": "Speak in a calm and professional tone."
  }' \
  --output speech.wav
```

## Parameter mapping

OpenAI TTS parameters are mapped onto `mlx-audio` Qwen3-TTS as follows:

| OpenAI field | Service behavior | Qwen3-TTS / MLX mapping |
| --- | --- | --- |
| `model` | Accepts OpenAI aliases (`gpt-4o-mini-tts`, `tts-1`, `tts-1-hd`) or a direct MLX model id | Resolved to `QWEN_TTS_MODEL` or passed through |
| `input` | Required text input | `text` |
| `voice` | OpenAI built-in voices are mapped to Qwen speakers via `OPENAI_VOICE_MAP`; unknown values pass through | `voice` |
| `instructions` | Combined with a voice-style hint from `OPENAI_VOICE_STYLE_MAP`; passed best-effort to the backend | `instruct` when supported |
| `speed` | Range validated like OpenAI | `speed` |
| `response_format` | Encoded to `mp3`, `opus`, `aac`, `flac`, `wav`, or `pcm` | Post-processed response audio |
| `stream_format=sse` | Returns OpenAI-style `speech.audio.delta` / `speech.audio.done` SSE events | Service-side chunked stream |

The main gap is language: OpenAI TTS does not expose a `language` field, while Qwen3-TTS benefits from one. The service infers a best-effort language from the input script and falls back to `English`. Override with `QWEN_TTS_LANGUAGE`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `API_KEY` | unset | If set, requires `Authorization: Bearer <key>` |
| `QWEN_TTS_MODEL` | `mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16` | Backend MLX Qwen3-TTS model |
| `QWEN_ASR_MODEL` | `mlx-community/Qwen3-ASR-0.6B-8bit` | Reserved STT model id for future wiring |
| `QWEN_TTS_LANGUAGE` | empty | Force a backend language instead of auto-inference |
| `OPENAI_VOICE_MAP` | built-in JSON map | Maps OpenAI voice names to Qwen speakers |
| `OPENAI_VOICE_STYLE_MAP` | built-in JSON map | Voice-style hints folded into `instructions` |

Example custom voice mapping:

```bash
export OPENAI_VOICE_MAP='{"alloy":"Chelsie","nova":"Chelsie","sage":"Chelsie"}'
```

## STT reservation

`/v1/audio/transcriptions` and `/v1/audio/translations` already exist so OpenAI clients can point to this service today. They currently return `501 Not Implemented` with an OpenAI-shaped error payload until Qwen-ASR wiring is added.
