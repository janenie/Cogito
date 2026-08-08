import importlib.util
import io
import json
import sys
import tomllib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_PATH = REPO_ROOT / "tools" / "ai_play_kimi_orchestrator.py"
PROVIDER_AUTH_FIELD = "api" + "_key"


def load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "tools.ai_play_kimi_orchestrator",
        ORCHESTRATOR_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_kimi_config(home: Path, extra: str = "") -> Path:
    home.mkdir(parents=True)
    config = home / "config.toml"
    config.write_text(
        "\n".join(
            (
                '[providers."managed:kimi-code"]',
                'type = "kimi"',
                'base_url = "https://example.invalid/coding/v1"',
                f'{PROVIDER_AUTH_FIELD} = "fixture-key"',
                extra,
            )
        ),
        encoding="utf-8",
    )
    return config


def test_validate_kimi_home_accepts_provider_only_config(tmp_path):
    orchestrator = load_orchestrator()
    home = tmp_path / "kimi-home"
    write_kimi_config(home)

    assert orchestrator.validate_kimi_home(home) == home.resolve()


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("not toml =", "invalid Kimi config"),
        ('default_model = "kimi-test"', "at least one provider"),
        (
            "\n".join(
                (
                    '[providers."test"]',
                    'type = "kimi"',
                    'base_url = "http://example.invalid"',
                    f'{PROVIDER_AUTH_FIELD} = "fixture-key"',
                )
            ),
            "must use https",
        ),
        (
            "\n".join(
                (
                    '[providers."test"]',
                    'type = "kimi"',
                    'base_url = "https://example.invalid"',
                )
            ),
            "non-empty api_key",
        ),
        (
            "\n".join(
                (
                    '[providers."test"]',
                    'type = "kimi"',
                    f'{PROVIDER_AUTH_FIELD} = "fixture-key"',
                    "[hooks]",
                    'command = "must-not-run"',
                )
            ),
            "unsupported or executable sections: hooks",
        ),
    ],
)
def test_validate_kimi_home_rejects_unsafe_or_invalid_config(
    tmp_path,
    contents,
    message,
):
    orchestrator = load_orchestrator()
    home = tmp_path / "kimi-home"
    home.mkdir()
    (home / "config.toml").write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        orchestrator.validate_kimi_home(home)


def test_validate_kimi_home_rejects_missing_config(tmp_path):
    orchestrator = load_orchestrator()

    with pytest.raises(ValueError, match="missing Kimi config"):
        orchestrator.validate_kimi_home(tmp_path / "missing")


def test_temporary_kimi_config_is_private_mcp_only_and_removed(tmp_path):
    orchestrator = load_orchestrator()
    source_home = tmp_path / "source-home"
    source_config = write_kimi_config(source_home)

    with orchestrator.temporary_kimi_player_config(
        source_home,
        "http://127.0.0.1:8766/mcp",
        workflow_memory_enabled=True,
    ) as config:
        assert config.root.stat().st_mode & 0o777 == 0o700
        for path in (config.config_path, config.mcp_path, config.agent_path):
            assert path.stat().st_mode & 0o777 == 0o600
        copied_config = config.config_path.read_text(encoding="utf-8")
        assert copied_config.startswith(source_config.read_text(encoding="utf-8"))
        parsed_config = tomllib.loads(copied_config)
        assert parsed_config["permission"]["rules"] == [
            {"decision": "allow", "pattern": name}
            for name in (
                "mcp__cogito_ai_play__briefing",
                "mcp__cogito_ai_play__workflow_memory_read",
                "mcp__cogito_ai_play__observe",
                "mcp__cogito_ai_play__act",
                "mcp__cogito_ai_play__workflow_memory_update",
            )
        ]
        assert "fixture-key" not in config.mcp_path.read_text(encoding="utf-8")
        assert "fixture-key" not in config.agent_path.read_text(encoding="utf-8")
        assert str(source_home) not in config.agent_path.read_text(encoding="utf-8")
        assert json.loads(config.mcp_path.read_text(encoding="utf-8")) == {
            "mcpServers": {
                "cogito_ai_play": {
                    "url": "http://127.0.0.1:8766/mcp",
                    "enabledTools": [
                        "briefing",
                        "workflow_memory_read",
                        "observe",
                        "act",
                        "workflow_memory_update",
                    ],
                }
            }
        }
        agent = config.agent_path.read_text(encoding="utf-8")
        frontmatter = agent.split("---", 2)[1]
        assert "mcp__cogito_ai_play__briefing" in frontmatter
        assert "mcp__cogito_ai_play__workflow_memory_read" in frontmatter
        assert "mcp__cogito_ai_play__observe" in frontmatter
        assert "mcp__cogito_ai_play__act" in frontmatter
        assert "mcp__cogito_ai_play__workflow_memory_update" in frontmatter
        assert "mcp__cogito_ai_play__stop" not in frontmatter
        assert "subagents: []" in frontmatter
        for forbidden_tool in ("Read", "Bash", "WebSearch", "Agent"):
            assert f"  - {forbidden_tool}\n" not in frontmatter
        root = config.root

    assert not root.exists()


