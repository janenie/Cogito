import math

import pytest

from ai_play.action_schema import ActionValidationError, validate_action_batch


def test_validate_action_batch_accepts_current_safe_actions():
    actions = [
        {"type": "look", "yaw": 5, "pitch": -2},
        {"type": "move", "forward": 1, "right": 0, "duration_ms": 100},
        {"type": "interact", "action": "interact"},
    ]

    assert validate_action_batch(actions, {"interact"}, False) == actions


def test_validate_action_batch_rejects_unavailable_interaction():
    actions = [{"type": "interact", "action": "interact2"}]

    with pytest.raises(ActionValidationError, match="currently available"):
        validate_action_batch(actions, {"interact"}, False)


@pytest.mark.parametrize(
    "actions",
    [
        None,
        [],
        [{"type": "wait", "duration_ms": 50}] * 4,
        [{"type": "made_up"}],
        [{"type": "look", "yaw": 0}],
        [{"type": "move", "forward": 0, "right": 0, "duration_ms": 100, "extra": 1}],
    ],
)
def test_validate_action_batch_rejects_invalid_shape(actions):
    with pytest.raises(ActionValidationError):
        validate_action_batch(actions, set(), False)


@pytest.mark.parametrize(
    "action",
    [
        {"type": "look", "yaw": -45.1, "pitch": 0},
        {"type": "look", "yaw": math.inf, "pitch": 0},
        {"type": "move", "forward": -1.1, "right": 0, "duration_ms": 50},
        {"type": "move", "forward": 0, "right": 0, "duration_ms": 1001},
        {"type": "look", "yaw": True, "pitch": 0},
        {"type": "enter_digits", "digits": "12A"},
    ],
)
def test_validate_action_batch_rejects_unsafe_action_values(action):
    with pytest.raises(ActionValidationError):
        validate_action_batch([action], {"interact"}, False)


@pytest.mark.parametrize(
    ("actions", "interface_open"),
    [
        ([{"type": "stop"}, {"type": "wait", "duration_ms": 50}], False),
        ([{"type": "interact", "action": "interact"}, {"type": "wait", "duration_ms": 50}], False),
        ([{"type": "enter_digits", "digits": "1"}, {"type": "wait", "duration_ms": 50}], True),
        ([{"type": "close_ui"}, {"type": "wait", "duration_ms": 50}], True),
    ],
)
def test_context_changing_actions_must_end_the_batch(actions, interface_open):
    with pytest.raises(ActionValidationError, match="last"):
        validate_action_batch(actions, {"interact"}, interface_open)


def test_probe_interaction_must_be_the_only_action_and_use_closed_interface():
    probe = {"type": "probe_interaction", "target_x": 0.2, "target_y": 0.3}

    assert validate_action_batch([probe], set(), False) == [probe]
    with pytest.raises(ActionValidationError):
        validate_action_batch([probe, {"type": "wait", "duration_ms": 50}], set(), False)
    with pytest.raises(ActionValidationError, match="closed interface"):
        validate_action_batch([probe], set(), True)


@pytest.mark.parametrize("digits", ["", "1234567", "12A", 123, "１２"])
def test_digits_must_be_one_to_six_ascii_digits(digits):
    with pytest.raises(ActionValidationError):
        validate_action_batch([{"type": "enter_digits", "digits": digits}], set(), True)


def test_interface_actions_require_open_interface():
    for action in [
        {"type": "enter_digits", "digits": "123"},
        {"type": "close_ui"},
    ]:
        with pytest.raises(ActionValidationError, match="interface"):
            validate_action_batch([action], set(), False)
