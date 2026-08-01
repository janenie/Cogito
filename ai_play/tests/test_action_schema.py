import math

import pytest

from ai_play.action_schema import ActionValidationError, validate_action_batch


def test_validate_action_batch_accepts_current_safe_actions():
    actions = [
        {"type": "look", "direction": "left", "degrees": 5},
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
        [{"type": "stop"}],
        [{"type": "look", "direction": "left"}],
        [{"type": "move", "forward": 0, "right": 0, "duration_ms": 100, "extra": 1}],
    ],
)
def test_validate_action_batch_rejects_invalid_shape(actions):
    with pytest.raises(ActionValidationError):
        validate_action_batch(actions, set(), False)


@pytest.mark.parametrize(
    "action",
    [
        {"type": "look", "yaw": -15, "pitch": 0},
        {"type": "look", "direction": "north", "degrees": 10},
        {"type": "look", "direction": "left", "degrees": 0},
        {"type": "look", "direction": "left", "degrees": 45.1},
        {"type": "look", "direction": "left", "degrees": math.inf},
        {"type": "move", "forward": -1.1, "right": 0, "duration_ms": 50},
        {"type": "move", "forward": 0, "right": 0, "duration_ms": 251},
        {"type": "sprint", "forward": 0, "right": 0, "duration_ms": 251},
        {"type": "look", "direction": "left", "degrees": True},
        {"type": "enter_digits", "digits": "12A"},
    ],
)
def test_validate_action_batch_rejects_unsafe_action_values(action):
    with pytest.raises(ActionValidationError):
        validate_action_batch([action], {"interact"}, False)


@pytest.mark.parametrize("direction", ["left", "right", "up", "down"])
@pytest.mark.parametrize("degrees", [1, 45])
def test_validate_action_batch_accepts_semantic_look_directions(
    direction,
    degrees,
):
    action = {"type": "look", "direction": direction, "degrees": degrees}

    assert validate_action_batch([action], set(), False) == [action]


@pytest.mark.parametrize(
    ("actions", "interface_open"),
    [
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


def test_conveyor_actions_are_scenario_gated():
    actions = [
        {"type": "select_ingredient", "ingredient": "tomato"},
        {"type": "make"},
    ]

    assert validate_action_batch(
        actions,
        set(),
        False,
        "conveyor_profit",
    ) == actions
    with pytest.raises(ActionValidationError, match="scenario"):
        validate_action_batch(actions, set(), False, "find_contract")


@pytest.mark.parametrize("ingredient", ["potato", "Tomato", "../tomato", 7])
def test_conveyor_ingredient_ids_are_exact(ingredient):
    with pytest.raises(ActionValidationError, match="ingredient"):
        validate_action_batch(
            [{"type": "select_ingredient", "ingredient": ingredient}],
            set(),
            False,
            "conveyor_profit",
        )


def test_conveyor_make_must_end_the_batch():
    with pytest.raises(ActionValidationError, match="last"):
        validate_action_batch(
            [{"type": "make"}, {"type": "undo"}],
            set(),
            False,
            "conveyor_profit",
        )


def test_wait_next_window_is_conveyor_only_and_solo():
    action = {"type": "wait_next_window"}

    assert validate_action_batch(
        [action], set(), False, "conveyor_profit"
    ) == [action]
    with pytest.raises(ActionValidationError, match="only action"):
        validate_action_batch(
            [{"type": "undo"}, action], set(), False, "conveyor_profit"
        )
    with pytest.raises(ActionValidationError, match="scenario"):
        validate_action_batch([action], set(), False, "find_key")