def test_temporary_kimi_config_cleans_up_after_error(tmp_path):
    orchestrator = load_orchestrator()
    source_home = tmp_path / "source-home"
    write_kimi_config(source_home)

    with pytest.raises(RuntimeError, match="fixture failure"):
        with orchestrator.temporary_kimi_player_config(
            source_home,
            "http://127.0.0.1:8766/mcp",
        ) as config:
            root = config.root
            raise RuntimeError("fixture failure")

    assert not root.exists()


def test_temporary_kimi_config_disables_workflow_memory_tools(tmp_path):
    orchestrator = load_orchestrator()
    source_home = tmp_path / "source-home"
    write_kimi_config(source_home)

    with orchestrator.temporary_kimi_player_config(
        source_home,
        "http://127.0.0.1:8766/mcp",
        workflow_memory_enabled=False,
    ) as config:
        mcp = json.loads(config.mcp_path.read_text(encoding="utf-8"))
        assert mcp["mcpServers"]["cogito_ai_play"]["enabledTools"] == [
            "briefing",
            "observe",
            "act",
        ]
        agent = config.agent_path.read_text(encoding="utf-8")
        assert "workflow_memory" not in agent.split("---", 2)[1]


def test_build_kimi_cli_command_is_noninteractive_and_uses_explicit_agent(
    tmp_path,
):
    orchestrator = load_orchestrator()
    agent_path = tmp_path / "agent.md"

    command = orchestrator.build_kimi_cli_command(
        "/safe/bin/kimi",
        agent_path,
        "kimi-code/kimi-k3",
        "fixture prompt",
    )

    assert command[0] == "/safe/bin/kimi"
    assert "--yolo" not in command
    assert "--auto" not in command
    assert command[command.index("--model") + 1] == "kimi-code/kimi-k3"
    assert command[command.index("--agent-file") + 1] == str(agent_path)
    assert command[command.index("--output-format") + 1] == "text"
    assert command[command.index("--prompt") + 1] == "fixture prompt"
    for forbidden in ("--continue", "--session", "--add-dir"):
        assert forbidden not in command


def test_runner_command_does_not_contain_prompt_or_credentials(tmp_path):
    orchestrator = load_orchestrator()
    command = orchestrator.build_kimi_runner_command(
        "/safe/bin/python",
        "/safe/bin/kimi",
        tmp_path / "agent.md",
        "kimi-code/kimi-k3",
    )

    assert command[:3] == [
        "/safe/bin/python",
        str(ORCHESTRATOR_PATH),
        orchestrator.INTERNAL_PLAYER_FLAG,
    ]
    assert "--prompt" not in command
    assert "fixture-key" not in command


