import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

from ai_play.scenarios import supported_scenario_ids


REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_PATH = REPO_ROOT / "tools" / "ai_play_codex_orchestrator.py"


def load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "tools.ai_play_codex_orchestrator",
        ORCHESTRATOR_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_conveyor_scenario_uses_standalone_scene_by_default():
    orchestrator = load_orchestrator()

    assert orchestrator.resolve_scene("conveyor_profit", None) == (
        "conveyor_profit/scenes/conveyor_profit_preview.tscn"
    )
    assert orchestrator.resolve_scene("find_key", None) == orchestrator.DEFAULT_SCENE
    assert orchestrator.resolve_scene("daily_routine_cleanup", None) == (
        "dailyroutine/scenes/home_daily_routine.tscn"
    )
    assert orchestrator.resolve_scene("garden_watering", None) == (
        "garden/scenes/garden_vertical_slice.tscn"
    )
    assert orchestrator.resolve_scene("loop_staircase_anomaly", None) == (
        "addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn"
    )
    assert orchestrator.resolve_scene("laboratory_experiment", None) == (
        "addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn"
    )
    assert orchestrator.resolve_scene("conveyor_profit", "custom.tscn") == "custom.tscn"
    with pytest.raises(ValueError, match="unsupported"):
        orchestrator.resolve_scene("unknown", "custom.tscn")


def test_scene_registry_covers_every_public_scenario_with_an_existing_scene():
    orchestrator = load_orchestrator()

    assert orchestrator.SUPPORTED_SCENARIOS == supported_scenario_ids()
    for scenario in orchestrator.SUPPORTED_SCENARIOS:
        scene = orchestrator.resolve_scene(scenario, None)
        assert (orchestrator.REPO_ROOT / scene).is_file(), scenario


def test_codex_entry_reexports_common_orchestration_contract():
    orchestrator = load_orchestrator()

    assert orchestrator.DEFAULT_WS_HOST == "127.0.0.1"
    assert orchestrator.DEFAULT_WS_PORT == 8765
    assert orchestrator.DEFAULT_MCP_PORT == 8766
    assert orchestrator.BASE_PLAYER_TOOL_NAMES == (
        "briefing",
        "observe",
        "act",
    )
    assert orchestrator.AWM_PLAYER_TOOL_NAMES == (
        "briefing",
        "workflow_memory_read",
        "observe",
        "act",
        "workflow_memory_update",
    )


def test_create_run_paths_keeps_logs_trusted_and_player_workspace_empty(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )

    paths = orchestrator.create_run_paths(
        tmp_path,
        player="claude",
        model="../claude opus/test",
        reasoning_effort="high",
        scenario="find_contract",
        workflow_memory_enabled=True,
        requested_runs=4,
        timestamp="20260726-170000",
    )

    assert list(paths.player_workspace.iterdir()) == []
    assert paths.run_dir.name == (
        "20260726-170000__claude__claude_opus_test__find_contract__awm"
    )
    assert paths.log_root == paths.run_dir / "trusted_mcplogs"
    assert paths.log_root.is_dir()
    assert paths.session_metadata == paths.run_dir / "session.json"
    assert paths.session_metadata.stat().st_mode & 0o777 == 0o600
    metadata = json.loads(
        paths.session_metadata.read_text(encoding="utf-8")
    )
    assert metadata == {
        "schema_version": 2,
        "player": "claude",
        "model": "../claude opus/test",
        "reasoning_effort": "high",
        "scenario": "find_contract",
        "workflow_memory": "enabled",
        "requested_runs": 4,
        "started_at": metadata["started_at"],
        "benchmark": {
            "cycle_seed": orchestrator.DEFAULT_BENCHMARK_CYCLE_SEED,
            "attempts": [
                {
                    "attempt": attempt,
                    "round_seed": (
                        orchestrator.DEFAULT_BENCHMARK_CYCLE_SEED * 1_000_003
                        + attempt
                    ),
                }
                for attempt in range(1, 5)
            ],
        },
    }


def test_create_run_paths_can_separate_artifacts_from_runtime(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    runtime_root = tmp_path / "runtime"
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )

    paths = orchestrator.create_run_paths(
        runtime_root,
        artifact_root=artifact_root,
        player="codex",
        model="gemini-3.6-flash",
        reasoning_effort="none",
        scenario="find_contract",
        workflow_memory_enabled=True,
        requested_runs=3,
        timestamp="20260821-170000",
    )

    assert paths.run_dir.parent == artifact_root.resolve()
    assert paths.runtime_dir.parent == runtime_root.resolve()
    assert paths.runtime_dir != paths.run_dir
    assert paths.player_workspace == paths.runtime_dir / "player_workspace"
    assert paths.log_root == paths.run_dir / "trusted_mcplogs"
    assert paths.session_metadata == paths.run_dir / "session.json"
    assert not (paths.run_dir / "player_workspace").exists()


