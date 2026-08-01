"""Exact, bounded validation for observations entering the model boundary."""

from __future__ import annotations

import base64
import binascii
import math
import re


class ObservationValidationError(ValueError):
    """Raised when a Godot observation is outside the trusted DTO schema."""


APPROVED_ACTIONS = (
    "forward", "back", "left", "right", "jump", "sprint", "crouch",
    "interact", "interact2", "menu",
)
OBSERVATION_FIELDS = {
    "observation_id", "captured_at_ms", "image", "player", "interface",
    "bindings", "last_action_results",
}
OPTIONAL_OBSERVATION_FIELDS = {"routine", "garden", "conveyor"}
ACTION_TYPES = {
    "look", "move", "sprint", "jump", "crouch", "interact",
    "enter_digits", "close_ui", "wait", "stop", "probe_interaction",
    "select_ingredient", "undo", "make",
}
CONVEYOR_INGREDIENT_IDS = {
    "lettuce", "tomato", "bread", "egg", "mushroom", "cheese", "fish", "meat",
}
CONVEYOR_OUTCOMES = {
    "selected", "undone", "accepted", "invalid_combo",
    "ingredient_not_available", "window_locked", "game_finished", "tray_empty",
}
MAX_IMAGE_BYTES = 2 * 1024 * 1024


def _exact(value, fields, label):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ObservationValidationError(f"{label} has invalid fields")


def _integer(value, label):
    if type(value) is not int or not 0 <= value <= 9_007_199_254_740_991:
        raise ObservationValidationError(f"{label} must be a safe nonnegative integer")
    return value


def _signed_integer(value, label):
    if type(value) is not int or not -9_007_199_254_740_991 <= value <= 9_007_199_254_740_991:
        raise ObservationValidationError(f"{label} must be a safe integer")
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
            {"status", "type", "error", "reason", "outcome", "scan_steps", "ingredient"}
        ) or "status" not in result:
            raise ObservationValidationError("action result has invalid fields")
        status = _text(result["status"], "result status", 16, allow_empty=False)
        if status not in {"completed", "cancelled", "error", "blocked", "stopped"}:
            raise ObservationValidationError("action result status is invalid")
        result_fields = set(result)
        if status == "completed" and result.get("type") in {
            "select_ingredient", "undo", "make",
        }:
            expected = {"status", "type", "outcome"}
            if result["type"] == "select_ingredient":
                expected.add("ingredient")
            if result_fields != expected or result.get("outcome") not in CONVEYOR_OUTCOMES:
                raise ObservationValidationError("conveyor result fields are invalid")
            safe_result = {
                "status": status,
                "type": result["type"],
                "outcome": result["outcome"],
            }
            if result["type"] == "select_ingredient":
                if result.get("ingredient") not in CONVEYOR_INGREDIENT_IDS:
                    raise ObservationValidationError("conveyor result ingredient is invalid")
                safe_result["ingredient"] = result["ingredient"]
            safe_results.append(safe_result)
            continue
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


