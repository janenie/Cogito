#!/usr/bin/env python3
"""Shared hardened orchestration for isolated AI First Play model players."""

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import socket
import subprocess
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SESSION_ROOT = (
    Path(REPO_ROOT.anchor) / "cogito_ai_player_runs"
    if os.name == "nt"
    else Path("/tmp/cogito_ai_player_runs")
)
DEFAULT_WS_HOST = "127.0.0.1"
DEFAULT_WS_PORT = 8765
DEFAULT_MCP_PORT = 8766
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
    session_metadata: Path


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


def _run_directory_component(value: str, max_length: int = 64) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    component = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized)
    component = re.sub(r"_+", "_", component).strip("._-")
    if not component:
        component = "unknown"
    if len(component) <= max_length:
        return component
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    prefix = component[: max_length - len(digest) - 1].rstrip("._-")
    return f"{prefix}-{digest}"


def create_run_paths(
    session_root: Path,
    *,
    player: str,
    model: str,
    reasoning_effort: str,
    scenario: str,
    workflow_memory_enabled: bool,
    requested_runs: int,
    timestamp: str | None = None,
) -> RunPaths:
    root = validate_isolated_session_root(session_root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    started_at = datetime.now().astimezone()
    stamp = timestamp or started_at.strftime("%Y%m%d-%H%M%S")
    memory_label = "awm" if workflow_memory_enabled else "no-awm"
    run_name = "__".join(
        (
            stamp,
            _run_directory_component(player),
            _run_directory_component(model),
            _run_directory_component(scenario),
            memory_label,
        )
    )
    for index in range(1, 1000):
        suffix = "" if index == 1 else "-%02d" % index
        run_dir = root / f"{run_name}{suffix}"
        try:
            run_dir.mkdir(mode=0o700)
            break
        except FileExistsError:
            continue
    else:
        raise RuntimeError("could not allocate a fresh AI Play run directory")

    player_workspace = run_dir / "player_workspace"
    log_root = run_dir / "trusted_mcplogs"
    session_metadata = run_dir / "session.json"
    player_workspace.mkdir(mode=0o700)
    log_root.mkdir(mode=0o700)
    metadata = {
        "schema_version": 1,
        "player": player,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "scenario": scenario,
        "workflow_memory": (
            "enabled" if workflow_memory_enabled else "disabled"
        ),
        "requested_runs": requested_runs,
        "started_at": started_at.isoformat(timespec="seconds"),
    }
    with session_metadata.open("x", encoding="utf-8") as metadata_file:
        json.dump(metadata, metadata_file, ensure_ascii=False, indent=2)
        metadata_file.write("\n")
    os.chmod(session_metadata, 0o600)
    return RunPaths(
        run_dir=run_dir,
        player_workspace=player_workspace,
        log_root=log_root,
        session_metadata=session_metadata,
    )


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


def build_player_developer_instructions(
    approved_image_root: Path | None = None,
) -> str:
    if approved_image_root is None:
        visual_permission = """此视觉权限只覆盖当前模型会话中工具直接返回的图片。不得读取或保存磁盘截图、图片路径、Base64、
embedding、轨迹文件、仓库内容、场景源码或隐藏状态，也不得使用 shell、文件系统、搜索或网络扩展信息源。"""
    else:
        image_root = approved_image_root.resolve()
        visual_permission = f"""Claude Code 不会把 MCP ImageContent 直接交给模型。每次 briefing、observe 或 act 返回
approved_image_paths 后，每次都调用 Read 读取其中的 color 或 reference；只有导航需要时再读 depth。
Read 权限严格限制在 {image_root}。不得读取该目录之外的任何路径，不得读取轨迹、仓库内容、配置、
场景源码或隐藏状态，也不得使用 shell、搜索或网络扩展信息源。不得把图片、路径、Base64 或 embedding 写入 AWM。"""
    return f"""
你是通过视觉与获准 MCP 工具操作 3D 游戏的黑盒玩家。briefing 是游戏规则、目标和物体操作说明的
唯一权威来源；每局先读取并遵守它，像人类玩家一样从第一次进入场景开始观察、探索、规划和纠错。

observe 和 act 在工具结果中返回的图片属于你的获准视觉输入。第一张图片是正常画面的 JPEG 截图；
如果返回第二张图片，它是 PNG 深度图，越暗表示越近，白色表示 20 米外或当前无法取得深度。
首次 observe 后，每次成功的 act 已经携带下一份观察，
不要为了刷新画面重复调用 observe。你可以并且应该比较当前截图与本会话之前由 observe 或 act 返回的截图，
依据画面中物体大小、屏幕位置、透视、可见/遮挡和朝向的变化，推断相对位移、转向、遮挡变化和地标关系，
逐步建立以可见地标为依据的空间理解。动作后必须用新截图验证实际变化；
没有变化、变化方向不符或目标丢失时，应调整假设与动作，不要机械重复。

look 只使用 direction 和 degrees，例如向左转 30 度是
{{"type":"look","direction":"left","degrees":30}}。direction 只能是 left、right、up、down；
不要填写 yaw、pitch 或正负号。每次转向后比较当前截图与本会话之前由 observe 或 act 返回的截图中
地标的位置、大小与遮挡变化，确认方向正确后再移动。

如果 briefing 明确要求先读取出生点附近的任务卡，任务卡不是普通纸张：它在画面中表现为
青绿色或蓝绿色的独立标志，细杆底座上方带同心圆、靶心或旋涡状发光圆环，中间有白色小牌；
即使看起来像装饰标记，也要把它作为最高优先级任务卡候选。首次 observe 后保持原地，
首张截图已经出现该标志时，不要开始 45 度整圈扫描；立即停止搜索，每次只向标志方向转 5 到 15 度，
短步靠近并用新截图保持标志在准星附近。不要把附近门的 Open 提示误认为任务卡的阅读提示。
只有首张截图没有候选时，才每次水平旋转 45 度并获取新 observation，找到候选即停止，最多覆盖 360 度。
截图没有随公开朝向变化时不得把旧截图算作新扇区，必须等待全新 observation。找到候选后
用短步靠近、将准星对准标志中央，再单独调用 probe_interaction；远距离的 not_found 不能作为排除依据。出现读取
交互后执行 interact 并读完任务卡。读取任务卡前不得离开出生区域；水平一圈仍没找到时，才在
原地补充向上和向下扫描。

{visual_permission}
只输出简短、可公开的决策依据，不输出隐藏推理链。
""".strip()


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


def build_isolated_process_env(
    environment_root: Path,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    root = environment_root.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    home_dir = root / "home"
    appdata_dir = root / "appdata"
    localappdata_dir = root / "localappdata"
    temp_dir = root / "tmp"
    for directory in (home_dir, appdata_dir, localappdata_dir, temp_dir):
        directory.mkdir(mode=0o700, exist_ok=True)
    env = build_core_env(base_env)
    env.update(
        {
            "HOME": str(home_dir),
            "USERPROFILE": str(home_dir),
            "APPDATA": str(appdata_dir),
            "LOCALAPPDATA": str(localappdata_dir),
            "TEMP": str(temp_dir),
            "TMP": str(temp_dir),
            "TMPDIR": str(temp_dir),
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
    environment_root: Path,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    return build_isolated_process_env(environment_root, base_env)


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
    scenario: str = "",
    approved_image_read: bool = False,
) -> str:
    local_file_rule = (
        "每次 briefing、observe 或 act 返回 approved_image_paths 后，立即用 Read 读取这些获准图片；"
        "不得读取其他本地文件，也不得通过文件系统建立另一套记忆。"
        if approved_image_read
        else "不得读取任何本地轨迹或截图文件；不得通过 shell 或文件系统建立另一套记忆。"
    )
    if workflow_memory_enabled:
        startup = "先调用 briefing，再调用 workflow_memory_read，再调用 observe"
        allowed_tools = (
            "briefing、workflow_memory_read、observe、act、\n"
            "   workflow_memory_update"
        )
        memory_rules = f"""7. workflow memory 只是高层建议，不能替代最新 observe，也不能授权当前观察不允许的动作。
8. {local_file_rule}
9. 收到 success、failure、stopped 或 disconnected 后，停止本局动作。
10. 终局后调用 workflow_memory_update，但 stopped、disconnected 或其他异常局不要更新。
11. 成功局提交由本局公开证据支持的抽象 workflow、landmarks 和 avoid。
12. 失败局的 workflow 和 landmarks 必须为空；提交 avoid 和 failure_review，不得把未验证路线晋升为经验。
    failure_review 只包含 stage、bottlenecks 和 optimizations，概括目标分类、导航、交互选择或
    请求预算管理中可跨局复用的瓶颈与优化，不要叙述逐帧经过。
13. 下一局读取 failure_reviews 后，用最新 briefing 和 observe（或 act 返回的新观察）判断建议；
    公开说明哪些优化适用、有哪些新证据，以及适用建议如何改变当前计划；忽略不适用的建议。
14. 不要保存图片、图片引用、Base64 或 embedding；不要保存局内具体答案、随机答案或随机结果、绝对坐标、
    逐帧动作序列、文件路径、URL 或内部实现信息。
15. 局数以 workflow_memory_read 返回的 completed_runs 为准；stopped、disconnected、shutdown
    或其他异常重试不算完成一局，也不得自行增加局数。eligible 更新返回后再等待下一局，
    并重新从 briefing 开始。"""
        decision_memory = (
            "3. 记录 workflow memory 提供了什么高层经验；若有 failure_reviews，说明哪些优化适用、\n"
            "   最新 briefing 和 observe（或 act 新观察）提供了什么证据，以及适用建议如何改变当前计划。\n"
            "4. 记录最新 observe 或 act 截图显示了什么，包括可见物体、交互提示、距离和朝向变化。\n"
            "5. 主动 Keep 这份 memory：每次 observe 或 act 后用新证据更新当前目标、已确认地标、\n"
            "   已试过但失败的路线，以及终局后要提交的抽象候选；不要把图片本身写入 memory。"
        )
    else:
        startup = "先调用 briefing，再调用 observe"
        allowed_tools = "briefing、observe、act"
        memory_rules = f"""7. 只可在普通会话上下文中保留公开的简短笔记；没有结构化经验读写工具。
8. {local_file_rule}
9. 收到 success、failure、stopped 或 disconnected 后，停止本局动作。
10. 终局后等待下一局，并重新从 briefing 开始。"""
        decision_memory = (
            "3. 记录普通会话上下文中已有的高层经验，以及最新观察是否支持采用它。\n"
            "4. 记录最新 observe 或 act 截图显示了什么，包括可见物体、交互提示、距离和朝向变化。\n"
            "5. 每次 observe 或 act 后用公开新证据更新当前目标、已确认地标和已试过但失败的路线；\n"
            "   不要保存图片本身，也不要使用 shell 或文件系统保存笔记。"
        )
    staircase_guidance = ""
    if scenario == "loop_staircase_anomaly":
        staircase_guidance = """
循环楼梯专用规则：
1. 不要使用 move 或 sprint；上下楼只用 press_key 的 "up"/"down"。
2. 每次 press_key 后直接使用 act 返回的新观察，不要额外刷新 observe。
3. 完整观察五轮 2F 到 9F，维护候选楼层集合；不能只凭单张截图或当前楼层号作答。
4. 只有证据唯一时才用 press_key 的 "space" 提交当前楼层。
"""
    return f"""
你是 Cogito AI First Play 的隔离黑盒玩家。

本会话需要完成 {runs} 次独立游玩。每局开始时，{startup}。

严格限制：
1. 只使用 cogito_ai_play 的 {allowed_tools} 工具；不要尝试调用 stop，也不要把 stop 作为 act 动作。
2. 只能依据 briefing、observe 截图、公开结构化状态、可见交互提示和 act 返回结果决策。
3. 不要使用搜索、浏览器、GitHub 或任何其他工具获取游戏信息。
4. 不得请求或使用场景源码、节点路径、隐藏状态、谜题答案、测试、规格、开发者笔记或仓库文件信息。
5. 对答案、关系或一次性提交的证据不足时继续探索，不能盲猜。
6. 每次 act 必须使用最新 observation_id；每批 1 到 3 个动作；成功的 act 返回下一份观察，
   直接用它重新规划，不要再调用 observe。只有开局或 act 未返回观察且会话仍可继续时才调用 observe。
{memory_rules}
16. 在完成全部 {runs} 次独立游玩前，不要输出最终回答，也不要结束会话。
17. 若当前工具结果是 disconnected 且还没有完成全部 {runs} 次，继续调用 observe 等待同一局
   的异常重试；observe 仍返回 disconnected 时等待后再 observe，直到出现新的可玩观察。
   stopped 表示操作者主动中止整次运行：立即停止调用工具，此时允许结束会话，无需凑满局数。
18. observation_id 不是 act 请求计数，也不是已完成局数。不要根据 observation_id 推断动作上限、
   自行宣布成功或失败，或提前结束会话；只有工具返回正式 game_over 才表示本局终局。

{staircase_guidance.strip()}

像人一样玩：
1. 不要把游戏当 API 猜参数。先看清画面、HUD、标牌、物体和可见提示，再小步移动或转身。
   look 只使用 direction、degrees，例如向左转 30 度是
   {{"type":"look","direction":"left","degrees":30}}；direction 只能是 left、right、up、down，
   不要填写 yaw、pitch 或正负号。每次转向后比较当前截图与本会话之前由 observe 或 act 返回的截图中
   地标的位置、大小与遮挡变化，确认方向正确后再移动。
2. 避免贴着地图边界、围栏或不可通行表面移动，优先沿可见道路、门口和开阔区域前进；
   迷路时停下、环顾，并回到 briefing 或可见标牌提到的可靠地标。
3. 靠近目标时使用短距离 move，不要长时间 sprint；穿过狭窄门口或贴近门框时，优先使用
   单轴 0.2 到 0.4 的力度和 50 到 100ms，每步使用 act 返回的新观察和 movement_feedback 修正站位，
   不要连续使用满强度 250ms。转向后也检查同一次 act 返回的新观察，确认准星没有偏离目标。
4. 只有当前 observation 的 interface.available_interactions 中出现对应 action 时，才执行 interact。
   交互动作格式必须精确写成 {{"type":"interact","action":"interact"}} 或
   {{"type":"interact","action":"interact2"}}，不要把提示文字、物体名或绑定键写进 action。
5. 如果没有交互提示但画面中疑似有任务物体、可读文件、按钮或门，先靠近并单独调用 probe_interaction；
   probe_interaction 必须是单动作批次。
6. 如果一次 act failed，说明动作没有通过校验；若结果没有新观察，再调用 observe，然后改变站位、
   准星或动作类型。movement_feedback.blocked 为 true 时优先小幅侧移或重新对准门口。
   不要连续重试同一种 act，也不要在没有新 observation 时继续提交交互。
7. 每局把自己当成第一次进场的人类玩家：先建立 briefing 提到或可见标牌标出的关键地标之间
   的相对方位，再执行任务。不要为了省步数盲冲边界，也不要在未确认目标时触发交互。
8. 如果 briefing 要求先读取出生点附近任务卡，首次 observe 后先环顾出生点近处的悬浮标志、
   纸张或文件；离开出生区域前，优先靠近并对准最可信候选，单独调用 probe_interaction。
   探测失败后才换候选或扩大搜索，不要先走进远处房间。

每步公开决策记录：
1. 每一步都先写一段公开决策记录，保持简短，只记录可公开依据，不输出隐藏推理链。
2. 记录当前 goal 是什么，例如“先找到并读取任务卡”或“靠近当前可见交互物”。
{decision_memory}

游戏目标、规则和物体操作说明只由 briefing 提供。现在开始第 1 局。
""".strip()


def run_orchestrated_session(
    mcp_command: Sequence[str],
    player_label: str,
    player_command: Sequence[str],
    supervisor_command: Sequence[str],
    prompt: str,
    mcp_env: Mapping[str, str],
    player_env: Mapping[str, str],
    supervisor_env: Mapping[str, str],
    mcp_cwd: Path,
    player_cwd: Path,
    supervisor_cwd: Path,
    ws_port: int,
    mcp_port: int,
    mcp_start_timeout_seconds: float,
    player_exit_grace_seconds: float,
    idle_timeout_seconds: float,
    player_final_grace_seconds: float,
    player_restart_limit: int = 0,
    player_restart_prompt: str | None = None,
) -> int:
    outputs: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mcp = None
    player = None
    supervisor = None
    player_restarts = 0
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

        player = _start_process(
            player_label,
            player_command,
            player_cwd,
            player_env,
            stdin_text=prompt,
        )
        _start_output_reader(player_label, player, outputs)
        player_code = player.poll()
        if player_code is not None:
            return 3 if player_code == 0 else player_code

        supervisor = _start_process(
            "supervisor",
            supervisor_command,
            supervisor_cwd,
            supervisor_env,
        )
        _start_output_reader("supervisor", supervisor, outputs)
        last_activity_at = time.monotonic()

        while True:
            if _print_available_output(outputs):
                last_activity_at = time.monotonic()
            mcp_code = mcp.poll()
            supervisor_code = supervisor.poll()
            player_code = player.poll()
            if mcp_code is not None:
                return 4 if mcp_code == 0 else mcp_code
            if supervisor_code is not None:
                return _finish_after_supervisor(
                    supervisor_code,
                    mcp,
                    player,
                    outputs,
                    player_final_grace_seconds,
                )
            if player_code is not None:
                deadline = time.monotonic() + player_exit_grace_seconds
                while time.monotonic() < deadline:
                    _print_available_output(outputs)
                    mcp_code = mcp.poll()
                    supervisor_code = supervisor.poll()
                    if mcp_code is not None:
                        return 4 if mcp_code == 0 else mcp_code
                    if supervisor_code is not None:
                        return supervisor_code
                    time.sleep(0.05)
                if player_code == 0 and player_restarts < player_restart_limit:
                    player_restarts += 1
                    print(
                        "[orchestrator] %s exited before supervisor terminal; "
                        "restarting player turn (%s/%s)"
                        % (player_label, player_restarts, player_restart_limit),
                        flush=True,
                    )
                    player = _start_process(
                        player_label,
                        player_command,
                        player_cwd,
                        player_env,
                        stdin_text=player_restart_prompt or prompt,
                    )
                    _start_output_reader(player_label, player, outputs)
                    last_activity_at = time.monotonic()
                    continue
                return 3 if player_code == 0 else player_code
            if time.monotonic() - last_activity_at > idle_timeout_seconds:
                print(
                    "[orchestrator] no child-process output for %.1fs; "
                    "stopping stalled session" % idle_timeout_seconds,
                    flush=True,
                )
                return 5
            time.sleep(0.05)
    finally:
        for process in (supervisor, player, mcp):
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


def _finish_after_supervisor(
    supervisor_code: int,
    mcp: subprocess.Popen[str],
    player: subprocess.Popen[str],
    outputs: queue.Queue[tuple[str, str | None]],
    grace_seconds: float,
) -> int:
    """Allow the player to consume the terminal result and emit its final response."""
    deadline = time.monotonic() + grace_seconds
    while True:
        _print_available_output(outputs)
        mcp_code = mcp.poll()
        player_code = player.poll()
        if mcp_code is not None:
            return 4 if mcp_code == 0 else mcp_code
        if player_code is not None or time.monotonic() >= deadline:
            return supervisor_code
        time.sleep(0.05)


def _print_available_output(
    outputs: queue.Queue[tuple[str, str | None]],
) -> bool:
    printed = False
    while True:
        try:
            label, line = outputs.get_nowait()
        except queue.Empty:
            return printed
        if line is not None:
            print("[%s] %s" % (label, line), end="", flush=True)
            printed = True


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
