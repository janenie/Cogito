"""Deterministic trusted seed plans shared by AI Play launchers."""

from __future__ import annotations


DEFAULT_BENCHMARK_CYCLE_SEED = 20260809
MAX_BENCHMARK_CYCLE_SEED = 1_000_000_000


def benchmark_round_seed(
    scenario: str,
    cycle_seed: int,
    attempt_number: int,
) -> int:
    if cycle_seed < 0 or cycle_seed > MAX_BENCHMARK_CYCLE_SEED:
        raise ValueError(
            "benchmark cycle seed must be between 0 and %d"
            % MAX_BENCHMARK_CYCLE_SEED
        )
    if attempt_number < 1:
        raise ValueError("benchmark attempt number must be at least 1")
    if scenario == "find_key":
        return cycle_seed * 4 + attempt_number - 1
    if scenario == "conveyor_profit":
        # A fixed supply seed plus draw indices gives a non-repeating campaign pack.
        return cycle_seed + 1
    return cycle_seed * 1_000_003 + attempt_number


def benchmark_attempt_plan(
    scenario: str,
    cycle_seed: int,
    requested_runs: int,
) -> list[dict[str, int]]:
    if requested_runs < 1:
        raise ValueError("requested_runs must be at least 1")
    attempts = []
    for attempt_number in range(1, requested_runs + 1):
        attempt = {
            "attempt": attempt_number,
            "round_seed": benchmark_round_seed(
                scenario,
                cycle_seed,
                attempt_number,
            ),
        }
        if scenario == "conveyor_profit":
            attempt["draw_index"] = attempt_number - 1
        attempts.append(attempt)
    return attempts
