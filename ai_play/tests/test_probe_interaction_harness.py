from copy import deepcopy
import json

import pytest

from ai_play.probe_interaction_harness import build_probe_interaction_harness


SUCCESS_CONDITION = "current_available_interactions_non_empty"


def observation():
    return {
        "interface": {
            "is_open": False,
            "available_interactions": [],
        },
        "last_action_results": [],
    }


def expected(status, success, available_actions, required_next_step):
    return {
        "status": status,
        "success": success,
        "success_condition": SUCCESS_CONDITION,
        "available_actions": available_actions,
        "required_next_step": required_next_step,
    }


@pytest.mark.parametrize(
    ("outcome", "status", "required_next_step"),
    [
        ("aligned", "inconsistent", "reobserve_before_interacting"),
        ("not_found", "not_aligned", "approach_or_choose_new_target"),
    ],
)
def test_completed_probe_without_current_interactions_is_not_success(
    outcome,
    status,
    required_next_step,
):
    value = observation()
    value["last_action_results"] = [{
        "status": "completed",
        "type": "probe_interaction",
        "outcome": outcome,
        "scan_steps": 3,
    }]

    assert build_probe_interaction_harness(value) == expected(
        status,
        False,
        [],
        required_next_step,
    )


def test_current_interactions_are_the_only_alignment_success():
    value = observation()
    value["interface"]["available_interactions"] = [
        {"action": "interact", "binding": "F", "prompt": "Read secret"},
        {"action": "interact", "binding": "F", "prompt": "Duplicate"},
        {"action": "interact2", "binding": "E", "prompt": "Move"},
    ]
    value["last_action_results"] = [{
        "status": "completed",
        "type": "probe_interaction",
        "outcome": "not_found",
        "scan_steps": 9,
    }]
    original = deepcopy(value)

    result = build_probe_interaction_harness(value)

    assert result == expected(
        "aligned",
        True,
        ["interact", "interact2"],
        "use_available_interaction",
    )
    assert "Read secret" not in json.dumps(result)
    assert value == original


def test_open_interface_has_priority_over_visible_interactions():
    value = observation()
    value["interface"]["is_open"] = True
    value["interface"]["available_interactions"] = [
        {"action": "interact", "binding": "F", "prompt": "Read"},
    ]

    assert build_probe_interaction_harness(value) == expected(
        "interface_open",
        False,
        ["interact"],
        "resolve_open_interface",
    )


def test_no_probe_feedback_is_ready_to_probe():
    assert build_probe_interaction_harness(observation()) == expected(
        "ready_to_probe",
        False,
        [],
        "locate_visible_candidate",
    )


def test_only_latest_completed_probe_result_controls_failure_state():
    value = observation()
    value["last_action_results"] = [
        {
            "status": "completed",
            "type": "probe_interaction",
            "outcome": "not_found",
            "scan_steps": 9,
        },
        {"status": "completed", "type": "move"},
    ]

    assert build_probe_interaction_harness(value) == expected(
        "not_aligned",
        False,
        [],
        "approach_or_choose_new_target",
    )
