import asyncio
import io
import json
from pathlib import Path
import sys

import pytest

from tools.ai_play_orchestrator_common import create_run_paths
from tools_langgraph_deepagents.config import parse_args
from tools_langgraph_deepagents.runtime import (
    confirm_external_run,
    load_resume_progress,
    prepare_run,
    supervisor_process,
)


def test_noninteractive_confirmation_skips_input():
    called = False

    def input_fn(_prompt):
        nonlocal called
        called = True
        return ""

    assert confirm_external_run(
        confirmed=True,
        model="gemini-3.6-flash",
        scenario="find_contract",
        runs=3,
        input_fn=input_fn,
    )
    assert called is False


def test_interactive_confirmation_requires_run_word():
    prompts: list[str] = []

    assert not confirm_external_run(
        confirmed=False,
        model="gemini-3.6-flash",
        scenario="find_contract",
        runs=3,
        input_fn=lambda prompt: prompts.append(prompt) or "no",
    )
    assert "RGB/depth" in prompts[0]
    assert "paid tokens" in prompts[0]
    assert "checkpoints" in prompts[0]


def _checkpoint(completed: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "scenario_id": "find_contract",
        "active_attempt": None,
        "completed": completed,
        "version": 0,
        "goal_pattern": None,
        "workflow": [],
        "landmarks": [],
        "avoid": [],
        "failure_reviews": [],
    }


def test_resume_progress_counts_only_formal_terminals(tmp_path: Path):
    session_root = tmp_path / "sessions"
    run = create_run_paths(
        session_root,
        player="deepagents",
        model="gemini-3.6-flash",
        reasoning_effort="none",
        scenario="find_contract",
        workflow_memory_enabled=True,
        requested_runs=3,
        benchmark_cycle_seed=42,
    )
    checkpoint = _checkpoint(
        [
            {
                "number": 1,
                "scenario_id": "find_contract",
                "status": "disconnected",
                "terminal_reason": "bridge_disconnected",
                "consumed": True,
            },
            {
                "number": 2,
                "scenario_id": "find_contract",
                "status": "success",
                "terminal_reason": "completed",
                "consumed": True,
            },
        ]
    )
    (run.log_root / "workflow_memory.json").write_text(
        json.dumps(checkpoint),
        encoding="utf-8",
    )

    completed = load_resume_progress(
        run.run_dir,
        model="gemini-3.6-flash",
        scenario="find_contract",
        workflow_memory_enabled=True,
        requested_runs=3,
        benchmark_cycle_seed=42,
    )

    assert completed == 1


def test_resume_can_extend_one_run_target_to_three(tmp_path: Path):
    session_root = tmp_path / "sessions"
    run = create_run_paths(
        session_root,
        player="deepagents",
        model="gemini-3.6-flash",
        reasoning_effort="none",
        scenario="find_contract",
        workflow_memory_enabled=True,
        requested_runs=1,
        benchmark_cycle_seed=42,
    )
    checkpoint = _checkpoint(
        [
            {
                "number": 1,
                "scenario_id": "find_contract",
                "status": "failure",
                "terminal_reason": "max_requests",
                "consumed": True,
            }
        ]
    )
    (run.log_root / "workflow_memory.json").write_text(
        json.dumps(checkpoint),
        encoding="utf-8",
    )

    prepared = prepare_run(
        parse_args(
            [
                "--runs",
                "3",
                "--session-root",
                str(session_root),
                "--resume-run",
                str(run.run_dir),
                "--benchmark-cycle-seed",
                "42",
                "--godot-bin",
                "missing-godot-for-test",
            ]
        )
    )
    metadata = json.loads(run.session_metadata.read_text(encoding="utf-8"))
    memory = json.loads(
        (run.log_root / "workflow_memory.json").read_text(encoding="utf-8")
    )

    assert prepared.completed_runs == 1
    assert prepared.remaining_runs == 2
    assert metadata["requested_runs"] == 3
    assert len(metadata["benchmark"]["attempts"]) == 3
    assert memory["completed"][0]["consumed"] is False


def test_resume_progress_rejects_a_different_player(tmp_path: Path):
    session_root = tmp_path / "sessions"
    run = create_run_paths(
        session_root,
        player="codex",
        model="gemini-3.6-flash",
        reasoning_effort="none",
        scenario="find_contract",
        workflow_memory_enabled=False,
        requested_runs=3,
        benchmark_cycle_seed=42,
    )

    with pytest.raises(ValueError, match="player mismatch"):
        load_resume_progress(
            run.run_dir,
            model="gemini-3.6-flash",
            scenario="find_contract",
            workflow_memory_enabled=False,
            requested_runs=3,
            benchmark_cycle_seed=42,
        )


def test_prepare_run_keeps_checkpoint_thread_stable_on_resume(
    tmp_path: Path,
):
    session_root = tmp_path / "sessions"
    first = prepare_run(
        parse_args(
            [
                "--session-root",
                str(session_root),
                "--godot-bin",
                "missing-godot-for-test",
            ]
        )
    )
    resumed = prepare_run(
        parse_args(
            [
                "--session-root",
                str(session_root),
                "--resume-run",
                str(first.paths.run_dir),
                "--godot-bin",
                "missing-godot-for-test",
            ]
        )
    )

    assert first.remaining_runs == 3
    assert resumed.thread_id == first.thread_id
    assert resumed.checkpoint_path == first.checkpoint_path
    assert first.checkpoint_path.parent == first.paths.run_dir


async def _wait_for_text(output: io.StringIO, value: str) -> None:
    for _ in range(100):
        if value in output.getvalue():
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"subprocess did not write {value!r}")


@pytest.mark.asyncio
async def test_supervisor_process_relays_normal_exit(tmp_path: Path):
    output = io.StringIO()
    command = [sys.executable, "-c", "print('normal', flush=True)"]

    async with supervisor_process(
        command,
        cwd=tmp_path,
        env=None,
        output=output,
        terminal=None,
        termination_grace_seconds=0.1,
    ) as process:
        assert await process.wait() == 0

    assert "normal" in output.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize("ignore_terminate", [False, True])
async def test_supervisor_process_closes_long_running_children(
    tmp_path: Path,
    ignore_terminate: bool,
):
    output = io.StringIO()
    signal_setup = (
        "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
        if ignore_terminate
        else ""
    )
    command = [
        sys.executable,
        "-c",
        (
            "import signal,time;"
            + signal_setup
            + "print('ready',flush=True);time.sleep(60)"
        ),
    ]

    async with supervisor_process(
        command,
        cwd=tmp_path,
        env=None,
        output=output,
        terminal=None,
        termination_grace_seconds=0.1,
    ) as process:
        await _wait_for_text(output, "ready")
        assert process.returncode is None

    assert process.returncode is not None
    assert "ready" in output.getvalue()
