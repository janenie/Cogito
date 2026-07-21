import base64
from datetime import datetime, timezone
import json

import pytest

from ai_play.run_logger import RunLogger, sanitize_model_name


NOW = datetime(2026, 7, 21, 10, 45, tzinfo=timezone.utc)
JPEG_BYTES = b"\xff\xd8test-jpeg\xff\xd9"


def _image(encoded=None, mime_type="image/jpeg"):
    return {
        "mime_type": mime_type,
        "base64": encoded
        if encoded is not None
        else base64.b64encode(JPEG_BYTES).decode("ascii"),
        "width": 768,
        "height": 432,
    }


def test_sanitizes_model_for_one_safe_path_component():
    assert sanitize_model_name("gemini-3.5-flash") == "gemini-3_5-flash"
    assert sanitize_model_name("vendor/model:latest") == "vendor_model_latest"


def test_creates_collision_safe_run_directories(tmp_path):
    first = RunLogger.create(tmp_path, "gemini-3.5-flash", now=NOW)
    second = RunLogger.create(tmp_path, "gemini-3.5-flash", now=NOW)
    try:
        assert first.run_dir.name == "20260721-10-45"
        assert second.run_dir.name == "20260721-10-45-02"
        assert first.jsonl_path.name == "gemini_godot.jsonl"
    finally:
        first.close()
        second.close()


def test_persists_exact_jpeg_and_flushes_jsonl_event(tmp_path):
    logger = RunLogger.create(tmp_path, "gemini-3.5-flash", now=NOW)
    try:
        round_ref = logger.begin_round(17, _image())
        logger.write_event(
            "model_input",
            round_ref,
            model="gemini-3.5-flash",
            image_path=round_ref.image_path,
        )

        assert round_ref.round_idx == 1
        assert round_ref.observation_id == 17
        assert round_ref.image_path == "img/000001.jpg"
        assert (logger.run_dir / round_ref.image_path).read_bytes() == JPEG_BYTES
        line = logger.jsonl_path.read_text(encoding="utf-8").splitlines()[0]
        event = json.loads(line)
        assert event["event"] == "model_input"
        assert event["round_idx"] == 1
        assert event["observation_id"] == 17
        assert event["image_path"] == "img/000001.jpg"
        assert "base64" not in line
    finally:
        logger.close()


def test_round_indices_increase_and_correlations_are_removed(tmp_path):
    logger = RunLogger.create(tmp_path, "model", now=NOW)
    try:
        first = logger.begin_round(10, _image())
        second = logger.begin_round(11, _image())

        assert (first.round_idx, second.round_idx) == (1, 2)
        assert logger.round_for_observation(10) == first
        assert logger.finish_round(10) == first
        assert logger.round_for_observation(10) is None
        assert logger.finish_round(999) is None
    finally:
        logger.close()


def test_rejects_duplicate_observation_id(tmp_path):
    logger = RunLogger.create(tmp_path, "model", now=NOW)
    try:
        logger.begin_round(10, _image())
        with pytest.raises(ValueError, match="duplicate observation_id"):
            logger.begin_round(10, _image())
    finally:
        logger.close()


@pytest.mark.parametrize(
    ("image", "message"),
    [
        (_image(encoded="not-base64"), "base64"),
        (_image(mime_type="image/png"), "image/jpeg"),
    ],
)
def test_rejects_invalid_image_before_registering_round(tmp_path, image, message):
    logger = RunLogger.create(tmp_path, "model", now=NOW)
    try:
        with pytest.raises(ValueError, match=message):
            logger.begin_round(10, image)
        assert logger.round_for_observation(10) is None
        assert list((logger.run_dir / "img").iterdir()) == []
    finally:
        logger.close()


def test_rejects_base64_fields_in_events(tmp_path):
    logger = RunLogger.create(tmp_path, "model", now=NOW)
    try:
        round_ref = logger.begin_round(10, _image())
        with pytest.raises(ValueError, match="base64"):
            logger.write_event(
                "model_input",
                round_ref,
                observation={"image": {"base64": "secret-image"}},
            )
        assert logger.jsonl_path.read_text(encoding="utf-8") == ""
    finally:
        logger.close()