def test_resume_run_paths_reuses_artifacts_with_fresh_runtime(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )
    original = orchestrator.create_run_paths(
        tmp_path / "runtime-a",
        artifact_root=tmp_path / "artifacts",
        player="codex",
        model="gemini-3.6-flash",
        reasoning_effort="none",
        scenario="find_contract",
        workflow_memory_enabled=True,
        requested_runs=3,
        timestamp="20260821-170000",
    )
    marker = original.log_root / "partial-log.json"
    marker.write_text("{}", encoding="utf-8")

    resumed = orchestrator.resume_run_paths(
        tmp_path / "runtime-b",
        original.run_dir,
        timestamp="20260821-180000",
    )

    assert resumed.run_dir == original.run_dir
    assert resumed.log_root == original.log_root
    assert resumed.session_metadata == original.session_metadata
    assert resumed.runtime_dir != original.runtime_dir
    assert resumed.runtime_dir.parent == (tmp_path / "runtime-b").resolve()
    assert list(resumed.player_workspace.iterdir()) == []
    assert marker.is_file()


def test_benchmark_attempt_plan_preserves_special_campaign_contracts():
    orchestrator = load_orchestrator()

    assert orchestrator._common.benchmark_attempt_plan("find_key", 27, 4) == [
        {"attempt": 1, "round_seed": 108},
        {"attempt": 2, "round_seed": 109},
        {"attempt": 3, "round_seed": 110},
        {"attempt": 4, "round_seed": 111},
    ]
    assert orchestrator._common.benchmark_attempt_plan(
        "conveyor_profit", 27, 2,
    ) == [
        {"attempt": 1, "round_seed": 28, "draw_index": 0},
        {"attempt": 2, "round_seed": 28, "draw_index": 1},
    ]


def test_websocket_readiness_uses_a_real_protocol_handshake(monkeypatch):
    orchestrator = load_orchestrator()
    captured = {}

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_connect(uri, **kwargs):
        captured["uri"] = uri
        captured.update(kwargs)
        return FakeConnection()

    monkeypatch.setattr(orchestrator._common, "websocket_connect", fake_connect)

    assert orchestrator._common.is_websocket_listening("127.0.0.1", 8765)
    assert captured == {
        "uri": "ws://127.0.0.1:8765",
        "compression": None,
        "open_timeout": 0.2,
        "close_timeout": 0.2,
        "proxy": None,
    }


@pytest.mark.parametrize(
    "outputs",
    [
        ["unavailable", "unavailable"],
        ["unavailable", ""],
        ["a" * 40, "unavailable"],
    ],
)
def test_repository_metadata_distinguishes_unavailable_from_clean(
    monkeypatch,
    outputs,
):
    orchestrator = load_orchestrator()
    responses = iter(outputs)

    monkeypatch.setattr(
        orchestrator._common,
        "_run_metadata_command",
        lambda *_args, **_kwargs: next(responses),
    )

    assert orchestrator._common._repository_metadata() == {
        "available": False,
        "commit": None,
        "dirty": None,
    }


def test_repository_metadata_records_a_clean_repository(monkeypatch):
    orchestrator = load_orchestrator()
    responses = iter(["a" * 40, ""])
    monkeypatch.setattr(
        orchestrator._common,
        "_run_metadata_command",
        lambda *_args, **_kwargs: next(responses),
    )

    assert orchestrator._common._repository_metadata() == {
        "available": True,
        "commit": "a" * 40,
        "dirty": False,
    }


@pytest.mark.parametrize(
    ("marker", "directory"),
    [("AGENTS.md", False), (".git", True), (".codex/config.toml", False)],
)
def test_validate_session_root_rejects_project_instruction_ancestors(
    tmp_path,
    marker,
    directory,
):
    orchestrator = load_orchestrator()
    root = tmp_path / "session-root"
    root.mkdir()
    marker_path = root / marker
    if directory:
        marker_path.mkdir()
    else:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match="isolated"):
        orchestrator.validate_isolated_session_root(root)


def test_validate_session_root_rejects_repository_root():
    orchestrator = load_orchestrator()

    with pytest.raises(ValueError, match="isolated"):
        orchestrator.validate_isolated_session_root(orchestrator.REPO_ROOT)


def test_temporary_player_codex_home_copies_only_auth_and_removes_it(tmp_path):
    orchestrator = load_orchestrator()
    auth_home = tmp_path / "auth-home"
    auth_home.mkdir()
    (auth_home / "auth.json").write_text(
        '{"token":"fixture"}',
        encoding="utf-8",
    )
    (auth_home / "config.toml").write_text(
        'model = "leak"\n',
        encoding="utf-8",
    )

    with orchestrator.temporary_player_codex_home(auth_home) as player_home:
        assert (player_home / "auth.json").read_text(encoding="utf-8") == (
            '{"token":"fixture"}'
        )
        assert not (player_home / "config.toml").exists()
    assert not player_home.exists()


