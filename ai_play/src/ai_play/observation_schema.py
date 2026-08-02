"""Exact, bounded validation for observations entering the model boundary."""

from __future__ import annotations

import base64
import binascii
import math
import re
import struct
import zlib


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
OPTIONAL_OBSERVATION_FIELDS = {
    "routine", "garden", "depth_image", "conveyor", "laboratory", "staircase",
}
SCENARIO_OPTIONAL_OBSERVATION_FIELDS = {
    "find_contract": {"depth_image"},
    "find_key": {"depth_image"},
    "put_book": {"depth_image"},
    "greet_npc_meeting": {"depth_image"},
    "repair_lighting_circuit": {"depth_image"},
    "arrange_meeting_briefings": {"depth_image"},
    "daily_routine_cleanup": {"depth_image", "routine"},
    "garden_watering": {"depth_image", "garden"},
    "conveyor_profit": {"conveyor"},
    "loop_staircase_anomaly": {"depth_image", "staircase"},
    "laboratory_experiment": {"depth_image", "laboratory"},
}
ACTION_TYPES = {
    "look", "move", "sprint", "jump", "crouch", "interact",
    "enter_digits", "close_ui", "wait", "stop", "probe_interaction",
    "select_ingredient", "undo", "make",
    "wait_next_window",
    "press_key",
}
CONVEYOR_INGREDIENT_IDS = {
    "lettuce", "tomato", "carrot", "avocado", "sausage", "mushroom",
    "onion", "pumpkin", "bread", "meat", "egg", "cheese", "bacon",
    "broccoli", "corn", "fish",
}
CONVEYOR_RECIPE_IDS = {
    "garden_salad", "avocado_salad", "carrot_sausage_soup",
    "pumpkin_sausage_soup", "classic_burger", "avocado_burger",
    "broccoli_bacon_omelet", "corn_bacon_omelet",
    "garden_fish_sandwich", "avocado_fish_sandwich",
}
CONVEYOR_OUTCOMES = {
    "selected", "undone", "accepted", "invalid_combo",
    "ingredient_not_available", "window_locked", "game_finished", "tray_empty",
    "window_not_complete", "window_advanced", "tray_full", "recipe_limit_exceeded",
}
MAX_IMAGE_BYTES = 2 * 1024 * 1024
DEPTH_IMAGE_WIDTH = 1024
DEPTH_IMAGE_HEIGHT = 576
DEPTH_NEAR_METERS = 0.05
DEPTH_FAR_METERS = 20.0
DEPTH_ENCODING = "linear_depth_normalized_8bit"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DEPTH_IMAGE_FIELDS = {
    "mime_type", "base64", "width", "height", "encoding", "near_meters", "far_meters",
}


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


def _invalid_depth_png():
    raise ObservationValidationError("depth image must contain a valid protocol PNG")


