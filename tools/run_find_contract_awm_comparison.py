#!/usr/bin/env python3
"""Run an unattended same-checkout find_contract AWM comparison."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPARISON_ROOT = (
    Path(REPO_ROOT.anchor) / "cogito_ai_player_comparisons"
    if os.name == "nt"
    else Path("/tmp/cogito_ai_player_comparisons")
)
DEFAULT_CODEX_AUTH_HOME = Path("~/.codex-cogito-player")
OUTCOME_RE = re.compile(
    r"AI_PLAY_GAME_OVER outcome=(success|failure) reason=([a-z0-9_]+)"
)


@dataclass(frozen=True)
class GroupResult:
    name: str
    exit_code: int
    elapsed_seconds: float
    successes: int
    failures: int
    reasons: dict[str, int]
    run_dir: str | None
    trusted_log_root: str | None
    console_log: str


def allocate_comparison_dir(root: Path) -> Path:
    root = root.expanduser().resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    for index in range(1, 1000):
        suffix = "" if index == 1 else "-%02d" % index
        candidate = root / f"{stamp}{suffix}"
        try:
            candidate.mkdir(mode=0o700)
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError("could not allocate a fresh comparison directory")


def build_group_command(
    repo_root: Path,
    python_bin: str,
    session_root: Path,
    runs: int,
    model: str,
    reasoning_effort: str,
    workflow_memory: str,
    codex_auth_home: Path,
) -> list[str]:
    return [
        python_bin,
        str(repo_root / "tools" / "ai_play_codex_orchestrator.py"),
        "--runs",
        str(runs),
        "--scenario",
        "find_contract",
        "--session-root",
        str(session_root),
        "--codex-auth-home",
        str(codex_auth_home),
        "--model",
        model,
        "--reasoning-effort",
        reasoning_effort,
        "--workflow-memory",
        workflow_memory,
    ]


def parse_group_output(output: str) -> dict[str, object]:
    outcomes = OUTCOME_RE.findall(output)
    reasons = Counter(reason for _, reason in outcomes)
    run_dir = None
    trusted_log_root = None
    for line in output.splitlines():
        if "[orchestrator] run_dir=" in line:
            run_dir = line.split("[orchestrator] run_dir=", 1)[1].strip()
        elif "[orchestrator] trusted_log_root=" in line:
            trusted_log_root = line.split(
                "[orchestrator] trusted_log_root=", 1
            )[1].strip()
    return {
        "successes": sum(outcome == "success" for outcome, _ in outcomes),
        "failures": sum(outcome == "failure" for outcome, _ in outcomes),
        "reasons": dict(sorted(reasons.items())),
        "run_dir": run_dir,
        "trusted_log_root": trusted_log_root,
    }


def run_group(name: str, command: Sequence[str], console_log: Path) -> GroupResult:
    print(f"[comparison] starting {name}", flush=True)
    started = time.monotonic()
    output_lines: list[str] = []
    with console_log.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            list(command),
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                output_lines.append(line)
                log_file.write(line)
                log_file.flush()
                print(line, end="", flush=True)
            exit_code = process.wait()
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5.0)
            raise
    elapsed = time.monotonic() - started
    parsed = parse_group_output("".join(output_lines))
    result = GroupResult(
        name=name,
        exit_code=exit_code,
        elapsed_seconds=round(elapsed, 3),
        successes=int(parsed["successes"]),
        failures=int(parsed["failures"]),
        reasons=dict(parsed["reasons"]),
        run_dir=parsed["run_dir"],
        trusted_log_root=parsed["trusted_log_root"],
        console_log=str(console_log),
    )
    print(
        "[comparison] finished %s exit=%s success=%s failure=%s elapsed=%.1fs"
        % (
            name,
            result.exit_code,
            result.successes,
            result.failures,
            result.elapsed_seconds,
        ),
        flush=True,
    )
    return result


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare find_contract with and without session AWM.",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument(
        "--codex-auth-home",
        type=Path,
        default=DEFAULT_CODEX_AUTH_HOME,
    )
    parser.add_argument(
        "--comparison-root",
        type=Path,
        default=DEFAULT_COMPARISON_ROOT,
    )
    parser.add_argument("--python-bin", default=sys.executable)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    comparison_dir = allocate_comparison_dir(args.comparison_root)
    print(f"[comparison] output_dir={comparison_dir}", flush=True)
    results: list[GroupResult] = []
    for name, workflow_memory in (
        ("without_awm", "disabled"),
        ("with_awm", "enabled"),
    ):
        session_root = comparison_dir / name / "sessions"
        session_root.mkdir(mode=0o700, parents=True)
        command = build_group_command(
            repo_root=REPO_ROOT,
            python_bin=args.python_bin,
            session_root=session_root,
            runs=args.runs,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            workflow_memory=workflow_memory,
            codex_auth_home=args.codex_auth_home,
        )
        results.append(
            run_group(
                name,
                command,
                comparison_dir / f"{name}.console.log",
            )
        )
    summary = {
        "scenario": "find_contract",
        "runs_per_group": args.runs,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "group_order": ["without_awm", "with_awm"],
        "groups": [asdict(result) for result in results],
    }
    summary_path = comparison_dir / "comparison_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[comparison] summary={summary_path}", flush=True)
    return 0 if all(result.exit_code == 0 for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
