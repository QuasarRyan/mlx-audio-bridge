from __future__ import annotations

import argparse
import os

import uvicorn

DEFAULT_BIND_ADDRESS = "127.0.0.1"
DEFAULT_PORT = "8008"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the mlx-audio-bridge server.")
    parser.add_argument("--host", default=os.getenv("BIND_ADDRESS", DEFAULT_BIND_ADDRESS))
    parser.add_argument("--port", default=os.getenv("PORT", DEFAULT_PORT), type=int)
    parser.add_argument("--reload", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    uvicorn.run(
        "qwen3_tts_mlx_server.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
