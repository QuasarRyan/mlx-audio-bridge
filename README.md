# Qwen3-TTS MLX OpenAI Compatible 服务

这是一个本地 REST 服务，用 MLX 版 `Qwen3-TTS` 作为后端，并暴露与 OpenAI Compatible API 对齐的音频接口。

英文版说明已移到 [README.en.md](/Users/ryan/works/services/qwen3-tts-mlx/README.en.md)。

> 注意：该项目只能运行在搭载 Apple silicon 的 Mac 上，不支持 Intel Mac，也不支持 Linux 或 Windows。

当前已实现：

- `POST /v1/audio/speech`
- `GET /v1/models`
- `GET /v1/models/{model}`

为后续 Qwen-ASR 预留：

- `POST /v1/audio/transcriptions`
- `POST /v1/audio/translations`

## 目标

- REST API 与 OpenAI 音频接口兼容
- 运行时后端使用 `mlx-audio`
- 对 Qwen3-TTS 不兼容的参数做服务端映射
- 先把 STT 接口形状预留好，后面接入 Qwen-ASR 时不改客户端

## 安装

需要 Python 3.10 到 3.12，且运行环境必须是搭载 Apple silicon 的 macOS。

```bash
UV_CACHE_DIR=.uv-cache UV_PROJECT_ENVIRONMENT=.venv uv sync --extra dev
```

如果需要返回 `mp3`、`opus`、`aac`、`flac`，还需要安装 `ffmpeg`：

```bash
brew install ffmpeg
```

## 启动

先设置后端模型。默认使用示例里的 MLX 模型：

```bash
export QWEN_TTS_MODEL=mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16
export API_KEY=local-dev-key
qwen3-tts-mlx-server --host 0.0.0.0 --port 8000
```

## OpenAI Compatible 调用示例

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

## 参数映射

OpenAI TTS 请求参数会按下面的方式映射到 `mlx-audio` 的 Qwen3-TTS：

| OpenAI 字段 | 服务端行为 | Qwen3-TTS / MLX 映射 |
| --- | --- | --- |
| `model` | 支持 OpenAI 别名 `gpt-4o-mini-tts`、`tts-1`、`tts-1-hd`，也支持直接传 MLX 模型 ID | 映射到 `QWEN_TTS_MODEL` 或直接透传 |
| `input` | 必填文本 | `text` |
| `voice` | OpenAI voice 名称通过 `OPENAI_VOICE_MAP` 映射到 Qwen speaker，未知值直接透传 | `voice` |
| `instructions` | 与 `OPENAI_VOICE_STYLE_MAP` 中的风格提示合并后，尽力传给后端 | `instruct` |
| `speed` | 按 OpenAI 范围校验 | `speed` |
| `response_format` | 支持 `mp3`、`opus`、`aac`、`flac`、`wav`、`pcm` | 服务端编码输出 |
| `stream_format=sse` | 返回 OpenAI 风格的 `speech.audio.delta` / `speech.audio.done` 事件 | 服务端分块流式返回 |

一个关键差异是 `language`：OpenAI TTS 接口没有这个字段，但 Qwen3-TTS 往往更适合显式语言。当前服务会根据输入文本脚本自动推断语言，默认回落到 `English`；也可以用 `QWEN_TTS_LANGUAGE` 强制指定。

## 配置项

| 环境变量 | 默认值 | 作用 |
| --- | --- | --- |
| `API_KEY` | 未设置 | 如果设置，则要求 `Authorization: Bearer <key>` |
| `QWEN_TTS_MODEL` | `mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16` | Qwen3-TTS 后端模型 |
| `QWEN_ASR_MODEL` | `mlx-community/Qwen3-ASR-0.6B-8bit` | 预留给后续 STT 接入的模型 ID |
| `QWEN_TTS_LANGUAGE` | 空 | 强制指定后端语言，不做自动推断 |
| `OPENAI_VOICE_MAP` | 内置 JSON 映射 | 把 OpenAI voice 映射到 Qwen speaker |
| `OPENAI_VOICE_STYLE_MAP` | 内置 JSON 映射 | 把 voice 风格提示折叠进 `instructions` |

自定义 voice 映射示例：

```bash
export OPENAI_VOICE_MAP='{"alloy":"Chelsie","nova":"Chelsie","sage":"Chelsie"}'
```

## STT 预留

`/v1/audio/transcriptions` 和 `/v1/audio/translations` 已经存在，因此 OpenAI 客户端今天就可以指向这个服务。当前它们会返回 OpenAI 风格的 `501 Not Implemented` 错误，等后面接入 Qwen-ASR 后再补齐实际识别逻辑。