def test_write_player_codex_config_is_complete_and_has_no_repo_command(tmp_path):
    orchestrator = load_orchestrator()

    config_path = orchestrator.write_player_codex_config(
        tmp_path,
        model="gpt-test",
        reasoning_effort="high",
        mcp_url="http://127.0.0.1:8766/mcp",
    )

    text = config_path.read_text(encoding="utf-8")
    assert 'model = "gpt-test"' in text
    assert 'model_reasoning_effort = "high"' in text
    assert "developer_instructions = " in text
    assert "比较当前截图与本会话之前由 observe 或 act 返回的截图" in text
    assert "不要为了刷新画面重复调用 observe" in text
    assert "像人类玩家一样" in text
    assert 'url = "http://127.0.0.1:8766/mcp"' in text
    assert (
        'enabled_tools = ["briefing", "workflow_memory_read", "observe", '
        '"act", "workflow_memory_update"]'
    ) in text
    assert "generate_memories = false" in text
    assert "use_memories = false" in text
    assert 'web_search = "disabled"' in text
    assert 'cli_auth_credentials_store = "file"' in text
    assert 'mcp_oauth_credentials_store = "file"' in text
    assert 'default_permissions = "ai_play_player"' in text
    assert '":minimal" = "read"' in text
    assert '"." = "read"' in text
    assert "[permissions.ai_play_player.network]\nenabled = true" in text
    assert (
        '[permissions.ai_play_player.network.domains]\n"127.0.0.1" = "allow"'
        in text
    )
    assert '"*" = "allow"' not in text
    assert "[windows]" in text
    assert 'sandbox = "elevated"' in text
    assert (
        f'{json.dumps(str(tmp_path.resolve()), ensure_ascii=False)} = "deny"'
        in text
    )
    assert "start_ai.sh" not in text
    assert str(orchestrator.REPO_ROOT) not in text


def test_write_player_codex_config_can_disable_workflow_memory_tools(tmp_path):
    orchestrator = load_orchestrator()

    config_path = orchestrator.write_player_codex_config(
        tmp_path,
        model="gpt-test",
        reasoning_effort="high",
        mcp_url="http://127.0.0.1:8766/mcp",
        workflow_memory_enabled=False,
    )

    text = config_path.read_text(encoding="utf-8")
    assert 'enabled_tools = ["briefing", "observe", "act"]' in text
    assert "workflow_memory_read" not in text
    assert "workflow_memory_update" not in text


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--model", "gpt-test"],
        ["--reasoning-effort", "high"],
    ],
)
def test_parse_args_requires_model_and_reasoning_effort(argv):
    orchestrator = load_orchestrator()

    with pytest.raises(SystemExit) as error:
        orchestrator.parse_args(argv)

    assert error.value.code == 2


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--model", ""),
        ("--model", "gpt-test\ninvalid"),
        ("--reasoning-effort", "\t"),
        ("--reasoning-effort", "high\ninvalid"),
    ],
)
def test_main_rejects_unsafe_model_arguments_before_creating_run_paths(
    monkeypatch,
    tmp_path,
    option,
    value,
):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(
        orchestrator,
        "create_run_paths",
        lambda *args, **kwargs: pytest.fail("run paths must not be created"),
    )
    other_option = (
        ["--reasoning-effort", "high"]
        if option == "--model"
        else ["--model", "gpt-test"]
    )

    with pytest.raises(SystemExit, match="must not be empty or contain whitespace"):
        orchestrator.main(
            [
                "--session-root",
                str(tmp_path / "runs"),
                "--codex-auth-home",
                str(tmp_path / "auth-home"),
                option,
                value,
                *other_option,
            ]
        )


def test_main_rejects_unknown_scenario_before_external_setup(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )
    monkeypatch.setattr(
        orchestrator,
        "resolve_codex_bin",
        lambda _command: pytest.fail("Codex must not be resolved"),
    )
    monkeypatch.setattr(
        orchestrator,
        "create_run_paths",
        lambda *args, **kwargs: pytest.fail("run paths must not be created"),
    )

    with pytest.raises(SystemExit, match="unsupported AI Play scenario"):
        orchestrator.main([
            "--session-root",
            str(tmp_path / "runs"),
            "--codex-auth-home",
            str(tmp_path / "auth-home"),
            "--model",
            "gpt-test",
            "--reasoning-effort",
            "high",
            "--scenario",
            "unknown",
        ])


def test_build_player_env_drops_game_and_secret_environment(tmp_path):
    orchestrator = load_orchestrator()

    env = orchestrator.build_player_env(
        tmp_path / "player-home",
        base_env={
            "PATH": "C:/safe-bin",
            "PATHEXT": ".COM;.EXE;.BAT;.CMD",
            "SystemRoot": "C:/Windows",
            "OPENAI_API_KEY": "secret",
            "AI_PLAY_LOG_ROOT": "C:/logs",
            "PYTHONPATH": "C:/repo/ai_play/src",
            "HTTPS_PROXY": "http://proxy",
        },
    )

    assert env["CODEX_HOME"] == str(tmp_path / "player-home")
    assert env["PATH"] == "C:/safe-bin"
    assert env["PATHEXT"] == ".COM;.EXE;.BAT;.CMD"
    assert "OPENAI_API_KEY" not in env
    assert "AI_PLAY_LOG_ROOT" not in env
    assert "PYTHONPATH" not in env
    assert "HTTPS_PROXY" not in env
    assert env["NO_PROXY"] == "127.0.0.1,localhost"
    assert env["no_proxy"] == "127.0.0.1,localhost"


def test_build_player_env_normalizes_windows_path_casing(tmp_path):
    orchestrator = load_orchestrator()

    env = orchestrator.build_player_env(
        tmp_path / "player-home",
        base_env={"Path": "C:/safe-bin", "SystemRoot": "C:/Windows"},
    )

    assert env["PATH"] == "C:/safe-bin"
    assert "Path" not in env


