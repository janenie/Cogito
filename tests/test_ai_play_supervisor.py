import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR_PATH = REPO_ROOT / "tools" / "ai_play_supervisor.py"


def load_supervisor():
    spec = importlib.util.spec_from_file_location(
        "tools.ai_play_supervisor",
        SUPERVISOR_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_game_over_marker_accepts_exact_terminal_line():
    supervisor = load_supervisor()

    marker = supervisor.parse_game_over_marker(
        "AI_PLAY_GAME_OVER outcome=success reason=correct_password"
    )

    assert marker == ("success", "correct_password")


def test_game_over_disable_line_waits_for_exact_terminal_marker():
    supervisor = load_supervisor()

    assert supervisor.parse_game_over_marker(
        "AI_PLAY disabled; reason=game_over:efficiency_target_reached"
    ) is None
    assert supervisor.parse_game_over_marker(
        "AI_PLAY_GAME_OVER outcome=success reason=efficiency_target_reached"
    ) == ("success", "efficiency_target_reached")


def test_supervisor_resolves_conveyor_scene_without_override():
    supervisor = load_supervisor()

    assert supervisor.resolve_scene("conveyor_profit", None) == (
        "conveyor_profit/scenes/conveyor_profit_preview.tscn"
    )
    assert supervisor.resolve_scene("daily_routine_cleanup", None) == (
        "dailyroutine/scenes/home_daily_routine.tscn"
    )
    assert supervisor.resolve_scene("garden_watering", None) == (
        "garden/scenes/garden_vertical_slice.tscn"
    )
    assert supervisor.resolve_scene("loop_staircase_anomaly", None) == (
        "addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn"
    )
    assert supervisor.resolve_scene("laboratory_experiment", None) == (
        "addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn"
    )
    with pytest.raises(ValueError, match="unsupported"):
        supervisor.resolve_scene("unknown", None)


def test_parse_game_over_marker_rejects_unrelated_output():
    supervisor = load_supervisor()

    assert supervisor.parse_game_over_marker("AI_PLAY WebSocket connected") is None
    assert (
        supervisor.parse_game_over_marker(
            "AI_PLAY_GAME_OVER outcome=success reason=bad value"
        )
        is None
    )


def test_parse_game_over_marker_waits_for_formal_terminal_after_game_over_disable():
    supervisor = load_supervisor()

    assert supervisor.parse_game_over_marker(
        "AI_PLAY disabled; reason=game_over:key_picked_up"
    ) is None


def test_drain_lines_preserves_a_terminal_marker_buffered_at_process_exit():
    supervisor = load_supervisor()
    lines = supervisor.queue.Queue()
    lines.put("ordinary shutdown output\n")
    lines.put("AI_PLAY_GAME_OVER outcome=success reason=key_picked_up\n")
    lines.put(None)

    assert supervisor._drain_lines(lines) == ("success", "key_picked_up")


def test_parse_game_over_marker_treats_mcp_stop_as_intentional_stop():
    supervisor = load_supervisor()

    marker = supervisor.parse_game_over_marker("AI_PLAY disabled; reason=mcp_stop")

    assert marker == ("stopped", "mcp_stop")


def test_parse_game_over_marker_treats_disconnection_as_abnormal_attempt():
    supervisor = load_supervisor()

    assert supervisor.parse_game_over_marker(
        "AI_PLAY disabled; reason=bridge_disconnected"
    ) == ("abnormal", "bridge_disconnected")


def test_parse_game_over_marker_retries_nonterminal_controller_disable():
    supervisor = load_supervisor()

    assert supervisor.parse_game_over_marker(
        "AI_PLAY disabled; reason=unexpected_action_batch"
    ) == ("abnormal", "unexpected_action_batch")
    assert supervisor.parse_game_over_marker(
        "AI_PLAY WebSocket disconnected; reason=connection_closed"
    ) == ("abnormal", "bridge_disconnected")


def test_supervisor_retries_abnormal_exit_until_terminal_attempt_completes(tmp_path):
    supervisor = load_supervisor()
    script = tmp_path / "fake_godot.py"
    counter = tmp_path / "counter.txt"
    script.write_text(
        "\n".join(
            [
                "import pathlib",
                "import sys",
                f"counter = pathlib.Path({str(counter)!r})",
                "count = int(counter.read_text()) if counter.exists() else 0",
                "counter.write_text(str(count + 1))",
                "if count == 0:",
                "    print('boot failed before terminal')",
                "    sys.exit(3)",
                "print('AI_PLAY_GAME_OVER outcome=failure reason=wrong_password')",
                "sys.exit(1)",
            ]
        ),
        encoding="utf-8",
    )

    result = supervisor.run_supervised_attempt(
        command=[sys.executable, str(script)],
        cwd=tmp_path,
        attempt_number=1,
        max_retries=1,
        timeout_seconds=5.0,
        game_over_exit_timeout_seconds=1.0,
    )

    assert result.status == "failure"
    assert result.reason == "wrong_password"
    assert result.retries == 1
    assert result.exit_code == 1


def test_supervisor_finishes_stopped_attempt_without_waiting_for_timeout(tmp_path):
    supervisor = load_supervisor()
    script = tmp_path / "stopped_godot.py"
    script.write_text(
        "\n".join(
            [
                "import time",
                "print('AI_PLAY disabled; reason=mcp_stop', flush=True)",
                "time.sleep(5)",
            ]
        ),
        encoding="utf-8",
    )

    result = supervisor.run_supervised_attempt(
        command=[sys.executable, str(script)],
        cwd=tmp_path,
        attempt_number=1,
        max_retries=2,
        timeout_seconds=5.0,
        game_over_exit_timeout_seconds=0.1,
    )

    assert result.status == "stopped"
    assert result.reason == "mcp_stop"
    assert result.retries == 0


def test_supervisor_reports_timeout_as_abnormal_after_retries_are_exhausted(tmp_path):
    supervisor = load_supervisor()
    script = tmp_path / "hang.py"
    script.write_text(
        "import time\nprint('still running', flush=True)\ntime.sleep(5)\n",
        encoding="utf-8",
    )

    result = supervisor.run_supervised_attempt(
        command=[sys.executable, str(script)],
        cwd=tmp_path,
        attempt_number=1,
        max_retries=0,
        timeout_seconds=0.2,
        game_over_exit_timeout_seconds=0.1,
    )

    assert result.status == "abnormal"
    assert result.reason == "attempt_timeout"
    assert result.retries == 0
