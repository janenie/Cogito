#!/usr/bin/env python3
"""Run a hardened Codex player with a generic Yibu Responses provider."""

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
build_supervisor_command = _codex.build_supervisor_command
build_supervisor_env = _codex.build_supervisor_env
build_trusted_mcp_env = _codex.build_trusted_mcp_env
collect_runtime_metadata = _codex.collect_runtime_metadata
create_run_paths = _codex.create_run_paths
is_port_listening = _codex.is_port_listening
resume_run_paths = _codex.resume_run_paths
resolve_codex_bin = _codex.resolve_codex_bin
resolve_scene = _codex.resolve_scene
run_orchestrated_session = _codex.run_orchestrated_session
validate_isolated_session_root = _codex.validate_isolated_session_root
validate_model_argument = _codex.validate_model_argument
DEFAULT_CODEX_MAX_RESTARTS: int | None = None
DEFAULT_YIBU_CREDENTIALS = REPO_ROOT / "opus.py"
DEFAULT_PROVIDER_PROXY_PORT = 18767
RESPONSES_NAMESPACE_PROXY_PATH = (
    REPO_ROOT / "tools" / "ai_play_responses_namespace_proxy.py"
)
YIBU_ENV_KEY = "YIBU_API_KEY"
YIBU_PROVIDER_ID = "yibu"
MCP_TOOL_NAMESPACE = "mcp__cogito_ai_play"
DEFAULT_CONTEXT_WINDOW = 128_000
DEFAULT_AUTO_COMPACT_TOKEN_LIMIT = 90_000
MAX_CONTEXT_WINDOW = 10_000_000
MAX_MODEL_ID_BYTES = 256
WORKFLOW_MEMORY_FILENAME = "workflow_memory.json"
IMAGE_CONTEXT_LIMIT = 10
IMAGE_CONTEXT_PROMPT = f"""
图片上下文纪律（本次请求内最高优先级）：
1. 当前 Codex turn 最多主动参考最近 {IMAGE_CONTEXT_LIMIT} 张与当前任务相关的图片；RGB 和深度图分别按一张图片计数。
2. 收到新图片后，为每张新图片写一条简短 caption，只保留与当前目标、地标、交互提示、距离和方向有关的公开视觉事实。
3. 超过 {IMAGE_CONTEXT_LIMIT} 张后，停止引用、比较或重新分析更旧图片；更旧图片只使用此前生成的 caption。
4. 其他要求比较本会话历史截图的规则，仅适用于最近 {IMAGE_CONTEXT_LIMIT} 张相关图片；优先使用 act 返回的最新观察，不要为刷新画面重复调用 observe。
5. 这是模型行为约束，不是传输层保证。如果 Codex runtime 仍随历史传输了更旧图片，忽略它们并继续游戏，不要报错或停止。
""".strip()


@dataclass(frozen=True)
class YibuCredentials:
    api_key: str
    base_url: str


def _append_image_context_prompt(prompt: str) -> str:
    return f"{prompt}\n\n{IMAGE_CONTEXT_PROMPT}"


def build_player_prompt(
    runs: int,
    workflow_memory_enabled: bool = True,
    scenario: str = "",
    approved_image_read: bool = False,
    rotate_after_terminal: bool = False,
) -> str:
    return _append_image_context_prompt(
        _codex.build_player_prompt(
            runs,
            workflow_memory_enabled=workflow_memory_enabled,
            scenario=scenario,
            approved_image_read=approved_image_read,
            rotate_after_terminal=rotate_after_terminal,
        )
    )


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


def _normalize_loopback_provider_base_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("loopback provider URL must be a non-empty string")
    base_url = value.strip().rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or parsed.hostname != DEFAULT_WS_HOST:
        raise ValueError("loopback provider URL must use http://127.0.0.1")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("loopback provider URL must not contain credentials")
    if parsed.port is None:
        raise ValueError("loopback provider URL must include a port")
    if parsed.query or parsed.fragment or parsed.path.rstrip("/") != "/v1":
        raise ValueError("loopback provider URL path must be /v1 without query")
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
        prefix="cogito-ai-play-codex-yibu-"
    ) as raw_home:
        player_home = Path(raw_home)
        os.chmod(player_home, 0o700)
        yield player_home


