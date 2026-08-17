import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_PATH = (
    REPO_ROOT / "tools" / "ai_play_codex_gemini_orchestrator.py"
)


def load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "tools.ai_play_codex_gemini_orchestrator",
        ORCHESTRATOR_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_yibu_credentials_reads_literal_without_executing_file(tmp_path):
    marker = tmp_path / "executed"
    source = tmp_path / "opus.py"
    source.write_text(
        'ak = {"key": "secret", "url": "https://yibuapi.com"}\n'
        f'open({str(marker)!r}, "w").write("bad")\n',
        encoding="utf-8",
    )

    credentials = load_orchestrator().load_yibu_credentials(source)

    assert credentials.api_key == "secret"
    assert credentials.base_url == "https://yibuapi.com/v1"
    assert not marker.exists()


def test_load_yibu_credentials_accepts_existing_v1_suffix(tmp_path):
    source = tmp_path / "opus.py"
    source.write_text(
        'ak = {"key": "secret", "url": "https://yibuapi.com/v1/"}\n',
        encoding="utf-8",
    )

    credentials = load_orchestrator().load_yibu_credentials(source)

    assert credentials.base_url == "https://yibuapi.com/v1"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("value = {}", "literal ak dictionary"),
        ("ak = {}", "key must be a non-empty string"),
        (
            'ak = {"key": "", "url": "https://yibuapi.com"}',
            "key must be a non-empty string",
        ),
        (
            'ak = {"key": "secret", "url": "http://yibuapi.com"}',
            "URL must use https",
        ),
        (
            'ak = {"key": "secret", "url": "https://user@yibuapi.com"}',
            "URL must not contain credentials",
        ),
        (
            'ak = {"key": dynamic_key, "url": "https://yibuapi.com"}',
            "literal ak dictionary",
        ),
    ],
)
def test_load_yibu_credentials_rejects_invalid_values(
    tmp_path,
    payload,
    message,
):
    source = tmp_path / "opus.py"
    source.write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_orchestrator().load_yibu_credentials(source)


def test_load_yibu_credentials_reports_missing_file(tmp_path):
    with pytest.raises(ValueError, match="missing yibu credential file"):
        load_orchestrator().load_yibu_credentials(tmp_path / "missing.py")


def test_write_player_config_uses_responses_provider_without_secret_or_effort(
    tmp_path,
):
    orchestrator = load_orchestrator()

    config_path = orchestrator.write_player_codex_gemini_config(
        tmp_path,
        model="gemini-3.6-flash",
        base_url="http://127.0.0.1:18767/v1",
        mcp_url="http://127.0.0.1:8766/mcp",
    )

    text = config_path.read_text(encoding="utf-8")
    assert 'model = "gemini-3.6-flash"' in text
    assert 'model_provider = "yibu"' in text
    assert "model_reasoning_effort" not in text
    assert "model_supports_reasoning_summaries = false" in text
    assert '[model_providers.yibu]' in text
    assert 'base_url = "http://127.0.0.1:18767/v1"' in text
    assert 'env_key = "YIBU_API_KEY"' in text
    assert 'wire_api = "responses"' in text
    assert "secret" not in text
    assert "developer_instructions = " in text
    assert "比较当前截图与本会话之前由 observe 或 act 返回的截图" in text
    assert 'url = "http://127.0.0.1:8766/mcp"' in text
    assert (
        'enabled_tools = ["briefing", "workflow_memory_read", "observe", '
        '"act", "workflow_memory_update"]'
    ) in text
    assert 'web_search = "disabled"' in text
    assert "[features]" in text
    assert "shell_tool = false" in text
    assert "unified_exec = false" in text
    assert "apps = false" in text
    assert "goals = false" in text
    assert "multi_agent = false" in text
    assert "plugins = false" in text
    assert "tool_suggest = false" in text
    assert "[tools]" in text
    assert "view_image = false" in text
    assert 'default_permissions = "ai_play_player"' in text
    assert '":minimal" = "read"' in text
    assert '"." = "read"' in text
    assert (
        '[permissions.ai_play_player.network.domains]\n"127.0.0.1" = "allow"'
        in text
    )
    assert '"*" = "allow"' not in text
    assert (
        f'{json.dumps(str(tmp_path.resolve()), ensure_ascii=False)} = "deny"'
        in text
    )
    assert str(orchestrator.REPO_ROOT) not in text


def test_write_player_config_can_disable_workflow_memory_tools(tmp_path):
    orchestrator = load_orchestrator()

    config_path = orchestrator.write_player_codex_gemini_config(
        tmp_path,
        model="gemini-3.6-flash",
        base_url="http://127.0.0.1:18767/v1",
        mcp_url="http://127.0.0.1:8766/mcp",
        workflow_memory_enabled=False,
    )

    text = config_path.read_text(encoding="utf-8")
    assert 'enabled_tools = ["briefing", "observe", "act"]' in text
    assert "workflow_memory_read" not in text
    assert "workflow_memory_update" not in text


