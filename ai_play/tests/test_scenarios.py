from pathlib import Path

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
        "repair_lighting_circuit",
        "arrange_meeting_briefings",
        "conveyor_profit",
        "loop_staircase_anomaly",
        "laboratory_experiment",
    )
    assert is_supported_scenario("find_contract")
    assert is_supported_scenario("find_key")
    assert is_supported_scenario("put_book")
    assert is_supported_scenario("greet_npc_meeting")
    assert is_supported_scenario("daily_routine_cleanup")
    assert is_supported_scenario("garden_watering")
    assert is_supported_scenario("repair_lighting_circuit")
    assert is_supported_scenario("arrange_meeting_briefings")
    assert is_supported_scenario("conveyor_profit")
    assert is_supported_scenario("loop_staircase_anomaly")
    assert is_supported_scenario("laboratory_experiment")
    assert not is_supported_scenario("unknown")
    assert not is_supported_scenario(True)


def test_scenario_registry_loads_public_briefing_and_rejects_unknown():
    briefing, image_bytes = load_scenario_briefing("find_contract")

    assert briefing["game_id"] == "find_contract"
    assert image_bytes.startswith(b"\xff\xd8\xff")
    with pytest.raises(RuntimeError, match="unsupported_scenario"):
        load_scenario_briefing("unknown")


def test_loop_staircase_briefing_exposes_distinct_semantic_controls():
    briefing, _image_bytes = load_scenario_briefing("loop_staircase_anomaly")
    text = " ".join(briefing["rules"])

    assert "press_key" not in text
    assert '"front"' in text
    assert '"back"' in text
    assert '"left"' in text
    assert '"right"' in text
    assert '"floor_up"' in text
    assert '"floor_down"' in text
    assert '"toggle_board"' in text
    assert '"board_up"' in text
    assert '"board_down"' in text
    assert '"toggle_mark"' in text
    assert '"submit_floor"' in text
    assert "调查板" in text
    assert "small" in text
    assert "large" in text


def test_loop_staircase_briefing_recommends_scanning_room_blind_spots():
    briefing, _image_bytes = load_scenario_briefing("loop_staircase_anomaly")
    exploration_rules = [
        rule for rule in briefing["rules"] if "视野盲区" in rule
    ]

    assert len(exploration_rules) == 1
    rule = exploration_rules[0]
    assert rule.startswith("推荐")
    assert "look" in rule
    assert "前、后、左、右" in rule
    assert "单张初始截图可能无法覆盖" in rule
    assert "必须" not in rule


def test_scenario_request_limits_are_hard_caps():
    assert scenario_act_request_limit("find_contract", 500) == 300
    assert scenario_act_request_limit("find_contract", 120) == 120
    assert scenario_act_request_limit("find_key", 500) == 100
    assert scenario_act_request_limit("find_key", 80) == 80
    assert scenario_act_request_limit("put_book", 500) == 150
    assert scenario_act_request_limit("put_book", 120) == 120
    assert scenario_act_request_limit("greet_npc_meeting", 500) == 100
    assert scenario_act_request_limit("greet_npc_meeting", 75) == 75
    assert scenario_act_request_limit("daily_routine_cleanup", 500) == 150
    assert scenario_act_request_limit("daily_routine_cleanup", 90) == 90
    assert scenario_act_request_limit("garden_watering", 500) == 80
    assert scenario_act_request_limit("garden_watering", 60) == 60
    assert scenario_act_request_limit("repair_lighting_circuit", 500) == 100
    assert scenario_act_request_limit("repair_lighting_circuit", 80) == 80
    assert scenario_act_request_limit("arrange_meeting_briefings", 500) == 100
    assert scenario_act_request_limit("arrange_meeting_briefings", 80) == 80
    assert scenario_act_request_limit("conveyor_profit", 500) == 300
    assert scenario_act_request_limit("loop_staircase_anomaly", 500) == 160
    assert scenario_act_request_limit("loop_staircase_anomaly", 90) == 90
    assert scenario_act_request_limit("laboratory_experiment", 500) == 150
    assert scenario_act_request_limit("laboratory_experiment", 90) == 90


