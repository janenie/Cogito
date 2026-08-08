import base64
import struct
import zlib

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


def test_scenario_validation_rejects_another_scenario_public_state():
    observation = valid_observation_with_jpeg_base64()
    observation["routine"] = {
        "objective": "Collect trash.",
        "trash_collected": 0,
        "trash_required": 2,
        "held_item": "",
        "completed": False,
        "failed": False,
    }

    with pytest.raises(ObservationValidationError, match="invalid fields"):
        validate_observation(observation, "find_contract")
    assert validate_observation(
        observation,
        "daily_routine_cleanup",
    )["routine"] == observation["routine"]


def png_chunk(kind, data):
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", checksum)
    )


def depth_png(
    width=1024,
    height=576,
    idat_data=None,
    raw_rows=None,
    include_srgb=True,
    before_idat_chunks=(),
    after_idat_chunks=(),
):
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    rows = raw_rows or b"".join(
        b"\x00" + b"\xff\xff\xff" * width for _unused_row in range(height)
    )
    compressed = zlib.compress(rows) if idat_data is None else idat_data
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + (png_chunk(b"sRGB", b"\x00") if include_srgb else b"")
        + b"".join(png_chunk(kind, data) for kind, data in before_idat_chunks)
        + png_chunk(b"IDAT", compressed)
        + b"".join(png_chunk(kind, data) for kind, data in after_idat_chunks)
        + png_chunk(b"IEND", b"")
    )


VALID_DEPTH_PNG = depth_png()


def valid_depth_image():
    return {
        "mime_type": "image/png",
        "base64": base64.b64encode(VALID_DEPTH_PNG).decode("ascii"),
        "width": 1024,
        "height": 576,
        "encoding": "linear_depth_normalized_8bit",
        "near_meters": 0.05,
        "far_meters": 20.0,
    }


def valid_observation_with_depth_image():
    observation = valid_observation_with_jpeg_base64()
    observation["depth_image"] = valid_depth_image()
    return observation


def test_fixed_camera_conveyor_rejects_depth_image():
    observation = valid_observation_with_depth_image()

    with pytest.raises(ObservationValidationError, match="invalid fields"):
        validate_observation(observation, "conveyor_profit")


@pytest.mark.parametrize("outcome", ["aligned", "not_found"])
def test_probe_result_accepts_completed_outcome(outcome):
    results = [{
        "status": "completed",
        "type": "probe_interaction",
        "outcome": outcome,
        "scan_steps": 3,
    }]
    assert validate_action_results(results) == results


@pytest.mark.parametrize("action_type", [
    "front", "back", "left", "right", "floor_up", "floor_down",
    "toggle_board", "board_up", "board_down", "toggle_mark", "submit_floor",
])
def test_loop_semantic_result_accepts_completed_action_type(action_type):
    results = [{"status": "completed", "type": action_type}]

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
    assert depth_image_bytes == VALID_DEPTH_PNG
    assert public["depth_image"] == {
        "mime_type": "image/png",
        "width": 1024,
        "height": 576,
        "encoding": "linear_depth_normalized_8bit",
        "near_meters": 0.05,
        "far_meters": 20.0,
    }
    assert "base64" not in public["depth_image"]
    assert "base64" in observation["depth_image"]


def test_prepare_mcp_observation_validates_before_projection():
    observation = valid_observation_with_jpeg_base64()
    observation["image"]["base64"] = "not-base64"

    with pytest.raises(ObservationValidationError, match="base64"):
        prepare_mcp_observation(observation)


def test_depth_image_rejects_invalid_chunk_crc():
    observation = valid_observation_with_depth_image()
    corrupt_png = bytearray(VALID_DEPTH_PNG)
    corrupt_png[29] ^= 0x01
    observation["depth_image"]["base64"] = base64.b64encode(corrupt_png).decode("ascii")

    with pytest.raises(ObservationValidationError, match="PNG"):
        validate_observation(observation)


