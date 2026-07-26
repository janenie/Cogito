import importlib.util
import json
import sys
from pathlib import Path


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


def test_create_run_paths_makes_fresh_player_workspace_and_log_root(tmp_path):
    orchestrator = load_orchestrator()

    first = orchestrator.create_run_paths(tmp_path, timestamp="20260726-170000")
    second = orchestrator.create_run_paths(tmp_path, timestamp="20260726-170000")

    assert first.run_dir == tmp_path / "20260726-170000"
    assert second.run_dir == tmp_path / "20260726-170000-02"
    assert first.player_workspace == first.run_dir / "player_workspace"
    assert first.log_root == first.player_workspace / "mcplogs"
    assert first.player_workspace.is_dir()
    assert first.log_root.is_dir()


def test_write_player_run_config_records_log_root_in_player_workspace(tmp_path):
    orchestrator = load_orchestrator()
    paths = orchestrator.create_run_paths(tmp_path, timestamp="20260726-170000")

    config_path = orchestrator.write_player_run_config(
        paths=paths,
        runs=3,
        scenario="find_contract",
    )

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert config_path == paths.player_workspace / "ai_play_run_config.json"
    assert payload["scenario"] == "find_contract"
    assert payload["runs"] == 3
    assert payload["ai_play_log_root"] == str(paths.log_root)


def test_build_codex_command_uses_fresh_workspace_and_stdin_prompt(tmp_path):
    orchestrator = load_orchestrator()
    paths = orchestrator.create_run_paths(tmp_path, timestamp="20260726-170000")
    mcp_command = tmp_path / "start_ai.sh"

    command = orchestrator.build_codex_command(
        codex_bin="codex",
        player_workspace=paths.player_workspace,
        mcp_command=mcp_command,
        sandbox="read-only",
        approval_policy="never",
    )

    assert command == [
        "codex",
        "-c",
        f'mcp_servers.cogito_ai_play.command="{mcp_command}"',
        "--sandbox",
        "read-only",
        "--ask-for-approval",
        "never",
        "exec",
        "--cd",
        str(paths.player_workspace),
        "--skip-git-repo-check",
        "--ignore-rules",
        "--ephemeral",
        "-",
    ]


def test_build_child_env_sets_log_root_and_codex_home(tmp_path):
    orchestrator = load_orchestrator()
    paths = orchestrator.create_run_paths(tmp_path, timestamp="20260726-170000")
    codex_home = tmp_path / "codex-home"

    env = orchestrator.build_child_env(paths.log_root, codex_home, base_env={})

    assert env["AI_PLAY_LOG_ROOT"] == str(paths.log_root)
    assert env["CODEX_HOME"] == str(codex_home)


def test_build_child_env_sets_bridge_address(tmp_path):
    orchestrator = load_orchestrator()
    paths = orchestrator.create_run_paths(tmp_path, timestamp="20260726-170000")

    env = orchestrator.build_child_env(
        paths.log_root,
        tmp_path / "codex-home",
        ws_host="127.0.0.1",
        ws_port=8765,
        base_env={},
    )

    assert env["AI_PLAY_WS_HOST"] == "127.0.0.1"
    assert env["AI_PLAY_WS_PORT"] == "8765"


def test_build_player_prompt_requires_waiting_for_all_runs(tmp_path):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(
        runs=3,
        scenario="garden_watering",
        run_config=tmp_path / "ai_play_run_config.json",
    )

    assert "不要输出最终回答" in prompt
    assert "3 次" in prompt
    assert "stopped 或 disconnected" in prompt
    assert "继续调用 observe" in prompt


def test_build_player_prompt_requires_human_like_play_and_valid_interactions(tmp_path):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(
        runs=3,
        scenario="garden_watering",
        run_config=tmp_path / "ai_play_run_config.json",
    )

    assert "像人一样玩" in prompt
    assert '{"type":"interact","action":"interact"}' in prompt
    assert "available_interactions" in prompt
    assert "act failed" in prompt
    assert "不要连续重试同一种 act" in prompt


def test_build_player_prompt_allows_current_run_log_review(tmp_path):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(
        runs=3,
        scenario="garden_watering",
        run_config=tmp_path / "ai_play_run_config.json",
    )

    assert "可以边思考边玩" in prompt
    assert "AI_PLAY_LOG_ROOT" in prompt
    assert "可以读取本次 AI_PLAY_LOG_ROOT 下的所有日志内容" in prompt
    assert "trajectory.json" in prompt
    assert "run.json" in prompt
    assert "不要读取仓库源码" in prompt


def test_ensure_player_codex_config_writes_minimal_mcp_config(tmp_path):
    orchestrator = load_orchestrator()
    codex_home = tmp_path / "codex-home"
    mcp_command = tmp_path / "start_ai.sh"

    config_path = orchestrator.ensure_player_codex_config(codex_home, mcp_command)

    text = config_path.read_text(encoding="utf-8")
    assert config_path == codex_home / "config.toml"
    assert '[mcp_servers.cogito_ai_play]' in text
    assert f'command = "{mcp_command}"' in text
    assert '[mcp_servers.cogito_ai_play.tools.briefing]' in text
    assert '[mcp_servers.cogito_ai_play.tools.observe]' in text
    assert '[mcp_servers.cogito_ai_play.tools.act]' in text
    assert '[mcp_servers.cogito_ai_play.tools.stop]' in text
    assert text.count('approval_mode = "approve"') == 4


def test_ensure_player_codex_config_preserves_existing_file_and_adds_mcp(tmp_path):
    orchestrator = load_orchestrator()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text("model = \"custom\"\n", encoding="utf-8")

    result = orchestrator.ensure_player_codex_config(
        codex_home,
        tmp_path / "start_ai.sh",
    )

    assert result == config_path
    text = config_path.read_text(encoding="utf-8")
    assert 'model = "custom"' in text
    assert '[mcp_servers.cogito_ai_play]' in text
    assert '[mcp_servers.cogito_ai_play.tools.briefing]' in text
    assert '[mcp_servers.cogito_ai_play.tools.observe]' in text
    assert '[mcp_servers.cogito_ai_play.tools.act]' in text
    assert '[mcp_servers.cogito_ai_play.tools.stop]' in text


def test_ensure_player_codex_config_adds_missing_tool_approvals(tmp_path):
    orchestrator = load_orchestrator()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    config_path = codex_home / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[mcp_servers.cogito_ai_play]",
                'command = "/existing/start_ai.sh"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    orchestrator.ensure_player_codex_config(
        codex_home,
        tmp_path / "start_ai.sh",
    )

    text = config_path.read_text(encoding="utf-8")
    assert 'command = "/existing/start_ai.sh"' in text
    assert '[mcp_servers.cogito_ai_play.tools.briefing]' in text
    assert '[mcp_servers.cogito_ai_play.tools.observe]' in text
    assert '[mcp_servers.cogito_ai_play.tools.act]' in text
    assert '[mcp_servers.cogito_ai_play.tools.stop]' in text
    assert text.count('approval_mode = "approve"') == 4
