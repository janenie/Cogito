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
            "width": 768,
            "height": 432,
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

    public, image_bytes = prepare_mcp_observation(observation)

    assert public["image"] == {
        "mime_type": "image/jpeg",
        "width": 768,
        "height": 432,
    }
    assert image_bytes == b"\xff\xd8\xffjpeg-bytes\xff\xd9"
    assert "base64" not in public["image"]
    assert "base64" in observation["image"]


def test_prepare_mcp_observation_validates_before_projection():
    observation = valid_observation_with_jpeg_base64()
    observation["image"]["base64"] = "not-base64"

    with pytest.raises(ObservationValidationError, match="base64"):
        prepare_mcp_observation(observation)


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

    public, _image_bytes = prepare_mcp_observation(observation)

    assert public["routine"] == observation["routine"]