def _validate_depth_png(data):
    if not data.startswith(PNG_SIGNATURE):
        _invalid_depth_png()

    offset = len(PNG_SIGNATURE)
    chunk_index = 0
    saw_ihdr = False
    saw_srgb = False
    idat_chunks = []
    saw_iend = False

    try:
        while offset < len(data):
            if len(data) - offset < 12:
                _invalid_depth_png()
            chunk_length = struct.unpack_from(">I", data, offset)[0]
            chunk_end = offset + 12 + chunk_length
            if chunk_length > MAX_IMAGE_BYTES or chunk_end > len(data):
                _invalid_depth_png()

            chunk_type = data[offset + 4:offset + 8]
            chunk_data = data[offset + 8:offset + 8 + chunk_length]
            expected_crc = struct.unpack_from(">I", data, offset + 8 + chunk_length)[0]
            actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
            if expected_crc != actual_crc or any(
                not (65 <= byte <= 90 or 97 <= byte <= 122)
                for byte in chunk_type
            ):
                _invalid_depth_png()

            if chunk_index == 0 and chunk_type != b"IHDR":
                _invalid_depth_png()
            if chunk_type == b"IHDR":
                if saw_ihdr or chunk_length != 13:
                    _invalid_depth_png()
                header = struct.unpack(">IIBBBBB", chunk_data)
                if header != (
                    DEPTH_IMAGE_WIDTH,
                    DEPTH_IMAGE_HEIGHT,
                    8,
                    2,
                    0,
                    0,
                    0,
                ):
                    _invalid_depth_png()
                saw_ihdr = True
            elif chunk_type == b"sRGB":
                if (
                    not saw_ihdr
                    or saw_srgb
                    or idat_chunks
                    or chunk_data not in (b"\x00", b"\x01", b"\x02", b"\x03")
                ):
                    _invalid_depth_png()
                saw_srgb = True
            elif chunk_type == b"IDAT":
                if not saw_ihdr:
                    _invalid_depth_png()
                idat_chunks.append(chunk_data)
            elif chunk_type == b"IEND":
                if not idat_chunks or chunk_length != 0 or chunk_end != len(data):
                    _invalid_depth_png()
                saw_iend = True
                offset = chunk_end
                break
            else:
                _invalid_depth_png()

            offset = chunk_end
            chunk_index += 1
    except (IndexError, struct.error) as error:
        raise ObservationValidationError(
            "depth image must contain a valid protocol PNG"
        ) from error

    if not saw_ihdr or not saw_iend or offset != len(data):
        _invalid_depth_png()

    row_size = 1 + DEPTH_IMAGE_WIDTH * 3
    expected_size = DEPTH_IMAGE_HEIGHT * row_size
    try:
        decompressor = zlib.decompressobj()
        pixels = decompressor.decompress(b"".join(idat_chunks), expected_size + 1)
        if decompressor.unconsumed_tail:
            _invalid_depth_png()
        pixels += decompressor.flush()
    except zlib.error as error:
        raise ObservationValidationError(
            "depth image must contain a valid protocol PNG"
        ) from error
    if (
        not decompressor.eof
        or decompressor.unused_data
        or len(pixels) != expected_size
        or any(pixels[row * row_size] > 4 for row in range(DEPTH_IMAGE_HEIGHT))
    ):
        _invalid_depth_png()


def validate_action_results(results):
    if not isinstance(results, list) or len(results) > 3:
        raise ObservationValidationError("last_action_results is invalid")
    safe_results = []
    for result in results:
        if not isinstance(result, dict) or not set(result).issubset(
            {
                "status", "type", "error", "reason", "outcome", "scan_steps",
                "ingredient", "recipe_id",
            }
        ) or "status" not in result:
            raise ObservationValidationError("action result has invalid fields")
        status = _text(result["status"], "result status", 16, allow_empty=False)
        if status not in {"completed", "cancelled", "error", "blocked", "stopped"}:
            raise ObservationValidationError("action result status is invalid")
        result_fields = set(result)
        if status == "completed" and result.get("type") in {
            "select_ingredient", "undo", "make", "wait_next_window",
        }:
            expected = {"status", "type", "outcome"}
            if (
                result["type"] == "select_ingredient"
                and result.get("outcome") == "selected"
            ):
                expected.add("ingredient")
            if (
                result["type"] == "make"
                and result.get("outcome") in {"accepted", "recipe_limit_exceeded"}
            ):
                expected.add("recipe_id")
            if result_fields != expected or result.get("outcome") not in CONVEYOR_OUTCOMES:
                raise ObservationValidationError("conveyor result fields are invalid")
            safe_result = {
                "status": status,
                "type": result["type"],
                "outcome": result["outcome"],
            }
            if (
                result["type"] == "select_ingredient"
                and result["outcome"] == "selected"
            ):
                if result.get("ingredient") not in CONVEYOR_INGREDIENT_IDS:
                    raise ObservationValidationError("conveyor result ingredient is invalid")
                safe_result["ingredient"] = result["ingredient"]
            if "recipe_id" in expected:
                if result.get("recipe_id") not in CONVEYOR_RECIPE_IDS:
                    raise ObservationValidationError("conveyor result recipe is invalid")
                safe_result["recipe_id"] = result["recipe_id"]
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