def test_internal_runner_moves_stdin_prompt_into_kimi_argument(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    captured = {}

    def fake_execve(executable, command, env):
        captured.update(
            executable=executable,
            command=command,
            env=env,
        )
        raise RuntimeError("exec intercepted")

    monkeypatch.setattr(orchestrator.sys, "stdin", io.StringIO("private prompt"))
    monkeypatch.setattr(orchestrator.os, "execve", fake_execve)

    with pytest.raises(RuntimeError, match="exec intercepted"):
        orchestrator._run_internal_player(
            [
                "--kimi-bin",
                "/safe/bin/kimi",
                "--agent-file",
                str(tmp_path / "agent.md"),
                "--model",
                "kimi-code/kimi-k3",
            ]
        )

    assert captured["executable"] == "/safe/bin/kimi"
    command = captured["command"]
    assert command[command.index("--prompt") + 1] == "private prompt"
    assert captured["env"] == dict(orchestrator.os.environ)


def test_build_kimi_player_env_isolates_home_and_drops_host_secrets(tmp_path):
    orchestrator = load_orchestrator()
    player_root = tmp_path / "player-root"

    env = orchestrator.build_kimi_player_env(
        player_root,
        "high",
        base_env={
            "PATH": "/safe-bin",
            "HOME": "/host-home",
            "KIMI_API_KEY": "must-drop",
            "OPENAI_API_KEY": "must-drop",
            "AI_PLAY_LOG_ROOT": "/must/drop",
            "PYTHONPATH": "/must/drop",
            "HTTPS_PROXY": "http://must.drop",
        },
    )

    assert env["PATH"] == "/safe-bin"
    assert env["HOME"] == str(player_root / "home")
    assert env["KIMI_CODE_HOME"] == str(player_root.resolve())
    assert env["KIMI_MODEL_THINKING_EFFORT"] == "high"
    assert env["KIMI_DISABLE_CRON"] == "1"
    assert env["NO_PROXY"] == "127.0.0.1,localhost"
    for forbidden in (
        "KIMI_API_KEY",
        "OPENAI_API_KEY",
        "AI_PLAY_LOG_ROOT",
        "PYTHONPATH",
        "HTTPS_PROXY",
    ):
        assert forbidden not in env


def test_resolve_kimi_bin_uses_absolute_path(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    resolved = tmp_path / "kimi"
    monkeypatch.setattr(
        orchestrator.shutil,
        "which",
        lambda command: str(resolved) if command == "kimi" else None,
    )

    assert orchestrator.resolve_kimi_bin("kimi") == str(resolved)


def test_resolve_kimi_bin_rejects_missing_command(monkeypatch):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(orchestrator.shutil, "which", lambda _command: None)

    with pytest.raises(ValueError, match="could not locate Kimi executable"):
        orchestrator.resolve_kimi_bin("kimi")


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--model", "kimi-code/kimi-k3"],
        ["--effort", "high"],
    ],
)
def test_parse_args_requires_model_and_effort(argv):
    orchestrator = load_orchestrator()

    with pytest.raises(SystemExit) as error:
        orchestrator.parse_args(argv)

    assert error.value.code == 2


def test_parse_args_exposes_only_hardened_kimi_options():
    orchestrator = load_orchestrator()
    args = orchestrator.parse_args(
        ["--model", "kimi-code/kimi-k3", "--effort", "high"]
    )

    assert args.kimi_home == orchestrator.DEFAULT_KIMI_HOME
    assert args.mcp_port == 8766
    assert args.timeout_seconds == 100000.0
    assert args.idle_timeout_seconds == 600.0
    assert args.kimi_final_grace_seconds == 30.0
    assert args.kimi_max_restarts == 8
    assert args.workflow_memory == "enabled"
    assert not hasattr(args, "yolo")
    assert not hasattr(args, "add_dir")
    assert not hasattr(args, "tools")


