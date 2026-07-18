"""Strict validation for model-selected player actions."""

import math
import re


class ActionValidationError(ValueError):
    """Raised when a model decision is outside the safe action schema."""


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
    "stop": {"type"},
}


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


def _validate_action(action, available_interactions, interface_open):
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

    if action_type == "look":
        _require_number(action["yaw"], -45, 45, "yaw")
        _require_number(action["pitch"], -30, 30, "pitch")
    elif action_type in {"move", "sprint"}:
        _require_number(action["forward"], -1, 1, "forward")
        _require_number(action["right"], -1, 1, "right")
        _require_number(action["duration_ms"], 50, 1000, "duration_ms")
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


def validate_decision(payload, available_interactions, interface_open):
    """Validate and return a decoded model decision without modifying it."""
    if not isinstance(payload, dict) or set(payload) != {
        "reason",
        "memory_updates",
        "actions",
    }:
        raise ActionValidationError("decision has invalid fields")
    if not isinstance(payload["reason"], str) or len(payload["reason"]) > 500:
        raise ActionValidationError("reason must be a short string")
    if not isinstance(payload["memory_updates"], list):
        raise ActionValidationError("memory_updates must be a list")

    actions = payload["actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= 3:
        raise ActionValidationError("actions must contain 1..3 entries")

    available = set(available_interactions)
    for action in actions:
        _validate_action(action, available, interface_open)
    return payload
