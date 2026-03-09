# mlx-audio-bridge

This repository provides a local REST bridge built on `mlx-audio` to expose OpenAI-compatible TTS and STT audio endpoints. TTS currently runs on MLX `Qwen3-TTS`, and the STT surface is reserved for later `Qwen-ASR` integration.

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
export QWEN_MODEL_DIR=/opt/mlx-audio-bridge/models
export API_KEY=local-dev-key
mlx-audio-bridge-server --host 0.0.0.0 --port 8000
```

## Deploy With launchd

The repository includes a `launchd` template file: [deploy/com.quasarryan.mlxaudio.api.plist](/Users/ryan/works/services/mlx-audio-bridge/deploy/com.quasarryan.mlxaudio.api.plist).

The template is intended for a system-domain `LaunchDaemon`, runs as `root` by default, and is pinned to an `/opt/mlx-audio-bridge` deployment layout:

- Runtime user: `root`
- Executable: `/opt/mlx-audio-bridge/.venv/bin/mlx-audio-bridge-server`
- Working directory: `/opt/mlx-audio-bridge`
- Log directory: `/opt/mlx-audio-bridge/run/`
- Model directory: `/opt/mlx-audio-bridge/models/`
- Config directory: `/opt/mlx-audio-bridge/config/`
- Default bind address: `127.0.0.1:8000`

Before loading it, update at least:

- `Label`
- `UserName`, which defaults to `root`
- `API_KEY`
- `QWEN_MODEL_DIR`, which defaults to `/opt/mlx-audio-bridge/models`
- Add `QWEN_TTS_MODEL_NAME` / `QWEN_ASR_MODEL_NAME` only if your subdirectory names differ from the defaults
- `--host` and `--port` in `ProgramArguments`
- Any absolute paths that differ on your machine

First-time installation:

```bash
sudo mkdir -p /opt/mlx-audio-bridge/run /opt/mlx-audio-bridge/models /opt/mlx-audio-bridge/config
sudo cp /opt/mlx-audio-bridge/deploy/com.quasarryan.mlxaudio.api.plist /Library/LaunchDaemons/
sudo plutil -lint /Library/LaunchDaemons/com.quasarryan.mlxaudio.api.plist
sudo launchctl bootstrap system /Library/LaunchDaemons/com.quasarryan.mlxaudio.api.plist
sudo launchctl enable system/com.quasarryan.mlxaudio.api
sudo launchctl kickstart -k system/com.quasarryan.mlxaudio.api
```

Check service status:

```bash
sudo launchctl print system/com.quasarryan.mlxaudio.api
```

Check logs:

```bash
tail -f /opt/mlx-audio-bridge/run/mlx-audio-bridge.stdout.log
tail -f /opt/mlx-audio-bridge/run/mlx-audio-bridge.stderr.log
```

If you changed the plist, reload it like this:

```bash
sudo launchctl bootout system/com.quasarryan.mlxaudio.api
sudo launchctl bootstrap system /Library/LaunchDaemons/com.quasarryan.mlxaudio.api.plist
sudo launchctl kickstart -k system/com.quasarryan.mlxaudio.api
```

If you only updated code or dependencies and did not change the plist, a restart is enough:

```bash
sudo launchctl kickstart -k system/com.quasarryan.mlxaudio.api
```

To stop it and disable auto-start:

```bash
sudo launchctl bootout system/com.quasarryan.mlxaudio.api
sudo launchctl disable system/com.quasarryan.mlxaudio.api
```

If you want to run it as another user, you have two options:

- Keep it as a `LaunchDaemon`: change `UserName` in the plist from `root` to your target account, for example `svc-mlxaudio`, and make sure that user can read and write `/opt/mlx-audio-bridge`, `run/`, and `models/`. The `launchctl` commands stay in the `system` domain.
- Convert it to a per-user `LaunchAgent`: remove `UserName`, install the plist into `~/Library/LaunchAgents/`, and replace `system` in the `launchctl` commands with `gui/$(id -u)`. That makes it follow the login session of that user instead of running as a system daemon.

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
| `model` | Accepts OpenAI aliases (`gpt-4o-mini-tts`, `tts-1`, `tts-1-hd`) or a direct MLX model id / path | OpenAI aliases resolve through `QWEN_MODEL_DIR` + `QWEN_TTS_MODEL_NAME`, or pass through directly |
| `input` | Required text input | `text` |
| `voice` | OpenAI native voices use built-in defaults; custom entries from `voices.json` are resolved according to their configured mode | `voice` / `prompt_audio_path` / `prompt_text` |
| `instructions` | Combined with the `voice_design` description or request-level `instructions` and passed best-effort to the backend | `instruct` when supported |
| `speed` | Range validated like OpenAI | `speed` |
| `response_format` | Encoded to `mp3`, `opus`, `aac`, `flac`, `wav`, or `pcm` | Post-processed response audio |
| `stream_format=sse` | Returns OpenAI-style `speech.audio.delta` / `speech.audio.done` SSE events | Service-side chunked stream |

The main gap is language: OpenAI TTS does not expose a `language` field, while Qwen3-TTS benefits from one. The service infers a best-effort language from the input script and falls back to `English`. Override with `QWEN_TTS_LANGUAGE`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `API_KEY` | unset | If set, requires `Authorization: Bearer <key>` |
| `QWEN_MODEL_DIR` | `/opt/mlx-audio-bridge/models` | Shared root directory for local TTS and STT models |
| `QWEN_TTS_MODEL_NAME` | `Qwen3-TTS-12Hz-0.6B-Base-bf16` | TTS model subdirectory name |
| `QWEN_ASR_MODEL_NAME` | `Qwen3-ASR-0.6B-8bit` | Reserved STT model subdirectory name |
| `QWEN_TTS_MODEL` | empty | Backward-compatible direct override for a TTS model path or Hugging Face model id |
| `QWEN_ASR_MODEL` | empty | Backward-compatible direct override for an STT model path or Hugging Face model id |
| `QWEN_TTS_LANGUAGE` | empty | Force a backend language instead of auto-inference |

If your model layout looks like this:

```text
/opt/mlx-audio-bridge/models/
├── Qwen3-TTS-12Hz-0.6B-Base-bf16/
└── Qwen3-ASR-0.6B-8bit/
```

then setting `QWEN_MODEL_DIR=/opt/mlx-audio-bridge/models` is enough.

For compatibility with OpenAI voices such as `alloy`, `ash`, and `nova`, the service includes built-in defaults that approximate the official voice intent. The actual generated sound is still the final source of truth.

If you want to override those defaults, or add Qwen3-TTS built-in speakers, voice design presets, or voice clone entries, create `/opt/mlx-audio-bridge/config/voices.json`. Three modes are supported:

- `voice_design`
  Provide a longer `voice_description` and the service will fold it into the prompt.
- `custom_voice`
  Directly select a Qwen3-TTS speaker such as `Vivian` or `Serena`.
- `voice_clone`
  Provide a reference clip via `prompt_audio_path` and its transcript via `prompt_text`.

Example:

```json
{
  "maid": {
    "mode": "voice_design",
    "voice_description": "A private maid voice in her early twenties with a soft but substantial resonance, respectful restraint, slightly faster pacing, and a warm airy texture."
  },
  "storyteller": {
    "mode": "voice_design",
    "voice_description": "Warm Mandarin narrator voice, low expressiveness."
  },
  "vivian": {
    "mode": "custom_voice",
    "speaker": "Vivian"
  },
  "serena": {
    "mode": "custom_voice",
    "speaker": "Serena"
  },
  "assistant": {
    "mode": "voice_clone",
    "prompt_audio_path": "/opt/mlx-audio-bridge/references/assistant/default.wav",
    "prompt_text": "如果你愿意，我可以给你一个简短的当前状态回顾"
  }
}
```

This file acts as an extension and override layer. You do not need to repeat every OpenAI-native voice in it; any built-in voice you leave out continues using the service defaults. The repository includes an optional sample file: [deploy/voices.json](/Users/ryan/works/services/mlx-audio-bridge/deploy/voices.json).

## STT reservation

`/v1/audio/transcriptions` and `/v1/audio/translations` already exist so OpenAI clients can point to this service today. They currently return `501 Not Implemented` with an OpenAI-shaped error payload until Qwen-ASR wiring is added.
