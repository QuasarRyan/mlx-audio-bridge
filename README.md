# mlx-audio-bridge

这是一个基于 `mlx-audio` 的本地 REST 服务，用来实现兼容 OpenAI 的 TTS / STT 音频接口桥接层。当前 TTS 已接入 MLX 版 `Qwen3-TTS`，STT 接口已预留给后续 `Qwen-ASR`。

英文版说明已移到 [README.en.md](./README.en.md)。

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

需要 Python 3.10 到 3.13，且运行环境必须是搭载 Apple silicon 的 macOS。

```bash
UV_CACHE_DIR=.uv-cache UV_PROJECT_ENVIRONMENT=.venv uv sync --extra dev
```

如果你想显式指定 Python 版本，可以这样写：

```bash
UV_CACHE_DIR=.uv-cache UV_PROJECT_ENVIRONMENT=.venv uv sync --python 3.13 --extra dev
```

如果需要返回 `mp3`、`opus`、`aac`、`flac`，还需要安装 `ffmpeg`：

```bash
brew install ffmpeg
```

## 启动

先设置后端模型。默认使用示例里的 MLX 模型：

```bash
export QWEN_MODEL_DIR=/opt/mlx-audio-bridge/models
export API_KEY=local-dev-key
mlx-audio-bridge-server --host 0.0.0.0 --port 8000
```

## 用 launchd 部署

仓库里提供了一个 `launchd` 模板文件：[deploy/com.quasarryan.mlxaudio.api.plist](./deploy/com.quasarryan.mlxaudio.api.plist)。

这个模板是给 system domain 的 `LaunchDaemon` 用的，默认按 `root` 用户运行，并按 `/opt/mlx-audio-bridge` 的部署目录写死了以下内容：

- 运行用户：`root`
- 可执行文件：`/opt/mlx-audio-bridge/.venv/bin/mlx-audio-bridge-server`
- 工作目录：`/opt/mlx-audio-bridge`
- 日志目录：`/opt/mlx-audio-bridge/run/`
- 模型目录：`/opt/mlx-audio-bridge/models/`
- 配置目录：`/opt/mlx-audio-bridge/config/`
- 默认监听：`127.0.0.1:8000`

使用前请先编辑 plist，至少确认这些值：

- `Label`
- `UserName`，模板默认是 `root`
- `API_KEY`
- `QWEN_MODEL_DIR`，默认指向 `/opt/mlx-audio-bridge/models`
- 如果目录名不是默认值，再补 `QWEN_TTS_MODEL_NAME` / `QWEN_ASR_MODEL_NAME`
- `ProgramArguments` 里的 `--host` 和 `--port`
- 部署绝对路径是否与你本机一致

首次安装步骤：

```bash
sudo mkdir -p /opt/mlx-audio-bridge/run /opt/mlx-audio-bridge/models /opt/mlx-audio-bridge/config
sudo cp /opt/mlx-audio-bridge/deploy/com.quasarryan.mlxaudio.api.plist /Library/LaunchDaemons/
sudo plutil -lint /Library/LaunchDaemons/com.quasarryan.mlxaudio.api.plist
sudo launchctl bootstrap system /Library/LaunchDaemons/com.quasarryan.mlxaudio.api.plist
sudo launchctl enable system/com.quasarryan.mlxaudio.api
sudo launchctl kickstart -k system/com.quasarryan.mlxaudio.api
```

查看服务状态：

```bash
sudo launchctl print system/com.quasarryan.mlxaudio.api
```

查看日志：

```bash
tail -f /opt/mlx-audio-bridge/run/mlx-audio-bridge.stdout.log
tail -f /opt/mlx-audio-bridge/run/mlx-audio-bridge.stderr.log
```

如果你修改了 plist 内容，推荐这样重载：

```bash
sudo launchctl bootout system/com.quasarryan.mlxaudio.api
sudo launchctl bootstrap system /Library/LaunchDaemons/com.quasarryan.mlxaudio.api.plist
sudo launchctl kickstart -k system/com.quasarryan.mlxaudio.api
```

如果你只更新了代码或依赖，没有改 plist，可以直接重启服务：

```bash
sudo launchctl kickstart -k system/com.quasarryan.mlxaudio.api
```

如果要停止并取消开机自启：

```bash
sudo launchctl bootout system/com.quasarryan.mlxaudio.api
sudo launchctl disable system/com.quasarryan.mlxaudio.api
```

如果你要改成其它用户运行，有两种方式：

- 继续作为 `LaunchDaemon` 运行：把 plist 里的 `UserName` 从 `root` 改成目标用户，例如 `svc-mlxaudio`，然后确保 `/opt/mlx-audio-bridge`、`run/`、`models/` 对该用户可读写。`launchctl` 的 system 域命令保持不变。
- 改成登录用户自己的 `LaunchAgent`：删除 plist 里的 `UserName`，把文件放到 `~/Library/LaunchAgents/`，并把所有 `launchctl` 命令里的 `system` 改成 `gui/$(id -u)`。这种方式会随该用户登录态运行，而不是系统级守护进程。