@pytest.mark.parametrize(
    "chunks",
    [
        {"before_idat_chunks": ((b"PLTE", b"\x00"),)},
        {"before_idat_chunks": ((b"vpag", b"private"),)},
        {"before_idat_chunks": ((b"sRGB", b"\x00"),)},
        {
            "include_srgb": False,
            "before_idat_chunks": ((b"sRGB", b"\x04"),),
        },
        {"after_idat_chunks": ((b"tRNS", b"\x00"),)},
    ],
)
def test_depth_image_rejects_non_contract_or_misordered_chunks(chunks):
    observation = valid_observation_with_depth_image()
    observation["depth_image"]["base64"] = base64.b64encode(
        depth_png(**chunks)
    ).decode("ascii")

    with pytest.raises(ObservationValidationError, match="PNG"):
        validate_observation(observation)


def test_depth_image_rejects_ihdr_dimensions_that_disagree_with_metadata():
    observation = valid_observation_with_depth_image()
    observation["depth_image"]["base64"] = base64.b64encode(
        depth_png(width=512)
    ).decode("ascii")

    with pytest.raises(ObservationValidationError, match="PNG"):
        validate_observation(observation)


def test_depth_image_rejects_invalid_compressed_scanlines():
    observation = valid_observation_with_depth_image()
    observation["depth_image"]["base64"] = base64.b64encode(
        depth_png(idat_data=b"not-a-zlib-stream")
    ).decode("ascii")

    with pytest.raises(ObservationValidationError, match="PNG"):
        validate_observation(observation)


def test_depth_image_rejects_invalid_scanline_filter():
    observation = valid_observation_with_depth_image()
    rows = (
        b"\x05" + b"\xff\xff\xff" * 1024
        + b"".join(
            b"\x00" + b"\xff\xff\xff" * 1024
            for _unused_row in range(575)
        )
    )
    observation["depth_image"]["base64"] = base64.b64encode(
        depth_png(raw_rows=rows)
    ).decode("ascii")

    with pytest.raises(ObservationValidationError, match="PNG"):
        validate_observation(observation)


def test_depth_image_rejects_trailing_bytes_after_iend():
    observation = valid_observation_with_depth_image()
    trailing_png = VALID_DEPTH_PNG + b"trailingIEND\xaeB`\x82"
    observation["depth_image"]["base64"] = base64.b64encode(trailing_png).decode("ascii")

    with pytest.raises(ObservationValidationError, match="PNG"):
        validate_observation(observation)


