from __future__ import annotations

import ast
from dataclasses import dataclass
import os
from pathlib import Path


def _read_local_openai_config(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as error:
        raise ValueError("api_key.py could not be parsed") from error

    candidates: list[dict[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr
            if isinstance(node.func, ast.Attribute)
            else ""
        )
        if function_name != "OpenAI":
            continue
        values = {
            keyword.arg: keyword.value.value
            for keyword in node.keywords
            if keyword.arg in {"api_key", "base_url"}
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        }
        if set(values) == {"api_key", "base_url"}:
            candidates.append(values)

    if len(candidates) != 1:
        raise ValueError(
            "api_key.py must contain exactly one OpenAI call with literal "
            "base_url and api_key strings"
        )
    return candidates[0]


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str = "https://api-cn.freeailab.cn/v1"
    model: str = "gemini-3.5-flash"
    ws_host: str = "127.0.0.1"
    ws_port: int = 8765
    request_timeout_seconds: float = 45.0
    api_max_retries: int = 2
    data_dir: Path | None = None
    log_root: Path = Path("~/workspace/cogito_logs").expanduser()
    game_id: str = "find_contract"
    max_model_requests: int = 1000
    max_tokens: int = 8192

    @classmethod
    def from_env(cls) -> "Config":
        environment_key = os.environ.get("AI_PLAY_API_KEY", "").strip()
        environment_base_url = os.environ.get("AI_PLAY_BASE_URL", "").strip()
        local = (
            _read_local_openai_config(Path("api_key.py"))
            if not environment_key or not environment_base_url
            else {}
        )
        key = environment_key or local.get("api_key", "").strip()
        if not key:
            raise ValueError("AI_PLAY_API_KEY is required")
        try:
            api_max_retries = int(
                os.environ.get("AI_PLAY_API_MAX_RETRIES", str(cls.api_max_retries))
            )
        except ValueError as error:
            raise ValueError("AI_PLAY_API_MAX_RETRIES must be 0..5") from error
        try:
            max_model_requests = int(
                os.environ.get(
                    "AI_PLAY_MAX_MODEL_REQUESTS",
                    str(cls.max_model_requests),
                )
            )
        except ValueError as error:
            raise ValueError("AI_PLAY_MAX_MODEL_REQUESTS must be 1..10000") from error
        try:
            max_tokens = int(
                os.environ.get(
                    "AI_PLAY_MAX_TOKENS",
                    str(cls.max_tokens),
                )
            )
        except ValueError as error:
            raise ValueError("AI_PLAY_MAX_TOKENS must be 1..65536") from error
        config = cls(
            api_key=key,
            base_url=(
                environment_base_url or local.get("base_url", cls.base_url)
            ).rstrip("/"),
            model=os.environ.get("AI_PLAY_MODEL", cls.model),
            ws_host=os.environ.get("AI_PLAY_WS_HOST", cls.ws_host),
            ws_port=int(os.environ.get("AI_PLAY_WS_PORT", str(cls.ws_port))),
            request_timeout_seconds=float(
                os.environ.get(
                    "AI_PLAY_REQUEST_TIMEOUT_SECONDS",
                    str(cls.request_timeout_seconds),
                )
            ),
            api_max_retries=api_max_retries,
            data_dir=Path(os.environ["AI_PLAY_DATA_DIR"]).expanduser()
            if os.environ.get("AI_PLAY_DATA_DIR")
            else None,
            log_root=Path(
                os.environ.get("AI_PLAY_LOG_ROOT", str(cls.log_root))
            ).expanduser(),
            game_id=os.environ.get("AI_PLAY_GAME", cls.game_id).strip(),
            max_model_requests=max_model_requests,
            max_tokens=max_tokens,
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
        if type(self.api_max_retries) is not int or not 0 <= self.api_max_retries <= 5:
            raise ValueError("AI_PLAY_API_MAX_RETRIES must be 0..5")
        if (
            not self.game_id
            or len(self.game_id) > 64
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789_"
                for character in self.game_id
            )
        ):
            raise ValueError("AI_PLAY_GAME must contain lowercase letters, digits, or underscores")
        if (
            type(self.max_model_requests) is not int
            or not 1 <= self.max_model_requests <= 10000
        ):
            raise ValueError("AI_PLAY_MAX_MODEL_REQUESTS must be 1..10000")
        if type(self.max_tokens) is not int or not 1 <= self.max_tokens <= 65536:
            raise ValueError("AI_PLAY_MAX_TOKENS must be 1..65536")
