#!/usr/bin/env python3
"""Run supervised Cogito AI Play attempts by restarting Godot."""

from __future__ import annotations

import argparse
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

try:
    from .ai_play_benchmark import (
        DEFAULT_BENCHMARK_CYCLE_SEED,
        MAX_BENCHMARK_CYCLE_SEED,
        benchmark_round_seed,
    )
    from .ai_play_scene_registry import DEFAULT_SCENE, resolve_scene
except ImportError:
    from ai_play_benchmark import (
        DEFAULT_BENCHMARK_CYCLE_SEED,
        MAX_BENCHMARK_CYCLE_SEED,
        benchmark_round_seed,
    )
    from ai_play_scene_registry import DEFAULT_SCENE, resolve_scene


REPO_ROOT = Path(__file__).resolve().parents[1]
GAME_OVER_RE = re.compile(
    r"^AI_PLAY_GAME_OVER outcome=(success|failure) reason=([a-z0-9_]+)$"
)
AI_PLAY_DISABLED_RE = re.compile(r"^AI_PLAY disabled; reason=([a-z0-9_:]+)$")
AI_PLAY_DISCONNECTED_RE = re.compile(
    r"^AI_PLAY WebSocket disconnected; reason=([a-z0-9_:]+)$"
)
INTENTIONAL_STOP_REASONS = frozenset({"mcp_stop", "escape_stop"})
ABNORMAL_STOP_REASONS = frozenset({"bridge_disconnected", "mcp_shutdown"})


@dataclass(frozen=True)
class AttemptResult:
    attempt: int
    status: str
    reason: str
    exit_code: int | None
    retries: int


def parse_game_over_marker(line: str) -> tuple[str, str] | None:
    match = GAME_OVER_RE.match(line.strip())
    if match is not None:
        return match.group(1), match.group(2)
    match = AI_PLAY_DISABLED_RE.match(line.strip())
    if match is not None:
        reason = match.group(1)
        if reason.startswith("game_over:"):
            return None
        if reason in INTENTIONAL_STOP_REASONS:
            return "stopped", reason
        if reason in ABNORMAL_STOP_REASONS:
            return "abnormal", reason
        return "abnormal", reason
    match = AI_PLAY_DISCONNECTED_RE.match(line.strip())
    if match is not None:
        return "abnormal", "bridge_disconnected"
    return None


def build_godot_command(
    godot_bin: str,
    scene: str,
    scenario: str,
    conveyor_draw_index: int | None = None,
    round_seed: int | None = None,
    find_key_round_seed: int | None = None,
) -> list[str]:
    command = [
        godot_bin,
        "--path",
        ".",
        scene,
        "--",
        "--ai-play",
        f"--ai-play-scenario={scenario}",
        "--ai-play-exit-on-game-over",
    ]
    if scenario == "conveyor_profit" and conveyor_draw_index is not None:
        if conveyor_draw_index < 0:
            raise ValueError("conveyor_draw_index must be nonnegative")
        command.append(f"--conveyor-draw-index={conveyor_draw_index}")
    if round_seed is not None and find_key_round_seed is not None:
        raise ValueError("round seed must be provided only once")
    effective_round_seed = (
        round_seed if round_seed is not None else find_key_round_seed
    )
    if effective_round_seed is not None:
        if effective_round_seed < 0:
            raise ValueError("round_seed must be nonnegative")
        command.append(f"--ai-play-round-seed={effective_round_seed}")
    return command


def find_key_round_seed(cycle_seed: int, attempt_number: int) -> int:
    """Backward-compatible alias for the aligned find-key seed mapping."""
    return benchmark_round_seed("find_key", cycle_seed, attempt_number)


def redact_command(command: Sequence[str]) -> list[str]:
    return [
        "--ai-play-round-seed=REDACTED"
        if value.startswith("--ai-play-round-seed=") else value
        for value in command
    ]


def run_supervised_attempt(
    command: Sequence[str],
    cwd: Path,
    attempt_number: int,
    max_retries: int,
    timeout_seconds: float,
    game_over_exit_timeout_seconds: float,
) -> AttemptResult:
    for retry in range(max_retries + 1):
        result = _run_process_once(
            command=command,
            cwd=cwd,
            attempt_number=attempt_number,
            retry=retry,
            timeout_seconds=timeout_seconds,
            game_over_exit_timeout_seconds=game_over_exit_timeout_seconds,
        )
        if result.status in {"success", "failure", "stopped"}:
            return result
        if retry == max_retries:
            return result
        print(
            "[supervisor] attempt %d abnormal result %s/%s; retrying %d/%d"
            % (
                attempt_number,
                result.status,
                result.reason,
                retry + 1,
                max_retries,
            ),
            flush=True,
        )
    raise RuntimeError("unreachable retry loop")