@pytest.mark.parametrize(
    "patch",
    [
        {"mime_type": "image/jpeg"},
        {"encoding": "raw_depth"},
        {"near_meters": 4000.0},
        {"far_meters": 0.05},
        {"near_meters": 0.1},
        {"far_meters": 1000.0},
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


def test_conveyor_observation_is_hud_level_and_bounded():
    observation = valid_observation_with_jpeg_base64()
    observation["conveyor"] = {
        "total_time": "09:42",
        "window": "1 / 10",
        "window_time": "00:42",
        "dish": "0 / 1",
        "net_profit": -3,
        "tray": ["bread", "egg"],
        "last_receipt": {
            "outcome": "accepted",
            "recipe_id": "garden_salad",
            "profit": -3,
        },
        "market": {
            "category_multipliers": {
                "salad": 1.0,
                "soup": 1.25,
                "burger": 0.75,
                "omelet": 1.0,
                "sandwich": 1.5,
            },
            "signals": [
                "强冷空气抵达，下一轮汤类需求可能升高。",
                "部分办公楼恢复供暖，下一轮汤类需求可能降低。",
            ],
        },
        "contracts": _valid_conveyor_contracts(),
        "finished": False,
    }

    public, _image_bytes, _depth_image_bytes = prepare_mcp_observation(observation)

    assert public["conveyor"] == observation["conveyor"]


@pytest.mark.parametrize(
    "hidden_field",
    [
        "ingredients", "candidate_recipes", "best_profit", "future_supply", "seed",
        "passing_profit", "deck_id", "campaign_id", "candidate_recipe_ids",
        "baseline_recipe_id", "baseline_profit", "recipe_counts", "missing_ingredient",
        "theoretical_profit", "omniscient_profit", "optimal_route", "draw_index",
        "future_multipliers",
    ],
)
def test_conveyor_observation_rejects_hidden_fields(hidden_field):
    observation = valid_observation_with_jpeg_base64()
    observation["conveyor"] = {
        "total_time": "09:42",
        "window": "1 / 10",
        "window_time": "00:42",
        "dish": "0 / 1",
        "net_profit": 0,
        "tray": [],
        "last_receipt": {},
        "market": {
            "category_multipliers": {
                "salad": 1.0, "soup": 1.0, "burger": 1.0,
                "omelet": 1.0, "sandwich": 1.0,
            },
            "signals": ["下一轮汤类需求可能升高。", "下一轮汉堡需求可能降低。"],
        },
        "contracts": _valid_conveyor_contracts(),
        "finished": False,
        hidden_field: [],
    }

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

    public, _image_bytes, _depth_image_bytes = prepare_mcp_observation(observation)

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

    public, _image_bytes, _depth_image_bytes = prepare_mcp_observation(observation)

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


def test_conveyor_semantic_action_results_are_bounded():
    results = [
        {
            "status": "completed",
            "type": "select_ingredient",
            "outcome": "selected",
            "ingredient": "tomato",
        },
        {
            "status": "completed",
            "type": "make",
            "outcome": "recipe_limit_exceeded",
            "recipe_id": "garden_salad",
        },
        {
            "status": "completed",
            "type": "wait_next_window",
            "outcome": "window_advanced",
        },
    ]

    assert validate_action_results(results) == results


@pytest.mark.parametrize("outcome", ["accepted", "recipe_limit_exceeded"])
def test_conveyor_make_receipt_requires_a_public_recipe_id(outcome):
    result = [{
        "status": "completed",
        "type": "make",
        "outcome": outcome,
        "recipe_id": "avocado_fish_sandwich",
    }]

    assert validate_action_results(result) == result

    without_recipe = [{
        "status": "completed",
        "type": "make",
        "outcome": outcome,
    }]
    with pytest.raises(ObservationValidationError):
        validate_action_results(without_recipe)


def test_conveyor_observation_accepts_five_item_tray_and_empty_receipt():
    observation = valid_observation_with_jpeg_base64()
    observation["conveyor"] = {
        "total_time": "09:42",
        "window": "1 / 10",
        "window_time": "00:42",
        "dish": "0 / 1",
        "net_profit": 0,
        "tray": ["egg", "cheese", "bacon", "corn", "avocado"],
        "last_receipt": {},
        "market": {
            "category_multipliers": {
                "salad": 1.0, "soup": 1.0, "burger": 1.0,
                "omelet": 1.0, "sandwich": 1.0,
            },
            "signals": ["下一轮汤类需求可能升高。", "下一轮汉堡需求可能降低。"],
        },
        "contracts": _valid_conveyor_contracts(),
        "finished": False,
    }

    public, _image_bytes, _depth_image_bytes = prepare_mcp_observation(observation)

    assert len(public["conveyor"]["tray"]) == 5
    assert public["conveyor"]["last_receipt"] == {}


@pytest.mark.parametrize("bad_multiplier", [0.5, 0.8, 1.1, 2.0, True, "1.0"])
def test_conveyor_market_rejects_unknown_multipliers(bad_multiplier):
    observation = valid_observation_with_jpeg_base64()
    observation["conveyor"] = _valid_conveyor_market_state()
    observation["conveyor"]["market"]["category_multipliers"]["soup"] = bad_multiplier

    with pytest.raises(ObservationValidationError):
        validate_observation(observation, "conveyor_profit")


def test_conveyor_market_requires_exact_categories_and_signal_count():
    observation = valid_observation_with_jpeg_base64()
    observation["conveyor"] = _valid_conveyor_market_state()
    observation["conveyor"]["market"]["category_multipliers"]["dessert"] = 1.0
    with pytest.raises(ObservationValidationError):
        validate_observation(observation, "conveyor_profit")

    observation["conveyor"] = _valid_conveyor_market_state()
    observation["conveyor"]["market"]["signals"] = ["only one"]
    with pytest.raises(ObservationValidationError):
        validate_observation(observation, "conveyor_profit")


def test_conveyor_tenth_window_requires_no_future_signals():
    observation = valid_observation_with_jpeg_base64()
    observation["conveyor"] = _valid_conveyor_market_state()
    observation["conveyor"]["window"] = "10 / 10"
    observation["conveyor"]["market"]["signals"] = []
    public, _image_bytes, _depth_image_bytes = prepare_mcp_observation(observation)
    assert public["conveyor"]["market"]["signals"] == []

    observation["conveyor"]["market"]["signals"] = ["x", "y"]
    with pytest.raises(ObservationValidationError):
        validate_observation(observation, "conveyor_profit")


def test_conveyor_market_signals_are_bounded():
    observation = valid_observation_with_jpeg_base64()
    observation["conveyor"] = _valid_conveyor_market_state()
    observation["conveyor"]["market"]["signals"][0] = "x" * 241
    with pytest.raises(ObservationValidationError):
        validate_observation(observation, "conveyor_profit")


def _valid_conveyor_market_state():
    return {
        "total_time": "09:42",
        "window": "1 / 10",
        "window_time": "00:42",
        "dish": "0 / 1",
        "net_profit": 0,
        "tray": [],
        "last_receipt": {},
        "market": {
            "category_multipliers": {
                "salad": 1.0, "soup": 1.25, "burger": 0.75,
                "omelet": 1.0, "sandwich": 1.5,
            },
            "signals": ["下一轮汤类需求可能升高。", "下一轮汤类需求可能降低。"],
        },
        "contracts": _valid_conveyor_contracts(),
        "finished": False,
    }


def _valid_conveyor_contracts():
    return [
        {
            "id": "early_category",
            "deadline_window": 3,
            "requirement": "第 3 窗结束前累计完成至少 1 道 SOUP / Serve 1 SOUP dish by window 3",
            "reward": 8,
            "penalty": 10,
            "status": "active",
        },
        {
            "id": "mid_category",
            "deadline_window": 6,
            "requirement": "第 6 窗结束前累计完成至少 2 道 SALAD / Serve 2 SALAD dishes by window 6",
            "reward": 10,
            "penalty": 12,
            "status": "active",
        },
        {
            "id": "category_coverage",
            "deadline_window": 10,
            "requirement": "第 10 窗结束前覆盖至少 4 个菜品类别 / Cover 4 categories by window 10",
            "reward": 12,
            "penalty": 15,
            "status": "active",
        },
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "pending"),
        ("deadline_window", 4),
        ("deadline_window", 3.0),
        ("reward", 999),
        ("reward", 8.0),
        ("penalty", -10),
        ("penalty", 10.0),
        ("requirement", ""),
    ],
)
def test_conveyor_contracts_are_exact_and_bounded(field, value):
    observation = valid_observation_with_jpeg_base64()
    observation["conveyor"] = _valid_conveyor_market_state()
    observation["conveyor"]["contracts"][0][field] = value

    with pytest.raises(ObservationValidationError):
        validate_observation(observation, "conveyor_profit")


