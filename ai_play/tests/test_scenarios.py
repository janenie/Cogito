import pytest

import ai_play.scenarios as scenario_registry
from ai_play.scenarios import (
    DEFAULT_SCENARIO_ID,
    is_allowed_game_over,
    is_supported_scenario,
    load_scenario_briefing,
    scenario_act_request_limit,
    supported_scenario_ids,
)


def test_scenario_registry_exposes_only_allowlisted_scenarios():
    assert DEFAULT_SCENARIO_ID == "find_contract"
    assert supported_scenario_ids() == (
        "find_contract",
        "find_key",
        "put_book",
        "greet_npc_meeting",
        "daily_routine_cleanup",
        "garden_watering",
        "conveyor_profit",
    )
    assert is_supported_scenario("find_contract")
    assert is_supported_scenario("find_key")
    assert is_supported_scenario("put_book")
    assert is_supported_scenario("greet_npc_meeting")
    assert is_supported_scenario("daily_routine_cleanup")
    assert is_supported_scenario("garden_watering")
    assert is_supported_scenario("conveyor_profit")
    assert not is_supported_scenario("unknown")
    assert not is_supported_scenario(True)


def test_scenario_registry_loads_public_briefing_and_rejects_unknown():
    briefing, image_bytes = load_scenario_briefing("find_contract")

    assert briefing["game_id"] == "find_contract"
    assert image_bytes.startswith(b"\xff\xd8\xff")
    with pytest.raises(RuntimeError, match="unsupported_scenario"):
        load_scenario_briefing("unknown")


def test_scenario_request_limits_are_hard_caps():
    assert scenario_act_request_limit("find_contract", 500) == 300
    assert scenario_act_request_limit("find_contract", 120) == 120
    assert scenario_act_request_limit("find_key", 500) == 100
    assert scenario_act_request_limit("find_key", 80) == 80
    assert scenario_act_request_limit("put_book", 500) == 50
    assert scenario_act_request_limit("put_book", 35) == 35
    assert scenario_act_request_limit("greet_npc_meeting", 500) == 100
    assert scenario_act_request_limit("greet_npc_meeting", 75) == 75
    assert scenario_act_request_limit("daily_routine_cleanup", 500) == 150
    assert scenario_act_request_limit("daily_routine_cleanup", 90) == 90
    assert scenario_act_request_limit("garden_watering", 500) == 300
    assert scenario_act_request_limit("garden_watering", 200) == 200
    assert scenario_act_request_limit("conveyor_profit", 500) == 300


def test_find_key_round_request_limits_are_allowlisted():
    scenario_round_act_request_limit = getattr(
        scenario_registry,
        "scenario_round_act_request_limit",
        None,
    )
    assert callable(scenario_round_act_request_limit)
    assert scenario_round_act_request_limit("find_key") == 100
    assert scenario_round_act_request_limit("find_key", 50) == 50
    assert scenario_round_act_request_limit("find_key", 100) == 100
    assert scenario_act_request_limit("find_key", 500, 50) == 50
    assert scenario_act_request_limit("find_key", 40, 50) == 40


@pytest.mark.parametrize(
    ("scenario_id", "requested_limit"),
    [
        ("find_key", True),
        ("find_key", 50.0),
        ("find_key", "50"),
        ("find_key", 49),
        ("find_key", 51),
        ("find_key", 101),
        ("find_contract", 50),
    ],
)
def test_round_request_limit_rejects_unapproved_values(
    scenario_id,
    requested_limit,
):
    scenario_round_act_request_limit = getattr(
        scenario_registry,
        "scenario_round_act_request_limit",
        None,
    )
    assert callable(scenario_round_act_request_limit)
    with pytest.raises(RuntimeError, match="invalid_act_request_limit"):
        scenario_round_act_request_limit(scenario_id, requested_limit)


def test_terminal_results_are_scenario_specific():
    assert is_allowed_game_over("find_contract", "success", "correct_password")
    assert is_allowed_game_over("find_contract", "failure", "wrong_password")
    assert not is_allowed_game_over(
        "find_contract",
        "success",
        "key_picked_up",
    )
    assert is_allowed_game_over("find_key", "success", "key_picked_up")
    assert not is_allowed_game_over("find_key", "success", "correct_password")
    assert not is_allowed_game_over("find_key", "failure", "wrong_password")
    assert is_allowed_game_over("put_book", "success", "book_in_box")
    assert not is_allowed_game_over("put_book", "success", "key_picked_up")
    assert not is_allowed_game_over("put_book", "success", "correct_password")
    assert is_allowed_game_over(
        "greet_npc_meeting",
        "success",
        "meeting_door_closed",
    )
    assert is_allowed_game_over(
        "daily_routine_cleanup",
        "success",
        "cleanup_complete",
    )
    assert is_allowed_game_over(
        "daily_routine_cleanup",
        "failure",
        "cleanup_incomplete",
    )
    assert is_allowed_game_over(
        "garden_watering",
        "success",
        "garden_tasks_complete",
    )
    assert is_allowed_game_over(
        "garden_watering",
        "failure",
        "garden_task_failed",
    )
    assert is_allowed_game_over(
        "conveyor_profit",
        "success",
        "efficiency_target_reached",
    )
    assert is_allowed_game_over(
        "conveyor_profit",
        "failure",
        "efficiency_below_target",
    )
    assert not is_allowed_game_over(
        "greet_npc_meeting",
        "success",
        "book_in_box",
    )
    assert is_allowed_game_over("find_contract", "failure", "max_requests")
    assert is_allowed_game_over("find_key", "failure", "max_requests")
    assert is_allowed_game_over("put_book", "failure", "max_requests")
    assert is_allowed_game_over(
        "greet_npc_meeting",
        "failure",
        "max_requests",
    )
    assert is_allowed_game_over(
        "daily_routine_cleanup",
        "failure",
        "max_requests",
    )
    assert is_allowed_game_over(
        "garden_watering",
        "failure",
        "max_requests",
    )
    assert not is_allowed_game_over(
        "daily_routine_cleanup",
        "success",
        "meeting_door_closed",
    )
    assert not is_allowed_game_over(
        "garden_watering",
        "success",
        "cleanup_complete",
    )
