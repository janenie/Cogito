#!/usr/bin/env python3
"""Run a hardened, black-box Claude Code player with AI First Play."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping, Sequence

try:
    from . import ai_play_orchestrator_common as _common
except ImportError:
    import ai_play_orchestrator_common as _common

try:
    from .ai_play_scene_registry import resolve_scene
except ImportError:
    from ai_play_scene_registry import resolve_scene


REPO_ROOT = _common.REPO_ROOT
AWM_PLAYER_TOOL_NAMES = _common.AWM_PLAYER_TOOL_NAMES
BASE_PLAYER_TOOL_NAMES = _common.BASE_PLAYER_TOOL_NAMES
DEFAULT_MCP_PORT = _common.DEFAULT_MCP_PORT
DEFAULT_SESSION_ROOT = _common.DEFAULT_SESSION_ROOT
DEFAULT_WS_HOST = _common.DEFAULT_WS_HOST
DEFAULT_WS_PORT = _common.DEFAULT_WS_PORT
build_isolated_process_env = _common.build_isolated_process_env
build_mcp_command = _common.build_mcp_command
build_player_developer_instructions = _common.build_player_developer_instructions
build_player_prompt = _common.build_player_prompt
build_supervisor_command = _common.build_supervisor_command
build_supervisor_env = _common.build_supervisor_env
build_trusted_mcp_env = _common.build_trusted_mcp_env
create_run_paths = _common.create_run_paths
is_port_listening = _common.is_port_listening
run_orchestrated_session = _common.run_orchestrated_session
validate_isolated_session_root = _common.validate_isolated_session_root
validate_model_argument = _common.validate_model_argument
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


def claude_mcp_tool_names(
    workflow_memory_enabled: bool,
) -> tuple[str, ...]:
    tools = (
        AWM_PLAYER_TOOL_NAMES
        if workflow_memory_enabled
        else BASE_PLAYER_TOOL_NAMES
    )
    return tuple(f"mcp__cogito_ai_play__{name}" for name in tools)


def resolve_claude_bin(claude_bin: str) -> str:
    candidate = Path(claude_bin).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    resolved = shutil.which(claude_bin)
    if resolved is None:
        raise ValueError(f"could not locate Claude executable: {claude_bin}")
    return resolved


def build_claude_command(
    claude_bin: str,
    config: ClaudePlayerConfig,
    model: str,
    effort: str,
    workflow_memory_enabled: bool = True,
) -> list[str]:
    return [
        claude_bin,
        "--bare",
        "--print",
        "--no-session-persistence",
        "--strict-mcp-config",
        "--settings",
        str(config.settings_path),
        "--mcp-config",
        str(config.mcp_path),
        "--tools",
        "",
        "--allowed-tools",
        ",".join(claude_mcp_tool_names(workflow_memory_enabled)),
        "--permission-mode",
        "dontAsk",
        "--model",
        model,
        "--effort",
        effort,
        "--system-prompt",
        build_player_developer_instructions(),
    ]


def build_claude_player_env(
    player_root: Path,
    provider_env: Mapping[str, str],
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = build_isolated_process_env(player_root, base_env)
    env.update(provider_env)
    env.update(
        {
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        }
    )
    return env


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a hardened black-box Claude player with the Godot supervisor.",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--scenario", default="find_contract")
    parser.add_argument("--session-root", type=Path, default=DEFAULT_SESSION_ROOT)
    parser.add_argument(
        "--claude-settings",
        type=Path,
        default=DEFAULT_CLAUDE_SETTINGS,
    )
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--effort",
        required=True,
        choices=("low", "medium", "high", "xhigh", "max"),
    )
    parser.add_argument(
        "--workflow-memory",
        choices=("enabled", "disabled"),
        default="enabled",
    )
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--godot-bin", default="godot")
    parser.add_argument("--scene")
    parser.add_argument("--mcp-port", type=int, default=DEFAULT_MCP_PORT)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=100000.0)
    parser.add_argument("--mcp-start-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--claude-exit-grace-seconds", type=float, default=5.0)
    parser.add_argument("--idle-timeout-seconds", type=float, default=600.0)
    parser.add_argument("--claude-final-grace-seconds", type=float, default=30.0)
    return parser.parse_args(argv)


def _validate_port(name: str, port: int) -> None:
    if port < 1 or port > 65535:
        raise SystemExit(f"{name} must be between 1 and 65535")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        validate_model_argument("--model", args.model)
        session_root = validate_isolated_session_root(args.session_root)
        scene = resolve_scene(args.scenario, args.scene)
        provider_env = load_claude_provider_env(args.claude_settings)
        claude_bin = resolve_claude_bin(args.claude_bin)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be at least 0")
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive")
    _validate_port("--mcp-port", args.mcp_port)
    if DEFAULT_WS_PORT == args.mcp_port:
        raise SystemExit(
            "--mcp-port must differ from fixed bridge port %s" % DEFAULT_WS_PORT
        )
    if args.mcp_start_timeout_seconds <= 0:
        raise SystemExit("--mcp-start-timeout-seconds must be positive")
    if args.claude_exit_grace_seconds <= 0:
        raise SystemExit("--claude-exit-grace-seconds must be positive")
    if args.idle_timeout_seconds <= 0:
        raise SystemExit("--idle-timeout-seconds must be positive")
    if args.claude_final_grace_seconds <= 0:
        raise SystemExit("--claude-final-grace-seconds must be positive")

    for label, port in (
        ("AI Play bridge", DEFAULT_WS_PORT),
        ("MCP HTTP", args.mcp_port),
    ):
        if is_port_listening(DEFAULT_WS_HOST, port):
            raise SystemExit(
                "%s port %s:%s is already in use; stop the existing process "
                "first or choose a different port."
                % (label, DEFAULT_WS_HOST, port)
            )

    paths = create_run_paths(session_root)
    mcp_env = build_trusted_mcp_env(paths.log_root, DEFAULT_WS_PORT)
    supervisor_env = build_supervisor_env(paths.run_dir / "godot_environment")
    mcp_command = build_mcp_command(args.python_bin, args.mcp_port)
    supervisor_command = build_supervisor_command(
        python_bin=args.python_bin,
        runs=args.runs,
        scenario=args.scenario,
        scene=scene,
        godot_bin=args.godot_bin,
        max_retries=args.max_retries,
        timeout_seconds=args.timeout_seconds,
    )
    print("[orchestrator] run_dir=%s" % paths.run_dir, flush=True)
    print("[orchestrator] trusted_log_root=%s" % paths.log_root, flush=True)
    print(
        "[orchestrator] AI_PLAY_WS=%s:%s"
        % (DEFAULT_WS_HOST, DEFAULT_WS_PORT),
        flush=True,
    )
    print(
        "[orchestrator] MCP_HTTP=%s:%s"
        % (DEFAULT_WS_HOST, args.mcp_port),
        flush=True,
    )

    workflow_memory_enabled = args.workflow_memory == "enabled"
    mcp_url = f"http://{DEFAULT_WS_HOST}:{args.mcp_port}/mcp"
    with temporary_claude_player_config(provider_env, mcp_url) as config:
        return run_orchestrated_session(
            mcp_command=mcp_command,
            player_label="claude",
            player_command=build_claude_command(
                claude_bin,
                config,
                model=args.model,
                effort=args.effort,
                workflow_memory_enabled=workflow_memory_enabled,
            ),
            supervisor_command=supervisor_command,
            prompt=build_player_prompt(
                args.runs,
                workflow_memory_enabled=workflow_memory_enabled,
                scenario=args.scenario,
            ),
            mcp_env=mcp_env,
            player_env=build_claude_player_env(config.root, provider_env),
            supervisor_env=supervisor_env,
            mcp_cwd=REPO_ROOT,
            player_cwd=paths.player_workspace,
            supervisor_cwd=REPO_ROOT,
            ws_port=DEFAULT_WS_PORT,
            mcp_port=args.mcp_port,
            mcp_start_timeout_seconds=args.mcp_start_timeout_seconds,
            player_exit_grace_seconds=args.claude_exit_grace_seconds,
            idle_timeout_seconds=args.idle_timeout_seconds,
            player_final_grace_seconds=args.claude_final_grace_seconds,
        )


if __name__ == "__main__":
    raise SystemExit(main())
