import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR_PATH = REPO_ROOT / "tools" / "ai_play_supervisor.py"


def load_supervisor():
    spec = importlib.util.spec_from_file_location(
        "ai_play_supervisor",
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


def test_parse_game_over_marker_rejects_unrelated_output():
    supervisor = load_supervisor()

    assert supervisor.parse_game_over_marker("AI_PLAY WebSocket connected") is None
    assert (
        supervisor.parse_game_over_marker(
            "AI_PLAY_GAME_OVER outcome=success reason=bad value"
        )
        is None
    )


def test_parse_game_over_marker_treats_mcp_stop_as_failed_attempt():
    supervisor = load_supervisor()

    marker = supervisor.parse_game_over_marker("AI_PLAY disabled; reason=mcp_stop")

    assert marker == ("failure", "stopped")


def test_parse_game_over_marker_treats_disconnection_as_failed_attempt():
    supervisor = load_supervisor()

    assert supervisor.parse_game_over_marker(
        "AI_PLAY disabled; reason=bridge_disconnected"
    ) == ("failure", "bridge_disconnected")
    assert supervisor.parse_game_over_marker(
        "AI_PLAY WebSocket disconnected; reason=connection_closed"
    ) == ("failure", "bridge_disconnected")


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
        max_retries=0,
        timeout_seconds=5.0,
        game_over_exit_timeout_seconds=0.1,
    )

    assert result.status == "failure"
    assert result.reason == "stopped"
    assert result.retries == 0


def test_supervisor_counts_timeout_as_failed_attempt_after_retries_are_exhausted(tmp_path):
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

    assert result.status == "failure"
    assert result.reason == "attempt_timeout"
    assert result.retries == 0
