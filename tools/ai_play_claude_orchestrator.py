#!/usr/bin/env python3
"""Run a hardened, black-box Claude Code player with AI First Play."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping

try:
    from . import ai_play_orchestrator_common as _common
except ImportError:
    import ai_play_orchestrator_common as _common


REPO_ROOT = _common.REPO_ROOT
DEFAULT_CLAUDE_SETTINGS = REPO_ROOT / ".claude" / "settings.local.json"
CLAUDE_PROVIDER_ENV_NAMES = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
)


@dataclass(frozen=True)
class ClaudePlayerConfig:
    root: Path
    settings_path: Path
    mcp_path: Path


def load_claude_provider_env(settings_path: Path) -> dict[str, str]:
    source = settings_path.expanduser()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing Claude settings file: {source}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid Claude settings file: {source}") from error
    if not isinstance(payload, dict):
        raise ValueError("Claude settings root must be a JSON object")
    raw_env = payload.get("env")
    if not isinstance(raw_env, dict):
        raise ValueError("Claude settings must contain an env object")

    provider_env: dict[str, str] = {}
    for name in CLAUDE_PROVIDER_ENV_NAMES:
        value = raw_env.get(name)
        if value is None:
            continue
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"Claude settings env {name} must be a non-empty string"
            )
        provider_env[name] = value
    if not any(
        provider_env.get(name)
        for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    ):
        raise ValueError(
            "Claude settings must provide ANTHROPIC_API_KEY or "
            "ANTHROPIC_AUTH_TOKEN"
        )
    base_url = provider_env.get("ANTHROPIC_BASE_URL")
    if base_url is not None and not base_url.startswith("https://"):
        raise ValueError("ANTHROPIC_BASE_URL must use https")
    return provider_env


def _write_private_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


@contextmanager
def temporary_claude_player_config(
    provider_env: Mapping[str, str],
    mcp_url: str,
) -> Iterator[ClaudePlayerConfig]:
    with tempfile.TemporaryDirectory(
        prefix="cogito-ai-play-claude-"
    ) as raw_root:
        root = Path(raw_root)
        os.chmod(root, 0o700)
        settings_path = root / "settings.json"
        mcp_path = root / "mcp.json"
        _write_private_json(settings_path, {"env": dict(provider_env)})
        _write_private_json(
            mcp_path,
            {
                "mcpServers": {
                    "cogito_ai_play": {
                        "type": "http",
                        "url": mcp_url,
                    }
                }
            },
        )
        yield ClaudePlayerConfig(
            root=root,
            settings_path=settings_path,
            mcp_path=mcp_path,
        )
