from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, AsyncIterator, TextIO

from tools.ai_play_benchmark import benchmark_attempt_plan
from tools.ai_play_orchestrator_common import (
    DEFAULT_WS_PORT,
    RunPaths,
    collect_runtime_metadata,
    create_run_paths,
    resume_run_paths,
)
from tools.ai_play_scene_registry import resolve_scene
from tools_langgraph_deepagents import (
    CAPTION_BATCH_OBSERVATIONS,
    CAPTION_RETRY_SECONDS,
    IMAGE_CONTEXT_OBSERVATIONS,
)


WORKFLOW_MEMORY_FILENAME = "workflow_memory.json"
CHECKPOINT_FILENAME = "deepagents_checkpoint.sqlite"
FORMAL_TERMINAL_STATUSES = frozenset({"success", "failure"})
KNOWN_TERMINAL_STATUSES = FORMAL_TERMINAL_STATUSES | frozenset(
    {"stopped", "disconnected", "shutdown"}
)


@dataclass(frozen=True)
class PreparedRun:
    paths: RunPaths
    scene: str
    completed_runs: int
    remaining_runs: int
    thread_id: str
    checkpoint_path: Path
    workflow_memory_path: Path


def confirm_external_run(
    *,
    confirmed: bool,
    model: str,
    scenario: str,
    runs: int,
    input_fn: Any = input,
) -> bool:
    notice = (
        f"Model={model} scenario={scenario} runs={runs}. "
        "This uploads approved RGB/depth screenshots, consumes paid tokens, "
        "and stores local trajectory plus agent checkpoints. "
        "Type RUN to continue: "
    )
    return True if confirmed else input_fn(notice).strip() == "RUN"


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing {label}: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"invalid {label}")
    return payload


def load_resume_progress(
    run_dir: Path,
    *,
    model: str,
    scenario: str,
    workflow_memory_enabled: bool,
    requested_runs: int,
    benchmark_cycle_seed: int,
) -> int:
    artifact_dir = run_dir.expanduser().resolve()
    metadata = _read_json_object(
        artifact_dir / "session.json",
        "resume session metadata",
    )
    if metadata.get("schema_version") != 2:
        raise ValueError("unsupported resume session metadata")
    expected_memory = "enabled" if workflow_memory_enabled else "disabled"
    for key, expected, label in (
        ("player", "deepagents", "player"),
        ("model", model, "model"),
        ("reasoning_effort", "none", "reasoning effort"),
        ("scenario", scenario, "scenario"),
        ("workflow_memory", expected_memory, "workflow memory mode"),
    ):
        if metadata.get(key) != expected:
            raise ValueError(f"resume {label} mismatch")
    original_requested_runs = metadata.get("requested_runs")
    if (
        type(original_requested_runs) is not int
        or original_requested_runs < 1
        or requested_runs < original_requested_runs
    ):
        raise ValueError("resume requested runs mismatch")
    benchmark = metadata.get("benchmark")
    if (
        not isinstance(benchmark, dict)
        or benchmark.get("cycle_seed") != benchmark_cycle_seed
        or benchmark.get("attempts")
        != benchmark_attempt_plan(
            scenario,
            benchmark_cycle_seed,
            original_requested_runs,
        )
    ):
        raise ValueError("resume benchmark cycle seed mismatch")

    checkpoint_path = (
        artifact_dir / "trusted_mcplogs" / WORKFLOW_MEMORY_FILENAME
    )
    if not checkpoint_path.exists():
        return 0
    checkpoint = _read_json_object(
        checkpoint_path,
        "workflow memory checkpoint",
    )
    if checkpoint.get("schema_version") != 1:
        raise ValueError("unsupported workflow memory checkpoint")
    if checkpoint.get("scenario_id") != scenario:
        raise ValueError("resume checkpoint scenario mismatch")
    completed = checkpoint.get("completed")
    if not isinstance(completed, list):
        raise ValueError("invalid workflow memory checkpoint")
    completed_runs = 0
    for number, attempt in enumerate(completed, 1):
        if (
            not isinstance(attempt, dict)
            or attempt.get("number") != number
            or attempt.get("scenario_id") != scenario
            or attempt.get("status") not in KNOWN_TERMINAL_STATUSES
            or type(attempt.get("consumed")) is not bool
        ):
            raise ValueError("invalid workflow memory checkpoint")
        if attempt["status"] in FORMAL_TERMINAL_STATUSES:
            completed_runs += 1
    active_attempt = checkpoint.get("active_attempt")
    if active_attempt is not None and (
        not isinstance(active_attempt, dict)
        or active_attempt.get("number") != len(completed) + 1
        or active_attempt.get("scenario_id") != scenario
        or active_attempt.get("status") != "in_progress"
    ):
        raise ValueError("invalid workflow memory checkpoint")
    if completed_runs > requested_runs:
        raise ValueError("resume progress exceeds requested runs")
    if completed_runs == requested_runs:
        raise ValueError("resume run is already complete")
    return completed_runs