def test_conveyor_contract_ids_are_unique_and_complete():
    observation = valid_observation_with_jpeg_base64()
    observation["conveyor"] = _valid_conveyor_market_state()
    observation["conveyor"]["contracts"][1]["id"] = "early_category"

    with pytest.raises(ObservationValidationError):
        validate_observation(observation, "conveyor_profit")


def test_conveyor_full_tray_result_is_recoverable_and_bounded():
    result = [{
        "status": "completed",
        "type": "select_ingredient",
        "outcome": "tray_full",
    }]

    assert validate_action_results(result) == result


@pytest.mark.parametrize(
    "outcome",
    ["window_not_complete", "window_advanced", "game_finished"],
)
def test_wait_next_window_results_are_exact(outcome):
    result = [{
        "status": "completed",
        "type": "wait_next_window",
        "outcome": outcome,
    }]

    assert validate_action_results(result) == result


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("protocol", "hidden_protocol"),
        ("environment", "storm"),
        ("attempts_used", 4),
        ("attempts_used", -1),
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


def test_loop_staircase_observation_rejects_mismatched_floor_label():
    observation = valid_observation_with_jpeg_base64()
    observation["staircase"] = {
        "objective": "Find the true exit floor.",
        "current_floor": 7,
        "current_floor_label": "8F",
        "current_loop": 4,
        "total_loops": 5,
        "final_unlocked": True,
        "completed": False,
        "failed": False,
    }

    with pytest.raises(ObservationValidationError):
        validate_observation(observation)
