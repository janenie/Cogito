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


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENE = "addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
GAME_OVER_RE = re.compile(
    r"^AI_PLAY_GAME_OVER outcome=(success|failure) reason=([a-z0-9_]+)$"
)


@dataclass(frozen=True)
class AttemptResult:
    attempt: int
    status: str
    reason: str
    exit_code: int | None
    retries: int


def parse_game_over_marker(line: str) -> tuple[str, str] | None:
    match = GAME_OVER_RE.match(line.strip())
    if match is None:
        return None
    return match.group(1), match.group(2)


def build_godot_command(
    godot_bin: str,
    scene: str,
    scenario: str,
) -> list[str]:
    return [
        godot_bin,
        "--path",
        ".",
        scene,
        "--",
        "--ai-play",
        f"--ai-play-scenario={scenario}",
        "--ai-play-exit-on-game-over",
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
        if result.status in {"success", "failure"}:
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
        % (attempt_number, retry, " ".join(command)),
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
            _drain_lines(lines)
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
                status="timeout",
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


def _drain_lines(lines: queue.Queue[str | None]) -> None:
    while True:
        try:
            line = lines.get_nowait()
        except queue.Empty:
            return
        if line is not None:
            print(line, end="", flush=True)


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
    parser.add_argument("--scenario", default="find_contract")
    parser.add_argument("--scene", default=DEFAULT_SCENE)
    parser.add_argument("--godot-bin", default="godot")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=1200.0)
    parser.add_argument("--game-over-exit-timeout-seconds", type=float, default=10.0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be at least 0")
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive")
    if args.game_over_exit_timeout_seconds <= 0:
        raise SystemExit("--game-over-exit-timeout-seconds must be positive")

    command = build_godot_command(
        godot_bin=args.godot_bin,
        scene=args.scene,
        scenario=args.scenario,
    )
    results: list[AttemptResult] = []
    for attempt in range(1, args.runs + 1):
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