def test_main_rejects_unknown_scenario_before_kimi_config(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )
    monkeypatch.setattr(
        orchestrator,
        "validate_kimi_home",
        lambda _path: pytest.fail("Kimi config must not be loaded"),
    )

    with pytest.raises(SystemExit, match="unsupported AI Play scenario"):
        orchestrator.main(
            [
                "--session-root",
                str(tmp_path / "runs"),
                "--model",
                "kimi-code/kimi-k3",
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
    kimi_home = tmp_path / "kimi-home"
    write_kimi_config(kimi_home)
    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )
    monkeypatch.setattr(orchestrator, "resolve_kimi_bin", lambda _bin: "kimi")
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
                "--kimi-home",
                str(kimi_home),
                "--model",
                "kimi-code/kimi-k3",
                "--effort",
                "high",
                "--mcp-port",
                "8765",
            ]
        )


def test_main_wires_kimi_session_and_removes_private_config(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    kimi_home = tmp_path / "kimi-home"
    write_kimi_config(kimi_home)
    captured = {}
    monkeypatch.setattr(orchestrator, "is_port_listening", lambda *args: False)
    monkeypatch.setattr(
        orchestrator,
        "resolve_kimi_bin",
        lambda _kimi_bin: "/safe/bin/kimi",
    )
    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )

    def fake_run(**kwargs):
        captured.update(kwargs)
        temporary_root = Path(kwargs["player_env"]["KIMI_CODE_HOME"])
        captured["temporary_root"] = temporary_root
        assert (temporary_root / "config.toml").is_file()
        assert (temporary_root / "mcp.json").is_file()
        assert (temporary_root / "cogito-ai-play-agent.md").is_file()
        return 0

    monkeypatch.setattr(orchestrator, "run_orchestrated_session", fake_run)

    result = orchestrator.main(
        [
            "--runs",
            "2",
            "--session-root",
            str(tmp_path / "runs"),
            "--kimi-home",
            str(kimi_home),
            "--model",
            "kimi-code/kimi-k3",
            "--effort",
            "high",
            "--workflow-memory",
            "disabled",
        ]
    )

    assert result == 0
    assert captured["player_label"] == "kimi"
    assert captured["player_command"][2] == orchestrator.INTERNAL_PLAYER_FLAG
    assert "--prompt" not in captured["player_command"]
    assert captured["player_cwd"].name == "player_workspace"
    assert captured["player_env"]["KIMI_MODEL_THINKING_EFFORT"] == "high"
    assert "KIMI_API_KEY" not in captured["player_env"]
    assert "AI_PLAY_APPROVED_IMAGE_ROOT" not in captured["mcp_env"]
    assert captured["player_restart_limit"] == 8
    assert not captured["temporary_root"].exists()
    run_dir = Path(captured["player_cwd"]).parent
    assert run_dir.name.endswith(
        "__kimi__kimi-code_kimi-k3__find_contract__no-awm"
    )
    metadata = json.loads(
        (run_dir / "session.json").read_text(encoding="utf-8")
    )
    assert metadata["player"] == "kimi"
    assert metadata["model"] == "kimi-code/kimi-k3"
    assert metadata["reasoning_effort"] == "high"
    assert metadata["scenario"] == "find_contract"
    assert metadata["workflow_memory"] == "disabled"
    assert metadata["requested_runs"] == 2
    assert metadata["schema_version"] == 2
    assert metadata["repository"]["available"] is True
    assert metadata["benchmark"]["cycle_seed"] == (
        orchestrator.DEFAULT_BENCHMARK_CYCLE_SEED
    )
    assert len(metadata["benchmark"]["attempts"]) == 2
    assert metadata["execution"]["ws_port"] == 8765
    assert metadata["execution"]["mcp_port"] == 8766
    assert "fixture-key" not in json.dumps(metadata)


def test_kimi_restart_prompt_requires_formal_terminal():
    orchestrator = load_orchestrator()
    prompt = orchestrator.build_player_restart_prompt(
        2,
        workflow_memory_enabled=True,
        scenario="repair_lighting_circuit",
    )

    assert "同一 MCP 与 AWM 会话" in prompt
    assert "workflow_memory_read、briefing、observe" in prompt
    assert "只有工具返回正式 game_over" in prompt
    assert "observation_id" in prompt
