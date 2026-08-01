"""Load the approved, bounded public reference image shared by briefings."""

from pathlib import Path


MAX_REFERENCE_IMAGE_BYTES = 2 * 1024 * 1024
REFERENCE_IMAGE_PATH = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "find_contract"
    / "imgs"
    / "reference_atlas.jpg"
)


def load_reference_image() -> bytes:
    try:
        image_bytes = REFERENCE_IMAGE_PATH.read_bytes()
    except OSError as error:
        raise RuntimeError("briefing_reference_image_unavailable") from error
    if (
        len(image_bytes) > MAX_REFERENCE_IMAGE_BYTES
        or not image_bytes.startswith(b"\xff\xd8\xff")
        or not image_bytes.endswith(b"\xff\xd9")
    ):
        raise RuntimeError("briefing_reference_image_invalid")
    return image_bytes
