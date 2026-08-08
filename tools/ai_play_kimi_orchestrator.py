#!/usr/bin/env python3
"""Run a hardened, black-box Kimi Code player with AI First Play."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import tomllib
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

DEFAULT_KIMI_HOME = REPO_ROOT / ".kimi-code"
INTERNAL_PLAYER_FLAG = "--internal-kimi-player"
SAFE_KIMI_CONFIG_KEYS = frozenset(
    {
        "default_model",
        "identity",
        "loop_control",
        "mcp",
        "models",
        "providers",
        "thinking",
        "token_counting",
    }
)


@dataclass(frozen=True)
class KimiPlayerConfig:
    root: Path
    config_path: Path
    mcp_path: Path
    agent_path: Path


def validate_kimi_home(kimi_home: Path) -> Path:
    home = kimi_home.expanduser().resolve()
    config_path = home / "config.toml"
    try:
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing Kimi config file: {config_path}") from error
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"invalid Kimi config file: {config_path}") from error
    if not isinstance(payload, dict):
        raise ValueError("Kimi config root must be a TOML table")

    unsafe_keys = sorted(set(payload) - SAFE_KIMI_CONFIG_KEYS)
    if unsafe_keys:
        raise ValueError(
            "Kimi config contains unsupported or executable sections: %s"
            % ", ".join(unsafe_keys)
        )
    providers = payload.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise ValueError("Kimi config must contain at least one provider")
    for provider_name, provider in providers.items():
        if not isinstance(provider_name, str) or not provider_name:
            raise ValueError("Kimi provider names must be non-empty strings")
        if not isinstance(provider, dict):
            raise ValueError(
                f"Kimi provider {provider_name} must be a TOML table"
            )
        provider_type = provider.get("type")
        if not isinstance(provider_type, str) or not provider_type:
            raise ValueError(
                f"Kimi provider {provider_name} must define a non-empty type"
            )
        base_url = provider.get("base_url")
        if base_url is not None and (
            not isinstance(base_url, str)
            or not base_url.startswith("https://")
        ):
            raise ValueError(
                f"Kimi provider {provider_name} base_url must use https"
            )
        api_key = provider.get("api_key")
        if not isinstance(api_key, str) or not api_key:
            raise ValueError(
                f"Kimi provider {provider_name} must define a non-empty api_key"
            )
    return home


def _write_private_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def _write_private_json(path: Path, payload: Mapping[str, object]) -> None:
    _write_private_text(
        path,
        json.dumps(payload, ensure_ascii=False),
    )


def kimi_mcp_tool_names(
    workflow_memory_enabled: bool,
) -> tuple[str, ...]:
    tools = (
        AWM_PLAYER_TOOL_NAMES
        if workflow_memory_enabled
        else BASE_PLAYER_TOOL_NAMES
    )
    return tuple(f"mcp__cogito_ai_play__{name}" for name in tools)


def build_kimi_agent_file(workflow_memory_enabled: bool) -> str:
    tools = kimi_mcp_tool_names(workflow_memory_enabled)
    tool_lines = "\n".join(f"  - {name}" for name in tools)
    return (
        "---\n"
        "name: cogito-ai-play\n"
        "description: Isolated black-box Cogito game player\n"
        "tools:\n"
        f"{tool_lines}\n"
        "subagents: []\n"
        "---\n\n"
        f"{build_player_developer_instructions()}\n"
    )


def build_kimi_permission_rules(workflow_memory_enabled: bool) -> str:
    tools = kimi_mcp_tool_names(workflow_memory_enabled)
    rules = []
    for name in tools:
        rules.extend(
            (
                "[[permission.rules]]",
                'decision = "allow"',
                f'pattern = "{name}"',
                "",
            )
        )
    return "\n".join(rules)


@contextmanager
def temporary_kimi_player_config(
    source_home: Path,
    mcp_url: str,
    workflow_memory_enabled: bool = True,
) -> Iterator[KimiPlayerConfig]:
    validated_home = validate_kimi_home(source_home)
    with tempfile.TemporaryDirectory(
        prefix="cogito-ai-play-kimi-"
    ) as raw_root:
        root = Path(raw_root)
        os.chmod(root, 0o700)
        config_path = root / "config.toml"
        mcp_path = root / "mcp.json"
        agent_path = root / "cogito-ai-play-agent.md"
        shutil.copyfile(validated_home / "config.toml", config_path)
        with config_path.open("a", encoding="utf-8") as config_file:
            config_file.write("\n\n")
            config_file.write(
                build_kimi_permission_rules(workflow_memory_enabled)
            )
        os.chmod(config_path, 0o600)
        _write_private_json(
            mcp_path,
            {
                "mcpServers": {
                    "cogito_ai_play": {
                        "url": mcp_url,
                        "enabledTools": list(
                            AWM_PLAYER_TOOL_NAMES
                            if workflow_memory_enabled
                            else BASE_PLAYER_TOOL_NAMES
                        ),
                    }
                }
            },
        )
        _write_private_text(
            agent_path,
            build_kimi_agent_file(workflow_memory_enabled),
        )
        yield KimiPlayerConfig(
            root=root,
            config_path=config_path,
            mcp_path=mcp_path,
            agent_path=agent_path,
        )


def resolve_kimi_bin(kimi_bin: str) -> str:
    candidate = Path(kimi_bin).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    resolved = shutil.which(kimi_bin)
    if resolved is None:
        raise ValueError(f"could not locate Kimi executable: {kimi_bin}")
    return resolved


def build_kimi_cli_command(
    kimi_bin: str,
    agent_path: Path,
    model: str,
    prompt: str,
) -> list[str]:
    return [
        kimi_bin,
        "--model",
        model,
        "--agent-file",
        str(agent_path),
        "--output-format",
        "text",
        "--prompt",
        prompt,
    ]


def build_kimi_runner_command(
    python_bin: str,
    kimi_bin: str,
    agent_path: Path,
    model: str,
) -> list[str]:
    return [
        python_bin,
        str(Path(__file__).resolve()),
        INTERNAL_PLAYER_FLAG,
        "--kimi-bin",
        kimi_bin,
        "--agent-file",
        str(agent_path),
        "--model",
        model,
    ]


def build_kimi_player_env(
    player_root: Path,
    effort: str,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = build_isolated_process_env(player_root, base_env)
    env.update(
        {
            "KIMI_CODE_HOME": str(player_root.resolve()),
            "KIMI_DISABLE_CRON": "1",
            "KIMI_MODEL_THINKING_EFFORT": effort,
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        }
    )
    return env


def build_player_restart_prompt(
    runs: int,
    workflow_memory_enabled: bool,
    scenario: str,
) -> str:
    del scenario
    startup = (
        "workflow_memory_read、briefing、observe"
        if workflow_memory_enabled
        else "briefing、observe"
    )
    return (
        "这是同一 MCP 与 AWM 会话中的恢复 turn；此前 Kimi turn 提前结束，但可信 "
        "supervisor 尚未完成。不要假设新的一局已经开始，也不要把 observation_id 当作 "
        "act 请求计数或已完成局数。先依次调用 %s 恢复公开状态，然后继续当前局或后续局。"
        "本会话总目标仍是完成 %s 个正式终局；只有工具返回正式 game_over 才计算一局，"
        "完成全部局数前不要输出最终回答。" % (startup, runs)
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a hardened black-box Kimi player with the Godot supervisor.",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--scenario", default="find_contract")
    parser.add_argument("--session-root", type=Path, default=DEFAULT_SESSION_ROOT)
    parser.add_argument("--kimi-home", type=Path, default=DEFAULT_KIMI_HOME)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--effort",
        required=True,
        choices=("low", "high", "max"),
    )
    parser.add_argument(
        "--workflow-memory",
        choices=("enabled", "disabled"),
        default="enabled",
    )
    parser.add_argument("--kimi-bin", default="kimi")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--godot-bin", default="godot")
    parser.add_argument("--scene")
    parser.add_argument("--mcp-port", type=int, default=DEFAULT_MCP_PORT)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=100000.0)
    parser.add_argument("--mcp-start-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--kimi-exit-grace-seconds", type=float, default=5.0)
    parser.add_argument("--idle-timeout-seconds", type=float, default=600.0)
    parser.add_argument("--kimi-final-grace-seconds", type=float, default=30.0)
    parser.add_argument("--kimi-max-restarts", type=int, default=8)
    return parser.parse_args(argv)


def _parse_internal_player_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--kimi-bin", required=True)
    parser.add_argument("--agent-file", type=Path, required=True)
    parser.add_argument("--model", required=True)
    return parser.parse_args(argv)


def _run_internal_player(argv: Sequence[str]) -> int:
    args = _parse_internal_player_args(argv)
    prompt = sys.stdin.read()
    if not prompt:
        print("Kimi player prompt must not be empty", file=sys.stderr)
        return 2
    command = build_kimi_cli_command(
        args.kimi_bin,
        args.agent_file,
        args.model,
        prompt,
    )
    os.execve(args.kimi_bin, command, dict(os.environ))
    return 127


def _validate_port(name: str, port: int) -> None:
    if port < 1 or port > 65535:
        raise SystemExit(f"{name} must be between 1 and 65535")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        validate_model_argument("--model", args.model)
        session_root = validate_isolated_session_root(args.session_root)
        scene = resolve_scene(args.scenario, args.scene)
        kimi_home = validate_kimi_home(args.kimi_home)
        kimi_bin = resolve_kimi_bin(args.kimi_bin)
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
    if args.kimi_exit_grace_seconds <= 0:
        raise SystemExit("--kimi-exit-grace-seconds must be positive")
    if args.idle_timeout_seconds <= 0:
        raise SystemExit("--idle-timeout-seconds must be positive")
    if args.kimi_final_grace_seconds <= 0:
        raise SystemExit("--kimi-final-grace-seconds must be positive")
    if args.kimi_max_restarts < 0:
        raise SystemExit("--kimi-max-restarts must be at least 0")

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
        player="kimi",
        model=args.model,
        reasoning_effort=args.effort,
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

    mcp_url = f"http://{DEFAULT_WS_HOST}:{args.mcp_port}/mcp"
    with temporary_kimi_player_config(
        kimi_home,
        mcp_url,
        workflow_memory_enabled=workflow_memory_enabled,
    ) as config:
        return run_orchestrated_session(
            mcp_command=mcp_command,
            player_label="kimi",
            player_command=build_kimi_runner_command(
                args.python_bin,
                kimi_bin,
                config.agent_path,
                args.model,
            ),
            supervisor_command=supervisor_command,
            prompt=build_player_prompt(
                args.runs,
                workflow_memory_enabled=workflow_memory_enabled,
                scenario=args.scenario,
            ),
            mcp_env=mcp_env,
            player_env=build_kimi_player_env(config.root, args.effort),
            supervisor_env=supervisor_env,
            mcp_cwd=REPO_ROOT,
            player_cwd=paths.player_workspace,
            supervisor_cwd=REPO_ROOT,
            ws_port=DEFAULT_WS_PORT,
            mcp_port=args.mcp_port,
            mcp_start_timeout_seconds=args.mcp_start_timeout_seconds,
            player_exit_grace_seconds=args.kimi_exit_grace_seconds,
            idle_timeout_seconds=args.idle_timeout_seconds,
            player_final_grace_seconds=args.kimi_final_grace_seconds,
            player_restart_limit=args.kimi_max_restarts,
            player_restart_prompt=build_player_restart_prompt(
                args.runs,
                workflow_memory_enabled=workflow_memory_enabled,
                scenario=args.scenario,
            ),
        )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == INTERNAL_PLAYER_FLAG:
        raise SystemExit(_run_internal_player(sys.argv[2:]))
    raise SystemExit(main())