如果你调整了 plist 里的运行用户，记得把工作目录递归改成该用户拥有，例如：

```bash
sudo chown -R svc-mlxaudio:staff /opt/mlx-audio-bridge
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
| `model` | 支持 OpenAI 别名 `gpt-4o-mini-tts`、`tts-1`、`tts-1-hd`，也支持直接传 MLX 模型 ID / 路径 | OpenAI 别名映射到 `QWEN_MODEL_DIR` + `QWEN_TTS_MODEL_NAME`，或直接透传 |
| `input` | 必填文本 | `text` |
| `voice` | 如果是 OpenAI 原生音色，则命中服务内置默认配置；如果是 `voices.json` 里的自定义键，则按配置里的模式解析 | `voice` / `prompt_audio_path` / `prompt_text` |
| `instructions` | 与 `voice_design` 模式里的默认描述或请求内 `instructions` 合并后，尽力传给后端 | `instruct` |
| `speed` | 按 OpenAI 范围校验 | `speed` |
| `response_format` | 支持 `mp3`、`opus`、`aac`、`flac`、`wav`、`pcm` | 服务端编码输出 |
| `stream_format=sse` | 返回 OpenAI 风格的 `speech.audio.delta` / `speech.audio.done` 事件 | 服务端分块流式返回 |

一个关键差异是 `language`：OpenAI TTS 接口没有这个字段，但 Qwen3-TTS 往往更适合显式语言。当前服务会根据输入文本脚本自动推断语言，默认回落到 `English`；也可以用 `QWEN_TTS_LANGUAGE` 强制指定。

## 配置项

| 环境变量 | 默认值 | 作用 |
| --- | --- | --- |
| `API_KEY` | 未设置 | 如果设置，则要求 `Authorization: Bearer <key>` |
| `QWEN_MODEL_DIR` | `/opt/mlx-audio-bridge/models` | 本地模型根目录，TTS / STT 共用 |
| `QWEN_TTS_MODEL_NAME` | `Qwen3-TTS-12Hz-0.6B-Base-bf16` | TTS 模型子目录名 |
| `QWEN_ASR_MODEL_NAME` | `Qwen3-ASR-0.6B-8bit` | 预留给后续 STT 的模型子目录名 |
| `QWEN_TTS_MODEL` | 空 | 兼容旧配置，直接覆盖 TTS 模型路径或 Hugging Face 模型 ID |
| `QWEN_ASR_MODEL` | 空 | 兼容旧配置，直接覆盖 STT 模型路径或 Hugging Face 模型 ID |
| `QWEN_TTS_LANGUAGE` | 空 | 强制指定后端语言，不做自动推断 |

如果你的模型目录结构是：

```text
/opt/mlx-audio-bridge/models/
├── Qwen3-TTS-12Hz-0.6B-Base-bf16/
└── Qwen3-ASR-0.6B-8bit/
```

那么只设置 `QWEN_MODEL_DIR=/opt/mlx-audio-bridge/models` 就够了。

为了兼容 OpenAI 的 `alloy`、`ash`、`nova` 等音色，服务内置了一组参考官方风格的默认配置；最终效果仍以实际生成出来的音色为准。

如果你要覆盖这些默认配置，或者增加 Qwen3-TTS 自带 speaker、voice design、voice clone 等自定义音色，可以在 `/opt/mlx-audio-bridge/config/voices.json` 里配置。支持三种模式：

- `voice_design`
  使用一段较长的 `voice_description` 描述目标音色，服务会把它拼进提示词。
- `custom_voice`
  直接指定 Qwen3-TTS 的内置 speaker，例如 `Vivian`、`Serena`。
- `voice_clone`
  提供参考音频 `prompt_audio_path` 和对应文本 `prompt_text`。

文件格式示例：

```json
{
  "storyteller": {
    "mode": "voice_design",
    "voice_description": "Warm Mandarin narrator voice, low expressiveness."
  },
  "vivian": {
    "mode": "custom_voice",
    "speaker": "Vivian"
  },
  "assistant": {
    "mode": "voice_clone",
    "prompt_audio_path": "这里填你的参考音频的路径",
    "prompt_text": "这里填你的参考文本，建议与参考音频内容一致"
  }
}

```

这个文件是“扩展 + 覆盖层”，不是必须完整列出所有 OpenAI 原生音色。没写到的 OpenAI voice 会继续使用服务里内置的默认配置。仓库里的 [deploy/voices.json](./deploy/voices.json) 已经包含了 OpenAI 原生音色默认配置，以及 `voice_design`、`custom_voice` 的示例；`voice_clone` 示例保留在 README 中。

## STT 预留

`/v1/audio/transcriptions` 和 `/v1/audio/translations` 已经存在，因此 OpenAI 客户端今天就可以指向这个服务。当前它们会返回 OpenAI 风格的 `501 Not Implemented` 错误，等后面接入 Qwen-ASR 后再补齐实际识别逻辑。
