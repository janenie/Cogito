import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_PATH = REPO_ROOT / "tools" / "ai_play_codex_grok_orchestrator.py"


def load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "tools.ai_play_codex_grok_orchestrator",
        ORCHESTRATOR_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _settings_file(tmp_path, env=None):
    source = tmp_path / "settings.local.json"
    source.write_text(
        json.dumps(
            {
                "env": env
                or {
                    "XAI_API_KEY": "fixture-secret",
                    "XAI_BASE_URL": "https://api.x.ai",
                    "OPENAI_API_KEY": "ignore",
                }
            }
        ),
        encoding="utf-8",
    )
    return source


def test_load_xai_credentials_reads_whitelisted_json_env(tmp_path):
    orchestrator = load_orchestrator()

    credentials = orchestrator.load_xai_credentials(_settings_file(tmp_path))

    assert credentials.api_key == "fixture-secret"
    assert credentials.base_url == "https://api.x.ai/v1"


def test_load_xai_credentials_uses_official_base_url_by_default(tmp_path):
    orchestrator = load_orchestrator()

    credentials = orchestrator.load_xai_credentials(
        _settings_file(tmp_path, {"XAI_API_KEY": "fixture-secret"})
    )

    assert credentials.base_url == "https://api.x.ai/v1"


def test_load_xai_credentials_accepts_existing_v1_suffix(tmp_path):
    orchestrator = load_orchestrator()

    credentials = orchestrator.load_xai_credentials(
        _settings_file(
            tmp_path,
            {
                "XAI_API_KEY": "fixture-secret",
                "XAI_BASE_URL": "https://api.x.ai/v1/",
            },
        )
    )

    assert credentials.base_url == "https://api.x.ai/v1"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not-json", "JSON"),
        (json.dumps({}), "env"),
        (json.dumps({"env": {"XAI_BASE_URL": "https://api.x.ai"}}), "XAI_API_KEY"),
        (
            json.dumps({"env": {"XAI_API_KEY": "", "XAI_BASE_URL": "https://api.x.ai"}}),
            "XAI_API_KEY",
        ),
        (
            json.dumps(
                {
                    "env": {
                        "XAI_API_KEY": "fixture-secret",
                        "XAI_BASE_URL": "http://api.x.ai",
                    }
                }
            ),
            "HTTPS",
        ),
        (
            json.dumps(
                {
                    "env": {
                        "XAI_API_KEY": "fixture-secret",
                        "XAI_BASE_URL": "https://user@api.x.ai",
                    }
                }
            ),
            "credentials",
        ),
        (
            json.dumps(
                {
                    "env": {
                        "XAI_API_KEY": "fixture-secret",
                        "XAI_BASE_URL": "https://api.x.ai/v1?debug=true",
                    }
                }
            ),
            "query",
        ),
        (
            json.dumps(
                {
                    "env": {
                        "XAI_API_KEY": "fixture-secret",
                        "XAI_BASE_URL": "https://api.x.ai/other",
                    }
                }
            ),
            "/v1",
        ),
    ],
)
def test_load_xai_credentials_rejects_invalid_files(tmp_path, payload, message):
    source = tmp_path / "settings.local.json"
    source.write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_orchestrator().load_xai_credentials(source)


def test_load_xai_credentials_reports_missing_file(tmp_path):
    with pytest.raises(ValueError, match="missing xAI credential file"):
        load_orchestrator().load_xai_credentials(tmp_path / "missing.json")


def test_write_player_config_uses_xai_responses_provider_without_secret(tmp_path):
    orchestrator = load_orchestrator()

    config_path = orchestrator.write_player_codex_grok_config(
        tmp_path,
        model="grok-4.6",
        reasoning_effort="high",
        base_url="http://127.0.0.1:18768/v1",
        mcp_url="http://127.0.0.1:8766/mcp",
    )

    text = config_path.read_text(encoding="utf-8")
    assert 'model = "grok-4.6"' in text
    assert 'model_provider = "xai"' in text
    assert 'model_reasoning_effort = "high"' in text
    assert "model_supports_reasoning_summaries = false" in text
    assert '[model_providers.xai]' in text
    assert 'base_url = "http://127.0.0.1:18768/v1"' in text
    assert 'env_key = "XAI_API_KEY"' in text
    assert 'wire_api = "responses"' in text
    assert "fixture-secret" not in text
    assert "developer_instructions = " in text
    assert "比较当前截图与本会话之前由 observe 或 act 返回的截图" in text
    assert 'url = "http://127.0.0.1:8766/mcp"' in text
    assert (
        'enabled_tools = ["briefing", "workflow_memory_read", "observe", '
        '"act", "workflow_memory_update"]'
    ) in text
    assert 'web_search = "disabled"' in text
    assert "shell_tool = false" in text
    assert "unified_exec = false" in text
    assert "apps = false" in text
    assert "goals = false" in text
    assert "multi_agent = false" in text
    assert "plugins = false" in text
    assert "tool_suggest = false" in text
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
    assert config_path.stat().st_mode & 0o777 == 0o600


