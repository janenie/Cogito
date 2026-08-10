#!/usr/bin/env python3
"""Run a hardened Codex player with a yibu Gemini Responses provider."""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from urllib.parse import urlsplit

try:
    from . import ai_play_codex_orchestrator as _codex
except ImportError:
    import ai_play_codex_orchestrator as _codex


AWM_PLAYER_TOOL_NAMES = _codex.AWM_PLAYER_TOOL_NAMES
BASE_PLAYER_TOOL_NAMES = _codex.BASE_PLAYER_TOOL_NAMES
DEFAULT_BENCHMARK_CYCLE_SEED = _codex.DEFAULT_BENCHMARK_CYCLE_SEED
DEFAULT_MCP_PORT = _codex.DEFAULT_MCP_PORT
DEFAULT_SCENE = _codex.DEFAULT_SCENE
DEFAULT_SESSION_ROOT = _codex.DEFAULT_SESSION_ROOT
DEFAULT_WS_HOST = _codex.DEFAULT_WS_HOST
DEFAULT_WS_PORT = _codex.DEFAULT_WS_PORT
MAX_BENCHMARK_CYCLE_SEED = _codex.MAX_BENCHMARK_CYCLE_SEED
REPO_ROOT = _codex.REPO_ROOT
SUPPORTED_SCENARIOS = _codex.SUPPORTED_SCENARIOS
build_codex_command = _codex.build_codex_command
build_mcp_command = _codex.build_mcp_command
build_player_prompt = _codex.build_player_prompt
build_supervisor_command = _codex.build_supervisor_command
build_supervisor_env = _codex.build_supervisor_env
build_trusted_mcp_env = _codex.build_trusted_mcp_env
collect_runtime_metadata = _codex.collect_runtime_metadata
create_run_paths = _codex.create_run_paths
is_port_listening = _codex.is_port_listening
resolve_codex_bin = _codex.resolve_codex_bin
resolve_scene = _codex.resolve_scene
run_orchestrated_session = _codex.run_orchestrated_session
validate_isolated_session_root = _codex.validate_isolated_session_root
validate_model_argument = _codex.validate_model_argument
DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_YIBU_CREDENTIALS = REPO_ROOT / "opus.py"
YIBU_ENV_KEY = "YIBU_API_KEY"
YIBU_PROVIDER_ID = "yibu"


@dataclass(frozen=True)
class YibuCredentials:
    api_key: str
    base_url: str


def _find_literal_ak_assignment(tree: ast.Module) -> dict[str, Any]:
    for node in tree.body:
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "ak"
            for target in node.targets
        ):
            value = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "ak"
        ):
            value = node.value
        if value is None:
            continue
        try:
            payload = ast.literal_eval(value)
        except (ValueError, TypeError, SyntaxError) as error:
            raise ValueError(
                "yibu credential file must contain a literal ak dictionary"
            ) from error
        if not isinstance(payload, dict):
            raise ValueError(
                "yibu credential file must contain a literal ak dictionary"
            )
        return payload
    raise ValueError(
        "yibu credential file must contain a literal ak dictionary"
    )


