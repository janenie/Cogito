#!/usr/bin/env python3
"""Run a hardened, black-box Codex player beside trusted AI Play services."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping, Sequence

try:
    from . import ai_play_orchestrator_common as _common
except ImportError:
    import ai_play_orchestrator_common as _common

try:
    from .ai_play_scene_registry import (
        DEFAULT_SCENE,
        SUPPORTED_SCENARIOS,
        resolve_scene,
    )
except ImportError:
    from ai_play_scene_registry import (
        DEFAULT_SCENE,
        SUPPORTED_SCENARIOS,
        resolve_scene,
    )


AWM_PLAYER_TOOL_NAMES = _common.AWM_PLAYER_TOOL_NAMES
BASE_PLAYER_TOOL_NAMES = _common.BASE_PLAYER_TOOL_NAMES
DEFAULT_MCP_PORT = _common.DEFAULT_MCP_PORT
DEFAULT_SESSION_ROOT = _common.DEFAULT_SESSION_ROOT
DEFAULT_WS_HOST = _common.DEFAULT_WS_HOST
DEFAULT_WS_PORT = _common.DEFAULT_WS_PORT
REPO_ROOT = _common.REPO_ROOT
build_core_env = _common.build_core_env
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

DEFAULT_CODEX_AUTH_HOME = Path("~/.codex-cogito-player")
AUTH_FILE_NAME = "auth.json"


def validate_codex_auth_home(auth_home: Path) -> Path:
    home = auth_home.expanduser()
    source = home / AUTH_FILE_NAME
    if not source.is_file():
        raise ValueError(f"missing Codex credential file: {source}")
    return home


@contextmanager
def temporary_player_codex_home(auth_home: Path) -> Iterator[Path]:
    source_home = validate_codex_auth_home(auth_home)
    source = source_home / AUTH_FILE_NAME
    with tempfile.TemporaryDirectory(prefix="cogito-ai-play-codex-") as raw_home:
        player_home = Path(raw_home)
        shutil.copyfile(source, player_home / AUTH_FILE_NAME)
        yield player_home


def _toml_basic_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_player_codex_config(
    home: Path,
    model: str,
    reasoning_effort: str,
    mcp_url: str,
    workflow_memory_enabled: bool = True,
) -> Path:
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    player_home_path = _toml_basic_string(str(home.resolve()))
    config_path = home / "config.toml"
    filesystem_rules = [
        '":minimal" = "read"',
        f"{player_home_path} = \"deny\"",
    ]
    config_path.write_text(
        "\n".join(
            [
                f"model = {_toml_basic_string(model)}",
                "model_reasoning_effort = "
                f"{_toml_basic_string(reasoning_effort)}",
                "developer_instructions = "
                f"{_toml_basic_string(build_player_developer_instructions())}",
                'approval_policy = "never"',
                "allow_login_shell = false",
                'web_search = "disabled"',
                'cli_auth_credentials_store = "file"',
                'mcp_oauth_credentials_store = "file"',
                "project_doc_max_bytes = 0",
                'default_permissions = "ai_play_player"',
                "",
                "[windows]",
                'sandbox = "elevated"',
                "",
                "[agents]",
                "enabled = false",
                "",
                "[memories]",
                "generate_memories = false",
                "use_memories = false",
                "",
                "[shell_environment_policy]",
                'inherit = "none"',
                "",
                "[permissions.ai_play_player.filesystem]",
                *filesystem_rules,
                "",
                '[permissions.ai_play_player.filesystem.":workspace_roots"]',
                '"." = "read"',
                "",
                "[permissions.ai_play_player.network]",
                "enabled = true",
                "",
                "[permissions.ai_play_player.network.domains]",
                '"127.0.0.1" = "allow"',
                "",
                "[mcp_servers.cogito_ai_play]",
                f"url = {_toml_basic_string(mcp_url)}",
                "required = true",
                "enabled_tools = "
                + json.dumps(
                    list(
                        AWM_PLAYER_TOOL_NAMES
                        if workflow_memory_enabled
                        else BASE_PLAYER_TOOL_NAMES
                    ),
                    ensure_ascii=False,
                ),
                'default_tools_approval_mode = "approve"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def build_player_env(
    player_home: Path,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = build_isolated_process_env(player_home, base_env)
    env.update(
        {
            "CODEX_HOME": str(player_home.resolve()),
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        }
    )
    return env


def resolve_codex_bin(codex_bin: str) -> str:
    candidate = Path(codex_bin).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    resolved = shutil.which(codex_bin)
    if resolved is None:
        raise ValueError(f"could not locate Codex executable: {codex_bin}")
    return resolved


def build_codex_command(
    codex_bin: str,
    player_workspace: Path,
) -> list[str]:
    return [
        codex_bin,
        "exec",
        "--cd",
        str(player_workspace),
        "--skip-git-repo-check",
        "--ephemeral",
        "-",
    ]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a hardened black-box Codex player with the Godot supervisor.",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--scenario", default="find_contract")
    parser.add_argument("--session-root", type=Path, default=DEFAULT_SESSION_ROOT)
    parser.add_argument(
        "--codex-auth-home",
        type=Path,
        default=DEFAULT_CODEX_AUTH_HOME,
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning-effort", required=True)
    parser.add_argument(
        "--workflow-memory",
        choices=("enabled", "disabled"),
        default="enabled",
    )
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--godot-bin", default="godot")
    parser.add_argument("--scene")
    parser.add_argument("--mcp-port", type=int, default=DEFAULT_MCP_PORT)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=100000.0)
    parser.add_argument("--mcp-start-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--codex-exit-grace-seconds", type=float, default=5.0)
    parser.add_argument("--idle-timeout-seconds", type=float, default=600.0)
    parser.add_argument("--codex-final-grace-seconds", type=float, default=30.0)
    return parser.parse_args(argv)


def _validate_port(name: str, port: int) -> None:
    if port < 1 or port > 65535:
        raise SystemExit(f"{name} must be between 1 and 65535")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        validate_model_argument("--model", args.model)
        validate_model_argument("--reasoning-effort", args.reasoning_effort)
        session_root = validate_isolated_session_root(args.session_root)
        scene = resolve_scene(args.scenario, args.scene)
        codex_bin = resolve_codex_bin(args.codex_bin)
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
    if args.codex_exit_grace_seconds <= 0:
        raise SystemExit("--codex-exit-grace-seconds must be positive")
    if args.idle_timeout_seconds <= 0:
        raise SystemExit("--idle-timeout-seconds must be positive")
    if args.codex_final_grace_seconds <= 0:
        raise SystemExit("--codex-final-grace-seconds must be positive")
    try:
        auth_home = validate_codex_auth_home(args.codex_auth_home)
    except ValueError as error:
        raise SystemExit(str(error)) from error
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

    workflow_memory_enabled = args.workflow_memory == "enabled"
    paths = create_run_paths(
        session_root,
        player="codex",
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        scenario=args.scenario,
        workflow_memory_enabled=workflow_memory_enabled,
        requested_runs=args.runs,
    )
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
    with temporary_player_codex_home(auth_home) as player_home:
        write_player_codex_config(
            player_home,
            args.model,
            args.reasoning_effort,
            f"http://{DEFAULT_WS_HOST}:{args.mcp_port}/mcp",
            workflow_memory_enabled=workflow_memory_enabled,
        )
        return run_orchestrated_session(
            mcp_command=mcp_command,
            player_label="codex",
            player_command=build_codex_command(
                codex_bin,
                paths.player_workspace,
            ),
            supervisor_command=supervisor_command,
            prompt=build_player_prompt(
                args.runs,
                workflow_memory_enabled=workflow_memory_enabled,
                scenario=args.scenario,
            ),
            mcp_env=mcp_env,
            player_env=build_player_env(player_home),
            supervisor_env=supervisor_env,
            mcp_cwd=REPO_ROOT,
            player_cwd=paths.player_workspace,
            supervisor_cwd=REPO_ROOT,
            ws_port=DEFAULT_WS_PORT,
            mcp_port=args.mcp_port,
            mcp_start_timeout_seconds=args.mcp_start_timeout_seconds,
            player_exit_grace_seconds=args.codex_exit_grace_seconds,
            idle_timeout_seconds=args.idle_timeout_seconds,
            player_final_grace_seconds=args.codex_final_grace_seconds,
        )


if __name__ == "__main__":
    raise SystemExit(main())