def test_build_trusted_mcp_env_has_bridge_and_log_but_no_player_credentials(
    tmp_path,
):
    orchestrator = load_orchestrator()

    env = orchestrator.build_trusted_mcp_env(
        log_root=tmp_path / "trusted_mcplogs",
        ws_port=8765,
        base_env={"PATH": "C:/safe-bin", "OPENAI_API_KEY": "secret"},
    )

    assert env["AI_PLAY_WS_HOST"] == "127.0.0.1"
    assert env["AI_PLAY_WS_PORT"] == "8765"
    assert env["AI_PLAY_LOG_ROOT"] == str(tmp_path / "trusted_mcplogs")
    assert env["PYTHONPATH"] == str(orchestrator.REPO_ROOT / "ai_play" / "src")
    assert "OPENAI_API_KEY" not in env


def test_build_trusted_mcp_env_can_enable_resumable_workflow_memory(tmp_path):
    orchestrator = load_orchestrator()
    checkpoint = tmp_path / "trusted_mcplogs" / "workflow_memory.json"

    env = orchestrator.build_trusted_mcp_env(
        log_root=tmp_path / "trusted_mcplogs",
        ws_port=8765,
        base_env={"PATH": "/safe-bin"},
        workflow_memory_path=checkpoint,
    )

    assert env["AI_PLAY_WORKFLOW_MEMORY_PATH"] == str(checkpoint)


def test_build_supervisor_env_provides_isolated_godot_user_directories(tmp_path):
    orchestrator = load_orchestrator()

    env = orchestrator.build_supervisor_env(
        tmp_path / "godot-environment",
        base_env={
            "PATH": "/safe-bin",
            "HOME": "/host-home",
            "TMPDIR": "/host-tmp",
            "OPENAI_API_KEY": "secret",
        },
    )

    environment_root = tmp_path / "godot-environment"
    assert env["PATH"] == "/safe-bin"
    assert env["HOME"] == str(environment_root / "home")
    assert env["USERPROFILE"] == str(environment_root / "home")
    assert env["APPDATA"] == str(environment_root / "appdata")
    assert env["LOCALAPPDATA"] == str(environment_root / "localappdata")
    assert env["TEMP"] == str(environment_root / "tmp")
    assert env["TMP"] == str(environment_root / "tmp")
    assert env["TMPDIR"] == str(environment_root / "tmp")
    assert "OPENAI_API_KEY" not in env
    assert all(
        path.is_dir()
        for path in (
            environment_root / "home",
            environment_root / "appdata",
            environment_root / "localappdata",
            environment_root / "tmp",
        )
    )


def test_blackbox_commands_and_prompt_do_not_reveal_repo_or_scenario(tmp_path):
    orchestrator = load_orchestrator()

    mcp_command = orchestrator.build_mcp_command("python", 8766)
    codex_command = orchestrator.build_codex_command("codex", tmp_path / "workspace")
    prompt = orchestrator.build_player_prompt(runs=3)

    assert mcp_command == [
        "python",
        "-m",
        "ai_play.mcp_server",
        "--transport",
        "streamable-http",
        "--http-host",
        "127.0.0.1",
        "--http-port",
        "8766",
    ]
    assert "--sandbox" not in codex_command
    assert "start_ai.sh" not in " ".join(codex_command)
    assert "find_contract" not in prompt
    assert "ai_play_run_config.json" not in prompt
    assert str(orchestrator.REPO_ROOT) not in prompt
    for scenario_specific_hint in (
        "花园",
        "中央广场",
        "水壶",
        "向日葵",
        "绣球花",
        "兰花",
        "草坪",
        "门铃",
        "密码",
    ):
        assert scenario_specific_hint not in prompt


def test_blackbox_prompt_waits_for_all_runs_without_log_access(tmp_path):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(runs=3)

    assert "不要输出最终回答" in prompt
    assert "继续调用 observe" in prompt
    assert "stopped 表示操作者主动中止整次运行" in prompt
    assert "ai_play_log_root" not in prompt
    assert "public_mcp_log_root" not in prompt
    assert "trajectory.json" not in prompt
    assert "run.json" not in prompt
    assert "不得读取任何本地轨迹或截图文件" in prompt


@pytest.mark.parametrize("workflow_memory_enabled", [False, True])
def test_player_prompt_can_rotate_after_one_terminal(workflow_memory_enabled):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(
        runs=3,
        workflow_memory_enabled=workflow_memory_enabled,
        rotate_after_terminal=True,
    )

    assert "完整会话总共需要完成 3 次独立游玩" in prompt
    assert "当前 Codex turn 只负责下一个正式终局" in prompt
    assert "正式 success 或 failure" in prompt
    assert "结束当前 Codex turn" in prompt
    assert "完成全部 3 次独立游玩前，不要输出最终回答" not in prompt
    if workflow_memory_enabled:
        assert "workflow_memory_update 成功返回后" in prompt
    else:
        assert "workflow_memory_update" not in prompt


def test_blackbox_prompt_requires_public_step_memory(tmp_path):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(runs=3)

    assert "每一步都先写一段公开决策记录" in prompt
    assert "当前 goal 是什么" in prompt
    assert "workflow memory" in prompt
    assert "最新 observe 或 act 截图显示了什么" in prompt
    assert "主动 Keep 这份 memory" in prompt


