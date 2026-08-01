import base64

import pytest

from ai_play.observation_schema import (
    ObservationValidationError,
    prepare_mcp_observation,
    validate_action_results,
    validate_observation,
)


def valid_observation_with_jpeg_base64():
    image_bytes = b"\xff\xd8\xffjpeg-bytes\xff\xd9"
    bindings = {
        "forward": "W",
        "back": "S",
        "left": "A",
        "right": "D",
        "jump": "Space",
        "sprint": "Shift",
        "crouch": "Ctrl",
        "interact": "E",
        "interact2": "F",
        "menu": "Escape",
    }
    return {
        "observation_id": 7,
        "captured_at_ms": 123,
        "image": {
            "mime_type": "image/jpeg",
            "base64": base64.b64encode(image_bytes).decode("ascii"),
            "width": 1024,
            "height": 576,
        },
        "player": {
            "position": [0, 0, 0],
            "yaw_degrees": 0,
            "pitch_degrees": 0,
            "planar_velocity": [0, 0],
            "on_floor": True,
        },
        "interface": {
            "is_open": False,
            "visible_object_text": "",
            "available_interactions": [],
        },
        "bindings": bindings,
        "last_action_results": [],
    }


def valid_depth_image():
    depth_bytes = b"\x89PNG\r\n\x1a\ndepth-mapIEND\xaeB`\x82"
    return {
        "mime_type": "image/png",
        "base64": base64.b64encode(depth_bytes).decode("ascii"),
        "width": 1024,
        "height": 576,
        "encoding": "linear_depth_normalized_8bit",
        "near_meters": 0.05,
        "far_meters": 4000.0,
    }


def valid_observation_with_depth_image():
    observation = valid_observation_with_jpeg_base64()
    observation["depth_image"] = valid_depth_image()
    return observation


@pytest.mark.parametrize("outcome", ["aligned", "not_found"])
def test_probe_result_accepts_completed_outcome(outcome):
    results = [{
        "status": "completed",
        "type": "probe_interaction",
        "outcome": outcome,
        "scan_steps": 3,
    }]
    assert validate_action_results(results) == results


@pytest.mark.parametrize(
    "patch",
    [
        {"outcome": "clicked"},
        {"scan_steps": -1},
        {"scan_steps": 10},
        {"scan_steps": 1.5},
    ],
)
def test_probe_result_rejects_invalid_fields(patch):
    result = {
        "status": "completed",
        "type": "probe_interaction",
        "outcome": "aligned",
        "scan_steps": 1,
        **patch,
    }
    with pytest.raises(ObservationValidationError):
        validate_action_results([result])


def test_prepare_mcp_observation_removes_base64_from_structured_state():
    observation = valid_observation_with_jpeg_base64()

    public, image_bytes, depth_image_bytes = prepare_mcp_observation(observation)

    assert public["image"] == {
        "mime_type": "image/jpeg",
        "width": 1024,
        "height": 576,
    }
    assert image_bytes == b"\xff\xd8\xffjpeg-bytes\xff\xd9"
    assert depth_image_bytes is None
    assert "base64" not in public["image"]
    assert "base64" in observation["image"]


def test_prepare_mcp_observation_separates_depth_png_from_structured_state():
    observation = valid_observation_with_depth_image()

    public, image_bytes, depth_image_bytes = prepare_mcp_observation(observation)

    assert image_bytes == b"\xff\xd8\xffjpeg-bytes\xff\xd9"
    assert depth_image_bytes == b"\x89PNG\r\n\x1a\ndepth-mapIEND\xaeB`\x82"
    assert public["depth_image"] == {
        "mime_type": "image/png",
        "width": 1024,
        "height": 576,
        "encoding": "linear_depth_normalized_8bit",
        "near_meters": 0.05,
        "far_meters": 4000.0,
    }
    assert "base64" not in public["depth_image"]
    assert "base64" in observation["depth_image"]


def test_prepare_mcp_observation_validates_before_projection():
    observation = valid_observation_with_jpeg_base64()
    observation["image"]["base64"] = "not-base64"

    with pytest.raises(ObservationValidationError, match="base64"):
        prepare_mcp_observation(observation)


@pytest.mark.parametrize(
    "patch",
    [
        {"mime_type": "image/jpeg"},
        {"encoding": "raw_depth"},
        {"near_meters": 4000.0},
        {"far_meters": 0.05},
    ],
)
def test_depth_image_rejects_invalid_metadata(patch):
    observation = valid_observation_with_depth_image()
    observation["depth_image"].update(patch)

    with pytest.raises(ObservationValidationError):
        validate_observation(observation)


def test_home_routine_observation_fields_are_public_and_bounded():
    observation = valid_observation_with_jpeg_base64()
    observation["routine"] = {
        "objective": "把全部垃圾扔进客厅垃圾桶。",
        "trash_collected": 1,
        "trash_required": 3,
        "held_item": "无",
        "completed": False,
        "failed": False,
    }

    public, _image_bytes, _depth_image_bytes = prepare_mcp_observation(observation)

    assert public["routine"] == observation["routine"]


def test_garden_observation_fields_are_public_and_bounded():
    observation = valid_observation_with_jpeg_base64()
    observation["garden"] = {
        "objective": "给目标花园浇水，并在下雨时按警报。",
        "time": "09:42",
        "weather": "rain",
        "has_watering_can": True,
        "can_has_water": True,
        "watered_lawns": 2,
        "required_lawns": 4,
        "rain_alarm_pressed": False,
        "completed": False,
        "failed": False,
    }

    public, _image_bytes, _depth_image_bytes = prepare_mcp_observation(observation)

    assert public["garden"] == observation["garden"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("time", "9:42"),
        ("time", "24:00"),
        ("weather", "cloudy"),
        ("watered_lawns", -1),
        ("completed", 0),
    ],
)
def test_garden_observation_rejects_invalid_public_state(field, value):
    observation = valid_observation_with_jpeg_base64()
    observation["garden"] = {
        "objective": "给目标花园浇水。",
        "time": "09:42",
        "weather": "sunny",
        "has_watering_can": False,
        "can_has_water": True,
        "watered_lawns": 0,
        "required_lawns": 4,
        "rain_alarm_pressed": False,
        "completed": False,
        "failed": False,
    }
    observation["garden"][field] = value

    with pytest.raises(ObservationValidationError):
        validate_observation(observation)
