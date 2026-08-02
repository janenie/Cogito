from pathlib import Path

import pytest

from ai_host.config import parse_args


def test_defaults_target_daily_routine_cleanup():
    config = parse_args([])

    assert config.scenario_id == "daily_routine_cleanup"
    assert config.scene_path == Path("dailyroutine/scenes/home_daily_routine.tscn")
    assert config.max_attempts == 3
    assert config.adapter == "openai"
    assert config.api_mode == "responses"
    assert config.godot_command == "godot"
    assert config.mcp_command == Path("ai_play/start_ai.sh")
    assert config.codex_command == "codex"
    assert config.codex_reasoning_effort == "xhigh"
    assert config.max_mcp_interactions == 1000


def test_codex_local_is_rejected_in_favor_of_isolated_orchestrator():
    with pytest.raises(SystemExit):
        parse_args(["--adapter", "codex-local"])


def test_cli_overrides_are_parsed():
    config = parse_args([
        "--scenario", "find_key",
        "--scene", "addons/cogito/DemoScenes/COGITO_3_Lobby.tscn",
        "--max-attempts", "2",
        "--adapter", "external-command",
        "--api-mode", "chat",
        "--model", "gpt-test",
        "--run-dir", "tmp-runs",
        "--godot-command", "/opt/godot",
        "--mcp-command", "custom/start.sh",
        "--agent-command", "codex --prompt {prompt_file}",
        "--codex-command", "/opt/bin/codex",
        "--codex-reasoning-effort", "max",
        "--max-mcp-interactions", "25",
    ])

    assert config.scenario_id == "find_key"
    assert config.scene_path == Path("addons/cogito/DemoScenes/COGITO_3_Lobby.tscn")
    assert config.max_attempts == 2
    assert config.adapter == "external-command"
    assert config.api_mode == "chat"
    assert config.model == "gpt-test"
    assert config.run_dir == Path("tmp-runs")
    assert config.godot_command == "/opt/godot"
    assert config.mcp_command == Path("custom/start.sh")
    assert config.agent_command == "codex --prompt {prompt_file}"
    assert config.codex_command == "/opt/bin/codex"
    assert config.codex_reasoning_effort == "max"
    assert config.max_mcp_interactions == 25
