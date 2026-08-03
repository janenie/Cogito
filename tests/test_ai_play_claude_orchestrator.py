import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_PATH = REPO_ROOT / "tools" / "ai_play_claude_orchestrator.py"


def load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "tools.ai_play_claude_orchestrator",
        ORCHESTRATOR_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_claude_provider_env_keeps_only_explicit_service_keys(tmp_path):
    orchestrator = load_orchestrator()
    settings = tmp_path / "settings.local.json"
    settings.write_text(
        json.dumps(
            {
                "env": {
                    "ANTHROPIC_AUTH_TOKEN": "fixture-token",
                    "ANTHROPIC_BASE_URL": "https://example.invalid",
                    "ANTHROPIC_MODEL": "claude-test",
                    "ANTHROPIC_SMALL_FAST_MODEL": "claude-small-test",
                    "OPENAI_API_KEY": "must-drop",
                    "AI_PLAY_LOG_ROOT": "/must/drop",
                },
                "hooks": {"PreToolUse": ["must-drop"]},
                "permissions": {"allow": ["Bash"]},
            }
        ),
        encoding="utf-8",
    )

    assert orchestrator.load_claude_provider_env(settings) == {
        "ANTHROPIC_AUTH_TOKEN": "fixture-token",
        "ANTHROPIC_BASE_URL": "https://example.invalid",
        "ANTHROPIC_MODEL": "claude-test",
        "ANTHROPIC_SMALL_FAST_MODEL": "claude-small-test",
    }


def test_temporary_claude_player_config_is_private_and_removed(tmp_path):
    orchestrator = load_orchestrator()
    provider_env = {
        "ANTHROPIC_AUTH_TOKEN": "fixture-token",
        "ANTHROPIC_BASE_URL": "https://example.invalid",
    }

    with orchestrator.temporary_claude_player_config(
        provider_env,
        "http://127.0.0.1:8766/mcp",
    ) as config:
        assert config.root.stat().st_mode & 0o777 == 0o700
        assert config.settings_path.stat().st_mode & 0o777 == 0o600
        assert config.mcp_path.stat().st_mode & 0o777 == 0o600
        assert json.loads(config.settings_path.read_text(encoding="utf-8")) == {
            "env": provider_env
        }
        assert json.loads(config.mcp_path.read_text(encoding="utf-8")) == {
            "mcpServers": {
                "cogito_ai_play": {
                    "type": "http",
                    "url": "http://127.0.0.1:8766/mcp",
                }
            }
        }
        root = config.root

    assert not root.exists()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "root must be a JSON object"),
        ({}, "must contain an env object"),
        ({"env": []}, "must contain an env object"),
        ({"env": {"ANTHROPIC_AUTH_TOKEN": 7}}, "must be a non-empty string"),
        ({"env": {"ANTHROPIC_AUTH_TOKEN": ""}}, "must be a non-empty string"),
        ({"env": {"ANTHROPIC_MODEL": "claude-test"}}, "must provide"),
        (
            {
                "env": {
                    "ANTHROPIC_AUTH_TOKEN": "fixture-token",
                    "ANTHROPIC_BASE_URL": "http://example.invalid",
                }
            },
            "must use https",
        ),
    ],
)
def test_load_claude_provider_env_rejects_invalid_settings(
    tmp_path,
    payload,
    message,
):
    orchestrator = load_orchestrator()
    settings = tmp_path / "settings.local.json"
    settings.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        orchestrator.load_claude_provider_env(settings)


def test_load_claude_provider_env_rejects_missing_or_malformed_file(tmp_path):
    orchestrator = load_orchestrator()
    missing = tmp_path / "missing.json"

    with pytest.raises(ValueError, match="missing Claude settings"):
        orchestrator.load_claude_provider_env(missing)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid Claude settings"):
        orchestrator.load_claude_provider_env(malformed)


def test_temporary_claude_player_config_cleans_up_after_error():
    orchestrator = load_orchestrator()

    with pytest.raises(RuntimeError, match="fixture failure"):
        with orchestrator.temporary_claude_player_config(
            {"ANTHROPIC_API_KEY": "fixture-key"},
            "http://127.0.0.1:8766/mcp",
        ) as config:
            root = config.root
            raise RuntimeError("fixture failure")

    assert not root.exists()


