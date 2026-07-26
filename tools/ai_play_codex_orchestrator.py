#!/usr/bin/env python3
"""Start an isolated Codex player and the Godot AI Play supervisor together."""

from __future__ import annotations

import argparse
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SESSION_ROOT = Path("~/workspace/cogito_ai_player_runs")
DEFAULT_CODEX_HOME = Path("~/.codex-cogito-player")
DEFAULT_SCENE = "addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"


@dataclass(frozen=True)
class RunPaths:
    run_dir: Path
    player_workspace: Path
    log_root: Path
    last_message: Path
    run_config: Path


def create_run_paths(
    session_root: Path,
    timestamp: str | None = None,
) -> RunPaths:
    root = session_root.expanduser()
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
    log_root = player_workspace / "mcplogs"
    player_workspace.mkdir(mode=0o700)
    log_root.mkdir(mode=0o700)
    return RunPaths(
        run_dir=run_dir,
        player_workspace=player_workspace,
        log_root=log_root,
        last_message=run_dir / "codex_last_message.txt",
        run_config=player_workspace / "ai_play_run_config.json",
    )


def write_player_run_config(
    paths: RunPaths,
    runs: int,
    scenario: str,
) -> Path:
    payload = {
        "scenario": scenario,
        "runs": runs,
        "ai_play_log_root": str(paths.log_root),
    }
    paths.run_config.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return paths.run_config