def _normalize_yibu_base_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("yibu credential URL must be a non-empty string")
    base_url = value.strip().rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme != "https":
        raise ValueError("yibu credential URL must use https")
    if not parsed.hostname:
        raise ValueError("yibu credential URL must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("yibu credential URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("yibu credential URL must not contain query or fragment")
    if parsed.path in ("", "/"):
        return base_url + "/v1"
    if parsed.path.rstrip("/") != "/v1":
        raise ValueError("yibu credential URL path must be /v1 or empty")
    return base_url


def load_yibu_credentials(source: Path) -> YibuCredentials:
    credential_path = source.expanduser()
    try:
        text = credential_path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ValueError(
            f"missing yibu credential file: {credential_path}"
        ) from error
    except OSError as error:
        raise ValueError(
            f"could not read yibu credential file: {credential_path}"
        ) from error
    try:
        tree = ast.parse(text, filename=str(credential_path))
    except SyntaxError as error:
        raise ValueError("invalid yibu credential Python syntax") from error
    payload = _find_literal_ak_assignment(tree)
    api_key = payload.get("key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("yibu credential key must be a non-empty string")
    return YibuCredentials(
        api_key=api_key.strip(),
        base_url=_normalize_yibu_base_url(payload.get("url")),
    )


@contextmanager
def temporary_player_codex_home() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(
        prefix="cogito-ai-play-codex-gemini-"
    ) as raw_home:
        player_home = Path(raw_home)
        os.chmod(player_home, 0o700)
        yield player_home


def _toml_basic_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_player_codex_gemini_config(
    home: Path,
    model: str,
    base_url: str,
    mcp_url: str,
    workflow_memory_enabled: bool = True,
) -> Path:
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    player_home_path = _toml_basic_string(str(home.resolve()))
    filesystem_rules = [
        '":minimal" = "read"',
        f'{player_home_path} = "deny"',
    ]
    config_path = home / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                f"model = {_toml_basic_string(model)}",
                f'model_provider = "{YIBU_PROVIDER_ID}"',
                "model_supports_reasoning_summaries = false",
                "developer_instructions = "
                f"{_toml_basic_string(_codex.build_player_developer_instructions())}",
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
                f"[model_providers.{YIBU_PROVIDER_ID}]",
                'name = "Yibu API"',
                f"base_url = {_toml_basic_string(_normalize_yibu_base_url(base_url))}",
                f"env_key = {_toml_basic_string(YIBU_ENV_KEY)}",
                'wire_api = "responses"',
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
    os.chmod(config_path, 0o600)
    return config_path


def build_player_env(
    player_home: Path,
    api_key: str,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = _codex.build_player_env(player_home, base_env)
    env[YIBU_ENV_KEY] = api_key
    return env


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a hardened black-box Codex player with a yibu Gemini "
            "Responses provider and the Godot supervisor."
        ),
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--scenario", default="find_contract")
    parser.add_argument("--session-root", type=Path, default=DEFAULT_SESSION_ROOT)
    parser.add_argument(
        "--yibu-credentials",
        type=Path,
        default=DEFAULT_YIBU_CREDENTIALS,
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
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
    parser.add_argument(
        "--benchmark-cycle-seed",
        type=int,
        default=DEFAULT_BENCHMARK_CYCLE_SEED,
    )
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
        session_root = validate_isolated_session_root(args.session_root)
        scene = resolve_scene(args.scenario, args.scene)
        codex_bin = resolve_codex_bin(args.codex_bin)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be at least 0")
    if not 0 <= args.benchmark_cycle_seed <= MAX_BENCHMARK_CYCLE_SEED:
        raise SystemExit(
            "--benchmark-cycle-seed must be between 0 and %d"
            % MAX_BENCHMARK_CYCLE_SEED
        )
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
        credentials = load_yibu_credentials(args.yibu_credentials)
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
        reasoning_effort="none",
        scenario=args.scenario,
        workflow_memory_enabled=workflow_memory_enabled,
        requested_runs=args.runs,
        benchmark_cycle_seed=args.benchmark_cycle_seed,
        runtime_metadata=collect_runtime_metadata(
            python_bin=args.python_bin,
            player_bin=codex_bin,
            godot_bin=args.godot_bin,
            execution={
                "ws_port": DEFAULT_WS_PORT,
                "mcp_port": args.mcp_port,
                "max_retries": args.max_retries,
                "attempt_timeout_seconds": args.timeout_seconds,
                "mcp_start_timeout_seconds": args.mcp_start_timeout_seconds,
                "player_exit_grace_seconds": args.codex_exit_grace_seconds,
                "idle_timeout_seconds": args.idle_timeout_seconds,
                "player_final_grace_seconds": args.codex_final_grace_seconds,
                "player_restart_limit": 0,
            },
        ),
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
        benchmark_cycle_seed=args.benchmark_cycle_seed,
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
    with temporary_player_codex_home() as player_home:
        write_player_codex_gemini_config(
            player_home,
            args.model,
            credentials.base_url,
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
            player_env=build_player_env(player_home, credentials.api_key),
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
