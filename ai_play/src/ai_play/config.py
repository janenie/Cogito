from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str = "https://api-cn.freeailab.cn/v1"
    model: str = "gemini-3.5-flash"
    ws_host: str = "127.0.0.1"
    ws_port: int = 8765
    request_timeout_seconds: float = 45.0
    data_dir: Path | None = None

    @classmethod
    def from_env(cls) -> "Config":
        key = os.environ.get("AI_PLAY_API_KEY", "").strip()
        if not key:
            raise ValueError("AI_PLAY_API_KEY is required")
        config = cls(
            api_key=key,
            base_url=os.environ.get("AI_PLAY_BASE_URL", cls.base_url).rstrip("/"),
            model=os.environ.get("AI_PLAY_MODEL", cls.model),
            ws_host=os.environ.get("AI_PLAY_WS_HOST", cls.ws_host),
            ws_port=int(os.environ.get("AI_PLAY_WS_PORT", str(cls.ws_port))),
            request_timeout_seconds=float(
                os.environ.get(
                    "AI_PLAY_REQUEST_TIMEOUT_SECONDS",
                    str(cls.request_timeout_seconds),
                )
            ),
            data_dir=Path(os.environ["AI_PLAY_DATA_DIR"]).expanduser()
            if os.environ.get("AI_PLAY_DATA_DIR")
            else None,
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.ws_host != "127.0.0.1":
            raise ValueError("AI Play WebSocket host must be loopback 127.0.0.1")
        if not 1 <= self.ws_port <= 65535:
            raise ValueError("AI_PLAY_WS_PORT must be between 1 and 65535")
        if not 1.0 <= self.request_timeout_seconds <= 120.0:
            raise ValueError("AI_PLAY_REQUEST_TIMEOUT_SECONDS must be 1..120")