def test_build_claude_command_is_bare_nonpersistent_and_mcp_only(tmp_path):
    orchestrator = load_orchestrator()
    config = orchestrator.ClaudePlayerConfig(
        root=tmp_path,
        settings_path=tmp_path / "settings.json",
        mcp_path=tmp_path / "mcp.json",
    )

    command = orchestrator.build_claude_command(
        "/usr/local/bin/claude",
        config,
        model="claude-opus-test",
        effort="high",
        workflow_memory_enabled=True,
    )

    assert command[:2] == ["/usr/local/bin/claude", "--bare"]
    assert "--print" in command
    assert "--no-session-persistence" in command
    assert "--strict-mcp-config" in command
    assert command[command.index("--settings") + 1] == str(config.settings_path)
    assert command[command.index("--mcp-config") + 1] == str(config.mcp_path)
    assert command[command.index("--tools") + 1] == ""
    allowed = command[command.index("--allowed-tools") + 1]
    assert allowed.split(",") == [
        "mcp__cogito_ai_play__briefing",
        "mcp__cogito_ai_play__workflow_memory_read",
        "mcp__cogito_ai_play__observe",
        "mcp__cogito_ai_play__act",
        "mcp__cogito_ai_play__workflow_memory_update",
    ]
    assert "mcp__cogito_ai_play__stop" not in allowed
    assert command[command.index("--permission-mode") + 1] == "dontAsk"
    assert command[command.index("--model") + 1] == "claude-opus-test"
    assert command[command.index("--effort") + 1] == "high"
    assert "--system-prompt" in command
    for forbidden in (
        "--dangerously-skip-permissions",
        "--add-dir",
        "--agent",
        "--agents",
        "--plugin-dir",
        "--chrome",
        "--continue",
        "--resume",
    ):
        assert forbidden not in command


def test_build_claude_command_disables_workflow_memory_tools(tmp_path):
    orchestrator = load_orchestrator()
    config = orchestrator.ClaudePlayerConfig(
        root=tmp_path,
        settings_path=tmp_path / "settings.json",
        mcp_path=tmp_path / "mcp.json",
    )

    command = orchestrator.build_claude_command(
        "claude",
        config,
        model="claude-test",
        effort="medium",
        workflow_memory_enabled=False,
    )

    allowed = command[command.index("--allowed-tools") + 1]
    assert allowed.split(",") == [
        "mcp__cogito_ai_play__briefing",
        "mcp__cogito_ai_play__observe",
        "mcp__cogito_ai_play__act",
    ]
    assert "workflow_memory" not in allowed
    assert "stop" not in allowed


def test_build_claude_player_env_isolates_home_and_drops_host_secrets(tmp_path):
    orchestrator = load_orchestrator()

    env = orchestrator.build_claude_player_env(
        tmp_path / "player-root",
        {
            "ANTHROPIC_AUTH_TOKEN": "fixture-token",
            "ANTHROPIC_BASE_URL": "https://example.invalid",
        },
        base_env={
            "PATH": "/safe-bin",
            "HOME": "/host-home",
            "OPENAI_API_KEY": "must-drop",
            "AI_PLAY_LOG_ROOT": "/must/drop",
            "PYTHONPATH": "/must/drop",
            "HTTPS_PROXY": "http://must.drop",
        },
    )

    assert env["PATH"] == "/safe-bin"
    assert env["HOME"] == str(tmp_path / "player-root" / "home")
    assert env["ANTHROPIC_AUTH_TOKEN"] == "fixture-token"
    assert env["ANTHROPIC_BASE_URL"] == "https://example.invalid"
    assert env["NO_PROXY"] == "127.0.0.1,localhost"
    for forbidden in (
        "CODEX_HOME",
        "OPENAI_API_KEY",
        "AI_PLAY_LOG_ROOT",
        "PYTHONPATH",
        "HTTPS_PROXY",
    ):
        assert forbidden not in env


def test_resolve_claude_bin_uses_absolute_shim_path(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    resolved = tmp_path / "claude"
    monkeypatch.setattr(
        orchestrator.shutil,
        "which",
        lambda command: str(resolved) if command == "claude" else None,
    )

    assert orchestrator.resolve_claude_bin("claude") == str(resolved)


def test_resolve_claude_bin_rejects_missing_command(monkeypatch):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(orchestrator.shutil, "which", lambda _command: None)

    with pytest.raises(ValueError, match="could not locate Claude executable"):
        orchestrator.resolve_claude_bin("claude")


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--model", "claude-test"],
        ["--effort", "high"],
    ],
)
def test_parse_args_requires_model_and_effort(argv):
    orchestrator = load_orchestrator()

    with pytest.raises(SystemExit) as error:
        orchestrator.parse_args(argv)

    assert error.value.code == 2


