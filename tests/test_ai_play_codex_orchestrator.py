import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_PATH = REPO_ROOT / "tools" / "ai_play_codex_orchestrator.py"


def load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "ai_play_codex_orchestrator",
        ORCHESTRATOR_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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

    paths = orchestrator.create_run_paths(tmp_path, timestamp="20260726-170000")

    assert list(paths.player_workspace.iterdir()) == []
    assert paths.log_root == paths.run_dir / "trusted_mcplogs"
    assert paths.log_root.is_dir()


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
    assert "[permissions.ai_play_player.network]\nenabled = false" in text
    assert "[windows]" in text
    assert 'sandbox = "elevated"' in text
    assert (
        f'{json.dumps(str(tmp_path.resolve()), ensure_ascii=False)} = "deny"'
        in text
    )
    assert "start_ai.sh" not in text
    assert str(orchestrator.REPO_ROOT) not in text


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


def test_blackbox_prompt_waits_for_all_runs_without_log_access(tmp_path):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(runs=3)

    assert "不要输出最终回答" in prompt
    assert "继续调用 observe" in prompt
    assert "ai_play_log_root" not in prompt
    assert "public_mcp_log_root" not in prompt
    assert "trajectory.json" not in prompt
    assert "run.json" not in prompt
    assert "不得读取任何本地轨迹或截图文件" in prompt


def test_blackbox_prompt_requires_public_step_memory(tmp_path):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(runs=3)

    assert "每一步都先写一段公开决策记录" in prompt
    assert "当前 goal 是什么" in prompt
    assert "workflow memory" in prompt
    assert "最新 observe 截图显示了什么" in prompt
    assert "主动 Keep 这份 memory" in prompt


def test_player_prompt_requires_awm_lifecycle(tmp_path):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(runs=3)

    assert "briefing，再调用 workflow_memory_read，再调用 observe" in prompt
    assert "终局后调用 workflow_memory_update" in prompt
    assert "成功局" in prompt
    assert "失败局只提交 avoid" in prompt
    assert "不要保存图片" in prompt
    assert "不要保存密码" in prompt


def test_resolve_codex_bin_uses_absolute_shim_path(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    resolved = tmp_path / "codex.cmd"
    monkeypatch.setattr(
        orchestrator.shutil,
        "which",
        lambda command: str(resolved) if command == "codex" else None,
    )

    result = orchestrator.resolve_codex_bin("codex")

    assert result == str(resolved)


def test_parse_args_exposes_only_hardened_player_options():
    orchestrator = load_orchestrator()

    args = orchestrator.parse_args(
        ["--model", "gpt-test", "--reasoning-effort", "high"]
    )

    assert args.codex_auth_home == orchestrator.DEFAULT_CODEX_AUTH_HOME
    assert args.mcp_port == 8766
    assert args.timeout_seconds == 100000.0
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
        orchestrator,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: (
            started.append(label) or processes[label]
        ),
    )
    monkeypatch.setattr(orchestrator, "wait_for_listener", lambda *args, **kwargs: True)

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python", "-m", "ai_play.mcp_server"],
        codex_command=["codex", "exec"],
        supervisor_command=["python", "supervisor.py"],
        prompt="briefing",
        mcp_env={},
        codex_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        codex_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        codex_exit_grace_seconds=0.0,
    )

    assert result == 0
    assert started == ["mcp", "codex", "supervisor"]
    assert processes["codex"].terminated
    assert processes["mcp"].terminated


def test_sidecar_readiness_failure_never_starts_codex_or_supervisor(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    started = []
    mcp = FakeProcess()
    monkeypatch.setattr(
        orchestrator,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: started.append(label) or mcp,
    )
    monkeypatch.setattr(orchestrator, "wait_for_listener", lambda *args, **kwargs: False)

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python"],
        codex_command=["codex"],
        supervisor_command=["supervisor"],
        prompt="briefing",
        mcp_env={},
        codex_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        codex_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        codex_exit_grace_seconds=0.0,
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
        orchestrator,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: processes[label],
    )
    monkeypatch.setattr(orchestrator, "wait_for_listener", lambda *args, **kwargs: True)

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python"],
        codex_command=["codex"],
        supervisor_command=["supervisor"],
        prompt="briefing",
        mcp_env={},
        codex_env={},
        supervisor_env={},
        mcp_cwd=tmp_path,
        codex_cwd=tmp_path,
        supervisor_cwd=tmp_path,
        ws_port=8765,
        mcp_port=8766,
        mcp_start_timeout_seconds=1.0,
        codex_exit_grace_seconds=0.0,
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
        orchestrator,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: processes[label],
    )
    monkeypatch.setattr(orchestrator, "wait_for_listener", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        orchestrator,
        "_print_available_output",
        lambda outputs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        orchestrator.run_orchestrated_session(
            mcp_command=["python"],
            codex_command=["codex"],
            supervisor_command=["supervisor"],
            prompt="briefing",
            mcp_env={},
            codex_env={},
            supervisor_env={},
            mcp_cwd=tmp_path,
            codex_cwd=tmp_path,
            supervisor_cwd=tmp_path,
            ws_port=8765,
            mcp_port=8766,
            mcp_start_timeout_seconds=1.0,
            codex_exit_grace_seconds=0.0,
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
            player_home=Path(kwargs["codex_env"]["CODEX_HOME"])
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
