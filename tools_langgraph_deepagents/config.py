from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from tools.ai_play_benchmark import (
    DEFAULT_BENCHMARK_CYCLE_SEED,
    MAX_BENCHMARK_CYCLE_SEED,
)
from tools.ai_play_orchestrator_common import DEFAULT_SESSION_ROOT
from tools.ai_play_scene_registry import SUPPORTED_SCENARIOS
from tools_langgraph_deepagents import DEFAULT_MODEL


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Play Cogito with Deep Agents and Yibu Chat Completions."
        ),
    )
    parser.add_argument(
        "--scenario",
        choices=SUPPORTED_SCENARIOS,
        default="find_contract",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--yibu-credentials",
        type=Path,
        default=REPO_ROOT / "newak.py",
    )
    parser.add_argument("--credential-name", default="ak")
    parser.add_argument(
        "--session-root",
        type=Path,
        default=DEFAULT_SESSION_ROOT,
    )
    persistence = parser.add_mutually_exclusive_group()
    persistence.add_argument("--artifact-root", type=Path)
    persistence.add_argument("--resume-run", type=Path)
    parser.add_argument(
        "--workflow-memory",
        choices=("enabled", "disabled"),
        default="enabled",
    )
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--godot-bin", default="godot")
    parser.add_argument("--scene")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=100000.0)
    parser.add_argument(
        "--model-timeout-seconds",
        type=float,
        default=600.0,
    )
    parser.add_argument("--model-max-retries", type=int, default=4)
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--context-window-tokens", type=int, default=32768)
    parser.add_argument(
        "--agent-final-grace-seconds",
        type=float,
        default=30,
    )
    parser.add_argument(
        "--benchmark-cycle-seed",
        type=int,
        default=DEFAULT_BENCHMARK_CYCLE_SEED,
    )
    parser.add_argument("--confirm-external-run", action="store_true")
    args = parser.parse_args(list(argv))
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if args.max_retries < 0 or args.model_max_retries < 0:
        parser.error("retry counts must be nonnegative")
    if args.timeout_seconds <= 0 or args.model_timeout_seconds <= 0:
        parser.error("timeouts must be positive")
    if not 1 <= args.max_output_tokens <= 32768:
        parser.error("--max-output-tokens must be between 1 and 32768")
    if args.context_window_tokens < args.max_output_tokens:
        parser.error(
            "--context-window-tokens must be at least --max-output-tokens"
        )
    if args.agent_final_grace_seconds < 0:
        parser.error("--agent-final-grace-seconds must be nonnegative")
    if not args.model.strip() or any(ord(char) < 32 for char in args.model):
        parser.error("--model must be a non-empty printable string")
    if not args.credential_name.isidentifier():
        parser.error("--credential-name must be a Python identifier")
    if not 0 <= args.benchmark_cycle_seed <= MAX_BENCHMARK_CYCLE_SEED:
        parser.error(
            "--benchmark-cycle-seed must be between 0 and "
            f"{MAX_BENCHMARK_CYCLE_SEED}"
        )
    return args
