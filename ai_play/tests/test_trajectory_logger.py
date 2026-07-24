from datetime import datetime, timedelta, timezone
import json

import pytest

from ai_play.trajectory_logger import LogPersistenceError, TrajectoryLogger


class Clock:
    def __init__(self):
        self.value = datetime(2026, 7, 24, 14, 35, tzinfo=timezone.utc)

    def __call__(self):
        current = self.value
        self.value += timedelta(milliseconds=1)
        return current


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_logger_does_not_create_run_before_first_attempt(tmp_path):
    TrajectoryLogger(tmp_path, now=Clock())

    assert list(tmp_path.iterdir()) == []


def test_first_attempt_creates_run_and_empty_trajectory(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())

    attempt_dir = logger.start_attempt()

    assert attempt_dir == tmp_path / "20260724-14-35" / "attempt-01"
    assert load_json(attempt_dir / "trajectory.json") == {
        "trajectory": [],
        "result": {"total_steps": 0, "status": "in_progress"},
    }
    assert load_json(attempt_dir.parent / "run.json") == {
        "started_at": "2026-07-24T14:35:00+00:00",
        "max_attempts": 3,
        "completed_attempts": 0,
        "status": "in_progress",
        "successful_attempt": None,
        "attempts": [
            {"attempt": 1, "status": "in_progress", "total_steps": 0},
        ],
    }


def test_collision_and_fourth_attempt_rotate_runs(tmp_path):
    occupied = tmp_path / "20260724-14-35"
    occupied.mkdir()
    logger = TrajectoryLogger(tmp_path, now=Clock())

    assert logger.start_attempt().parent.name == "20260724-14-35-02"
    logger.finish_attempt("failure")
    logger.start_attempt()
    logger.finish_attempt("failure")
    logger.start_attempt()
    logger.finish_attempt("failure")

    assert logger.start_attempt().parent.name == "20260724-14-35-03"
    assert logger.current_attempt_number == 1


def test_act_request_is_persisted_before_completion(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    attempt_dir = logger.start_attempt()

    token = logger.begin_tool_call("act", {
        "observation_id": 7,
        "actions": [{"type": "wait", "duration_ms": 50}],
    })

    assert token is not None
    snapshot = load_json(attempt_dir / "trajectory.json")
    assert snapshot["result"]["total_steps"] == 1
    assert snapshot["trajectory"][0]["event_index"] == 1
    assert snapshot["trajectory"][0]["act_step"] == 1
    assert snapshot["trajectory"][0]["response"] is None


def test_only_agreed_tools_are_recorded_in_event_order(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    attempt_dir = logger.start_attempt()

    assert logger.begin_tool_call("briefing", {}) is None
    logger.begin_tool_call("observe", {})
    logger.begin_tool_call("act", {"observation_id": 7, "actions": []})
    logger.begin_tool_call("stop", {})

    entries = load_json(attempt_dir / "trajectory.json")["trajectory"]
    assert [(entry["event_index"], entry["tool"]) for entry in entries] == [
        (1, "observe"),
        (2, "act"),
        (3, "stop"),
    ]
    assert "act_step" not in entries[0]
    assert entries[1]["act_step"] == 1
    assert "act_step" not in entries[2]


def test_completion_saves_exact_jpeg_without_base64(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    attempt_dir = logger.start_attempt()
    logger.begin_tool_call("observe", {})
    token = logger.begin_tool_call("act", {
        "observation_id": 7,
        "actions": [{"type": "wait", "duration_ms": 50}],
    })
    jpeg = b"\xff\xd8\xfftrajectory-image\xff\xd9"

    logger.complete_tool_call(token, False, {
        "status": "ready",
        "observation": {"observation_id": 8},
    }, jpeg)

    relative = "imgs/000002-act-obs000008.jpg"
    assert (attempt_dir / relative).read_bytes() == jpeg
    snapshot = load_json(attempt_dir / "trajectory.json")
    assert snapshot["trajectory"][1]["images"] == [relative]
    assert snapshot["trajectory"][1]["response"] == {
        "is_error": False,
        "structured_content": {
            "status": "ready",
            "observation": {"observation_id": 8},
        },
    }
    serialized = (attempt_dir / "trajectory.json").read_text(encoding="utf-8")
    assert "base64" not in serialized


@pytest.mark.parametrize(
    ("statuses", "expected_run_status", "successful_attempt"),
    [
        (["success"], "success", 1),
        (["failure", "failure", "failure"], "failure", None),
        (["failure", "stopped", "failure"], "stopped", None),
    ],
)
def test_attempt_results_update_run_summary(
    tmp_path,
    statuses,
    expected_run_status,
    successful_attempt,
):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    attempt_dir = None
    for index, status in enumerate(statuses):
        attempt_dir = logger.start_attempt()
        logger.begin_tool_call("act", {
            "observation_id": index,
            "actions": [],
        })
        logger.finish_attempt(status)

    run = load_json(attempt_dir.parent / "run.json")
    assert run["completed_attempts"] == len(statuses)
    assert run["status"] == expected_run_status
    assert run["successful_attempt"] == successful_attempt
    assert [attempt["status"] for attempt in run["attempts"]] == statuses


def test_terminal_attempt_ignores_later_calls(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    attempt_dir = logger.start_attempt()
    logger.begin_tool_call("act", {"observation_id": 7, "actions": []})
    logger.finish_attempt("success")

    assert logger.begin_tool_call("act", {
        "observation_id": 7,
        "actions": [],
    }) is None
    snapshot = load_json(attempt_dir / "trajectory.json")
    assert snapshot["result"] == {"total_steps": 1, "status": "success"}


def test_call_started_before_terminal_can_complete_afterward(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    attempt_dir = logger.start_attempt()
    token = logger.begin_tool_call("act", {
        "observation_id": 7,
        "actions": [],
    })
    logger.finish_attempt("success")

    logger.complete_tool_call(token, False, {
        "status": "game_over",
        "observation": None,
    })

    entry = load_json(attempt_dir / "trajectory.json")["trajectory"][0]
    assert entry["response"]["structured_content"]["status"] == "game_over"


def test_token_completes_original_attempt_after_reconnect(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    first_dir = logger.start_attempt()
    token = logger.begin_tool_call("observe", {})
    logger.finish_attempt("stopped")
    logger.start_attempt()

    logger.complete_tool_call(token, True, {
        "status": "error",
        "code": "disconnected",
    })

    first = load_json(first_dir / "trajectory.json")
    assert first["trajectory"][0]["response"]["is_error"] is True


def test_close_marks_active_attempt_and_run_stopped(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    attempt_dir = logger.start_attempt()

    logger.close()

    assert load_json(attempt_dir / "trajectory.json")["result"]["status"] == "stopped"
    assert load_json(attempt_dir.parent / "run.json")["status"] == "stopped"


def test_atomic_write_failure_disables_logger(tmp_path, monkeypatch):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    logger.start_attempt()
    monkeypatch.setattr(
        logger,
        "_atomic_write_json",
        lambda path, payload: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(LogPersistenceError, match="logging_failed"):
        logger.begin_tool_call("observe", {})
    with pytest.raises(LogPersistenceError, match="logging_failed"):
        logger.begin_tool_call("observe", {})