def test_build_player_env_injects_only_yibu_key(tmp_path):
    orchestrator = load_orchestrator()

    env = orchestrator.build_player_env(
        tmp_path / "player-home",
        "secret",
        base_env={
            "PATH": "/safe-bin",
            "OPENAI_API_KEY": "drop",
            "ANTHROPIC_AUTH_TOKEN": "drop",
            "AI_PLAY_LOG_ROOT": "/logs",
            "HTTPS_PROXY": "http://proxy",
        },
    )

    assert env["CODEX_HOME"] == str(tmp_path / "player-home")
    assert env["PATH"] == "/safe-bin"
    assert env["YIBU_API_KEY"] == "secret"
    assert "OPENAI_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert "AI_PLAY_LOG_ROOT" not in env
    assert "HTTPS_PROXY" not in env
    assert env["NO_PROXY"] == "127.0.0.1,localhost"


def test_temporary_player_codex_home_is_empty_and_removed():
    orchestrator = load_orchestrator()

    with orchestrator.temporary_player_codex_home() as player_home:
        assert player_home.is_dir()
        assert list(player_home.iterdir()) == []

    assert not player_home.exists()


def test_parse_args_defaults_to_gemini_flash_without_reasoning_option():
    orchestrator = load_orchestrator()

    args = orchestrator.parse_args([])

    assert args.model == "gemini-3.6-flash"
    assert args.runs == 3
    assert args.scenario == "find_contract"
    assert args.yibu_credentials == orchestrator.REPO_ROOT / "opus.py"
    assert args.workflow_memory == "enabled"
    assert args.provider_proxy_port == 18767
    assert args.codex_max_restarts == 2
    assert not hasattr(args, "reasoning_effort")


def test_build_player_restart_prompt_recovers_public_state_for_awm_modes():
    orchestrator = load_orchestrator()

    enabled = orchestrator.build_player_restart_prompt(3, True)
    disabled = orchestrator.build_player_restart_prompt(3, False)

    assert "同一 MCP 与 AWM 会话中的恢复 turn" in enabled
    assert "workflow_memory_read、briefing、observe" in enabled
    assert "completed_runs" in enabled
    assert "workflow_memory_read" not in disabled
    assert "briefing、observe" in disabled


def test_build_provider_proxy_command_uses_exact_tool_whitelist():
    orchestrator = load_orchestrator()

    command = orchestrator.build_provider_proxy_command(
        python_bin="python",
        port=18767,
        upstream_base_url="https://yibuapi.com/v1",
        workflow_memory_enabled=False,
    )

    assert command[:2] == [
        "python",
        str(orchestrator.RESPONSES_NAMESPACE_PROXY_PATH),
    ]
    assert "127.0.0.1" in command
    assert "https://yibuapi.com/v1" in command
    assert "mcp__cogito_ai_play" in command
    allowed = [
        command[index + 1]
        for index, value in enumerate(command)
        if value == "--allowed-tool"
    ]
    assert allowed == ["briefing", "observe", "act"]


def test_write_player_config_rejects_non_loopback_provider_url(tmp_path):
    orchestrator = load_orchestrator()

    with pytest.raises(ValueError, match="loopback provider URL"):
        orchestrator.write_player_codex_gemini_config(
            tmp_path,
            model="gemini-3.6-flash",
            base_url="https://yibuapi.com/v1",
            mcp_url="http://127.0.0.1:8766/mcp",
        )


def test_parse_args_rejects_reasoning_effort_option():
    orchestrator = load_orchestrator()

    with pytest.raises(SystemExit) as error:
        orchestrator.parse_args(["--reasoning-effort", "high"])

    assert error.value.code == 2


def test_entry_reuses_scene_and_mcp_contracts():
    orchestrator = load_orchestrator()

    assert orchestrator.DEFAULT_WS_HOST == "127.0.0.1"
    assert orchestrator.DEFAULT_WS_PORT == 8765
    assert orchestrator.DEFAULT_MCP_PORT == 8766
    assert orchestrator.resolve_scene("find_contract", None) == (
        orchestrator.DEFAULT_SCENE
    )
    assert orchestrator.resolve_scene("conveyor_profit", None) == (
        "conveyor_profit/scenes/conveyor_profit_preview.tscn"
    )


