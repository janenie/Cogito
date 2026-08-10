#!/usr/bin/env python3
"""Run Codex against Doubao through a private Responses compatibility proxy."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from typing import Any, Callable, Iterator, Mapping, Sequence
from urllib.parse import urlsplit

try:
    from . import ai_play_codex_orchestrator as _codex
    from .ai_play_doubao_responses_proxy import (
        DoubaoProxyServer,
        MAX_PROVIDER_OUTPUT_TOKENS,
        ProxySettings,
    )
except ImportError:
    import ai_play_codex_orchestrator as _codex
    from ai_play_doubao_responses_proxy import (
        DoubaoProxyServer,
        MAX_PROVIDER_OUTPUT_TOKENS,
        ProxySettings,
    )


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

DEFAULT_MODEL = "doubao-seed-2-1-pro-260628"
DEFAULT_CREDENTIALS = REPO_ROOT / ".claude" / "settings.local.json"
DEFAULT_MAX_OUTPUT_TOKENS = 8192
DEFAULT_CODEX_MAX_RESTARTS = 8
INTERNAL_PLAYER_FLAG = "--internal-doubao-player"
DOUBAO_UPSTREAM_KEY_ENV = "AI_PLAY_DOUBAO_UPSTREAM_KEY"
DOUBAO_UPSTREAM_URL_ENV = "AI_PLAY_DOUBAO_UPSTREAM_URL"
PROXY_KEY_ENV = "DOUBAO_PROXY_API_KEY"
PROXY_PROVIDER_ID = "doubao_proxy"


@dataclass(frozen=True)
class DoubaoCredentials:
    api_key: str
    base_url: str


def _normalize_yibu_base_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Doubao base URL must be a non-empty HTTPS URL")
    base_url = value.strip().rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme != "https":
        raise ValueError("Doubao base URL must use HTTPS")
    if not parsed.hostname:
        raise ValueError("Doubao base URL must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Doubao base URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("Doubao base URL must not contain query or fragment")
    if parsed.path in ("", "/"):
        return base_url + "/v1"
    if parsed.path.rstrip("/") != "/v1":
        raise ValueError("Doubao base URL path must be /v1 or empty")
    return base_url


def load_doubao_credentials(source: Path) -> DoubaoCredentials:
    path = source.expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing Doubao credential file: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError("Doubao credential file must contain valid JSON") from error
    except OSError as error:
        raise ValueError(f"could not read Doubao credential file: {path}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("env"), dict):
        raise ValueError("Doubao credential JSON must contain an env object")
    env = payload["env"]
    token = env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Doubao credential env must contain a non-empty token")
    return DoubaoCredentials(
        api_key=token.strip(),
        base_url=_normalize_yibu_base_url(env.get("ANTHROPIC_BASE_URL")),
    )


@contextmanager
def temporary_player_codex_home() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(
        prefix="cogito-ai-play-codex-doubao-"
    ) as raw_home:
        home = Path(raw_home)
        os.chmod(home, 0o700)
        yield home


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _validate_loopback_proxy_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname != DEFAULT_WS_HOST
        or parsed.port is None
        or parsed.path.rstrip("/") != "/v1"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("proxy base URL must be an HTTP numeric-loopback /v1 URL")
    return value.rstrip("/")


def write_player_codex_doubao_config(
    home: Path,
    *,
    model: str,
    proxy_base_url: str,
    mcp_url: str,
    workflow_memory_enabled: bool,
) -> Path:
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    player_home = _toml_string(str(home.resolve()))
    enabled_tools = (
        AWM_PLAYER_TOOL_NAMES if workflow_memory_enabled else BASE_PLAYER_TOOL_NAMES
    )
    config_path = home / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                f"model = {_toml_string(model)}",
                f'model_provider = "{PROXY_PROVIDER_ID}"',
                "model_supports_reasoning_summaries = false",
                "developer_instructions = "
                f"{_toml_string(_codex.build_player_developer_instructions())}",
                'approval_policy = "never"',
                "allow_login_shell = false",
                'web_search = "disabled"',
                'cli_auth_credentials_store = "file"',
                'mcp_oauth_credentials_store = "file"',
                "project_doc_max_bytes = 0",
                'default_permissions = "ai_play_player"',
                "",
                "[features]",
                "apps = false",
                "goals = false",
                "multi_agent = false",
                "plugins = false",
                "shell_tool = false",
                "tool_suggest = false",
                "unified_exec = false",
                "",
                "[tools]",
                "view_image = false",
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
                f"[model_providers.{PROXY_PROVIDER_ID}]",
                'name = "Doubao loopback proxy"',
                f"base_url = {_toml_string(_validate_loopback_proxy_url(proxy_base_url))}",
                f"env_key = {_toml_string(PROXY_KEY_ENV)}",
                'wire_api = "responses"',
                "",
                "[permissions.ai_play_player.filesystem]",
                '":minimal" = "read"',
                f"{player_home} = \"deny\"",
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
                f"url = {_toml_string(mcp_url)}",
                "required = true",
                "enabled_tools = "
                + json.dumps(list(enabled_tools), ensure_ascii=False),
                'default_tools_approval_mode = "approve"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    os.chmod(config_path, 0o600)
    return config_path


def build_wrapper_env(
    credentials: DoubaoCredentials,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = _codex.build_core_env(base_env)
    env[DOUBAO_UPSTREAM_KEY_ENV] = credentials.api_key
    env[DOUBAO_UPSTREAM_URL_ENV] = credentials.base_url
    return env


def build_codex_proxy_env(
    player_home: Path,
    proxy_token: str,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = _codex.build_player_env(player_home, base_env)
    env[PROXY_KEY_ENV] = proxy_token
    return env


def build_player_restart_prompt(runs: int, workflow_memory_enabled: bool) -> str:
    startup = (
        "workflow_memory_read、briefing、observe"
        if workflow_memory_enabled
        else "briefing、observe"
    )
    return (
        "这是同一可信 MCP/supervisor 会话中的恢复 turn。此前 Codex 提前退出，"
        "但不要假设新局已经开始或已有终局。先依次调用 %s 恢复公开状态；"
        "以 workflow memory 返回的 completed_runs 和 MCP 正式 game_over 为准，"
        "继续当前局或后续局，直到完成总计 %d 局。" % (startup, runs)
    )


def build_internal_player_command(
    *,
    python_bin: str,
    codex_bin: str,
    player_workspace: Path,
    model: str,
    mcp_url: str,
    max_output_tokens: int,
    workflow_memory_enabled: bool,
) -> list[str]:
    return [
        python_bin,
        str(Path(__file__).resolve()),
        INTERNAL_PLAYER_FLAG,
        "--codex-bin",
        codex_bin,
        "--player-workspace",
        str(player_workspace),
        "--model",
        model,
        "--mcp-url",
        mcp_url,
        "--max-output-tokens",
        str(max_output_tokens),
        "--workflow-memory",
        "enabled" if workflow_memory_enabled else "disabled",
    ]


def _parse_internal_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--codex-bin", required=True)
    parser.add_argument("--player-workspace", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--mcp-url", required=True)
    parser.add_argument("--max-output-tokens", type=int, required=True)
    parser.add_argument(
        "--workflow-memory",
        choices=("enabled", "disabled"),
        required=True,
    )
    return parser.parse_args(argv)


def run_internal_player(
    argv: Sequence[str],
    *,
    stdin_text: str | None = None,
    base_env: Mapping[str, str] | None = None,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    proxy_factory: Callable[..., Any] = DoubaoProxyServer,
    token_factory: Callable[[], str] | None = None,
) -> int:
    args = _parse_internal_args(argv)
    prompt = sys.stdin.read() if stdin_text is None else stdin_text
    if not prompt:
        raise ValueError("Codex player prompt must not be empty")
    source_env = os.environ if base_env is None else base_env
    upstream_token = source_env.get(DOUBAO_UPSTREAM_KEY_ENV)
    upstream_url = source_env.get(DOUBAO_UPSTREAM_URL_ENV)
    if not upstream_token or not upstream_url:
        raise ValueError("internal Doubao player is missing upstream credentials")
    validate_model_argument("--model", args.model)
    settings = ProxySettings(
        model=args.model,
        enabled_tools=(
            AWM_PLAYER_TOOL_NAMES
            if args.workflow_memory == "enabled"
            else BASE_PLAYER_TOOL_NAMES
        ),
        max_output_tokens=args.max_output_tokens,
    )
    proxy_token = (token_factory or (lambda: secrets.token_urlsafe(32)))()
    with proxy_factory(
        settings=settings,
        upstream_base_url=_normalize_yibu_base_url(upstream_url),
        upstream_token=upstream_token,
        proxy_token=proxy_token,
    ) as proxy:
        with temporary_player_codex_home() as player_home:
            write_player_codex_doubao_config(
                player_home,
                model=args.model,
                proxy_base_url=proxy.base_url,
                mcp_url=args.mcp_url,
                workflow_memory_enabled=args.workflow_memory == "enabled",
            )
            codex_env = build_codex_proxy_env(
                player_home,
                proxy_token,
                base_env=source_env,
            )
            command = _codex.build_codex_command(
                args.codex_bin,
                args.player_workspace,
            )
            process = popen_factory(
                command,
                cwd=args.player_workspace,
                env=codex_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            try:
                if process.stdin is None or process.stdout is None:
                    raise RuntimeError("Codex process pipes were not created")
                process.stdin.write(prompt)
                process.stdin.close()
                for line in process.stdout:
                    print(line, end="", flush=True)
                return int(process.wait())
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5.0)
                raise


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Codex with Doubao through a loopback Responses proxy.",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--scenario", default="find_contract")
    parser.add_argument("--session-root", type=Path, default=DEFAULT_SESSION_ROOT)
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--workflow-memory",
        choices=("enabled", "disabled"),
        default="enabled",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
    )
    parser.add_argument(
        "--codex-max-restarts",
        type=int,
        default=DEFAULT_CODEX_MAX_RESTARTS,
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
    if not 1 <= port <= 65535:
        raise SystemExit(f"{name} must be between 1 and 65535")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        validate_model_argument("--model", args.model)
        session_root = validate_isolated_session_root(args.session_root)
        scene = resolve_scene(args.scenario, args.scene)
        codex_bin = resolve_codex_bin(args.codex_bin)
        ProxySettings(
            model=args.model,
            enabled_tools=BASE_PLAYER_TOOL_NAMES,
            max_output_tokens=args.max_output_tokens,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be at least 0")
    if args.codex_max_restarts < 0:
        raise SystemExit("--codex-max-restarts must be at least 0")
    if not 0 <= args.benchmark_cycle_seed <= MAX_BENCHMARK_CYCLE_SEED:
        raise SystemExit(
            "--benchmark-cycle-seed must be between 0 and %d"
            % MAX_BENCHMARK_CYCLE_SEED
        )
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive")
    _validate_port("--mcp-port", args.mcp_port)
    if args.mcp_port == DEFAULT_WS_PORT:
        raise SystemExit("--mcp-port must differ from fixed bridge port 8765")
    for name in (
        "mcp_start_timeout_seconds",
        "codex_exit_grace_seconds",
        "idle_timeout_seconds",
        "codex_final_grace_seconds",
    ):
        if getattr(args, name) <= 0:
            raise SystemExit("--%s must be positive" % name.replace("_", "-"))
    try:
        credentials = load_doubao_credentials(args.credentials)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    for label, port in (
        ("AI Play bridge", DEFAULT_WS_PORT),
        ("MCP HTTP", args.mcp_port),
    ):
        if is_port_listening(DEFAULT_WS_HOST, port):
            raise SystemExit(
                f"{label} port {DEFAULT_WS_HOST}:{port} is already in use"
            )

    workflow_memory_enabled = args.workflow_memory == "enabled"
    paths = create_run_paths(
        session_root,
        player="codex-doubao",
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
                "player_restart_limit": args.codex_max_restarts,
                "max_output_tokens": args.max_output_tokens,
            },
        ),
    )
    mcp_url = f"http://{DEFAULT_WS_HOST}:{args.mcp_port}/mcp"
    return run_orchestrated_session(
        mcp_command=build_mcp_command(args.python_bin, args.mcp_port),
        player_label="codex-doubao",
        player_command=build_internal_player_command(
            python_bin=args.python_bin,
            codex_bin=codex_bin,
            player_workspace=paths.player_workspace,
            model=args.model,
            mcp_url=mcp_url,
            max_output_tokens=args.max_output_tokens,
            workflow_memory_enabled=workflow_memory_enabled,
        ),
        supervisor_command=build_supervisor_command(
            python_bin=args.python_bin,
            runs=args.runs,
            scenario=args.scenario,
            scene=scene,
            godot_bin=args.godot_bin,
            max_retries=args.max_retries,
            timeout_seconds=args.timeout_seconds,
            benchmark_cycle_seed=args.benchmark_cycle_seed,
        ),
        prompt=build_player_prompt(
            args.runs,
            workflow_memory_enabled=workflow_memory_enabled,
            scenario=args.scenario,
        ),
        mcp_env=build_trusted_mcp_env(paths.log_root, DEFAULT_WS_PORT),
        player_env=build_wrapper_env(credentials),
        supervisor_env=build_supervisor_env(paths.run_dir / "godot_environment"),
        mcp_cwd=REPO_ROOT,
        player_cwd=paths.player_workspace,
        supervisor_cwd=REPO_ROOT,
        ws_port=DEFAULT_WS_PORT,
        mcp_port=args.mcp_port,
        mcp_start_timeout_seconds=args.mcp_start_timeout_seconds,
        player_exit_grace_seconds=args.codex_exit_grace_seconds,
        idle_timeout_seconds=args.idle_timeout_seconds,
        player_final_grace_seconds=args.codex_final_grace_seconds,
        player_restart_limit=args.codex_max_restarts,
        player_restart_prompt=build_player_restart_prompt(
            args.runs,
            workflow_memory_enabled,
        ),
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == INTERNAL_PLAYER_FLAG:
        try:
            raise SystemExit(run_internal_player(sys.argv[2:]))
        except ValueError as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(2)
    raise SystemExit(main())