def test_readme_lists_all_request_caps_in_scenario_order():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()

    assert (
        "自身的 300、50、150、100、150、80、100、100、300、160、150 次硬上限"
        in readme
    )


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
    assert scenario_registry._SCENARIOS["put_book"].terminal_results == frozenset({
        ("success", "books_in_ceo_office"),
        ("failure", "wrong_book_pickup"),
        ("failure", "max_requests"),
    })
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
    assert is_allowed_game_over("put_book", "success", "books_in_ceo_office")
    assert is_allowed_game_over("put_book", "failure", "wrong_book_pickup")
    assert not is_allowed_game_over("put_book", "success", "book_in_box")
    assert not is_allowed_game_over("put_book", "failure", "book_in_wrong_box")
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
        "repair_lighting_circuit",
        "success",
        "circuit_repaired",
    )
    assert is_allowed_game_over(
        "repair_lighting_circuit",
        "failure",
        "wrong_breaker",
    )
    assert is_allowed_game_over(
        "repair_lighting_circuit",
        "failure",
        "incorrect_circuit_configuration",
    )
    assert is_allowed_game_over(
        "arrange_meeting_briefings",
        "success",
        "meeting_prepared",
    )
    assert is_allowed_game_over(
        "arrange_meeting_briefings",
        "failure",
        "incorrect_seating_assignment",
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
    assert is_allowed_game_over(
        "loop_staircase_anomaly",
        "success",
        "correct_floor_selected",
    )
    assert is_allowed_game_over(
        "loop_staircase_anomaly",
        "failure",
        "wrong_floor_selected",
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
    assert is_allowed_game_over(
        "repair_lighting_circuit",
        "failure",
        "max_requests",
    )
    assert is_allowed_game_over(
        "arrange_meeting_briefings",
        "failure",
        "max_requests",
    )
    assert is_allowed_game_over(
        "conveyor_profit",
        "failure",
        "max_requests",
    )
    assert not is_allowed_game_over(
        "find_contract",
        "success",
        "circuit_repaired",
    )
    assert not is_allowed_game_over(
        "find_contract",
        "success",
        "meeting_prepared",
    )
    assert not is_allowed_game_over(
        "arrange_meeting_briefings",
        "success",
        "circuit_repaired",
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
    assert is_allowed_game_over(
        "loop_staircase_anomaly",
        "failure",
        "max_requests",
    )
    assert not is_allowed_game_over(
        "loop_staircase_anomaly",
        "success",
        "garden_tasks_complete",
    )
    assert is_allowed_game_over(
        "laboratory_experiment",
        "success",
        "experiment_completed",
    )
    assert is_allowed_game_over(
        "laboratory_experiment",
        "failure",
        "experiment_attempts_exhausted",
    )
    assert is_allowed_game_over(
        "laboratory_experiment",
        "failure",
        "max_requests",
    )
    assert not is_allowed_game_over(
        "laboratory_experiment",
        "success",
        "correct_password",
    )


def test_loop_staircase_anomaly_loads_public_briefing():
    briefing, image_bytes = load_scenario_briefing("loop_staircase_anomaly")

    assert briefing["game_id"] == "loop_staircase_anomaly"
    assert briefing["success_condition"] == "第五轮选择唯一满足完整累计证据链的楼层。"
    serialized = str(briefing)
    assert "exactly two boxes" not in serialized.lower()
    assert "五轮" in serialized
    assert "2F 到 9F" in serialized
    assert "调查板" in serialized
    assert "跨轮" in serialized or "逐轮" in serialized
    assert "target symbol" not in serialized.lower()
    for symbol in ("circle", "triangle", "square", "star"):
        assert symbol not in serialized.lower()
    for secret in (
        "受害者姓名",
        "清洁员",
        "垃圾",
        "ABAB",
        "红蓝红蓝",
        "访客时间",
        "8 → 6 → 5 → 3 → 2 → 1",
        "凶案楼层",
    ):
        assert secret not in serialized
    assert image_bytes is None


def test_laboratory_experiment_loads_public_briefing_without_solution():
    briefing, image_bytes = load_scenario_briefing("laboratory_experiment")

    assert briefing["game_id"] == "laboratory_experiment"
    assert "三次" in briefing["failure_condition"]
    assert "interact2" in str(briefing["objects"])
    assert image_bytes is None
    assert "answer" not in str(briefing).lower()
    assert "solution" not in str(briefing).lower()
