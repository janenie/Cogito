"""Allowlisted AI Play scenario metadata and public briefing registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .arrange_meeting_briefings_briefing import (
    load_arrange_meeting_briefings_briefing,
)
from .briefing import load_public_briefing
from .conveyor_profit_briefing import load_conveyor_profit_briefing
from .daily_routine_cleanup_briefing import load_daily_routine_cleanup_briefing
from .find_key_briefing import load_find_key_briefing
from .garden_watering_briefing import load_garden_watering_briefing
from .greet_npc_meeting_briefing import load_greet_npc_meeting_briefing
from .put_book_briefing import load_put_book_briefing
from .repair_lighting_circuit_briefing import (
    load_repair_lighting_circuit_briefing,
)


DEFAULT_SCENARIO_ID = "find_contract"
FIND_KEY_ROUND_ACT_REQUEST_LIMITS = frozenset({50, 100})


@dataclass(frozen=True)
class ScenarioDefinition:
    briefing_loader: Callable
    max_act_requests: int
    terminal_results: frozenset[tuple[str, str]]


_SCENARIOS = {
    "find_contract": ScenarioDefinition(
        briefing_loader=load_public_briefing,
        max_act_requests=300,
        terminal_results=frozenset({
            ("success", "correct_password"),
            ("failure", "wrong_password"),
            ("failure", "max_requests"),
        }),
    ),
    "find_key": ScenarioDefinition(
        briefing_loader=load_find_key_briefing,
        max_act_requests=100,
        terminal_results=frozenset({
            ("success", "key_picked_up"),
            ("failure", "max_requests"),
        }),
    ),
    "put_book": ScenarioDefinition(
        briefing_loader=load_put_book_briefing,
        max_act_requests=150,
        terminal_results=frozenset({
            ("success", "books_in_ceo_office"),
            ("failure", "wrong_book_pickup"),
            ("failure", "max_requests"),
        }),
    ),
    "greet_npc_meeting": ScenarioDefinition(
        briefing_loader=load_greet_npc_meeting_briefing,
        max_act_requests=100,
        terminal_results=frozenset({
            ("success", "meeting_door_closed"),
            ("failure", "max_requests"),
        }),
    ),
    "daily_routine_cleanup": ScenarioDefinition(
        briefing_loader=load_daily_routine_cleanup_briefing,
        max_act_requests=150,
        terminal_results=frozenset({
            ("success", "cleanup_complete"),
            ("failure", "cleanup_incomplete"),
            ("failure", "max_requests"),
        }),
    ),
    "garden_watering": ScenarioDefinition(
        briefing_loader=load_garden_watering_briefing,
        max_act_requests=300,
        terminal_results=frozenset({
            ("success", "garden_tasks_complete"),
            ("failure", "garden_task_failed"),
            ("failure", "max_requests"),
        }),
    ),
    "repair_lighting_circuit": ScenarioDefinition(
        briefing_loader=load_repair_lighting_circuit_briefing,
        max_act_requests=100,
        terminal_results=frozenset({
            ("success", "circuit_repaired"),
            ("failure", "wrong_breaker"),
            ("failure", "incorrect_circuit_configuration"),
            ("failure", "max_requests"),
        }),
    ),
    "arrange_meeting_briefings": ScenarioDefinition(
        briefing_loader=load_arrange_meeting_briefings_briefing,
        max_act_requests=200,
        terminal_results=frozenset({
            ("success", "meeting_prepared"),
            ("failure", "incorrect_seating_assignment"),
            ("failure", "max_requests"),
        }),
    ),
    "conveyor_profit": ScenarioDefinition(
        briefing_loader=load_conveyor_profit_briefing,
        max_act_requests=300,
        terminal_results=frozenset({
            ("success", "efficiency_target_reached"),
            ("failure", "efficiency_below_target"),
            ("failure", "max_requests"),
        }),
    ),
}


def is_supported_scenario(scenario_id: object) -> bool:
    return type(scenario_id) is str and scenario_id in _SCENARIOS


def load_scenario_briefing(scenario_id: str):
    try:
        definition = _SCENARIOS[scenario_id]
    except (KeyError, TypeError) as error:
        raise RuntimeError("unsupported_scenario") from error
    return definition.briefing_loader()


def scenario_act_request_limit(
    scenario_id: str,
    configured_limit: int,
    round_limit: object = None,
) -> int:
    return min(
        scenario_round_act_request_limit(scenario_id, round_limit),
        configured_limit,
    )


def scenario_round_act_request_limit(
    scenario_id: str,
    requested_limit: object = None,
) -> int:
    try:
        default_limit = _SCENARIOS[scenario_id].max_act_requests
    except (KeyError, TypeError) as error:
        raise RuntimeError("unsupported_scenario") from error
    if requested_limit is None:
        return default_limit
    if (
        scenario_id != "find_key"
        or type(requested_limit) is not int
        or requested_limit not in FIND_KEY_ROUND_ACT_REQUEST_LIMITS
    ):
        raise RuntimeError("invalid_act_request_limit")
    return requested_limit


def is_allowed_game_over(
    scenario_id: str,
    outcome: str,
    reason: str,
) -> bool:
    try:
        definition = _SCENARIOS[scenario_id]
    except (KeyError, TypeError):
        return False
    return (outcome, reason) in definition.terminal_results


def supported_scenario_ids() -> tuple[str, ...]:
    return tuple(_SCENARIOS)
