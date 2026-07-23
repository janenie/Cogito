"""Exact, bounded validation for observations entering the model boundary."""

from __future__ import annotations

import base64
import binascii
import math


class ObservationValidationError(ValueError):
    """Raised when a Godot observation is outside the trusted DTO schema."""


APPROVED_ACTIONS = (
    "forward", "back", "left", "right", "jump", "sprint", "crouch",
    "interact", "interact2", "menu",
)
OBSERVATION_FIELDS = {
    "observation_id", "captured_at_ms", "image", "player", "interface",
    "nearby_interactables", "bindings", "last_action_results",
}
NEARBY_FIELDS = {
    "tracking_id", "category", "distance_m", "world_position",
    "relative_position", "relative_yaw_degrees", "relative_pitch_degrees",
    "screen_position", "interactions",
}
NEARBY_CATEGORIES = {
    "readable", "keypad", "door", "button", "character", "object",
    "interactable",
}
ACTION_TYPES = {
    "look", "move", "sprint", "jump", "crouch", "interact",
    "enter_digits", "close_ui", "wait", "stop", "probe_interaction",
}
MAX_IMAGE_BYTES = 2 * 1024 * 1024


def _exact(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ObservationValidationError(f"{label} has invalid fields")


def _integer(value, label):
    if type(value) is not int or not 0 <= value <= 9_007_199_254_740_991:
        raise ObservationValidationError(f"{label} must be a safe nonnegative integer")
    return value


def _number(value, label, lower=None, upper=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObservationValidationError(f"{label} must be finite")
    try:
        finite = math.isfinite(value)
    except OverflowError as error:
        raise ObservationValidationError(f"{label} must be finite") from error
    if not finite or (lower is not None and value < lower) or (upper is not None and value > upper):
        raise ObservationValidationError(f"{label} is outside its bounds")
    return value


def _text(value, label, maximum, allow_empty=True):
    if not isinstance(value, str) or len(value) > maximum:
        raise ObservationValidationError(f"{label} must be bounded text")
    if not allow_empty and not value:
        raise ObservationValidationError(f"{label} must not be empty")
    if any(ord(character) < 32 for character in value):
        raise ObservationValidationError(f"{label} contains a control character")
    return value


def _vector(value, length, label, lower, upper):
    if not isinstance(value, list) or len(value) != length:
        raise ObservationValidationError(f"{label} has invalid dimensions")
    return [_number(component, label, lower, upper) for component in value]


def validate_action_results(results):
    if not isinstance(results, list) or len(results) > 3:
        raise ObservationValidationError("last_action_results is invalid")
    safe_results = []
    for result in results:
        if not isinstance(result, dict) or not set(result).issubset(
            {"status", "type", "error", "reason", "outcome", "scan_steps"}
        ) or "status" not in result:
            raise ObservationValidationError("action result has invalid fields")
        status = _text(result["status"], "result status", 16, allow_empty=False)
        if status not in {"completed", "cancelled", "error", "blocked", "stopped"}:
            raise ObservationValidationError("action result status is invalid")
        result_fields = set(result)
        if status == "completed" and result.get("type") == "probe_interaction":
            if result_fields != {"status", "type", "outcome", "scan_steps"}:
                raise ObservationValidationError("probe result fields are invalid")
            if result["outcome"] not in {"aligned", "not_found"}:
                raise ObservationValidationError("probe outcome is invalid")
            if type(result["scan_steps"]) is not int or not 0 <= result["scan_steps"] <= 9:
                raise ObservationValidationError("probe scan_steps is invalid")
            safe_results.append({
                "status": status,
                "type": "probe_interaction",
                "outcome": result["outcome"],
                "scan_steps": result["scan_steps"],
            })
            continue
        if (
            (status == "completed" and result_fields != {"status", "type"})
            or (status == "error" and result_fields != {"status", "error"})
            or (
                status == "cancelled"
                and result_fields not in ({"status"}, {"status", "reason"})
            )
            or (status in {"blocked", "stopped"} and result_fields != {"status", "type"})
        ):
            raise ObservationValidationError("action result fields do not match status")
        safe_result = {"status": status}
        for key in ("type", "error", "reason"):
            if key in result:
                safe_result[key] = _text(result[key], f"result {key}", 200, allow_empty=False)
        if "type" in safe_result and safe_result["type"] not in ACTION_TYPES:
            raise ObservationValidationError("action result type is invalid")
        if status == "blocked" and safe_result["type"] not in {"move", "sprint"}:
            raise ObservationValidationError("blocked result type is invalid")
        if status == "stopped" and safe_result["type"] != "stop":
            raise ObservationValidationError("stopped result type is invalid")
        safe_results.append(safe_result)
    return safe_results


def _validate_nearby_interactables(items):
    if not isinstance(items, list) or len(items) > 5:
        raise ObservationValidationError("nearby_interactables is invalid")
    safe_items = []
    seen_ids = set()
    previous_distance = -1.0
    for item in items:
        _exact(item, NEARBY_FIELDS, "nearby interactable")
        tracking_id = _integer(item["tracking_id"], "nearby tracking_id")
        if tracking_id in seen_ids:
            raise ObservationValidationError("nearby tracking_id must be unique")
        seen_ids.add(tracking_id)
        category = item["category"]
        if category not in NEARBY_CATEGORIES:
            raise ObservationValidationError("nearby category is invalid")
        distance = _number(item["distance_m"], "nearby distance_m", 0, 2_000_000)
        if distance < previous_distance:
            raise ObservationValidationError("nearby interactables are not distance sorted")
        previous_distance = distance

        relative = item["relative_position"]
        _exact(relative, {"forward", "right", "up"}, "nearby relative_position")
        screen = item["screen_position"]
        _exact(screen, {"x", "y"}, "nearby screen_position")
        interactions = item["interactions"]
        if not isinstance(interactions, list) or not 1 <= len(interactions) <= 2:
            raise ObservationValidationError("nearby interactions are invalid")
        safe_interactions = []
        seen_actions = set()
        for interaction in interactions:
            _exact(interaction, {"action", "prompt"}, "nearby interaction")
            action = interaction["action"]
            if action not in {"interact", "interact2"} or action in seen_actions:
                raise ObservationValidationError("nearby interaction action is invalid")
            seen_actions.add(action)
            safe_interactions.append({
                "action": action,
                "prompt": _text(
                    interaction["prompt"], "nearby interaction prompt", 200
                ),
            })
        safe_items.append({
            "tracking_id": tracking_id,
            "category": category,
            "distance_m": distance,
            "world_position": _vector(
                item["world_position"], 3, "nearby world_position",
                -1_000_000, 1_000_000,
            ),
            "relative_position": {
                axis: _number(
                    relative[axis], f"nearby relative {axis}",
                    -2_000_000, 2_000_000,
                )
                for axis in ("forward", "right", "up")
            },
            "relative_yaw_degrees": _number(
                item["relative_yaw_degrees"], "nearby relative_yaw_degrees",
                -180, 180,
            ),
            "relative_pitch_degrees": _number(
                item["relative_pitch_degrees"], "nearby relative_pitch_degrees",
                -90, 90,
            ),
            "screen_position": {
                axis: _number(screen[axis], f"nearby screen {axis}", 0, 1)
                for axis in ("x", "y")
            },
            "interactions": safe_interactions,
        })
    return safe_items


def validate_observation(value):
    """Return a fresh safe observation DTO or raise before any model call."""
    _exact(value, OBSERVATION_FIELDS, "observation")

    image = value["image"]
    _exact(image, {"mime_type", "base64", "width", "height"}, "image")
    encoded = image["base64"]
    if not isinstance(encoded, str) or len(encoded) > ((MAX_IMAGE_BYTES + 2) // 3) * 4:
        raise ObservationValidationError("image base64 is invalid")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ObservationValidationError("image base64 is invalid") from error
    if (
        len(image_bytes) > MAX_IMAGE_BYTES
        or not image_bytes.startswith(b"\xff\xd8\xff")
        or not image_bytes.endswith(b"\xff\xd9")
    ):
        raise ObservationValidationError("image must contain a bounded JPEG")
    if image["mime_type"] != "image/jpeg" or image["width"] != 768 or image["height"] != 432:
        raise ObservationValidationError("image metadata is invalid")

    player = value["player"]
    required_player_fields = {
        "position", "yaw_degrees", "pitch_degrees", "planar_velocity", "on_floor",
    }
    optional_player_fields = {"health_ratio", "stamina_ratio"}
    if (
        not isinstance(player, dict)
        or not required_player_fields.issubset(player)
        or not set(player).issubset(required_player_fields | optional_player_fields)
    ):
        raise ObservationValidationError("player fields are invalid")
    if type(player["on_floor"]) is not bool:
        raise ObservationValidationError("on_floor must be boolean")
    ratios = {}
    for name in ("health_ratio", "stamina_ratio"):
        if name in player:
            ratios[name] = (
                None if player[name] is None else _number(player[name], name, 0, 1)
            )

    bindings = value["bindings"]
    _exact(bindings, APPROVED_ACTIONS, "bindings")
    safe_bindings = {
        action: _text(bindings[action], f"binding {action}", 32, allow_empty=False)
        for action in APPROVED_ACTIONS
    }

    interface = value["interface"]
    _exact(interface, {"is_open", "visible_object_text", "available_interactions"}, "interface")
    if type(interface["is_open"]) is not bool:
        raise ObservationValidationError("interface is_open must be boolean")
    interactions = interface["available_interactions"]
    if not isinstance(interactions, list) or len(interactions) > 2:
        raise ObservationValidationError("available_interactions is invalid")
    safe_interactions = []
    seen_actions = set()
    for interaction in interactions:
        _exact(interaction, {"action", "binding", "prompt"}, "interaction")
        action = interaction["action"]
        if action not in {"interact", "interact2"} or action in seen_actions:
            raise ObservationValidationError("interaction action is invalid")
        binding = _text(interaction["binding"], "interaction binding", 32, allow_empty=False)
        if binding != safe_bindings[action]:
            raise ObservationValidationError("interaction binding does not match bindings")
        seen_actions.add(action)
        safe_interactions.append({
            "action": action,
            "binding": binding,
            "prompt": _text(interaction["prompt"], "interaction prompt", 200),
        })

    safe_results = validate_action_results(value["last_action_results"])
    safe_nearby = _validate_nearby_interactables(value["nearby_interactables"])

    return {
        "observation_id": _integer(value["observation_id"], "observation_id"),
        "captured_at_ms": _integer(value["captured_at_ms"], "captured_at_ms"),
        "image": {
            "mime_type": "image/jpeg", "base64": encoded, "width": 768, "height": 432,
        },
        "player": {
            "position": _vector(player["position"], 3, "position", -1_000_000, 1_000_000),
            "yaw_degrees": _number(player["yaw_degrees"], "yaw_degrees", -1_000_000, 1_000_000),
            "pitch_degrees": _number(player["pitch_degrees"], "pitch_degrees", -90, 90),
            "planar_velocity": _vector(
                player["planar_velocity"], 2, "planar_velocity", -10_000, 10_000
            ),
            "on_floor": player["on_floor"],
            **ratios,
        },
        "nearby_interactables": safe_nearby,
        "interface": {
            "is_open": interface["is_open"],
            "visible_object_text": _text(interface["visible_object_text"], "visible object text", 500),
            "available_interactions": safe_interactions,
        },
        "bindings": safe_bindings,
        "last_action_results": safe_results,
    }
