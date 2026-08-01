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
BASE_PLAYER_TOOL_NAMES = (
    "briefing",
    "observe",
    "act",
)
AWM_PLAYER_TOOL_NAMES = (
    "briefing",
    "workflow_memory_read",
    "observe",
    "act",
    "workflow_memory_update",
)
CORE_ENV_NAMES = ("PATH", "PATHEXT", "SystemRoot", "WINDIR", "ComSpec")


@dataclass(frozen=True)
class RunPaths:
    run_dir: Path
    player_workspace: Path
    log_root: Path


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


def build_player_developer_instructions() -> str:
    return """
你是通过视觉与获准 MCP 工具操作 3D 游戏的黑盒玩家。briefing 是游戏规则、目标和物体操作说明的
唯一权威来源；每局先读取并遵守它，像人类玩家一样从第一次进入场景开始观察、探索、规划和纠错。

observe 在工具结果中返回的截图属于你的获准视觉输入。你可以并且应该比较当前截图与本会话之前由 observe 返回的截图，
依据画面中物体大小、屏幕位置、透视、可见/遮挡和朝向的变化，推断相对位移、转向、遮挡变化和地标关系，
逐步建立以可见地标为依据的空间理解。动作后必须用新截图验证实际变化；
没有变化、变化方向不符或目标丢失时，应调整假设与动作，不要机械重复。

look 只使用 direction 和 degrees，例如向左转 30 度是
{"type":"look","direction":"left","degrees":30}。direction 只能是 left、right、up、down；
不要填写 yaw、pitch 或正负号。每次转向后比较当前截图与本会话之前由 observe 返回的截图中
地标的位置、大小与遮挡变化，确认方向正确后再移动。

此视觉权限只覆盖当前模型会话中工具直接返回的图片。不得读取或保存磁盘截图、图片路径、Base64、
embedding、轨迹文件、仓库内容、场景源码或隐藏状态，也不得使用 shell、文件系统、搜索或网络扩展信息源。
只输出简短、可公开的决策依据，不输出隐藏推理链。
""".strip()


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
                "enabled = false",
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


def build_player_prompt(
    runs: int,
    workflow_memory_enabled: bool = True,
) -> str:
    if workflow_memory_enabled:
        startup = "先调用 briefing，再调用 workflow_memory_read，再调用 observe"
        allowed_tools = (
            "briefing、workflow_memory_read、observe、act、\n"
            "   workflow_memory_update"
        )
        memory_rules = """7. workflow memory 只是高层建议，不能替代最新 observe，也不能授权当前观察不允许的动作。
8. 不得读取任何本地轨迹或截图文件；不得通过 shell 或文件系统建立另一套记忆。
9. 收到 success、failure、stopped 或 disconnected 后，停止本局动作。
10. 终局后调用 workflow_memory_update，但 stopped、disconnected 或其他异常局不要更新。
11. 成功局提交由本局公开证据支持的抽象 workflow、landmarks 和 avoid。
12. 失败局只提交 avoid：workflow 和 landmarks 必须为空，不得把未验证路线晋升为经验。
13. 不要保存图片、图片引用、Base64 或 embedding；不要保存密码、随机答案、绝对坐标、
    逐帧动作序列、文件路径、URL 或内部实现信息。
14. eligible 更新返回后再等待下一局，并重新从 briefing 开始。"""
        decision_memory = (
            "3. 记录 workflow memory 提供了什么高层经验，以及最新观察是否支持采用它。\n"
            "4. 记录最新 observe 截图显示了什么，包括可见物体、交互提示、距离和朝向变化。\n"
            "5. 主动 Keep 这份 memory：每次 observe 或 act 后用新证据更新当前目标、已确认地标、\n"
            "   已试过但失败的路线，以及终局后要提交的抽象候选；不要把图片本身写入 memory。"
        )
    else:
        startup = "先调用 briefing，再调用 observe"
        allowed_tools = "briefing、observe、act"
        memory_rules = """7. 只可在普通会话上下文中保留公开的简短笔记；没有结构化经验读写工具。
8. 不得读取任何本地轨迹或截图文件；不得通过 shell 或文件系统建立另一套记忆。
9. 收到 success、failure、stopped 或 disconnected 后，停止本局动作。
10. 终局后等待下一局，并重新从 briefing 开始。"""
        decision_memory = (
            "3. 记录普通会话上下文中已有的高层经验，以及最新观察是否支持采用它。\n"
            "4. 记录最新 observe 截图显示了什么，包括可见物体、交互提示、距离和朝向变化。\n"
            "5. 每次 observe 或 act 后用公开新证据更新当前目标、已确认地标和已试过但失败的路线；\n"
            "   不要保存图片本身，也不要使用 shell 或文件系统保存笔记。"
        )
    return f"""
你是 Cogito AI First Play 的隔离黑盒玩家。

本会话需要完成 {runs} 次独立游玩。每局开始时，{startup}。

严格限制：
1. 只使用 cogito_ai_play 的 {allowed_tools} 工具；不要尝试调用 stop，也不要把 stop 作为 act 动作。
2. 只能依据 briefing、observe 截图、公开结构化状态、可见交互提示和 act 返回结果决策。
3. 不要使用搜索、浏览器、GitHub 或任何其他工具获取游戏信息。
4. 不得请求或使用场景源码、节点路径、隐藏状态、谜题答案、测试、规格、开发者笔记或仓库文件信息。
5. 密码证据不足时继续探索，不能盲猜。
6. 每次 act 必须使用最新 observation_id；每批 1 到 3 个动作；每次 act 后重新观察和规划。
{memory_rules}
15. 在完成全部 {runs} 次独立游玩前，不要输出最终回答，也不要结束会话。
16. 若当前工具结果是 stopped 或 disconnected，但还没有完成全部 {runs} 次，继续调用 observe
   等待下一局；observe 仍返回 stopped/disconnected 时等待后再 observe，直到出现新的可玩观察。

像人一样玩：
1. 不要把游戏当 API 猜参数。先看清画面、HUD、标牌、物体和可见提示，再小步移动或转身。
   look 只使用 direction、degrees，例如向左转 30 度是
   {{"type":"look","direction":"left","degrees":30}}；direction 只能是 left、right、up、down，
   不要填写 yaw、pitch 或正负号。每次转向后比较当前截图与本会话之前由 observe 返回的截图中
   地标的位置、大小与遮挡变化，确认方向正确后再移动。
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

每步公开决策记录：
1. 每一步都先写一段公开决策记录，保持简短，只记录可公开依据，不输出隐藏推理链。
2. 记录当前 goal 是什么，例如“先找到并读取任务卡”或“靠近当前可见交互物”。
{decision_memory}

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
    parser.add_argument(
        "--workflow-memory",
        choices=("enabled", "disabled"),
        default="enabled",
    )
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--godot-bin", default="godot")
    parser.add_argument("--scene", default=DEFAULT_SCENE)
    parser.add_argument("--mcp-port", type=int, default=DEFAULT_MCP_PORT)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=100000.0)
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
            workflow_memory_enabled=args.workflow_memory == "enabled",
        )
        return run_orchestrated_session(
            mcp_command=mcp_command,
            codex_command=build_codex_command(
                codex_bin,
                paths.player_workspace,
            ),
            supervisor_command=supervisor_command,
            prompt=build_player_prompt(
                args.runs,
                workflow_memory_enabled=args.workflow_memory == "enabled",
            ),
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