def _toml_basic_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def validate_context_limits(
    context_window: int,
    auto_compact_limit: int,
) -> None:
    if not 1 <= context_window <= MAX_CONTEXT_WINDOW:
        raise ValueError("--context-window must be between 1 and 10000000")
    if not 1 <= auto_compact_limit < context_window:
        raise ValueError(
            "--auto-compact-token-limit must be positive and smaller than "
            "--context-window"
        )


def validate_yibu_model_argument(model: str) -> str:
    validate_model_argument("--model", model)
    if len(model.encode("utf-8")) > MAX_MODEL_ID_BYTES:
        raise ValueError("--model must not exceed 256 UTF-8 bytes")
    return model


def load_resume_progress(
    run_dir: Path,
    *,
    model: str,
    scenario: str,
    workflow_memory_enabled: bool,
    requested_runs: int,
    benchmark_cycle_seed: int,
    context_window: int,
    auto_compact_token_limit: int,
) -> int:
    artifact_dir = run_dir.expanduser().resolve()
    metadata = _read_json_object(
        artifact_dir / "session.json",
        "resume session metadata",
    )
    expected_memory = "enabled" if workflow_memory_enabled else "disabled"
    for key, expected, label in (
        ("player", "codex", "player"),
        ("model", model, "model"),
        ("reasoning_effort", "none", "reasoning effort"),
        ("scenario", scenario, "scenario"),
        ("workflow_memory", expected_memory, "workflow memory mode"),
        ("requested_runs", requested_runs, "requested runs"),
    ):
        if metadata.get(key) != expected:
            raise ValueError(f"resume {label} mismatch")
    benchmark = metadata.get("benchmark")
    if (
        not isinstance(benchmark, dict)
        or benchmark.get("cycle_seed") != benchmark_cycle_seed
    ):
        raise ValueError("resume benchmark cycle seed mismatch")
    execution = metadata.get("execution")
    if not isinstance(execution, dict):
        raise ValueError("resume execution metadata is missing")
    if execution.get("model_context_window") != context_window:
        raise ValueError("resume context window mismatch")
    if (
        execution.get("model_auto_compact_token_limit")
        != auto_compact_token_limit
    ):
        raise ValueError("resume auto-compact limit mismatch")

    checkpoint_path = (
        artifact_dir / "trusted_mcplogs" / WORKFLOW_MEMORY_FILENAME
    )
    if not checkpoint_path.exists():
        return 0
    checkpoint = _read_json_object(
        checkpoint_path,
        "workflow memory checkpoint",
    )
    if checkpoint.get("schema_version") != 1:
        raise ValueError("unsupported workflow memory checkpoint")
    if checkpoint.get("scenario_id") != scenario:
        raise ValueError("resume checkpoint scenario mismatch")
    completed = checkpoint.get("completed")
    if not isinstance(completed, list):
        raise ValueError("invalid workflow memory checkpoint")
    completed_runs = 0
    for index, attempt in enumerate(completed, 1):
        if (
            not isinstance(attempt, dict)
            or attempt.get("number") != index
            or attempt.get("scenario_id") != scenario
            or attempt.get("status")
            not in {"success", "failure", "stopped", "disconnected", "shutdown"}
        ):
            raise ValueError("invalid workflow memory checkpoint")
        completed_runs += attempt["status"] in {"success", "failure"}
    if completed_runs > requested_runs:
        raise ValueError("resume progress exceeds requested runs")
    if completed_runs == requested_runs:
        raise ValueError("resume run is already complete")
    return completed_runs


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing {label}: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"invalid {label}")
    return payload