def _run_process_once(
    command: Sequence[str],
    cwd: Path,
    attempt_number: int,
    retry: int,
    timeout_seconds: float,
    game_over_exit_timeout_seconds: float,
) -> AttemptResult:
    print(
        "[supervisor] starting attempt %d retry %d: %s"
        % (attempt_number, retry, " ".join(redact_command(command))),
        flush=True,
    )
    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: queue.Queue[str | None] = queue.Queue()
    reader = threading.Thread(
        target=_read_process_output,
        args=(process, lines),
        daemon=True,
    )
    reader.start()

    started_at = time.monotonic()
    game_over: tuple[str, str] | None = None
    game_over_at: float | None = None

    while True:
        try:
            line = lines.get(timeout=0.05)
        except queue.Empty:
            line = None
        if line is not None:
            print(line, end="", flush=True)
            marker = parse_game_over_marker(line)
            if marker is not None and game_over is None:
                game_over = marker
                game_over_at = time.monotonic()

        exit_code = process.poll()
        if exit_code is not None:
            reader.join(timeout=1.0)
            drained_marker = _drain_lines(lines)
            if game_over is None:
                game_over = drained_marker
            if game_over is not None:
                return AttemptResult(
                    attempt=attempt_number,
                    status=game_over[0],
                    reason=game_over[1],
                    exit_code=exit_code,
                    retries=retry,
                )
            return AttemptResult(
                attempt=attempt_number,
                status="early_exit",
                reason="no_game_over",
                exit_code=exit_code,
                retries=retry,
            )

        now = time.monotonic()
        if game_over_at is not None:
            if now - game_over_at > game_over_exit_timeout_seconds:
                _terminate_process(process)
        elif now - started_at > timeout_seconds:
            _terminate_process(process)
            return AttemptResult(
                attempt=attempt_number,
                status="abnormal",
                reason="attempt_timeout",
                exit_code=process.returncode,
                retries=retry,
            )


def _read_process_output(
    process: subprocess.Popen[str],
    lines: queue.Queue[str | None],
) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        lines.put(line)
    lines.put(None)


def _drain_lines(lines: queue.Queue[str | None]) -> tuple[str, str] | None:
    marker = None
    while True:
        try:
            line = lines.get_nowait()
        except queue.Empty:
            return marker
        if line is not None:
            print(line, end="", flush=True)
            parsed = parse_game_over_marker(line)
            if marker is None and parsed is not None:
                marker = parsed


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5.0)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restart Godot for supervised Cogito AI Play attempts.",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--attempt-offset", type=int, default=0)
    parser.add_argument("--scenario", default="find_contract")
    parser.add_argument("--scene")
    parser.add_argument("--godot-bin", default="godot")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=1200.0)
    parser.add_argument("--game-over-exit-timeout-seconds", type=float, default=10.0)
    parser.add_argument(
        "--benchmark-cycle-seed",
        "--find-key-cycle-seed",
        dest="benchmark_cycle_seed",
        type=int,
        default=DEFAULT_BENCHMARK_CYCLE_SEED,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.attempt_offset < 0:
        raise SystemExit("--attempt-offset must be nonnegative")
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be at least 0")
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive")
    if args.game_over_exit_timeout_seconds <= 0:
        raise SystemExit("--game-over-exit-timeout-seconds must be positive")
    if (
        args.benchmark_cycle_seed < 0
        or args.benchmark_cycle_seed > MAX_BENCHMARK_CYCLE_SEED
    ):
        raise SystemExit(
            "--benchmark-cycle-seed must be between 0 and %d"
            % MAX_BENCHMARK_CYCLE_SEED
        )

    try:
        scene = resolve_scene(args.scenario, args.scene)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    results: list[AttemptResult] = []
    for local_attempt in range(1, args.runs + 1):
        attempt = args.attempt_offset + local_attempt
        command = build_godot_command(
            godot_bin=args.godot_bin,
            scene=scene,
            scenario=args.scenario,
            conveyor_draw_index=attempt - 1,
            round_seed=benchmark_round_seed(
                args.scenario,
                args.benchmark_cycle_seed,
                attempt,
            ),
        )
        result = run_supervised_attempt(
            command=command,
            cwd=REPO_ROOT,
            attempt_number=attempt,
            max_retries=args.max_retries,
            timeout_seconds=args.timeout_seconds,
            game_over_exit_timeout_seconds=args.game_over_exit_timeout_seconds,
        )
        results.append(result)
        if result.status not in {"success", "failure"}:
            _print_summary(results)
            return 2

    _print_summary(results)
    return 0 if all(result.status == "success" for result in results) else 1


def _print_summary(results: Sequence[AttemptResult]) -> None:
    print("\n[supervisor] summary", flush=True)
    for result in results:
        print(
            "attempt-%02d: %s/%s exit_code=%s retries=%d"
            % (
                result.attempt,
                result.status,
                result.reason,
                result.exit_code,
                result.retries,
            ),
            flush=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