def validate_observation(value, scenario_id=None):
    """Return a fresh safe observation DTO or raise before any model call."""
    allowed_optional_fields = OPTIONAL_OBSERVATION_FIELDS
    if scenario_id is not None:
        try:
            allowed_optional_fields = SCENARIO_OPTIONAL_OBSERVATION_FIELDS[scenario_id]
        except (KeyError, TypeError) as error:
            raise ObservationValidationError("observation scenario is invalid") from error
    if (
        not isinstance(value, dict)
        or not OBSERVATION_FIELDS.issubset(value)
        or not set(value).issubset(OBSERVATION_FIELDS | allowed_optional_fields)
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

    safe_depth_image = None
    if "depth_image" in value:
        depth_image = value["depth_image"]
        _exact(depth_image, DEPTH_IMAGE_FIELDS, "depth image")
        depth_encoded = depth_image["base64"]
        if (
            not isinstance(depth_encoded, str)
            or len(depth_encoded) > ((MAX_IMAGE_BYTES + 2) // 3) * 4
        ):
            raise ObservationValidationError("depth image base64 is invalid")
        try:
            depth_image_bytes = base64.b64decode(depth_encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ObservationValidationError("depth image base64 is invalid") from error
        if (
            len(depth_image_bytes) > MAX_IMAGE_BYTES
            or not depth_image_bytes.startswith(PNG_SIGNATURE)
        ):
            raise ObservationValidationError("depth image must contain a bounded PNG")
        _validate_depth_png(depth_image_bytes)
        near_meters = _number(
            depth_image["near_meters"], "depth image near_meters", 0.001, 1_000
        )
        far_meters = _number(
            depth_image["far_meters"], "depth image far_meters", 0.002, 1_000_000
        )
        if (
            near_meters != DEPTH_NEAR_METERS
            or far_meters != DEPTH_FAR_METERS
        ):
            raise ObservationValidationError("depth image range is invalid")
        if (
            depth_image["mime_type"] != "image/png"
            or depth_image["width"] != DEPTH_IMAGE_WIDTH
            or depth_image["height"] != DEPTH_IMAGE_HEIGHT
            or depth_image["encoding"] != DEPTH_ENCODING
        ):
            raise ObservationValidationError("depth image metadata is invalid")
        safe_depth_image = {
            "mime_type": "image/png",
            "base64": depth_encoded,
            "width": DEPTH_IMAGE_WIDTH,
            "height": DEPTH_IMAGE_HEIGHT,
            "encoding": DEPTH_ENCODING,
            "near_meters": DEPTH_NEAR_METERS,
            "far_meters": DEPTH_FAR_METERS,
        }

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
                "net_profit", "tray", "last_receipt", "finished",
            },
            "conveyor",
        )
        if type(conveyor["finished"]) is not bool:
            raise ObservationValidationError("conveyor finished must be boolean")
        tray = conveyor["tray"]
        if (
            not isinstance(tray, list)
            or len(tray) > 5
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
        receipt = conveyor["last_receipt"]
        if not isinstance(receipt, dict):
            raise ObservationValidationError("conveyor receipt is invalid")
        safe_receipt = {}
        if receipt:
            _exact(receipt, {"outcome", "recipe_id", "profit"}, "conveyor receipt")
            outcome = receipt["outcome"]
            recipe_id = receipt["recipe_id"]
            if outcome not in {"accepted", "invalid_combo", "recipe_limit_exceeded"}:
                raise ObservationValidationError("conveyor receipt outcome is invalid")
            if (
                (outcome == "invalid_combo" and recipe_id != "")
                or (
                    outcome in {"accepted", "recipe_limit_exceeded"}
                    and recipe_id not in CONVEYOR_RECIPE_IDS
                )
            ):
                raise ObservationValidationError("conveyor receipt recipe is invalid")
            safe_receipt = {
                "outcome": outcome,
                "recipe_id": recipe_id,
                "profit": _signed_integer(receipt["profit"], "conveyor receipt profit"),
            }
        safe_conveyor = {
            "total_time": conveyor["total_time"],
            "window": window,
            "window_time": conveyor["window_time"],
            "dish": dish,
            "net_profit": _signed_integer(conveyor["net_profit"], "conveyor net_profit"),
            "tray": list(tray),
            "last_receipt": safe_receipt,
            "finished": conveyor["finished"],
        }

    safe_laboratory = None
    if "laboratory" in value:
        laboratory = value["laboratory"]
        _exact(
            laboratory,
            {
                "objective", "protocol", "environment", "attempts_used",
                "attempts_limit", "battery_installed", "selected_sample",
                "sample_state", "metal_bar_installed", "setup_ready",
                "experiment_running", "last_power", "last_current",
                "last_stability", "last_temperature", "last_lamp",
                "completed", "failed",
            },
            "laboratory",
        )
        for name in (
            "metal_bar_installed", "setup_ready", "experiment_running",
            "completed", "failed",
        ):
            if type(laboratory[name]) is not bool:
                raise ObservationValidationError("laboratory booleans are invalid")
        enum_fields = {
            "protocol": {"stable_conduction", "moisture_safety", "thermal_tolerance"},
            "environment": {"standard", "high_humidity", "limited_cooling", "power_fluctuation"},
            "battery_installed": {"none", "alpha", "beta", "gamma"},
            "selected_sample": {"none", "a", "b", "c"},
            "sample_state": {"none", "dry", "wet", "heated"},
            "last_power": {"none", "low", "normal", "high"},
            "last_current": {"none", "zero", "low", "safe", "high"},
            "last_stability": {"none", "interrupted", "flicker", "stable"},
            "last_temperature": {"none", "safe", "elevated", "dangerous"},
            "last_lamp": {"none", "off", "dim", "flicker", "stable"},
        }
        safe_laboratory = {
            "objective": _text(laboratory["objective"], "laboratory objective", 500),
            "attempts_used": _integer(laboratory["attempts_used"], "attempts_used"),
            "attempts_limit": _integer(laboratory["attempts_limit"], "attempts_limit"),
            **{
                name: laboratory[name]
                for name in (
                    "metal_bar_installed", "setup_ready", "experiment_running",
                    "completed", "failed",
                )
            },
        }
        if (
            safe_laboratory["attempts_limit"] != 3
            or safe_laboratory["attempts_used"] < 0
            or safe_laboratory["attempts_used"] > 3
        ):
            raise ObservationValidationError("laboratory attempts are invalid")
        for name, allowed in enum_fields.items():
            item = _text(
                laboratory[name], f"laboratory {name}", 32, allow_empty=False
            )
            if item not in allowed:
                raise ObservationValidationError(f"laboratory {name} is invalid")
            safe_laboratory[name] = item

    safe_staircase = None
    if "staircase" in value:
        staircase = value["staircase"]
        _exact(
            staircase,
            {
                "objective", "current_floor", "current_floor_label",
                "current_loop", "total_loops", "final_unlocked",
                "completed", "failed",
            },
            "staircase",
        )
        for name in ("final_unlocked", "completed", "failed"):
            if type(staircase[name]) is not bool:
                raise ObservationValidationError("staircase booleans are invalid")
        current_floor = _integer(staircase["current_floor"], "staircase current_floor")
        current_loop = _integer(staircase["current_loop"], "staircase current_loop")
        total_loops = _integer(staircase["total_loops"], "staircase total_loops")
        if (
            current_floor < 2
            or current_floor > 9
            or current_loop < 1
            or current_loop > 5
            or total_loops != 5
        ):
            raise ObservationValidationError("staircase public state is invalid")
        current_floor_label = _text(
            staircase["current_floor_label"],
            "staircase current_floor_label",
            3,
            allow_empty=False,
        )
        if current_floor_label != f"{current_floor}F":
            raise ObservationValidationError("staircase floor label is invalid")
        safe_staircase = {
            "objective": _text(staircase["objective"], "staircase objective", 500),
            "current_floor": current_floor,
            "current_floor_label": current_floor_label,
            "current_loop": current_loop,
            "total_loops": total_loops,
            "final_unlocked": staircase["final_unlocked"],
            "completed": staircase["completed"],
            "failed": staircase["failed"],
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
    if safe_depth_image is not None:
        safe["depth_image"] = safe_depth_image
    if safe_conveyor is not None:
        safe["conveyor"] = safe_conveyor
    if safe_laboratory is not None:
        safe["laboratory"] = safe_laboratory
    if safe_staircase is not None:
        safe["staircase"] = safe_staircase
    return safe


def prepare_mcp_observation(value):
    """Return public structured data plus separately carried screenshot and depth bytes."""
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
    depth_image_bytes = None
    if "depth_image" in safe:
        try:
            depth_image_bytes = base64.b64decode(
                safe["depth_image"]["base64"], validate=True
            )
        except (binascii.Error, ValueError) as error:
            raise ObservationValidationError("depth image base64 is invalid") from error
        public["depth_image"] = {
            key: item
            for key, item in safe["depth_image"].items()
            if key != "base64"
        }
    return public, image_bytes, depth_image_bytes
