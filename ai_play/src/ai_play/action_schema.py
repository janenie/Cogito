"""Strict validation for actions entering the Godot executor."""

import math
import re


class ActionValidationError(ValueError):
    """Raised when an action is outside the safe action schema."""


LOOK_MAX_DEGREES = 45
MOVE_MAX_DURATION_MS = 250
LOOP_STEP_SIZES = {"small", "large"}

ALLOWED_KEYS = {
    "look": {"type", "yaw", "pitch"},
    "move": {"type", "forward", "right", "duration_ms"},
    "sprint": {"type", "forward", "right", "duration_ms"},
    "jump": {"type"},
    "crouch": {"type"},
    "interact": {"type", "action"},
    "enter_digits": {"type", "digits"},
    "close_ui": {"type"},
    "wait": {"type", "duration_ms"},
    "probe_interaction": {"type", "target_x", "target_y"},
    "select_ingredient": {"type", "ingredient"},
    "undo": {"type"},
    "make": {"type"},
    "wait_next_window": {"type"},
    "front": {"type", "step"},
    "back": {"type", "step"},
    "left": {"type", "step"},
    "right": {"type", "step"},
    "floor_up": {"type"},
    "floor_down": {"type"},
    "toggle_board": {"type"},
    "board_up": {"type"},
    "board_down": {"type"},
    "toggle_mark": {"type"},
    "submit_floor": {"type"},
}
CONVEYOR_ACTIONS = frozenset({
    "select_ingredient", "undo", "make", "wait_next_window",
})
CONVEYOR_INGREDIENT_IDS = frozenset({
    "lettuce", "tomato", "carrot", "avocado", "sausage", "mushroom",
    "onion", "pumpkin", "bread", "meat", "egg", "cheese", "bacon",
    "broccoli", "corn", "fish",
})
LOOP_STAIRCASE_ACTIONS = frozenset({
    "front", "back", "left", "right", "floor_up", "floor_down",
    "toggle_board", "board_up", "board_down", "toggle_mark", "submit_floor",
})


def _require_number(value, lower, upper, field):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not lower <= value <= upper
        or not math.isfinite(value)
    ):
        raise ActionValidationError(
            f"{field} must be a finite number between {lower} and {upper}"
        )


def _validate_action(action, available_interactions, interface_open, scenario_id):
    if not isinstance(action, dict):
        raise ActionValidationError("action must be an object")

    action_type = action.get("type")
    if not isinstance(action_type, str):
        raise ActionValidationError("action type is not allowed")
    expected_keys = ALLOWED_KEYS.get(action_type)
    if expected_keys is None:
        raise ActionValidationError("action type is not allowed")
    if set(action) != expected_keys:
        raise ActionValidationError("action has invalid fields")
    if action_type in CONVEYOR_ACTIONS and scenario_id != "conveyor_profit":
        raise ActionValidationError("action is not allowed for this scenario")
    if (
        action_type in LOOP_STAIRCASE_ACTIONS
        and scenario_id != "loop_staircase_anomaly"
    ):
        raise ActionValidationError("action is not allowed for this scenario")

    if action_type == "look":
        _require_number(action["yaw"], -LOOK_MAX_DEGREES, LOOK_MAX_DEGREES, "yaw")
        _require_number(
            action["pitch"], -LOOK_MAX_DEGREES, LOOK_MAX_DEGREES, "pitch"
        )
    elif action_type in {"front", "back", "left", "right"}:
        step = action["step"]
        if not isinstance(step, str) or step not in LOOP_STEP_SIZES:
            raise ActionValidationError("step must be small or large")
    elif action_type in {"move", "sprint"}:
        _require_number(action["forward"], -1, 1, "forward")
        _require_number(action["right"], -1, 1, "right")
        _require_number(action["duration_ms"], 50, MOVE_MAX_DURATION_MS, "duration_ms")
    elif action_type == "wait":
        _require_number(action["duration_ms"], 50, 2000, "duration_ms")
    elif action_type == "interact":
        interaction = action["action"]
        if not isinstance(interaction, str) or interaction not in {
            "interact",
            "interact2",
        }:
            raise ActionValidationError("interaction action is not allowed")
        if interaction not in available_interactions:
            raise ActionValidationError("interaction is not currently available")
    elif action_type == "enter_digits":
        digits = action["digits"]
        if not isinstance(digits, str) or re.fullmatch(r"[0-9]{1,6}", digits) is None:
            raise ActionValidationError("digits must contain one to six decimal digits")
        if not interface_open:
            raise ActionValidationError("enter_digits requires an open interface")
    elif action_type == "close_ui" and not interface_open:
        raise ActionValidationError("close_ui requires an open interface")
    elif action_type == "probe_interaction":
        _require_number(action["target_x"], 0, 1, "target_x")
        _require_number(action["target_y"], 0, 1, "target_y")
        if interface_open:
            raise ActionValidationError(
                "probe_interaction requires a closed interface"
            )
    elif action_type == "select_ingredient":
        ingredient = action["ingredient"]
        if (
            not isinstance(ingredient, str)
            or ingredient not in CONVEYOR_INGREDIENT_IDS
        ):
            raise ActionValidationError("ingredient is not allowed")


def validate_action_batch(
    actions,
    available_interactions,
    interface_open,
    scenario_id=None,
):
    """Validate and return an unchanged bounded batch of player actions."""
    if not isinstance(actions, list) or not 1 <= len(actions) <= 3:
        raise ActionValidationError("actions must contain 1..3 entries")

    available = set(available_interactions)
    for index, action in enumerate(actions):
        _validate_action(action, available, interface_open, scenario_id)
        if action["type"] == "wait_next_window" and len(actions) != 1:
            raise ActionValidationError("wait_next_window must be the only action")
        if action["type"] in {
            "interact", "enter_digits", "close_ui", "make", "toggle_board",
            "submit_floor",
        }:
            if index != len(actions) - 1:
                raise ActionValidationError("context-changing action must be last")
    if (
        any(action["type"] == "probe_interaction" for action in actions)
        and len(actions) != 1
    ):
        raise ActionValidationError("probe_interaction must be the only action")
    return actions
