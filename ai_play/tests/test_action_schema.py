import math

import pytest

from ai_play.action_schema import ActionValidationError, validate_decision


def valid(payload, interactions={"interact"}, interface_open=False):
    return validate_decision(payload, interactions, interface_open)


def decision(*actions):
    return {"reason": "explore", "memory_updates": [], "actions": list(actions)}


def test_accepts_bounded_actions():
    payload = decision(
        {"type": "look", "yaw": 10, "pitch": -2},
        {"type": "move", "forward": 1, "right": 0, "duration_ms": 600},
        {"type": "interact", "action": "interact"},
    )

    result = valid(payload)

    assert result is payload
    assert len(result["actions"]) == 3


@pytest.mark.parametrize(
    "action",
    [
        {"type": "press_key", "key": "F"},
        {"type": "move", "forward": 1, "right": 0, "duration_ms": 1001},
        {"type": "look", "yaw": math.inf, "pitch": 0},
        {"type": "enter_digits", "digits": "12A"},
    ],
)
def test_rejects_unsafe_actions(action):
    with pytest.raises(ActionValidationError):
        valid(decision(action))


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"reason": "x", "memory_updates": [], "actions": [], "extra": True},
        {"reason": "x", "memory_updates": []},
    ],
)
def test_rejects_invalid_decision_fields(payload):
    with pytest.raises(ActionValidationError, match="fields"):
        valid(payload)


@pytest.mark.parametrize("reason", [None, 42, "x" * 501])
def test_rejects_invalid_reason(reason):
    with pytest.raises(ActionValidationError, match="reason"):
        valid({"reason": reason, "memory_updates": [], "actions": [{"type": "stop"}]})


def test_rejects_non_list_memory_updates():
    with pytest.raises(ActionValidationError, match="memory_updates"):
        valid({"reason": "x", "memory_updates": {}, "actions": [{"type": "stop"}]})


@pytest.mark.parametrize("actions", [None, [], [{"type": "stop"}] * 4])
def test_rejects_invalid_action_count(actions):
    with pytest.raises(ActionValidationError, match="1..3"):
        valid({"reason": "x", "memory_updates": [], "actions": actions})


@pytest.mark.parametrize(
    "action",
    [
        None,
        {"type": "stop", "extra": 1},
        {"type": "look", "yaw": 0},
        {"type": "made_up"},
        {"type": []},
        {"type": "interact", "action": []},
    ],
)
def test_rejects_unknown_or_missing_action_fields(action):
    with pytest.raises(ActionValidationError):
        valid(decision(action))


@pytest.mark.parametrize(
    ("action_type", "action"),
    [
        ("look", {"type": "look", "yaw": -45, "pitch": 30}),
        ("move", {"type": "move", "forward": -1, "right": 1, "duration_ms": 50}),
        ("sprint", {"type": "sprint", "forward": 1, "right": -1, "duration_ms": 1000}),
        ("wait", {"type": "wait", "duration_ms": 2000}),
    ],
)
def test_accepts_numeric_boundaries(action_type, action):
    assert valid(decision(action))["actions"][0]["type"] == action_type


@pytest.mark.parametrize(
    "action",
    [
        {"type": "look", "yaw": -45.1, "pitch": 0},
        {"type": "look", "yaw": 0, "pitch": 30.1},
        {"type": "look", "yaw": math.nan, "pitch": 0},
        {"type": "move", "forward": -1.1, "right": 0, "duration_ms": 50},
        {"type": "sprint", "forward": 0, "right": math.inf, "duration_ms": 50},
        {"type": "move", "forward": 0, "right": 0, "duration_ms": 49},
        {"type": "wait", "duration_ms": 2001},
        {"type": "look", "yaw": True, "pitch": 0},
    ],
)
def test_rejects_out_of_range_or_non_finite_numbers(action):
    with pytest.raises(ActionValidationError):
        valid(decision(action))


def test_rejects_unrepresentably_large_integer_as_validation_error():
    with pytest.raises(ActionValidationError):
        valid(decision({"type": "look", "yaw": 10**10000, "pitch": 0}))


def test_rejects_interaction_not_currently_visible():
    with pytest.raises(ActionValidationError, match="available"):
        valid(decision({"type": "interact", "action": "interact2"}))


@pytest.mark.parametrize("action_name", ["F", "E", "use", ""])
def test_rejects_arbitrary_interaction_names_even_if_visible(action_name):
    with pytest.raises(ActionValidationError):
        valid(decision({"type": "interact", "action": action_name}), {action_name})


@pytest.mark.parametrize("digits", ["0", "123456"])
def test_accepts_one_to_six_digits_when_interface_is_open(digits):
    assert valid(decision({"type": "enter_digits", "digits": digits}), interface_open=True)


@pytest.mark.parametrize("digits", ["", "1234567", "12A", 123, "１２"])
def test_rejects_invalid_digits(digits):
    with pytest.raises(ActionValidationError):
        valid(decision({"type": "enter_digits", "digits": digits}), interface_open=True)


def test_digits_require_open_interface():
    with pytest.raises(ActionValidationError, match="interface"):
        valid(decision({"type": "enter_digits", "digits": "123"}))


def test_close_ui_requires_open_interface():
    with pytest.raises(ActionValidationError, match="interface"):
        valid(decision({"type": "close_ui"}))


@pytest.mark.parametrize("action_type", ["jump", "crouch", "close_ui", "stop"])
def test_accepts_exact_field_state_actions(action_type):
    assert valid(decision({"type": action_type}), interface_open=True)


@pytest.mark.parametrize(
    ("actions", "interface_open"),
    [
        ([{"type": "stop"}, {"type": "look", "yaw": 0, "pitch": 0}], False),
        ([{"type": "interact", "action": "interact"}, {"type": "wait", "duration_ms": 50}], False),
        ([{"type": "enter_digits", "digits": "1"}, {"type": "wait", "duration_ms": 50}], True),
        ([{"type": "close_ui"}, {"type": "wait", "duration_ms": 50}], True),
    ],
)
def test_context_changing_actions_must_end_the_batch(actions, interface_open):
    with pytest.raises(ActionValidationError, match="last"):
        valid(decision(*actions), interface_open=interface_open)
