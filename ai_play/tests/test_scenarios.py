import pytest

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
    )
    assert is_supported_scenario("find_contract")
    assert is_supported_scenario("find_key")
    assert is_supported_scenario("put_book")
    assert is_supported_scenario("greet_npc_meeting")
    assert is_supported_scenario("daily_routine_cleanup")
    assert not is_supported_scenario("unknown")
    assert not is_supported_scenario(True)


def test_scenario_registry_loads_public_briefing_and_rejects_unknown():
    briefing, image_bytes = load_scenario_briefing("find_contract")

    assert briefing["game_id"] == "find_contract"
    assert image_bytes.startswith(b"\xff\xd8\xff")
    with pytest.raises(RuntimeError, match="unsupported_scenario"):
        load_scenario_briefing("unknown")


def test_scenario_request_limits_are_hard_caps():
    assert scenario_act_request_limit("find_contract", 500) == 500
    assert scenario_act_request_limit("find_contract", 120) == 120
    assert scenario_act_request_limit("find_key", 500) == 200
    assert scenario_act_request_limit("find_key", 80) == 80
    assert scenario_act_request_limit("put_book", 500) == 50
    assert scenario_act_request_limit("put_book", 35) == 35
    assert scenario_act_request_limit("greet_npc_meeting", 500) == 100
    assert scenario_act_request_limit("greet_npc_meeting", 75) == 75
    assert scenario_act_request_limit("daily_routine_cleanup", 500) == 150
    assert scenario_act_request_limit("daily_routine_cleanup", 90) == 90


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
    assert not is_allowed_game_over(
        "daily_routine_cleanup",
        "success",
        "meeting_door_closed",
    )
