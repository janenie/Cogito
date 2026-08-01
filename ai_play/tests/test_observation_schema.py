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


def test_press_key_result_accepts_completed_action_type():
    results = [{"status": "completed", "type": "press_key"}]

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

    public, _image_bytes = prepare_mcp_observation(observation)

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


def valid_laboratory_state():
    return {
        "objective": "Produce a safe, stable circuit and keep the experiment lamp lit.",
        "protocol": "stable_conduction",
        "environment": "high_humidity",
        "attempts_used": 1,
        "attempts_limit": 3,
        "battery_installed": "beta",
        "selected_sample": "b",
        "sample_state": "wet",
        "metal_bar_installed": True,
        "setup_ready": True,
        "experiment_running": False,
        "last_power": "normal",
        "last_current": "safe",
        "last_stability": "stable",
        "last_temperature": "safe",
        "last_lamp": "stable",
        "completed": False,
        "failed": False,
    }


def test_laboratory_observation_fields_are_public_and_bounded():
    observation = valid_observation_with_jpeg_base64()
    observation["laboratory"] = valid_laboratory_state()

    public, _image_bytes = prepare_mcp_observation(observation)

    assert public["laboratory"] == observation["laboratory"]


def test_loop_staircase_observation_fields_are_public_and_bounded():
    observation = valid_observation_with_jpeg_base64()
    observation["staircase"] = {
        "objective": "Find the true exit floor.",
        "current_floor": 7,
        "current_floor_label": "7F",
        "current_loop": 4,
        "total_loops": 5,
        "final_unlocked": True,
        "completed": False,
        "failed": False,
    }

    public, _image_bytes = prepare_mcp_observation(observation)

    assert public["staircase"] == observation["staircase"]
    assert "lamp_color" not in public["staircase"]
    assert "wall_marker" not in public["staircase"]
    assert "box_count" not in public["staircase"]


@pytest.mark.parametrize("hidden_field", ["lamp_color", "wall_marker", "box_count"])
def test_loop_staircase_observation_rejects_visual_clue_fields(hidden_field):
    observation = valid_observation_with_jpeg_base64()
    observation["staircase"] = {
        "objective": "Find the true exit floor.",
        "current_floor": 7,
        "current_floor_label": "7F",
        "current_loop": 4,
        "total_loops": 5,
        "final_unlocked": True,
        "completed": False,
        "failed": False,
        hidden_field: "hidden",
    }

    with pytest.raises(ObservationValidationError):
        validate_observation(observation)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("protocol", "hidden_protocol"),
        ("environment", "storm"),
        ("attempts_used", 4),
        ("attempts_limit", 4),
        ("battery_installed", "delta"),
        ("selected_sample", "d"),
        ("sample_state", "frozen"),
        ("last_current", "secret"),
        ("completed", 1),
    ],
)
def test_laboratory_observation_rejects_invalid_public_state(field, value):
    observation = valid_observation_with_jpeg_base64()
    observation["laboratory"] = valid_laboratory_state()
    observation["laboratory"][field] = value

    with pytest.raises(ObservationValidationError):
        validate_observation(observation)


def test_laboratory_observation_rejects_hidden_solution_fields():
    observation = valid_observation_with_jpeg_base64()
    observation["laboratory"] = valid_laboratory_state()
    observation["laboratory"]["round_seed"] = 123

    with pytest.raises(ObservationValidationError):
        validate_observation(observation)