def test_parse_args_exposes_only_hardened_claude_options():
    orchestrator = load_orchestrator()

    args = orchestrator.parse_args(
        ["--model", "claude-test", "--effort", "high"]
    )

    assert args.claude_settings == orchestrator.DEFAULT_CLAUDE_SETTINGS
    assert args.mcp_port == 8766
    assert args.timeout_seconds == 100000.0
    assert args.idle_timeout_seconds == 600.0
    assert args.claude_final_grace_seconds == 30.0
    assert args.workflow_memory == "enabled"
    assert not hasattr(args, "dangerously_skip_permissions")
    assert not hasattr(args, "add_dir")
    assert not hasattr(args, "tools")


def test_main_rejects_unknown_scenario_before_provider_setup(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )
    monkeypatch.setattr(
        orchestrator,
        "load_claude_provider_env",
        lambda _path: pytest.fail("Claude settings must not be loaded"),
    )
    monkeypatch.setattr(
        orchestrator,
        "create_run_paths",
        lambda *args, **kwargs: pytest.fail("run paths must not be created"),
    )

    with pytest.raises(SystemExit, match="unsupported AI Play scenario"):
        orchestrator.main(
            [
                "--session-root",
                str(tmp_path / "runs"),
                "--model",
                "claude-test",
                "--effort",
                "high",
                "--scenario",
                "unknown",
            ]
        )


def test_main_rejects_matching_ports_before_creating_run_paths(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"env": {"ANTHROPIC_AUTH_TOKEN": "fixture-token"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )
    monkeypatch.setattr(orchestrator, "resolve_claude_bin", lambda _bin: "claude")
    monkeypatch.setattr(
        orchestrator,
        "create_run_paths",
        lambda *args, **kwargs: pytest.fail("run paths must not be created"),
    )

    with pytest.raises(SystemExit, match="must differ"):
        orchestrator.main(
            [
                "--session-root",
                str(tmp_path / "runs"),
                "--claude-settings",
                str(settings),
                "--model",
                "claude-test",
                "--effort",
                "high",
                "--mcp-port",
                "8765",
            ]
        )


def test_main_wires_claude_session_and_removes_private_config(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "env": {
                    "ANTHROPIC_AUTH_TOKEN": "fixture-token",
                    "ANTHROPIC_BASE_URL": "https://example.invalid",
                }
            }
        ),
        encoding="utf-8",
    )
    captured = {}
    monkeypatch.setattr(orchestrator, "is_port_listening", lambda *args: False)
    monkeypatch.setattr(
        orchestrator,
        "resolve_claude_bin",
        lambda _claude_bin: "/safe/bin/claude",
    )
    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )

    def fake_run(**kwargs):
        captured.update(kwargs)
        settings_path = Path(
            kwargs["player_command"][kwargs["player_command"].index("--settings") + 1]
        )
        mcp_path = Path(
            kwargs["player_command"][kwargs["player_command"].index("--mcp-config") + 1]
        )
        captured["temporary_root"] = settings_path.parent
        assert settings_path.is_file()
        assert mcp_path.is_file()
        return 0

    monkeypatch.setattr(orchestrator, "run_orchestrated_session", fake_run)

    result = orchestrator.main(
        [
            "--runs",
            "2",
            "--session-root",
            str(tmp_path / "runs"),
            "--claude-settings",
            str(settings),
            "--model",
            "claude-test",
            "--effort",
            "high",
            "--workflow-memory",
            "disabled",
        ]
    )

    assert result == 0
    assert captured["player_label"] == "claude"
    assert captured["player_command"][:2] == ["/safe/bin/claude", "--bare"]
    assert captured["player_cwd"].name == "player_workspace"
    assert captured["player_env"]["ANTHROPIC_AUTH_TOKEN"] == "fixture-token"
    assert "CODEX_HOME" not in captured["player_env"]
    assert "workflow_memory" not in captured["player_command"][
        captured["player_command"].index("--allowed-tools") + 1
    ]
    assert not captured["temporary_root"].exists()