def test_write_player_config_can_disable_workflow_memory_tools(tmp_path):
    orchestrator = load_orchestrator()

    config_path = orchestrator.write_player_codex_grok_config(
        tmp_path,
        model="grok-4.6",
        reasoning_effort="medium",
        base_url="http://127.0.0.1:18768/v1",
        mcp_url="http://127.0.0.1:8766/mcp",
        workflow_memory_enabled=False,
    )

    text = config_path.read_text(encoding="utf-8")
    assert 'enabled_tools = ["briefing", "observe", "act"]' in text
    assert "workflow_memory_read" not in text
    assert "workflow_memory_update" not in text


def test_build_player_env_injects_only_xai_key(tmp_path):
    orchestrator = load_orchestrator()

    env = orchestrator.build_player_env(
        tmp_path / "player-home",
        "fixture-secret",
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
    assert env["XAI_API_KEY"] == "fixture-secret"
    assert "OPENAI_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert "AI_PLAY_LOG_ROOT" not in env
    assert "HTTPS_PROXY" not in env
    assert env["NO_PROXY"] == "127.0.0.1,localhost"
    assert env["no_proxy"] == "127.0.0.1,localhost"


def test_temporary_player_codex_home_is_empty_and_removed():
    orchestrator = load_orchestrator()

    with orchestrator.temporary_player_codex_home() as player_home:
        assert player_home.is_dir()
        assert list(player_home.iterdir()) == []

    assert not player_home.exists()


def test_parse_args_defaults_to_grok_46_with_high_reasoning():
    orchestrator = load_orchestrator()

    args = orchestrator.parse_args([])

    assert args.model == "grok-4.6"
    assert args.reasoning_effort == "high"
    assert args.runs == 3
    assert args.scenario == "find_contract"
    assert args.xai_credentials == orchestrator.REPO_ROOT / ".xai/settings.local.json"
    assert args.workflow_memory == "enabled"
    assert args.provider_proxy_port == 18768


def test_parse_args_accepts_xhigh_reasoning_effort():
    orchestrator = load_orchestrator()

    args = orchestrator.parse_args(["--reasoning-effort", "xhigh"])

    assert args.reasoning_effort == "xhigh"


def test_parse_args_rejects_unknown_reasoning_effort():
    orchestrator = load_orchestrator()

    with pytest.raises(SystemExit) as error:
        orchestrator.parse_args(["--reasoning-effort", "max"])

    assert error.value.code == 2


def test_build_provider_proxy_command_uses_exact_tool_whitelist():
    orchestrator = load_orchestrator()

    command = orchestrator.build_provider_proxy_command(
        python_bin="python",
        port=18768,
        upstream_base_url="https://api.x.ai/v1",
        workflow_memory_enabled=False,
    )

    assert command[:2] == [
        "python",
        str(orchestrator.RESPONSES_NAMESPACE_PROXY_PATH),
    ]
    assert "127.0.0.1" in command
    assert "https://api.x.ai/v1" in command
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
        orchestrator.write_player_codex_grok_config(
            tmp_path,
            model="grok-4.6",
            reasoning_effort="high",
            base_url="https://api.x.ai/v1",
            mcp_url="http://127.0.0.1:8766/mcp",
        )


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


def test_main_rejects_unsafe_model_before_reading_credentials(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(
        orchestrator,
        "load_xai_credentials",
        lambda _source: pytest.fail("credentials must not be read"),
    )
    monkeypatch.setattr(
        orchestrator,
        "create_run_paths",
        lambda *args, **kwargs: pytest.fail("run paths must not be created"),
    )

    with pytest.raises(SystemExit, match="must not be empty or contain whitespace"):
        orchestrator.main(
            [
                "--session-root",
                str(tmp_path / "runs"),
                "--model",
                "grok\ninvalid",
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
        "load_xai_credentials",
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


def test_main_wires_xai_key_only_to_codex_player_environment(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    credential_path = _settings_file(
        tmp_path,
        {
            "XAI_API_KEY": "fixture-secret",
            "XAI_BASE_URL": "https://api.x.ai",
        },
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
        lambda **kwargs: {"runtime": "fixture", "captured_execution": kwargs},
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
        captured["config_text"] = (
            Path(kwargs["player_env"]["CODEX_HOME"]) / "config.toml"
        ).read_text(encoding="utf-8")
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
            "--xai-credentials",
            str(credential_path),
            "--scenario",
            "find_contract",
        ]
    )

    assert result == 23
    assert captured["run_path_kwargs"]["player"] == "codex-grok"
    assert captured["run_path_kwargs"]["model"] == "grok-4.6"
    assert captured["run_path_kwargs"]["reasoning_effort"] == "high"
    assert "fixture-secret" not in repr(captured["run_path_kwargs"])
    assert "settings.local.json" not in repr(captured["run_path_kwargs"])
    session = captured["session"]
    assert session["player_label"] == "codex-grok"
    assert session["player_env"]["XAI_API_KEY"] == "fixture-secret"
    assert "fixture-secret" not in captured["config_text"]
    assert 'model_provider = "xai"' in captured["config_text"]
    assert 'base_url = "http://127.0.0.1:18768/v1"' in captured["config_text"]
    assert 'model_reasoning_effort = "high"' in captured["config_text"]
    assert session["provider_proxy_port"] == 18768
    assert session["provider_proxy_env"] == {"PROXY": "safe"}
    assert "fixture-secret" not in repr(session["provider_proxy_command"])
    assert "fixture-secret" not in repr(session["provider_proxy_env"])
    assert session["mcp_env"] == {"MCP": "safe"}
    assert session["supervisor_env"] == {"GODOT": "safe"}
