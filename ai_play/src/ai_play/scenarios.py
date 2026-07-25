"""Allowlisted AI Play scenario metadata and public briefing registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .briefing import load_public_briefing
from .daily_routine_cleanup_briefing import load_daily_routine_cleanup_briefing
from .find_key_briefing import load_find_key_briefing
from .greet_npc_meeting_briefing import load_greet_npc_meeting_briefing
from .put_book_briefing import load_put_book_briefing


DEFAULT_SCENARIO_ID = "find_contract"


@dataclass(frozen=True)
class ScenarioDefinition:
    briefing_loader: Callable
    max_act_requests: int
    terminal_results: frozenset[tuple[str, str]]


_SCENARIOS = {
    "find_contract": ScenarioDefinition(
        briefing_loader=load_public_briefing,
        max_act_requests=500,
        terminal_results=frozenset({
            ("success", "correct_password"),
            ("failure", "wrong_password"),
            ("failure", "max_requests"),
        }),
    ),
    "find_key": ScenarioDefinition(
        briefing_loader=load_find_key_briefing,
        max_act_requests=200,
        terminal_results=frozenset({
            ("success", "key_picked_up"),
            ("failure", "max_requests"),
        }),
    ),
    "put_book": ScenarioDefinition(
        briefing_loader=load_put_book_briefing,
        max_act_requests=50,
        terminal_results=frozenset({
            ("success", "book_in_box"),
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
) -> int:
    try:
        scenario_limit = _SCENARIOS[scenario_id].max_act_requests
    except (KeyError, TypeError) as error:
        raise RuntimeError("unsupported_scenario") from error
    return min(scenario_limit, configured_limit)


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