def test_player_developer_instructions_authorize_visual_comparison_only():
    orchestrator = load_orchestrator()

    instructions = orchestrator.build_player_developer_instructions()

    assert "briefing" in instructions
    assert "游戏规则" in instructions
    assert "比较当前截图与本会话之前由 observe 或 act 返回的截图" in instructions
    assert "相对位移、转向、遮挡变化和地标关系" in instructions
    assert '{"type":"look","yaw":-30,"pitch":0}' in instructions
    assert "yaw 为负数时左转" in instructions
    assert "地标的位置、大小与遮挡变化" in instructions
    assert "第一张图片" in instructions
    assert "JPEG" in instructions
    assert "如果返回第二张图片" in instructions
    assert "PNG" in instructions
    assert "越暗表示越近" in instructions
    assert "白色" in instructions
    assert "磁盘" in instructions
    assert "隐藏状态" in instructions
    assert "青绿色或蓝绿色的独立标志" in instructions
    assert "同心圆、靶心或旋涡状发光圆环" in instructions
    assert "每次水平旋转 45 度" in instructions
    assert "最多覆盖 360 度" in instructions
    assert "截图没有随公开朝向变化" in instructions
    assert "用短步靠近" in instructions
    assert "远距离的 not_found 不能作为排除依据" in instructions
    assert "读取任务卡前不得离开出生区域" in instructions
    assert "首张截图已经出现该标志时，不要开始 45 度整圈扫描" in instructions
    assert "每次只向标志方向转 5 到 15 度" in instructions
    assert "不要把附近门的 Open 提示误认为任务卡" in instructions


@pytest.mark.parametrize("workflow_memory_enabled", [False, True])
def test_player_prompt_teaches_identical_signed_axis_look_control(workflow_memory_enabled):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(
        runs=3,
        workflow_memory_enabled=workflow_memory_enabled,
    )

    assert "yaw、pitch" in prompt
    assert '"yaw":-30,"pitch":0' in prompt
    assert "比较当前截图与本会话之前由 observe 或 act 返回的截图" in prompt
    assert "成功的 act 返回下一份观察" in prompt
    assert "movement_feedback" in prompt


@pytest.mark.parametrize("workflow_memory_enabled", [False, True])
def test_player_prompt_prioritizes_nearby_task_card_before_leaving_spawn(
    workflow_memory_enabled,
):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(
        runs=3,
        workflow_memory_enabled=workflow_memory_enabled,
    )

    assert "briefing 要求先读取出生点附近任务卡" in prompt
    assert "离开出生区域前" in prompt
    assert "probe 专用单动作分支调用 act" in prompt
    assert 'actions=[{"type":"probe_interaction"' in prompt


@pytest.mark.parametrize("workflow_memory_enabled", [False, True])
def test_player_prompt_scales_movement_to_navigation_risk(workflow_memory_enabled):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(
        runs=3,
        workflow_memory_enabled=workflow_memory_enabled,
    )

    assert "开阔、方向明确的路线" in prompt
    assert "满强度 move 150 到 250ms" in prompt
    assert "单轴 0.2 到 0.6" in prompt
    assert "50 到 100ms" in prompt
    assert "连续两次同方向移动都未受阻" in prompt
    assert "不要继续用相同或更小步幅逐帧确认" in prompt
    assert "楼梯对齐且公开玩家高度持续变化" in prompt
    assert "先转向 15 到 30 度重新对齐" in prompt
    assert "再选择与路线风险相称的移动或转身" in prompt
    assert "再小步移动或转身" not in prompt


def test_player_prompt_requires_awm_lifecycle(tmp_path):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(runs=3)

    assert "briefing，再调用 workflow_memory_read，再调用 observe" in prompt
    assert "终局后调用 workflow_memory_update" in prompt
    assert "成功局" in prompt
    assert "失败局的 workflow 和 landmarks 必须为空" in prompt
    assert "以 workflow_memory_read 返回的 completed_runs 为准" in prompt
    assert "异常重试不算完成一局" in prompt
    assert "不要保存图片" in prompt
    assert "不要保存局内具体答案" in prompt


def test_player_prompt_requires_failure_reflection_loop():
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(runs=2)

    assert "failure_review" in prompt
    assert "stage、bottlenecks 和 optimizations" in prompt
    assert "失败局的 workflow 和 landmarks 必须为空" in prompt
    assert "最新 briefing 和 observe" in prompt
    assert "说明哪些优化适用" in prompt
    assert "如何改变当前计划" in prompt
    assert "随机答案" in prompt


def test_player_prompt_without_awm_uses_only_in_context_notes():
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(
        runs=3,
        workflow_memory_enabled=False,
    )

    assert "briefing，再调用 observe" in prompt
    assert "workflow_memory_read" not in prompt
    assert "workflow_memory_update" not in prompt
    assert "failure_review" not in prompt
    assert "failure_reviews" not in prompt
    assert "普通会话上下文" in prompt


def test_loop_staircase_prompt_distinguishes_room_floor_and_board_actions():
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(
        runs=3,
        scenario="loop_staircase_anomaly",
    )

    assert "press_key" not in prompt
    assert "front/back/left/right" in prompt
    assert "small=80ms" in prompt
    assert "large=180ms" in prompt
    assert "floor_up/floor_down" in prompt
    assert "toggle_board" in prompt
    assert "board_up/board_down" in prompt
    assert "toggle_mark" in prompt
    assert "submit_floor" in prompt
    assert "不要使用 move 或 sprint" in prompt


