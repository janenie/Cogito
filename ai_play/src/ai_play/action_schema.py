"""Strict validation for model-selected player actions."""

import math
import re
import unicodedata


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
MEMORY_UPDATE_KEYS = {
    "fact": {"kind", "text", "source", "confidence"},
    "landmark": {"kind", "text", "source", "confidence"},
    "goal": {"kind", "text"},
    "question": {"kind", "text", "confidence"},
    "hypothesis": {"kind", "text", "confidence"},
    "failure": {"kind", "text", "confidence"},
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


def validate_memory_updates(updates):
    if not isinstance(updates, list) or len(updates) > 8:
        raise ActionValidationError("memory_updates must contain at most 8 entries")
    for update in updates:
        if not isinstance(update, dict):
            raise ActionValidationError("memory update must be an object")
        kind = update.get("kind")
        if kind not in MEMORY_UPDATE_KEYS or set(update) != MEMORY_UPDATE_KEYS[kind]:
            raise ActionValidationError("memory update has invalid fields")
        text = update["text"]
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text) > 300
            or any(ord(character) < 32 for character in text)
        ):
            raise ActionValidationError("memory update text is invalid")
        if kind in {"fact", "landmark"}:
            source = update["source"]
            if (
                not isinstance(source, str)
                or not source
                or len(source) > 64
                or any(ord(character) < 32 for character in source)
            ):
                raise ActionValidationError("memory update source is invalid")
        if "confidence" in update:
            confidence = update["confidence"]
            if (
                isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not math.isfinite(confidence)
                or not 0.0 <= confidence <= 1.0
            ):
                raise ActionValidationError("memory update confidence is invalid")
    return updates


def validate_decision(payload, available_interactions, interface_open):
    """Validate and return a decoded model decision without modifying it."""
    if not isinstance(payload, dict) or set(payload) != {
        "reason",
        "memory_updates",
        "actions",
    }:
        raise ActionValidationError("decision has invalid fields")
    reason = payload["reason"]
    if (
        not isinstance(reason, str)
        or not reason.strip()
        or len(reason) > 500
        or any(unicodedata.category(character) == "Cc" for character in reason)
    ):
        raise ActionValidationError("reason must be a short string")
    validate_memory_updates(payload["memory_updates"])

    actions = payload["actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= 3:
        raise ActionValidationError("actions must contain 1..3 entries")

    available = set(available_interactions)
    for index, action in enumerate(actions):
        _validate_action(action, available, interface_open)
        if action["type"] in {"stop", "interact", "enter_digits", "close_ui"} and index != len(actions) - 1:
            raise ActionValidationError("context-changing action must be last")
    return payload