def validate_observation(value):
    """Return a fresh safe observation DTO or raise before any model call."""
    if (
        not isinstance(value, dict)
        or not OBSERVATION_FIELDS.issubset(value)
        or not set(value).issubset(OBSERVATION_FIELDS | OPTIONAL_OBSERVATION_FIELDS)
    ):
        raise ObservationValidationError("observation has invalid fields")

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
    if image["mime_type"] != "image/jpeg" or image["width"] != 1024 or image["height"] != 576:
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
    safe_routine = None
    if "routine" in value:
        routine = value["routine"]
        _exact(
            routine,
            {
                "objective", "trash_collected", "trash_required", "held_item",
                "completed", "failed",
            },
            "routine",
        )
        if type(routine["completed"]) is not bool or type(routine["failed"]) is not bool:
            raise ObservationValidationError("routine booleans are invalid")
        safe_routine = {
            "objective": _text(routine["objective"], "routine objective", 500),
            "trash_collected": _integer(routine["trash_collected"], "trash_collected"),
            "trash_required": _integer(routine["trash_required"], "trash_required"),
            "held_item": _text(routine["held_item"], "held item", 100),
            "completed": routine["completed"],
            "failed": routine["failed"],
        }

    safe_garden = None
    if "garden" in value:
        garden = value["garden"]
        _exact(
            garden,
            {
                "objective", "time", "weather", "has_watering_can",
                "can_has_water", "watered_lawns", "required_lawns",
                "rain_alarm_pressed", "completed", "failed",
            },
            "garden",
        )
        for name in (
            "has_watering_can", "can_has_water", "rain_alarm_pressed",
            "completed", "failed",
        ):
            if type(garden[name]) is not bool:
                raise ObservationValidationError("garden booleans are invalid")
        weather = _text(garden["weather"], "garden weather", 16, allow_empty=False)
        if weather not in {"sunny", "rain"}:
            raise ObservationValidationError("garden weather is invalid")
        time = _text(garden["time"], "garden time", 5, allow_empty=False)
        if (
            len(time) != 5
            or time[2] != ":"
            or not time[:2].isdigit()
            or not time[3:].isdigit()
            or int(time[:2]) > 23
            or int(time[3:]) > 59
        ):
            raise ObservationValidationError("garden time is invalid")
        safe_garden = {
            "objective": _text(garden["objective"], "garden objective", 500),
            "time": time,
            "weather": weather,
            "has_watering_can": garden["has_watering_can"],
            "can_has_water": garden["can_has_water"],
            "watered_lawns": _integer(garden["watered_lawns"], "watered_lawns"),
            "required_lawns": _integer(garden["required_lawns"], "required_lawns"),
            "rain_alarm_pressed": garden["rain_alarm_pressed"],
            "completed": garden["completed"],
            "failed": garden["failed"],
        }

    safe_conveyor = None
    if "conveyor" in value:
        conveyor = value["conveyor"]
        _exact(
            conveyor,
            {
                "total_time", "window", "window_time", "dish",
                "net_profit", "tray", "finished",
            },
            "conveyor",
        )
        if type(conveyor["finished"]) is not bool:
            raise ObservationValidationError("conveyor finished must be boolean")
        tray = conveyor["tray"]
        if (
            not isinstance(tray, list)
            or len(tray) > 4
            or any(item not in CONVEYOR_INGREDIENT_IDS for item in tray)
        ):
            raise ObservationValidationError("conveyor tray is invalid")
        for clock_field in ("total_time", "window_time"):
            clock = _text(conveyor[clock_field], f"conveyor {clock_field}", 5, allow_empty=False)
            if re.fullmatch(r"[0-9]{2}:[0-9]{2}", clock) is None or int(clock[3:]) > 59:
                raise ObservationValidationError(f"conveyor {clock_field} is invalid")
        window = _text(conveyor["window"], "conveyor window", 7, allow_empty=False)
        dish = _text(conveyor["dish"], "conveyor dish", 5, allow_empty=False)
        if re.fullmatch(r"[0-9]{1,2} / [0-9]{1,2}", window) is None:
            raise ObservationValidationError("conveyor window is invalid")
        if re.fullmatch(r"[0-9] / [0-9]", dish) is None:
            raise ObservationValidationError("conveyor dish is invalid")
        safe_conveyor = {
            "total_time": conveyor["total_time"],
            "window": window,
            "window_time": conveyor["window_time"],
            "dish": dish,
            "net_profit": _signed_integer(conveyor["net_profit"], "conveyor net_profit"),
            "tray": list(tray),
            "finished": conveyor["finished"],
        }

    safe = {
        "observation_id": _integer(value["observation_id"], "observation_id"),
        "captured_at_ms": _integer(value["captured_at_ms"], "captured_at_ms"),
        "image": {
            "mime_type": "image/jpeg", "base64": encoded, "width": 1024, "height": 576,
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
        "interface": {
            "is_open": interface["is_open"],
            "visible_object_text": _text(interface["visible_object_text"], "visible object text", 500),
            "available_interactions": safe_interactions,
        },
        "bindings": safe_bindings,
        "last_action_results": safe_results,
    }
    if safe_routine is not None:
        safe["routine"] = safe_routine
    if safe_garden is not None:
        safe["garden"] = safe_garden
    if safe_conveyor is not None:
        safe["conveyor"] = safe_conveyor
    return safe


def prepare_mcp_observation(value):
    """Return public structured observation data and its separately carried image bytes."""
    safe = validate_observation(value)
    encoded = safe["image"]["base64"]
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ObservationValidationError("image base64 is invalid") from error

    public = {key: item for key, item in safe.items()}
    public["image"] = {
        key: item
        for key, item in safe["image"].items()
        if key != "base64"
    }
    return public, image_bytes
