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
