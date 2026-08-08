import math

import pytest

from ai_play.action_schema import ActionValidationError, validate_action_batch


def test_validate_action_batch_accepts_current_safe_actions():
    actions = [
        {"type": "look", "yaw": -5, "pitch": 0},
        {"type": "move", "forward": 1, "right": 0, "duration_ms": 100},
        {"type": "interact", "action": "interact"},
    ]

    assert validate_action_batch(actions, {"interact"}, False) == actions


def test_validate_action_batch_accepts_loop_staircase_semantic_actions():
    actions = [
        {"type": "front", "step": "small"},
        {"type": "left", "step": "large"},
        {"type": "floor_up"},
    ]

    assert validate_action_batch(
        actions,
        set(),
        False,
        scenario_id="loop_staircase_anomaly",
    ) == actions
    board_actions = [
        {"type": "board_down"},
        {"type": "toggle_mark"},
    ]
    assert validate_action_batch(
        board_actions,
        set(),
        False,
        scenario_id="loop_staircase_anomaly",
    ) == board_actions
    assert validate_action_batch(
        [{"type": "toggle_board"}],
        set(),
        False,
        scenario_id="loop_staircase_anomaly",
    ) == [{"type": "toggle_board"}]
    assert validate_action_batch(
        [{"type": "floor_down"}, {"type": "submit_floor"}],
        set(),
        False,
        scenario_id="loop_staircase_anomaly",
    ) == [{"type": "floor_down"}, {"type": "submit_floor"}]


@pytest.mark.parametrize(
    "action",
    [
        {"type": "back", "step": "small"},
        {"type": "right", "step": "large"},
        {"type": "floor_up"},
        {"type": "floor_down"},
        {"type": "toggle_board"},
        {"type": "board_up"},
        {"type": "board_down"},
        {"type": "toggle_mark"},
        {"type": "submit_floor"},
    ],
)
def test_validate_action_batch_rejects_loop_actions_outside_loop_staircase(action):
    with pytest.raises(ActionValidationError, match="not allowed for this scenario"):
        validate_action_batch(
            [action],
            set(),
            False,
            scenario_id="find_contract",
        )


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
        [{"type": "look", "yaw": 5}],
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
        {"type": "look", "yaw": 0, "pitch": 45.1},
        {"type": "look", "yaw": math.inf, "pitch": 0},
        {"type": "look", "direction": "north", "degrees": 10},
        {"type": "move", "forward": -1.1, "right": 0, "duration_ms": 50},
        {"type": "move", "forward": 0, "right": 0, "duration_ms": 251},
        {"type": "sprint", "forward": 0, "right": 0, "duration_ms": 251},
        {"type": "look", "yaw": True, "pitch": 0},
        {"type": "enter_digits", "digits": "12A"},
        {"type": "press_key", "key": "escape"},
        {"type": "press_key", "key": 1},
        {"type": "front", "step": "medium"},
        {"type": "back", "step": 80},
    ],
)
def test_validate_action_batch_rejects_unsafe_action_values(action):
    with pytest.raises(ActionValidationError):
        validate_action_batch([action], {"interact"}, False)


@pytest.mark.parametrize(("yaw", "pitch"), [(-45, 0), (45, 0), (0, -45), (0, 45)])
def test_validate_action_batch_accepts_bounded_look_axes(yaw, pitch):
    action = {"type": "look", "yaw": yaw, "pitch": pitch}

    assert validate_action_batch([action], set(), False) == [action]


def test_validate_action_batch_rejects_legacy_loop_key_press():
    with pytest.raises(ActionValidationError, match="not allowed"):
        validate_action_batch(
            [{"type": "press_key", "key": "up"}],
            set(),
            False,
            scenario_id="loop_staircase_anomaly",
        )


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
    with pytest.raises(
        ActionValidationError,
        match="submit exactly one probe_interaction entry",
    ):
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


def test_conveyor_rejects_undo():
    with pytest.raises(ActionValidationError, match="not allowed"):
        validate_action_batch(
            [{"type": "undo"}], set(), False, "conveyor_profit"
        )


@pytest.mark.parametrize("ingredient", ["potato", "Tomato", "../tomato", 7])
def test_conveyor_ingredient_ids_are_exact(ingredient):
    with pytest.raises(ActionValidationError, match="ingredient"):
        validate_action_batch(
            [{"type": "select_ingredient", "ingredient": ingredient}],
            set(),
            False,
            "conveyor_profit",
        )


@pytest.mark.parametrize("ingredient", [
    "lettuce", "tomato", "carrot", "avocado", "sausage", "mushroom",
    "onion", "pumpkin", "bread", "meat", "egg", "cheese", "bacon",
    "broccoli", "corn", "fish",
])
def test_conveyor_accepts_every_public_ingredient_id(ingredient):
    action = {"type": "select_ingredient", "ingredient": ingredient}

    assert validate_action_batch(
        [action], set(), False, "conveyor_profit"
    ) == [action]


def test_conveyor_make_must_end_the_batch():
    with pytest.raises(ActionValidationError, match="last"):
        validate_action_batch(
            [
                {"type": "make"},
                {"type": "select_ingredient", "ingredient": "tomato"},
            ],
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
            [
                {"type": "select_ingredient", "ingredient": "tomato"},
                action,
            ],
            set(),
            False,
            "conveyor_profit",
        )
    with pytest.raises(ActionValidationError, match="scenario"):
        validate_action_batch([action], set(), False, "find_key")