def build_child_env(
    log_root: Path,
    codex_home: Path,
    ws_host: str = "127.0.0.1",
    ws_port: int = 8765,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env["AI_PLAY_LOG_ROOT"] = str(log_root)
    env["CODEX_HOME"] = str(codex_home.expanduser())
    env["AI_PLAY_WS_HOST"] = ws_host
    env["AI_PLAY_WS_PORT"] = str(ws_port)
    return env


def ensure_player_codex_config(codex_home: Path, mcp_command: Path) -> Path:
    home = codex_home.expanduser()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    config_path = home / "config.toml"
    mcp_block = _build_cogito_mcp_config_block(mcp_command)
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8")
        missing_blocks = _missing_cogito_mcp_config_blocks(text, mcp_command)
        if not missing_blocks:
            return config_path
        separator = "" if text.endswith("\n") else "\n"
        config_path.write_text(
            text + separator + "\n" + "\n".join(missing_blocks),
            encoding="utf-8",
        )
        return config_path
    config_path.write_text(mcp_block, encoding="utf-8")
    return config_path


def _build_cogito_mcp_config_block(mcp_command: Path) -> str:
    return "\n".join(
        [
            '[mcp_servers.cogito_ai_play]',
            f'command = "{mcp_command}"',
            "",
            '[mcp_servers.cogito_ai_play.tools.briefing]',
            'approval_mode = "approve"',
            "",
            '[mcp_servers.cogito_ai_play.tools.observe]',
            'approval_mode = "approve"',
            "",
            '[mcp_servers.cogito_ai_play.tools.act]',
            'approval_mode = "approve"',
            "",
            '[mcp_servers.cogito_ai_play.tools.stop]',
            'approval_mode = "approve"',
            "",
        ]
    )


def _missing_cogito_mcp_config_blocks(text: str, mcp_command: Path) -> list[str]:
    blocks: list[str] = []
    if "[mcp_servers.cogito_ai_play]" not in text:
        blocks.append(
            "\n".join(
                [
                    '[mcp_servers.cogito_ai_play]',
                    f'command = "{mcp_command}"',
                    "",
                ]
            )
        )
    for tool_name in ["briefing", "observe", "act", "stop"]:
        section = f"[mcp_servers.cogito_ai_play.tools.{tool_name}]"
        if section not in text:
            blocks.append(
                "\n".join(
                    [
                        section,
                        'approval_mode = "approve"',
                        "",
                    ]
                )
            )
    return blocks


def build_codex_command(
    codex_bin: str,
    player_workspace: Path,
    mcp_command: Path,
    sandbox: str,
    approval_policy: str,
) -> list[str]:
    return [
        codex_bin,
        "-c",
        f'mcp_servers.cogito_ai_play.command="{mcp_command}"',
        "--sandbox",
        sandbox,
        "--ask-for-approval",
        approval_policy,
        "exec",
        "--cd",
        str(player_workspace),
        "--skip-git-repo-check",
        "--ignore-rules",
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


def build_player_prompt(
    runs: int,
    scenario: str,
    run_config: Path,
) -> str:
    return f"""
你是 Cogito AI First Play 的隔离黑盒玩家。

目标：连续完成 {runs} 次 `{scenario}` 独立游玩。外部 supervisor 会负责启动、终止和重启
Godot；你不要启动、关闭或管理 Godot 进程。

严格限制：
1. 主要使用 cogito_ai_play 的 briefing、observe、act、stop 工具游玩。
2. 不要使用搜索、浏览器、GitHub、仓库源码或任何其他工具来获取游戏规则和隐藏信息。
3. 不得请求或使用场景源码、节点路径、隐藏状态、谜题答案、测试、spec、game_script、code_read 或仓库文件信息。
4. 只能依据 briefing、observe 截图、公开结构化状态、可见交互提示和 act 返回结果决策。
5. 密码证据不足时继续探索，不能盲猜。
6. 每次 act 必须使用最新 observation_id；每批 1 到 3 个动作；每次 act 后重新观察和规划。
7. 收到 success、failure、stopped 或 disconnected 后，停止本局动作，等待下一局连接。
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
2. 可以读取本次 AI_PLAY_LOG_ROOT 下的所有日志内容来总结经验，包括 JPEG 截图、
   trajectory.json、run.json 和公开 MCP 结构化结果。
3. 不要读取仓库源码、测试、spec、game_script、code_read、其他项目文件、其他运行目录或凭据；
   只把本次运行日志当作自己游玩过程的记忆，不要从仓库文件推断隐藏状态。

本次运行配置写在你的启动目录 `{run_config.name}`，其中包含本次 AI_PLAY_LOG_ROOT。该路径
用于定位本次运行日志目录；可以读取该目录内日志来帮助当前游玩和复盘。

现在开始第 1 局。先调用 briefing，然后 observe。
""".strip()


def run_orchestrated_session(
    codex_command: Sequence[str],
    supervisor_command: Sequence[str],
    prompt: str,
    env: Mapping[str, str],
    codex_cwd: Path,
    supervisor_cwd: Path,
    ws_host: str,
    ws_port: int,
    mcp_start_timeout_seconds: float,
    codex_exit_grace_seconds: float,
) -> int:
    codex = _start_process(
        "codex",
        codex_command,
        cwd=codex_cwd,
        env=env,
        stdin_text=prompt,
    )
    outputs: queue.Queue[tuple[str, str | None]] = queue.Queue()
    threading.Thread(
        target=_read_labeled_output,
        args=("codex", codex, outputs),
        daemon=True,
    ).start()
    deadline = time.monotonic() + mcp_start_timeout_seconds
    while time.monotonic() < deadline:
        _print_available_output(outputs)
        if codex.poll() is not None:
            break
        if is_port_listening(ws_host, ws_port):
            break
        time.sleep(0.05)
    if codex.poll() is not None:
        _print_available_output(outputs)
        return codex.returncode if codex.returncode is not None else 3
    if not is_port_listening(ws_host, ws_port):
        _terminate_process(codex)
        _print_available_output(outputs)
        print(
            "[orchestrator] MCP bridge did not listen on %s:%s within %.1fs"
            % (ws_host, ws_port, mcp_start_timeout_seconds),
            flush=True,
        )
        return 4
    supervisor = _start_process(
        "supervisor",
        supervisor_command,
        cwd=supervisor_cwd,
        env=env,
    )
    threading.Thread(
        target=_read_labeled_output,
        args=("supervisor", supervisor, outputs),
        daemon=True,
    ).start()

    try:
        while True:
            _print_available_output(outputs)
            supervisor_code = supervisor.poll()
            codex_code = codex.poll()
            if supervisor_code is not None:
                _terminate_process(codex)
                _print_available_output(outputs)
                return supervisor_code
            if codex_code is not None:
                deadline = time.monotonic() + codex_exit_grace_seconds
                while time.monotonic() < deadline:
                    _print_available_output(outputs)
                    supervisor_code = supervisor.poll()
                    if supervisor_code is not None:
                        _print_available_output(outputs)
                        return supervisor_code
                    time.sleep(0.05)
                _terminate_process(supervisor)
                _print_available_output(outputs)
                return 3 if codex_code == 0 else codex_code
            time.sleep(0.05)
    except KeyboardInterrupt:
        _terminate_process(codex)
        _terminate_process(supervisor)
        raise


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
        description="Run an isolated Codex player with the Godot supervisor.",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--scenario", default="find_contract")
    parser.add_argument("--session-root", type=Path, default=DEFAULT_SESSION_ROOT)
    parser.add_argument("--codex-home", type=Path, default=DEFAULT_CODEX_HOME)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--godot-bin", default="godot")
    parser.add_argument("--scene", default=DEFAULT_SCENE)
    parser.add_argument("--ws-host", default="127.0.0.1")
    parser.add_argument("--ws-port", type=int, default=8765)
    parser.add_argument("--sandbox", default="read-only")
    parser.add_argument("--approval-policy", default="never")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=1200.0)
    parser.add_argument("--mcp-start-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--codex-exit-grace-seconds", type=float, default=5.0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be at least 0")
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive")
    if args.ws_port < 1 or args.ws_port > 65535:
        raise SystemExit("--ws-port must be between 1 and 65535")
    if args.mcp_start_timeout_seconds <= 0:
        raise SystemExit("--mcp-start-timeout-seconds must be positive")
    if args.codex_exit_grace_seconds <= 0:
        raise SystemExit("--codex-exit-grace-seconds must be positive")
    if is_port_listening(args.ws_host, args.ws_port):
        raise SystemExit(
            "AI Play bridge port %s:%s is already in use; stop the existing MCP/Codex "
            "process first or choose --ws-port."
            % (args.ws_host, args.ws_port)
        )

    paths = create_run_paths(args.session_root)
    write_player_run_config(paths, args.runs, args.scenario)
    codex_home = args.codex_home.expanduser()
    config_path = ensure_player_codex_config(
        codex_home,
        REPO_ROOT / "ai_play" / "start_ai.sh",
    )
    env = build_child_env(paths.log_root, codex_home, args.ws_host, args.ws_port)
    prompt = build_player_prompt(args.runs, args.scenario, paths.run_config)
    codex_command = build_codex_command(
        codex_bin=args.codex_bin,
        player_workspace=paths.player_workspace,
        mcp_command=REPO_ROOT / "ai_play" / "start_ai.sh",
        sandbox=args.sandbox,
        approval_policy=args.approval_policy,
    )
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
    print("[orchestrator] player_workspace=%s" % paths.player_workspace, flush=True)
    print("[orchestrator] AI_PLAY_LOG_ROOT=%s" % paths.log_root, flush=True)
    print(
        "[orchestrator] AI_PLAY_WS=%s:%s" % (args.ws_host, args.ws_port),
        flush=True,
    )
    print("[orchestrator] CODEX_HOME=%s" % codex_home, flush=True)
    print("[orchestrator] Codex config=%s" % config_path, flush=True)
    return run_orchestrated_session(
        codex_command=codex_command,
        supervisor_command=supervisor_command,
        prompt=prompt,
        env=env,
        codex_cwd=paths.player_workspace,
        supervisor_cwd=REPO_ROOT,
        ws_host=args.ws_host,
        ws_port=args.ws_port,
        mcp_start_timeout_seconds=args.mcp_start_timeout_seconds,
        codex_exit_grace_seconds=args.codex_exit_grace_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