def test_resolve_codex_bin_resolves_path_shim_symlink(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    executable = tmp_path / "releases" / "codex"
    executable.parent.mkdir()
    executable.write_text("", encoding="utf-8")
    shim = tmp_path / "bin" / "codex"
    shim.parent.mkdir()
    shim.symlink_to(executable)
    monkeypatch.setattr(
        orchestrator.shutil,
        "which",
        lambda command: str(shim) if command == "codex" else None,
    )

    result = orchestrator.resolve_codex_bin("codex")

    assert result == str(executable)


def test_parse_args_exposes_only_hardened_player_options():
    orchestrator = load_orchestrator()

    args = orchestrator.parse_args(
        ["--model", "gpt-test", "--reasoning-effort", "high"]
    )

    assert args.codex_auth_home == orchestrator.DEFAULT_CODEX_AUTH_HOME
    assert args.mcp_port == 8766
    assert args.timeout_seconds == 100000.0
    assert args.idle_timeout_seconds == 600.0
    assert args.codex_final_grace_seconds == 30.0
    assert args.workflow_memory == "enabled"
    assert not hasattr(args, "sandbox")
    assert not hasattr(args, "approval_policy")
    assert not hasattr(args, "codex_home")


@pytest.mark.parametrize(
    "legacy_option",
    ["--codex-home", "--sandbox", "--approval-policy", "--ws-port"],
)
def test_parse_args_rejects_legacy_player_boundary_options(legacy_option):
    orchestrator = load_orchestrator()

    with pytest.raises(SystemExit) as error:
        orchestrator.parse_args(
            [
                "--model",
                "gpt-test",
                "--reasoning-effort",
                "high",
                legacy_option,
                "9000" if legacy_option == "--ws-port" else "value",
            ]
        )

    assert error.value.code == 2


def test_main_rejects_matching_mcp_and_bridge_ports_before_creating_run_paths(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(
        orchestrator,
        "create_run_paths",
        lambda *args, **kwargs: pytest.fail("run paths must not be created"),
    )
    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )

    with pytest.raises(SystemExit, match="must differ"):
        orchestrator.main(
            [
                "--session-root",
                str(tmp_path / "runs"),
                "--codex-auth-home",
                str(tmp_path / "auth-home"),
                "--model",
                "gpt-test",
                "--reasoning-effort",
                "high",
                "--mcp-port",
                "8765",
            ]
        )


class FakeProcess:
    def __init__(self, return_codes=None):
        self._return_codes = list(return_codes or [])
        self.returncode = None
        self.stdout = io.StringIO()
        self.terminated = False
        self.killed = False

    def poll(self):
        if self._return_codes:
            self.returncode = self._return_codes.pop(0)
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


def test_session_starts_trusted_mcp_before_codex_and_supervisor(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    started = []
    processes = {
        "mcp": FakeProcess(),
        "codex": FakeProcess(),
        "supervisor": FakeProcess(return_codes=[0]),
    }
    monkeypatch.setattr(
        orchestrator._common,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: (
            started.append(label) or processes[label]
        ),
    )
    monkeypatch.setattr(
        orchestrator._common,
        "wait_for_listener",
        lambda *args, **kwargs: True,
    )

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python", "-m", "ai_play.mcp_server"],
        player_label="codex",
        player_command=["codex", "exec"],
        supervisor_command=["python", "supervisor.py"],
        prompt="briefing",
        mcp_env={},
        player_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        player_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        player_exit_grace_seconds=0.0,
        idle_timeout_seconds=10.0,
        player_final_grace_seconds=0.0,
    )

    assert result == 0
    assert started == ["mcp", "codex", "supervisor"]
    assert processes["codex"].terminated
    assert processes["mcp"].terminated


def test_session_starts_provider_proxy_before_mcp_codex_and_supervisor(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    started = []
    processes = {
        "provider-proxy": FakeProcess(),
        "mcp": FakeProcess(),
        "codex": FakeProcess(),
        "supervisor": FakeProcess(return_codes=[0]),
    }
    monkeypatch.setattr(
        orchestrator._common,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: (
            started.append(label) or processes[label]
        ),
    )
    monkeypatch.setattr(
        orchestrator._common,
        "wait_for_listener",
        lambda *args, **kwargs: True,
    )

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python", "mcp.py"],
        player_label="codex",
        player_command=["codex", "exec"],
        supervisor_command=["python", "supervisor.py"],
        prompt="briefing",
        mcp_env={},
        player_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        player_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        player_exit_grace_seconds=0.0,
        idle_timeout_seconds=10.0,
        player_final_grace_seconds=0.0,
        provider_proxy_command=["python", "proxy.py"],
        provider_proxy_env={},
        provider_proxy_cwd=tmp_path,
        provider_proxy_port=8767,
    )

    assert result == 0
    assert started == ["provider-proxy", "mcp", "codex", "supervisor"]
    assert processes["provider-proxy"].terminated


def test_provider_proxy_readiness_failure_starts_no_other_process(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    started = []
    provider_proxy = FakeProcess()
    monkeypatch.setattr(
        orchestrator._common,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: (
            started.append(label) or provider_proxy
        ),
    )
    monkeypatch.setattr(
        orchestrator._common,
        "wait_for_listener",
        lambda *args, **kwargs: False,
    )

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python", "mcp.py"],
        player_label="codex",
        player_command=["codex", "exec"],
        supervisor_command=["python", "supervisor.py"],
        prompt="briefing",
        mcp_env={},
        player_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        player_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        player_exit_grace_seconds=0.0,
        idle_timeout_seconds=10.0,
        player_final_grace_seconds=0.0,
        provider_proxy_command=["python", "proxy.py"],
        provider_proxy_env={},
        provider_proxy_cwd=tmp_path,
        provider_proxy_port=8767,
    )

    assert result == 4
    assert started == ["provider-proxy"]
    assert provider_proxy.terminated


def test_session_allows_codex_to_finish_after_supervisor_terminal_exit(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    processes = {
        "mcp": FakeProcess(),
        "codex": FakeProcess(return_codes=[None, None, 0]),
        "supervisor": FakeProcess(return_codes=[0]),
    }
    monkeypatch.setattr(
        orchestrator._common,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: processes[label],
    )
    monkeypatch.setattr(
        orchestrator._common,
        "wait_for_listener",
        lambda *args, **kwargs: True,
    )

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python"],
        player_label="codex",
        player_command=["codex"],
        supervisor_command=["supervisor"],
        prompt="briefing",
        mcp_env={},
        player_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        player_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        player_exit_grace_seconds=0.0,
        idle_timeout_seconds=10.0,
        player_final_grace_seconds=1.0,
    )

    assert result == 0
    assert not processes["codex"].terminated
    assert processes["mcp"].terminated


def test_session_restarts_clean_player_until_supervisor_terminal_without_limit(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    started = []
    player_prompts = []
    mcp = FakeProcess()
    supervisor = FakeProcess(return_codes=[None, None, None, 0])
    players = iter(
        [
            FakeProcess(return_codes=[None, 0]),
            FakeProcess(return_codes=[0]),
            FakeProcess(return_codes=[0]),
            FakeProcess(),
        ]
    )

    def fake_start(label, command, cwd, env, stdin_text=None):
        started.append(label)
        if label == "mcp":
            return mcp
        if label == "supervisor":
            return supervisor
        player_prompts.append(stdin_text)
        return next(players)

    monkeypatch.setattr(orchestrator._common, "_start_process", fake_start)
    monkeypatch.setattr(
        orchestrator._common,
        "_start_output_reader",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        orchestrator._common,
        "wait_for_listener",
        lambda *args, **kwargs: True,
    )

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python"],
        player_label="codex",
        player_command=["codex"],
        supervisor_command=["supervisor"],
        prompt="play until a formal terminal",
        mcp_env={},
        player_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        player_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        player_exit_grace_seconds=0.0,
        idle_timeout_seconds=10.0,
        player_final_grace_seconds=0.0,
        player_restart_limit=None,
        player_restart_prompt="resume the same active attempt",
    )

    assert result == 0
    assert started == [
        "mcp",
        "codex",
        "supervisor",
        "codex",
        "codex",
        "codex",
    ]
    assert player_prompts == [
        "play until a formal terminal",
        "resume the same active attempt",
        "resume the same active attempt",
        "resume the same active attempt",
    ]


def test_session_can_stop_player_immediately_after_supervisor_terminal_exit(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    processes = {
        "mcp": FakeProcess(),
        "codex-doubao": FakeProcess(),
        "supervisor": FakeProcess(return_codes=[0]),
    }
    monkeypatch.setattr(
        orchestrator._common,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: processes[label],
    )
    monkeypatch.setattr(
        orchestrator._common,
        "wait_for_listener",
        lambda *args, **kwargs: True,
    )

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python"],
        player_label="codex-doubao",
        player_command=["codex"],
        supervisor_command=["supervisor"],
        prompt="briefing",
        mcp_env={},
        player_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        player_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        player_exit_grace_seconds=0.0,
        idle_timeout_seconds=10.0,
        player_final_grace_seconds=1000.0,
        stop_player_on_supervisor_exit=True,
    )

    assert result == 0
    assert processes["codex-doubao"].terminated
    assert processes["mcp"].terminated


def test_session_stops_when_all_children_are_idle(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    processes = {
        "mcp": FakeProcess(),
        "codex": FakeProcess(),
        "supervisor": FakeProcess(),
    }
    monotonic_values = iter([0.0, 11.0])
    monkeypatch.setattr(
        orchestrator._common,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: processes[label],
    )
    monkeypatch.setattr(
        orchestrator._common,
        "wait_for_listener",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        orchestrator._common.time,
        "monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr(orchestrator._common.time, "sleep", lambda _seconds: None)

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python"],
        player_label="codex",
        player_command=["codex"],
        supervisor_command=["supervisor"],
        prompt="briefing",
        mcp_env={},
        player_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        player_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        player_exit_grace_seconds=1.0,
        idle_timeout_seconds=10.0,
        player_final_grace_seconds=1.0,
    )

    assert result == 5
    assert all(process.terminated for process in processes.values())


def test_native_resume_limit_is_infrastructure_failure_without_game_over(
    monkeypatch,
    tmp_path,
    capsys,
):
    orchestrator = load_orchestrator()
    started = []
    processes = {
        "mcp": FakeProcess(),
        "codex-doubao": FakeProcess(return_codes=[None, 6]),
        "supervisor": FakeProcess(),
    }
    monkeypatch.setattr(
        orchestrator._common,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: (
            started.append(label) or processes[label]
        ),
    )
    monkeypatch.setattr(
        orchestrator._common,
        "wait_for_listener",
        lambda *args, **kwargs: True,
    )

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python"],
        player_label="codex-doubao",
        player_command=["codex"],
        supervisor_command=["supervisor"],
        prompt="briefing",
        mcp_env={},
        player_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        player_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        player_exit_grace_seconds=0.0,
        idle_timeout_seconds=10.0,
        player_final_grace_seconds=0.0,
        player_restart_limit=0,
    )

    assert result == 6
    assert started.count("codex-doubao") == 1
    assert processes["supervisor"].terminated
    assert "game_over" not in capsys.readouterr().out


def test_sidecar_readiness_failure_never_starts_codex_or_supervisor(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    started = []
    mcp = FakeProcess()
    monkeypatch.setattr(
        orchestrator._common,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: started.append(label) or mcp,
    )
    monkeypatch.setattr(
        orchestrator._common,
        "wait_for_listener",
        lambda *args, **kwargs: False,
    )

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python"],
        player_label="codex",
        player_command=["codex"],
        supervisor_command=["supervisor"],
        prompt="briefing",
        mcp_env={},
        player_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        player_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        player_exit_grace_seconds=0.0,
        idle_timeout_seconds=10.0,
        player_final_grace_seconds=0.0,
    )

    assert result == 4
    assert started == ["mcp"]
    assert mcp.terminated


def test_codex_early_exit_terminates_trusted_mcp(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    processes = {
        "mcp": FakeProcess(),
        "codex": FakeProcess(return_codes=[17]),
    }
    monkeypatch.setattr(
        orchestrator._common,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: processes[label],
    )
    monkeypatch.setattr(
        orchestrator._common,
        "wait_for_listener",
        lambda *args, **kwargs: True,
    )

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python"],
        player_label="codex",
        player_command=["codex"],
        supervisor_command=["supervisor"],
        prompt="briefing",
        mcp_env={},
        player_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        player_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        player_exit_grace_seconds=0.0,
        idle_timeout_seconds=10.0,
        player_final_grace_seconds=0.0,
    )

    assert result == 17
    assert processes["mcp"].terminated


def test_keyboard_interrupt_terminates_all_started_processes(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    processes = {
        "mcp": FakeProcess(),
        "codex": FakeProcess(),
        "supervisor": FakeProcess(),
    }
    monkeypatch.setattr(
        orchestrator._common,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: processes[label],
    )
    monkeypatch.setattr(
        orchestrator._common,
        "wait_for_listener",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        orchestrator._common,
        "_print_available_output",
        lambda outputs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        orchestrator.run_orchestrated_session(
            mcp_command=["python"],
            player_label="codex",
            player_command=["codex"],
            supervisor_command=["supervisor"],
            prompt="briefing",
            mcp_env={},
            player_env={},
            supervisor_env={},
            mcp_cwd=tmp_path,
            player_cwd=tmp_path,
            supervisor_cwd=tmp_path,
            ws_port=8765,
            mcp_port=8766,
            mcp_start_timeout_seconds=1.0,
            player_exit_grace_seconds=0.0,
            idle_timeout_seconds=10.0,
            player_final_grace_seconds=0.0,
        )

    assert processes["supervisor"].terminated
    assert processes["codex"].terminated
    assert processes["mcp"].terminated


def test_main_removes_temporary_codex_home_after_session(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    auth_home = tmp_path / "auth-home"
    auth_home.mkdir()
    (auth_home / "auth.json").write_text("fixture", encoding="utf-8")
    captured = {}
    monkeypatch.setattr(orchestrator, "is_port_listening", lambda *args: False)
    monkeypatch.setattr(
        orchestrator,
        "resolve_codex_bin",
        lambda codex_bin: "codex.exe",
    )
    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )
    monkeypatch.setattr(
        orchestrator,
        "run_orchestrated_session",
        lambda **kwargs: captured.update(
            player_home=Path(kwargs["player_env"]["CODEX_HOME"]),
            run_dir=Path(kwargs["player_cwd"]).parent,
        )
        or 0,
    )

    result = orchestrator.main(
        [
            "--session-root",
            str(tmp_path / "runs"),
            "--codex-auth-home",
            str(auth_home),
            "--model",
            "gpt-test",
            "--reasoning-effort",
            "high",
        ]
    )

    assert result == 0
    assert not captured["player_home"].exists()
    assert captured["run_dir"].name.endswith(
        "__codex__gpt-test__find_contract__awm"
    )
    metadata = json.loads(
        (captured["run_dir"] / "session.json").read_text(encoding="utf-8")
    )
    assert metadata["player"] == "codex"
    assert metadata["model"] == "gpt-test"
    assert metadata["reasoning_effort"] == "high"
    assert metadata["scenario"] == "find_contract"
    assert metadata["workflow_memory"] == "enabled"
    assert metadata["requested_runs"] == 3
    assert metadata["schema_version"] == 2
    assert metadata["repository"]["available"] is True
    assert len(metadata["repository"]["commit"]) == 40
    assert isinstance(metadata["repository"]["dirty"], bool)
    assert metadata["runtime"]["python"] != "unavailable"
    assert set(metadata["runtime"]["packages"]) == {
        "mcp", "pydantic", "websockets",
    }
    assert metadata["execution"]["ws_port"] == 8765
    assert metadata["execution"]["mcp_port"] == 8766
    assert metadata["benchmark"]["cycle_seed"] == (
        orchestrator.DEFAULT_BENCHMARK_CYCLE_SEED
    )
    assert len(metadata["benchmark"]["attempts"]) == 3
