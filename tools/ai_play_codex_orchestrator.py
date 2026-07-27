#!/usr/bin/env python3
"""Run a hardened, black-box Codex player beside trusted AI Play services."""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SESSION_ROOT = (
    Path(REPO_ROOT.anchor) / "cogito_ai_player_runs"
    if os.name == "nt"
    else Path("/tmp/cogito_ai_player_runs")
)
DEFAULT_CODEX_AUTH_HOME = Path("~/.codex-cogito-player")
DEFAULT_SCENE = "addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
DEFAULT_WS_HOST = "127.0.0.1"
DEFAULT_WS_PORT = 8765
DEFAULT_MCP_PORT = 8766
AUTH_FILE_NAME = "auth.json"
PLAYER_TOOL_NAMES = ("briefing", "observe", "act", "stop")
CORE_ENV_NAMES = ("PATH", "PATHEXT", "SystemRoot", "WINDIR", "ComSpec")
PUBLIC_MCP_LOG_ROOT = Path("~/workspace/cogito_logs/mcplogs").expanduser()


@dataclass(frozen=True)
class RunPaths:
    run_dir: Path
    player_workspace: Path
    log_root: Path
    run_config: Path


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def validate_isolated_session_root(session_root: Path) -> Path:
    root = session_root.expanduser().resolve()
    if _is_relative_to(root, REPO_ROOT):
        raise ValueError(
            "session root must be isolated from the current repository"
        )
    for ancestor in (root, *root.parents):
        if (
            (ancestor / ".git").exists()
            or (ancestor / "AGENTS.md").is_file()
            or (ancestor / ".codex" / "config.toml").is_file()
        ):
            raise ValueError(
                "session root must be isolated from repository and project "
                "instructions"
            )
    return root