def _extend_resume_target(
    session_metadata: Path,
    *,
    scenario: str,
    requested_runs: int,
    benchmark_cycle_seed: int,
) -> None:
    metadata = _read_json_object(session_metadata, "resume session metadata")
    if metadata["requested_runs"] == requested_runs:
        return
    metadata["requested_runs"] = requested_runs
    metadata["benchmark"]["attempts"] = benchmark_attempt_plan(
        scenario,
        benchmark_cycle_seed,
        requested_runs,
    )
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=session_metadata.parent,
            prefix=f".{session_metadata.name}.",
            delete=False,
        ) as output:
            temporary_name = output.name
            json.dump(metadata, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, session_metadata)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _thread_id(run_dir: Path) -> str:
    digest = hashlib.sha256(
        str(run_dir.expanduser().resolve()).encode("utf-8")
    ).hexdigest()
    return f"cogito-{digest}"


def prepare_run(args: Any) -> PreparedRun:
    workflow_memory_enabled = args.workflow_memory == "enabled"
    scene = resolve_scene(args.scenario, args.scene)
    if args.resume_run is None:
        runtime_metadata = collect_runtime_metadata(
            python_bin=args.python_bin,
            player_bin=args.python_bin,
            godot_bin=args.godot_bin,
            execution={
                "ws_port": DEFAULT_WS_PORT,
                "max_retries": args.max_retries,
                "attempt_timeout_seconds": args.timeout_seconds,
                "model_timeout_seconds": args.model_timeout_seconds,
                "model_max_retries": args.model_max_retries,
                "max_output_tokens": args.max_output_tokens,
                "context_window_tokens": args.context_window_tokens,
                "agent_final_grace_seconds": (
                    args.agent_final_grace_seconds
                ),
                "caption_batch_observations": (
                    CAPTION_BATCH_OBSERVATIONS
                ),
                "image_context_observations": (
                    IMAGE_CONTEXT_OBSERVATIONS
                ),
                "visual_history_mode": (
                    "one_compact_summary_per_caption_batch"
                ),
                "caption_retry_seconds": list(CAPTION_RETRY_SECONDS),
                "caption_failure_mode": (
                    "fail_closed_at_next_batch_boundary"
                ),
            },
        )
        paths = create_run_paths(
            args.session_root,
            artifact_root=args.artifact_root,
            player="deepagents",
            model=args.model,
            reasoning_effort="none",
            scenario=args.scenario,
            workflow_memory_enabled=workflow_memory_enabled,
            requested_runs=args.runs,
            benchmark_cycle_seed=args.benchmark_cycle_seed,
            runtime_metadata=runtime_metadata,
        )
        completed_runs = 0
    else:
        paths = resume_run_paths(args.session_root, args.resume_run)
        completed_runs = load_resume_progress(
            paths.run_dir,
            model=args.model,
            scenario=args.scenario,
            workflow_memory_enabled=workflow_memory_enabled,
            requested_runs=args.runs,
            benchmark_cycle_seed=args.benchmark_cycle_seed,
        )
        _extend_resume_target(
            paths.session_metadata,
            scenario=args.scenario,
            requested_runs=args.runs,
            benchmark_cycle_seed=args.benchmark_cycle_seed,
        )
    return PreparedRun(
        paths=paths,
        scene=scene,
        completed_runs=completed_runs,
        remaining_runs=args.runs - completed_runs,
        thread_id=_thread_id(paths.run_dir),
        checkpoint_path=paths.run_dir / CHECKPOINT_FILENAME,
        workflow_memory_path=(
            paths.log_root / WORKFLOW_MEMORY_FILENAME
        ),
    )


async def relay_output(
    stream: asyncio.StreamReader,
    output: TextIO,
    terminal: TextIO | None = sys.stdout,
) -> None:
    while True:
        raw_line = await stream.readline()
        if not raw_line:
            break
        line = raw_line.decode("utf-8", errors="replace")
        output.write(line)
        output.flush()
        if terminal is not None and terminal is not output:
            terminal.write(line)
            terminal.flush()


@asynccontextmanager
async def supervisor_process(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None,
    output: TextIO,
    terminal: TextIO | None = sys.stdout,
    termination_grace_seconds: float = 5.0,
) -> AsyncIterator[asyncio.subprocess.Process]:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert process.stdout is not None
    pump = asyncio.create_task(
        relay_output(process.stdout, output, terminal)
    )
    try:
        yield process
    finally:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.terminate()
            try:
                await asyncio.wait_for(
                    process.wait(),
                    timeout=termination_grace_seconds,
                )
            except asyncio.TimeoutError:
                with suppress(ProcessLookupError):
                    process.kill()
                await process.wait()
        await pump
