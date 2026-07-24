from ai_play.briefing import load_public_briefing
from ai_play.scenarios import load_scenario_briefing


def test_load_public_briefing_returns_fresh_sanitized_data_and_jpeg():
    first, image_bytes = load_public_briefing()
    second, second_image_bytes = load_public_briefing()

    assert first == second
    assert first is not second
    assert image_bytes == second_image_bytes
    assert image_bytes.startswith(b"\xff\xd8\xff")
    assert image_bytes.endswith(b"\xff\xd9")
    assert len(image_bytes) <= 2 * 1024 * 1024

    first["rules"].append("mutated")
    assert "mutated" not in second["rules"]


def test_find_key_registry_loads_bounded_public_briefing():
    briefing, image_bytes = load_scenario_briefing("find_key")

    assert briefing["game_id"] == "find_key"
    assert briefing["success_condition"] == "成功拾取办公室中唯一的目标钥匙。"
    assert "200" in briefing["failure_condition"]
    assert image_bytes.startswith(b"\xff\xd8\xff")
    serialized = repr(briefing)
    for forbidden in [
        "DesktopDeskAnchor",
        "LaptopDeskAnchor",
        "ArchiveSofaAnchor",
        "MeetingTableAnchor",
        "TvCoffeeTableAnchor",
        "round_seed",
    ]:
        assert forbidden not in serialized