def test_main_rejects_unsafe_model_before_reading_credentials(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(
        orchestrator,
        "load_yibu_credentials",
        lambda _source: pytest.fail("credentials must not be read"),
    )
    monkeypatch.setattr(
        orchestrator,
        "create_run_paths",
        lambda *args, **kwargs: pytest.fail("run paths must not be created"),
    )

    with pytest.raises(
        SystemExit,
        match="must not be empty or contain whitespace",
    ):
        orchestrator.main(
            [
                "--session-root",
                str(tmp_path / "runs"),
                "--model",
                "gemini\ninvalid",
            ]
        )


def test_main_rejects_invalid_run_count_before_reading_credentials(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(orchestrator, "resolve_codex_bin", lambda _value: "/codex")
    monkeypatch.setattr(
        orchestrator,
        "load_yibu_credentials",
        lambda _source: pytest.fail("credentials must not be read"),
    )

    with pytest.raises(SystemExit, match="--runs must be at least 1"):
        orchestrator.main(
            [
                "--session-root",
                str(tmp_path / "runs"),
                "--runs",
                "0",
            ]
        )


def test_main_rejects_negative_codex_restart_limit_before_reading_credentials(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(orchestrator, "resolve_codex_bin", lambda _value: "/codex")
    monkeypatch.setattr(
        orchestrator,
        "load_yibu_credentials",
        lambda _source: pytest.fail("credentials must not be read"),
    )

    with pytest.raises(
        SystemExit,
        match="--codex-max-restarts must be at least 0",
    ):
        orchestrator.main(
            [
                "--session-root",
                str(tmp_path / "runs"),
                "--codex-max-restarts",
                "-1",
            ]
        )


def test_main_wires_yibu_key_only_to_codex_player_environment(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    credential_path = tmp_path / "opus.py"
    credential_path.write_text(
        'ak = {"key": "fixture-secret", "url": "https://yibuapi.com"}',
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    player_workspace = run_dir / "player_workspace"
    log_root = run_dir / "trusted_mcplogs"
    player_workspace.mkdir(parents=True)
    log_root.mkdir()
    paths = SimpleNamespace(
        run_dir=run_dir,
        player_workspace=player_workspace,
        log_root=log_root,
    )
    captured = {}

    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )
    monkeypatch.setattr(orchestrator, "resolve_codex_bin", lambda _value: "/codex")
    monkeypatch.setattr(orchestrator, "is_port_listening", lambda *_args: False)
    monkeypatch.setattr(
        orchestrator,
        "collect_runtime_metadata",
        lambda **_kwargs: {"runtime": "fixture"},
    )

    def fake_create_run_paths(*args, **kwargs):
        captured["run_path_args"] = args
        captured["run_path_kwargs"] = kwargs
        return paths

    monkeypatch.setattr(orchestrator, "create_run_paths", fake_create_run_paths)
    monkeypatch.setattr(orchestrator, "build_mcp_command", lambda *_args: ["mcp"])
    monkeypatch.setattr(
        orchestrator,
        "build_supervisor_command",
        lambda **_kwargs: ["supervisor"],
    )
    monkeypatch.setattr(
        orchestrator,
        "build_trusted_mcp_env",
        lambda *_args, **_kwargs: {"MCP": "safe"},
    )
    monkeypatch.setattr(
        orchestrator,
        "build_supervisor_env",
        lambda *_args, **_kwargs: {"GODOT": "safe"},
    )
    monkeypatch.setattr(
        orchestrator,
        "build_provider_proxy_env",
        lambda *_args, **_kwargs: {"PROXY": "safe"},
    )

    def fake_run_orchestrated_session(**kwargs):
        captured["session"] = kwargs
        config_text = (
            Path(kwargs["player_env"]["CODEX_HOME"]) / "config.toml"
        ).read_text(encoding="utf-8")
        captured["config_text"] = config_text
        return 23

    monkeypatch.setattr(
        orchestrator,
        "run_orchestrated_session",
        fake_run_orchestrated_session,
    )

    result = orchestrator.main(
        [
            "--session-root",
            str(tmp_path / "sessions"),
            "--yibu-credentials",
            str(credential_path),
            "--scenario",
            "find_contract",
        ]
    )

    assert result == 23
    assert captured["run_path_kwargs"]["player"] == "codex"
    assert captured["run_path_kwargs"]["model"] == "gemini-3.6-flash"
    assert captured["run_path_kwargs"]["reasoning_effort"] == "none"
    assert "fixture-secret" not in repr(captured["run_path_kwargs"])
    assert "opus.py" not in repr(captured["run_path_kwargs"])
    session = captured["session"]
    assert session["player_env"]["YIBU_API_KEY"] == "fixture-secret"
    assert "fixture-secret" not in captured["config_text"]
    assert 'model_provider = "yibu"' in captured["config_text"]
    assert 'base_url = "http://127.0.0.1:18767/v1"' in captured["config_text"]
    assert "model_reasoning_effort" not in captured["config_text"]
    assert session["provider_proxy_port"] == 18767
    assert session["provider_proxy_env"] == {"PROXY": "safe"}
    assert "fixture-secret" not in repr(session["provider_proxy_command"])
    assert "fixture-secret" not in repr(session["provider_proxy_env"])
    assert session["mcp_env"] == {"MCP": "safe"}
    assert session["supervisor_env"] == {"GODOT": "safe"}
    assert session["player_restart_limit"] == 2
    assert "workflow_memory_read、briefing、observe" in session[
        "player_restart_prompt"
    ]
