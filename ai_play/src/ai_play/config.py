from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path


@dataclass(frozen=True)
class Config:
    ws_host: str = "127.0.0.1"
    ws_port: int = 8765
    wait_timeout_seconds: float = 30.0
    stop_timeout_seconds: float = 5.0
    max_act_requests: int = 150
    log_root: Path = Path("~/workspace/cogito_logs/mcplogs").expanduser()
    workflow_memory_path: Path | None = None
    approved_image_root: Path | None = None

    @classmethod
    def from_env(cls) -> "Config":
        config = cls(
            ws_host=os.environ.get("AI_PLAY_WS_HOST", cls.ws_host).strip(),
            ws_port=_read_int("AI_PLAY_WS_PORT", cls.ws_port),
            wait_timeout_seconds=_read_float(
                "AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS",
                cls.wait_timeout_seconds,
            ),
            stop_timeout_seconds=_read_float(
                "AI_PLAY_STOP_TIMEOUT_SECONDS",
                cls.stop_timeout_seconds,
            ),
            max_act_requests=_read_int(
                "AI_PLAY_MAX_ACT_REQUESTS",
                cls.max_act_requests,
            ),
            log_root=_read_path("AI_PLAY_LOG_ROOT", cls.log_root),
            workflow_memory_path=_read_optional_absolute_path(
                "AI_PLAY_WORKFLOW_MEMORY_PATH"
            ),
            approved_image_root=_read_optional_absolute_path(
                "AI_PLAY_APPROVED_IMAGE_ROOT"
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.ws_host != "127.0.0.1":
            raise ValueError("AI_PLAY_WS_HOST must be 127.0.0.1")
        if type(self.ws_port) is not int or not 1 <= self.ws_port <= 65535:
            raise ValueError("AI_PLAY_WS_PORT must be between 1 and 65535")
        if (
            type(self.max_act_requests) is not int
            or not 1 <= self.max_act_requests <= 1_000_000
        ):
            raise ValueError(
                "AI_PLAY_MAX_ACT_REQUESTS must be between 1 and 1000000"
            )
        for name, value, lower, upper in [
            (
                "AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS",
                self.wait_timeout_seconds,
                0.1,
                120.0,
            ),
            (
                "AI_PLAY_STOP_TIMEOUT_SECONDS",
                self.stop_timeout_seconds,
                0.1,
                30.0,
            ),
        ]:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number")
            if not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f"{name} is outside its allowed range")


def _read_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


def _read_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error


def _read_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    if raw is None:
        return Path(default).expanduser()
    if not raw.strip():
        raise ValueError(f"{name} must not be empty")
    return Path(raw).expanduser()


def _read_optional_absolute_path(name: str) -> Path | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    if not raw.strip():
        raise ValueError(f"{name} must not be empty")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    return path.resolve()