def _single_model_catalog(model: str, context_window: int) -> dict[str, Any]:
    # Adapted from the catalog shape documented in third_party/cc-switch/SOURCE.md.
    return {
        "models": [
            {
                "slug": model,
                "display_name": model,
                "description": "Yibu Responses model for Cogito AI Play",
                "base_instructions": "Use only the approved Cogito AI Play tools.",
                "supported_reasoning_levels": [],
                "shell_type": "shell_command",
                "visibility": "list",
                "supported_in_api": True,
                "priority": 0,
                "supports_reasoning_summaries": False,
                "support_verbosity": False,
                "truncation_policy": {"mode": "bytes", "limit": 10000},
                "supports_parallel_tool_calls": False,
                "supports_image_detail_original": False,
                "context_window": context_window,
                "max_context_window": context_window,
                "effective_context_window_percent": 95,
                "experimental_supported_tools": [],
                "input_modalities": ["text", "image"],
                "supports_search_tool": False,
            }
        ]
    }


def write_player_codex_yibu_config(
    home: Path,
    model: str,
    base_url: str,
    mcp_url: str,
    workflow_memory_enabled: bool = True,
    context_window: int = DEFAULT_CONTEXT_WINDOW,
    auto_compact_token_limit: int = DEFAULT_AUTO_COMPACT_TOKEN_LIMIT,
) -> Path:
    validate_yibu_model_argument(model)
    validate_context_limits(context_window, auto_compact_token_limit)
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(home, 0o700)
    catalog_path = home / "model-catalog.json"
    catalog_path.write_text(
        json.dumps(
            _single_model_catalog(model, context_window),
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    os.chmod(catalog_path, 0o600)
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
                f"model_catalog_json = {_toml_basic_string(str(catalog_path.resolve()))}",
                f"model_context_window = {context_window}",
                "model_auto_compact_token_limit = "
                f"{auto_compact_token_limit}",
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
                f"[model_providers.{YIBU_PROVIDER_ID}]",
                'name = "Yibu API"',
                "base_url = "
                f"{_toml_basic_string(_normalize_loopback_provider_base_url(base_url))}",
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


def build_provider_proxy_env(
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    return _codex.build_core_env(base_env)


def build_provider_proxy_command(
    *,
    python_bin: str,
    port: int,
    upstream_base_url: str,
    workflow_memory_enabled: bool,
    diagnostics_jsonl: Path,
) -> list[str]:
    command = [
        python_bin,
        str(RESPONSES_NAMESPACE_PROXY_PATH),
        "--host",
        DEFAULT_WS_HOST,
        "--port",
        str(port),
        "--upstream-base-url",
        _normalize_yibu_base_url(upstream_base_url),
        "--namespace",
        MCP_TOOL_NAMESPACE,
    ]
    tool_names = (
        AWM_PLAYER_TOOL_NAMES
        if workflow_memory_enabled
        else BASE_PLAYER_TOOL_NAMES
    )
    for tool_name in tool_names:
        command.extend(("--allowed-tool", tool_name))
    command.extend(("--diagnostics-jsonl", str(diagnostics_jsonl)))
    return command


def build_player_restart_prompt(
    runs: int,
    workflow_memory_enabled: bool,
) -> str:
    startup = (
        "workflow_memory_read、briefing、observe"
        if workflow_memory_enabled
        else "briefing、observe"
    )
    progress = (
        "以 workflow_memory_read 返回的 completed_runs 判断已完成局数，然后"
        if workflow_memory_enabled
        else "不要自行推断已完成局数，"
    )
    handoff = (
        "正式终局后先调用 workflow_memory_update；成功返回后输出简短最终回答并结束当前 Codex turn。"
        if workflow_memory_enabled
        else "正式终局后输出简短最终回答并结束当前 Codex turn。"
    )
    prompt = (
        "这是同一 MCP 与 AWM 会话中的恢复 turn；此前 Codex turn 提前正常结束，"
        "但可信 supervisor 尚未完成。不要假设新的一局已经开始，也不要把 "
        "observation_id 当作 act 请求计数或已完成局数。先依次调用 %s 恢复公开状态，"
        "%s继续当前局。当前 Codex turn 只负责下一个正式终局；只有工具返回正式 "
        "game_over 才计算一局，在此之前不要输出最终回答。%s完整会话总目标仍是由可信 "
        "supervisor 完成 %s 个正式终局。" % (startup, progress, handoff, runs)
    )
    return _append_image_context_prompt(prompt)


def parse_args(
    argv: Sequence[str],
    *,
    default_model: str | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a hardened black-box Codex player with a generic Yibu "
            "Responses provider and the Godot supervisor."
        ),
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--scenario", default="find_contract")
    parser.add_argument("--session-root", type=Path, default=DEFAULT_SESSION_ROOT)
    persistence = parser.add_mutually_exclusive_group()
    persistence.add_argument("--artifact-root", type=Path)
    persistence.add_argument("--resume-run", type=Path)
    parser.add_argument(
        "--yibu-credentials",
        type=Path,
        default=DEFAULT_YIBU_CREDENTIALS,
    )
    parser.add_argument(
        "--model",
        required=default_model is None,
        default=default_model,
    )
    parser.add_argument(
        "--context-window",
        type=int,
        default=DEFAULT_CONTEXT_WINDOW,
    )
    parser.add_argument(
        "--auto-compact-token-limit",
        type=int,
        default=DEFAULT_AUTO_COMPACT_TOKEN_LIMIT,
    )
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
    parser.add_argument(
        "--provider-proxy-port",
        type=int,
        default=DEFAULT_PROVIDER_PROXY_PORT,
    )
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument(
        "--codex-max-restarts",
        type=int,
        default=DEFAULT_CODEX_MAX_RESTARTS,
    )
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


def main(
    argv: Sequence[str] | None = None,
    *,
    default_model: str | None = None,
) -> int:
    args = parse_args(
        sys.argv[1:] if argv is None else argv,
        default_model=default_model,
    )
    try:
        validate_yibu_model_argument(args.model)
        validate_context_limits(
            args.context_window,
            args.auto_compact_token_limit,
        )
        session_root = validate_isolated_session_root(args.session_root)
        scene = resolve_scene(args.scenario, args.scene)
        codex_bin = resolve_codex_bin(args.codex_bin)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be at least 0")
    if (
        args.codex_max_restarts is not None
        and args.codex_max_restarts < 0
    ):
        raise SystemExit("--codex-max-restarts must be at least 0")
    if not 0 <= args.benchmark_cycle_seed <= MAX_BENCHMARK_CYCLE_SEED:
        raise SystemExit(
            "--benchmark-cycle-seed must be between 0 and %d"
            % MAX_BENCHMARK_CYCLE_SEED
        )
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive")
    _validate_port("--mcp-port", args.mcp_port)
    _validate_port("--provider-proxy-port", args.provider_proxy_port)
    if DEFAULT_WS_PORT == args.mcp_port:
        raise SystemExit(
            "--mcp-port must differ from fixed bridge port %s" % DEFAULT_WS_PORT
        )
    if args.provider_proxy_port in (DEFAULT_WS_PORT, args.mcp_port):
        raise SystemExit(
            "--provider-proxy-port must differ from bridge and MCP ports"
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
        ("provider proxy", args.provider_proxy_port),
    ):
        if is_port_listening(DEFAULT_WS_HOST, port):
            raise SystemExit(
                "%s port %s:%s is already in use; stop the existing process "
                "first or choose a different port."
                % (label, DEFAULT_WS_HOST, port)
            )

    workflow_memory_enabled = args.workflow_memory == "enabled"
    runtime_metadata = collect_runtime_metadata(
        python_bin=args.python_bin,
        player_bin=codex_bin,
        godot_bin=args.godot_bin,
        execution={
            "ws_port": DEFAULT_WS_PORT,
            "mcp_port": args.mcp_port,
            "provider_proxy_port": args.provider_proxy_port,
            "max_retries": args.max_retries,
            "attempt_timeout_seconds": args.timeout_seconds,
            "mcp_start_timeout_seconds": args.mcp_start_timeout_seconds,
            "player_exit_grace_seconds": args.codex_exit_grace_seconds,
            "idle_timeout_seconds": args.idle_timeout_seconds,
            "player_final_grace_seconds": args.codex_final_grace_seconds,
            "player_restart_limit": args.codex_max_restarts,
            "model_context_window": args.context_window,
            "model_auto_compact_token_limit": args.auto_compact_token_limit,
        },
    )
    try:
        if args.resume_run is None:
            paths = create_run_paths(
                session_root,
                artifact_root=args.artifact_root,
                player="codex",
                model=args.model,
                reasoning_effort="none",
                scenario=args.scenario,
                workflow_memory_enabled=workflow_memory_enabled,
                requested_runs=args.runs,
                benchmark_cycle_seed=args.benchmark_cycle_seed,
                runtime_metadata=runtime_metadata,
            )
            completed_runs = 0
        else:
            paths = resume_run_paths(session_root, args.resume_run)
            completed_runs = load_resume_progress(
                paths.run_dir,
                model=args.model,
                scenario=args.scenario,
                workflow_memory_enabled=workflow_memory_enabled,
                requested_runs=args.runs,
                benchmark_cycle_seed=args.benchmark_cycle_seed,
                context_window=args.context_window,
                auto_compact_token_limit=args.auto_compact_token_limit,
            )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    remaining_runs = args.runs - completed_runs
    workflow_memory_path = paths.log_root / WORKFLOW_MEMORY_FILENAME
    mcp_env = build_trusted_mcp_env(
        paths.log_root,
        DEFAULT_WS_PORT,
        workflow_memory_path=workflow_memory_path,
    )
    supervisor_env = build_supervisor_env(
        paths.runtime_dir / "godot_environment"
    )
    mcp_command = build_mcp_command(
        args.python_bin,
        args.mcp_port,
        codex_media_output=True,
    )
    provider_proxy_command = build_provider_proxy_command(
        python_bin=args.python_bin,
        port=args.provider_proxy_port,
        upstream_base_url=credentials.base_url,
        workflow_memory_enabled=workflow_memory_enabled,
        diagnostics_jsonl=paths.log_root / "provider_requests.jsonl",
    )
    supervisor_command = build_supervisor_command(
        python_bin=args.python_bin,
        runs=remaining_runs,
        scenario=args.scenario,
        scene=scene,
        godot_bin=args.godot_bin,
        max_retries=args.max_retries,
        timeout_seconds=args.timeout_seconds,
        benchmark_cycle_seed=args.benchmark_cycle_seed,
        attempt_offset=completed_runs,
    )
    print("[orchestrator] run_dir=%s" % paths.run_dir, flush=True)
    print("[orchestrator] runtime_dir=%s" % paths.runtime_dir, flush=True)
    print("[orchestrator] trusted_log_root=%s" % paths.log_root, flush=True)
    print(
        "[orchestrator] progress=%s/%s remaining=%s"
        % (completed_runs, args.runs, remaining_runs),
        flush=True,
    )
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
        write_player_codex_yibu_config(
            player_home,
            args.model,
            "http://%s:%s/v1"
            % (DEFAULT_WS_HOST, args.provider_proxy_port),
            f"http://{DEFAULT_WS_HOST}:{args.mcp_port}/mcp",
            workflow_memory_enabled=workflow_memory_enabled,
            context_window=args.context_window,
            auto_compact_token_limit=args.auto_compact_token_limit,
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
                rotate_after_terminal=True,
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
            player_restart_limit=args.codex_max_restarts,
            player_restart_prompt=build_player_restart_prompt(
                args.runs,
                workflow_memory_enabled=workflow_memory_enabled,
            ),
            provider_proxy_command=provider_proxy_command,
            provider_proxy_env=build_provider_proxy_env(),
            provider_proxy_cwd=REPO_ROOT,
            provider_proxy_port=args.provider_proxy_port,
        )


if __name__ == "__main__":
    raise SystemExit(main())
