#!/usr/bin/env python3
"""Compatibility entry for the generic Yibu Codex orchestrator."""

from __future__ import annotations

from typing import Sequence

try:
    from . import ai_play_codex_yibu_orchestrator as _yibu
except ImportError:
    import ai_play_codex_yibu_orchestrator as _yibu


DEFAULT_MODEL = "gemini-3.6-flash"

# Public compatibility aliases retained for callers and tests that imported the
# original Gemini-specific helper module.
AWM_PLAYER_TOOL_NAMES = _yibu.AWM_PLAYER_TOOL_NAMES
BASE_PLAYER_TOOL_NAMES = _yibu.BASE_PLAYER_TOOL_NAMES
DEFAULT_BENCHMARK_CYCLE_SEED = _yibu.DEFAULT_BENCHMARK_CYCLE_SEED
DEFAULT_CODEX_MAX_RESTARTS = _yibu.DEFAULT_CODEX_MAX_RESTARTS
DEFAULT_CONTEXT_WINDOW = _yibu.DEFAULT_CONTEXT_WINDOW
DEFAULT_MCP_PORT = _yibu.DEFAULT_MCP_PORT
DEFAULT_PROVIDER_PROXY_PORT = _yibu.DEFAULT_PROVIDER_PROXY_PORT
DEFAULT_SCENE = _yibu.DEFAULT_SCENE
DEFAULT_SESSION_ROOT = _yibu.DEFAULT_SESSION_ROOT
DEFAULT_WS_HOST = _yibu.DEFAULT_WS_HOST
DEFAULT_WS_PORT = _yibu.DEFAULT_WS_PORT
DEFAULT_YIBU_CREDENTIALS = _yibu.DEFAULT_YIBU_CREDENTIALS
MAX_BENCHMARK_CYCLE_SEED = _yibu.MAX_BENCHMARK_CYCLE_SEED
MCP_TOOL_NAMESPACE = _yibu.MCP_TOOL_NAMESPACE
REPO_ROOT = _yibu.REPO_ROOT
RESPONSES_NAMESPACE_PROXY_PATH = _yibu.RESPONSES_NAMESPACE_PROXY_PATH
SUPPORTED_SCENARIOS = _yibu.SUPPORTED_SCENARIOS
YIBU_ENV_KEY = _yibu.YIBU_ENV_KEY
YIBU_PROVIDER_ID = _yibu.YIBU_PROVIDER_ID
YibuCredentials = _yibu.YibuCredentials
build_player_env = _yibu.build_player_env
build_player_restart_prompt = _yibu.build_player_restart_prompt
build_provider_proxy_command = _yibu.build_provider_proxy_command
load_yibu_credentials = _yibu.load_yibu_credentials
resolve_scene = _yibu.resolve_scene
temporary_player_codex_home = _yibu.temporary_player_codex_home
validate_context_limits = _yibu.validate_context_limits
validate_yibu_model_argument = _yibu.validate_yibu_model_argument
write_player_codex_gemini_config = _yibu.write_player_codex_yibu_config


def parse_args(argv: Sequence[str]):
    return _yibu.parse_args(argv, default_model=DEFAULT_MODEL)


def main(argv: Sequence[str] | None = None) -> int:
    return _yibu.main(argv, default_model=DEFAULT_MODEL)


if __name__ == "__main__":
    raise SystemExit(main())