def create_run_paths(
    session_root: Path,
    timestamp: str | None = None,
) -> RunPaths:
    root = validate_isolated_session_root(session_root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = timestamp or datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    for index in range(1, 1000):
        suffix = "" if index == 1 else "-%02d" % index
        run_dir = root / f"{stamp}{suffix}"
        try:
            run_dir.mkdir(mode=0o700)
            break
        except FileExistsError:
            continue
    else:
        raise RuntimeError("could not allocate a fresh AI Play run directory")

    player_workspace = run_dir / "player_workspace"
    log_root = run_dir / "trusted_mcplogs"
    player_workspace.mkdir(mode=0o700)
    log_root.mkdir(mode=0o700)
    return RunPaths(
        run_dir=run_dir,
        player_workspace=player_workspace,
        log_root=log_root,
        run_config=player_workspace / "ai_play_run_config.json",
    )


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


def validate_model_argument(name: str, value: str) -> str:
    if not value or any(
        character.isspace()
        or unicodedata.category(character).startswith("C")
        for character in value
    ):
        raise ValueError(
            f"{name} must not be empty or contain whitespace or control characters"
        )
    return value


def _toml_basic_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_player_codex_config(
    home: Path,
    model: str,
    reasoning_effort: str,
    mcp_url: str,
    readable_log_roots: Sequence[Path] = (),
) -> Path:
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    player_home_path = _toml_basic_string(str(home.resolve()))
    config_path = home / "config.toml"
    filesystem_rules = [
        '":minimal" = "read"',
        f"{player_home_path} = \"deny\"",
    ]
    for log_root in readable_log_roots:
        filesystem_rules.append(
            f"{_toml_basic_string(str(log_root.expanduser().resolve()))} = \"read\""
        )
    config_path.write_text(
        "\n".join(
            [
                f"model = {_toml_basic_string(model)}",
                "model_reasoning_effort = "
                f"{_toml_basic_string(reasoning_effort)}",
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
                "enabled = false",
                "",
                "[mcp_servers.cogito_ai_play]",
                f"url = {_toml_basic_string(mcp_url)}",
                "required = true",
                "enabled_tools = "
                + json.dumps(list(PLAYER_TOOL_NAMES), ensure_ascii=False),
                'default_tools_approval_mode = "approve"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def write_player_run_config(paths: RunPaths, runs: int, scenario: str) -> Path:
    payload = {
        "scenario": scenario,
        "runs": runs,
        "ai_play_log_root": str(paths.log_root),
        "public_mcp_log_root": str(PUBLIC_MCP_LOG_ROOT),
        "public_latest_log_pattern": str(
            PUBLIC_MCP_LOG_ROOT / scenario / "<latest_time>"
        ),
    }
    paths.run_config.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return paths.run_config


def build_core_env(
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = os.environ if base_env is None else base_env
    env: dict[str, str] = {}
    for name in CORE_ENV_NAMES:
        value = source.get(name)
        if value is None:
            value = next(
                (
                    candidate
                    for candidate_name, candidate in source.items()
                    if candidate_name.casefold() == name.casefold()
                ),
                None,
            )
        if value is not None:
            env[name] = value
    return env


def build_player_env(
    player_home: Path,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    home = player_home.resolve()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    home_dir = home / "home"
    appdata_dir = home / "appdata"
    localappdata_dir = home / "localappdata"
    temp_dir = home / "tmp"
    for directory in (home_dir, appdata_dir, localappdata_dir, temp_dir):
        directory.mkdir(mode=0o700, exist_ok=True)
    env = build_core_env(base_env)
    env.update(
        {
            "CODEX_HOME": str(home),
            "HOME": str(home_dir),
            "USERPROFILE": str(home_dir),
            "APPDATA": str(appdata_dir),
            "LOCALAPPDATA": str(localappdata_dir),
            "TEMP": str(temp_dir),
            "TMP": str(temp_dir),
        }
    )
    return env


def build_trusted_mcp_env(
    log_root: Path,
    ws_port: int,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = build_core_env(base_env)
    env.update(
        {
            "AI_PLAY_LOG_ROOT": str(log_root),
            "AI_PLAY_WS_HOST": DEFAULT_WS_HOST,
            "AI_PLAY_WS_PORT": str(ws_port),
            "PYTHONPATH": str(REPO_ROOT / "ai_play" / "src"),
        }
    )
    return env


def build_supervisor_env(
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    return build_core_env(base_env)


def build_mcp_command(python_bin: str, mcp_port: int) -> list[str]:
    return [
        python_bin,
        "-m",
        "ai_play.mcp_server",
        "--transport",
        "streamable-http",
        "--http-host",
        DEFAULT_WS_HOST,
        "--http-port",
        str(mcp_port),
    ]


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


def build_supervisor_command(
    python_bin: str,
    runs: int,
    scenario: str,
    scene: str,
    godot_bin: str,
    max_retries: int,
    timeout_seconds: float,
) -> list[str]:
    return [
        python_bin,
        str(REPO_ROOT / "tools" / "ai_play_supervisor.py"),
        "--runs",
        str(runs),
        "--scenario",
        scenario,
        "--scene",
        scene,
        "--godot-bin",
        godot_bin,
        "--max-retries",
        str(max_retries),
        "--timeout-seconds",
        str(timeout_seconds),
    ]


def build_player_prompt(runs: int, scenario: str, run_config: Path) -> str:
    return f"""
你是 Cogito AI First Play 的隔离黑盒玩家。

本会话需要完成 {runs} 次独立游玩。每局开始时，先调用 briefing，再调用 observe。

严格限制：
1. 只使用 cogito_ai_play 的 briefing、observe、act、stop 工具。
2. 只能依据 briefing、observe 截图、公开结构化状态、可见交互提示和 act 返回结果决策。
3. 不要使用搜索、浏览器、GitHub 或任何其他工具获取游戏信息。
4. 不得请求或使用场景源码、节点路径、隐藏状态、谜题答案、测试、规格、开发者笔记或仓库文件信息。
5. 密码证据不足时继续探索，不能盲猜。
6. 每次 act 必须使用最新 observation_id；每批 1 到 3 个动作；每次 act 后重新观察和规划。
7. 收到 success、failure、stopped 或 disconnected 后，停止本局动作；下一局可用时重新从 briefing 开始。
8. 在完成全部 {runs} 次独立游玩前，不要输出最终回答，也不要结束会话。
9. 若当前工具结果是 stopped 或 disconnected，但还没有完成全部 {runs} 次，继续调用 observe
   等待下一局；observe 仍返回 stopped/disconnected 时等待后再 observe，直到出现新的可玩观察。

像人一样玩：
1. 不要把游戏当 API 猜参数。先看清画面、HUD、标牌、物体和可见提示，再小步移动或转身。
2. 在花园里避免贴着边界和围栏走，优先沿路面、广场和房屋正面移动；迷路时停下、环顾、回到中央广场。
3. 靠近目标时使用短距离 move，不要长时间 sprint；转向后重新 observe，确认准星没有偏离目标。
4. 只有当前 observation 的 interface.available_interactions 中出现对应 action 时，才执行 interact。
   交互动作格式必须精确写成 {{"type":"interact","action":"interact"}} 或
   {{"type":"interact","action":"interact2"}}，不要把提示文字、物体名或绑定键写进 action。
5. 如果没有交互提示但画面中疑似有水壶、草坪或门铃，先靠近并单独调用 probe_interaction；
   probe_interaction 必须是单动作批次。
6. 如果一次 act failed，说明动作没有通过校验；立即 observe，改变站位、准星或动作类型。
   不要连续重试同一种 act，也不要在没有新 observation 时继续提交交互。
7. 每局把自己当成第一次进场的人类玩家：先建立中央广场、水壶、向日葵房、绣球花房和兰花房
   的相对方位，再执行任务。不要为了省步数盲冲边界或在未确认标牌时浇水/按铃。

经验总结：
1. 可以边思考边玩，在自己的上下文中记录简短经验，例如安全路线、房屋相对方位、边界位置、
   哪些动作会导致越界或 act failed。
2. 只允许使用 shell/文件读取本启动目录的 `{run_config.name}`，以及该配置列出的
   ai_play_log_root、public_mcp_log_root/{scenario}/<latest_time> 日志目录；不要读取
   任何其他路径。
3. 可以读取本次 ai_play_log_root 下的所有日志内容来总结经验，包括 JPEG 截图、
   trajectory.json、run.json 和公开 MCP 结构化结果。
4. 本次运行配置同时包含 public_mcp_log_root 和 public_latest_log_pattern。每局开始后，
   读取 public_mcp_log_root 下 `{scenario}` 子目录里最新创建的时间戳目录，例如
   `{PUBLIC_MCP_LOG_ROOT / scenario}/20260727-01-36`，把里面的 trajectory.json、
   run.json 和 imgs/*.jpg 当作本局公开观察记忆。
5. 不要读取仓库源码、测试、spec、game_script、code_read、其他项目文件、其他运行目录或凭据；
   只把本次运行日志当作自己游玩过程的记忆，不要从仓库文件推断隐藏状态。

本次运行配置写在你的启动目录 `{run_config.name}`，其中包含 AI_PLAY_LOG_ROOT、
public_mcp_log_root 和 public_latest_log_pattern。先读这个配置；如果 AI_PLAY_LOG_ROOT
为空，立刻按 public_mcp_log_root/{scenario}/<latest_time> 选择最新目录读取日志和图片。

游戏目标、规则和物体操作说明只由 briefing 提供。现在开始第 1 局。
""".strip()


def run_orchestrated_session(
    mcp_command: Sequence[str],
    codex_command: Sequence[str],
    supervisor_command: Sequence[str],
    prompt: str,
    mcp_env: Mapping[str, str],
    codex_env: Mapping[str, str],
    supervisor_env: Mapping[str, str],
    mcp_cwd: Path,
    codex_cwd: Path,
    supervisor_cwd: Path,
    ws_port: int,
    mcp_port: int,
    mcp_start_timeout_seconds: float,
    codex_exit_grace_seconds: float,
) -> int:
    outputs: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mcp = None
    codex = None
    supervisor = None
    try:
        mcp = _start_process("mcp", mcp_command, mcp_cwd, mcp_env)
        _start_output_reader("mcp", mcp, outputs)
        if not wait_for_listener(
            mcp,
            DEFAULT_WS_HOST,
            mcp_port,
            mcp_start_timeout_seconds,
            outputs,
        ):
            print(
                "[orchestrator] trusted MCP sidecar did not listen on %s:%s "
                "within %.1fs"
                % (DEFAULT_WS_HOST, mcp_port, mcp_start_timeout_seconds),
                flush=True,
            )
            return 4
        if not wait_for_listener(
            mcp,
            DEFAULT_WS_HOST,
            ws_port,
            mcp_start_timeout_seconds,
            outputs,
        ):
            print(
                "[orchestrator] AI Play bridge did not listen on %s:%s within %.1fs"
                % (DEFAULT_WS_HOST, ws_port, mcp_start_timeout_seconds),
                flush=True,
            )
            return 4

        codex = _start_process(
            "codex",
            codex_command,
            codex_cwd,
            codex_env,
            stdin_text=prompt,
        )
        _start_output_reader("codex", codex, outputs)
        codex_code = codex.poll()
        if codex_code is not None:
            return 3 if codex_code == 0 else codex_code

        supervisor = _start_process(
            "supervisor",
            supervisor_command,
            supervisor_cwd,
            supervisor_env,
        )
        _start_output_reader("supervisor", supervisor, outputs)

        while True:
            _print_available_output(outputs)
            mcp_code = mcp.poll()
            supervisor_code = supervisor.poll()
            codex_code = codex.poll()
            if mcp_code is not None:
                return 4 if mcp_code == 0 else mcp_code
            if supervisor_code is not None:
                return supervisor_code
            if codex_code is not None:
                deadline = time.monotonic() + codex_exit_grace_seconds
                while time.monotonic() < deadline:
                    _print_available_output(outputs)
                    mcp_code = mcp.poll()
                    supervisor_code = supervisor.poll()
                    if mcp_code is not None:
                        return 4 if mcp_code == 0 else mcp_code
                    if supervisor_code is not None:
                        return supervisor_code
                    time.sleep(0.05)
                return 3 if codex_code == 0 else codex_code
            time.sleep(0.05)
    finally:
        for process in (supervisor, codex, mcp):
            if process is not None:
                _terminate_process(process)
        _print_available_output(outputs)


def _start_output_reader(
    label: str,
    process: subprocess.Popen[str],
    outputs: queue.Queue[tuple[str, str | None]],
) -> None:
    threading.Thread(
        target=_read_labeled_output,
        args=(label, process, outputs),
        daemon=True,
    ).start()


def wait_for_listener(
    process: subprocess.Popen[str],
    host: str,
    port: int,
    timeout_seconds: float,
    outputs: queue.Queue[tuple[str, str | None]],
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        _print_available_output(outputs)
        if process.poll() is not None:
            _print_available_output(outputs)
            return False
        if is_port_listening(host, port):
            return True
        time.sleep(0.05)
    _print_available_output(outputs)
    return False


def _start_process(
    label: str,
    command: Sequence[str],
    cwd: Path,
    env: Mapping[str, str],
    stdin_text: str | None = None,
) -> subprocess.Popen[str]:
    print("[%s] starting: %s" % (label, " ".join(command)), flush=True)
    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        env=dict(env),
        stdin=subprocess.PIPE if stdin_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if stdin_text is not None:
        assert process.stdin is not None
        process.stdin.write(stdin_text)
        process.stdin.close()
    return process


def _read_labeled_output(
    label: str,
    process: subprocess.Popen[str],
    outputs: queue.Queue[tuple[str, str | None]],
) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        outputs.put((label, line))
    outputs.put((label, None))


def _print_available_output(outputs: queue.Queue[tuple[str, str | None]]) -> None:
    while True:
        try:
            label, line = outputs.get_nowait()
        except queue.Empty:
            return
        if line is not None:
            print("[%s] %s" % (label, line), end="", flush=True)


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5.0)


def is_port_listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


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
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--godot-bin", default="godot")
    parser.add_argument("--scene", default=DEFAULT_SCENE)
    parser.add_argument("--mcp-port", type=int, default=DEFAULT_MCP_PORT)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=1200.0)
    parser.add_argument("--mcp-start-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--codex-exit-grace-seconds", type=float, default=5.0)
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

    paths = create_run_paths(session_root)
    write_player_run_config(paths, args.runs, args.scenario)
    mcp_env = build_trusted_mcp_env(paths.log_root, DEFAULT_WS_PORT)
    supervisor_env = build_supervisor_env()
    mcp_command = build_mcp_command(args.python_bin, args.mcp_port)
    supervisor_command = build_supervisor_command(
        python_bin=args.python_bin,
        runs=args.runs,
        scenario=args.scenario,
        scene=args.scene,
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
            readable_log_roots=(
                paths.log_root,
                PUBLIC_MCP_LOG_ROOT / args.scenario,
            ),
        )
        return run_orchestrated_session(
            mcp_command=mcp_command,
            codex_command=build_codex_command(
                codex_bin,
                paths.player_workspace,
            ),
            supervisor_command=supervisor_command,
            prompt=build_player_prompt(args.runs, args.scenario, paths.run_config),
            mcp_env=mcp_env,
            codex_env=build_player_env(player_home),
            supervisor_env=supervisor_env,
            mcp_cwd=REPO_ROOT,
            codex_cwd=paths.player_workspace,
            supervisor_cwd=REPO_ROOT,
            ws_port=DEFAULT_WS_PORT,
            mcp_port=args.mcp_port,
            mcp_start_timeout_seconds=args.mcp_start_timeout_seconds,
            codex_exit_grace_seconds=args.codex_exit_grace_seconds,
        )


if __name__ == "__main__":
    raise SystemExit(main())
