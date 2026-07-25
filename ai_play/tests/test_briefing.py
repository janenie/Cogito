from ai_play.briefing import load_public_briefing
from ai_play.common_briefing_rules import COMMON_CONTROL_RULES
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


def test_put_book_registry_loads_bounded_public_briefing():
    briefing, image_bytes = load_scenario_briefing("put_book")

    assert briefing["game_id"] == "put_book"
    assert briefing["success_condition"] == "目标书进入档案室地上的目标纸箱。"
    assert "50" in briefing["failure_condition"]
    assert image_bytes.startswith(b"\xff\xd8\xff")
    serialized = repr(briefing)
    for forbidden in [
        "ArchiveDoor",
        "PutBook",
        "cardboardBoxOpen",
        "books2",
        "round_seed",
    ]:
        assert forbidden not in serialized


def test_greet_npc_meeting_registry_loads_bounded_public_briefing():
    briefing, image_bytes = load_scenario_briefing("greet_npc_meeting")

    assert briefing["game_id"] == "greet_npc_meeting"
    assert briefing["success_condition"] == "已经和 NPC 打招呼，并在会议室内关上会议室门。"
    assert "100" in briefing["failure_condition"]
    assert image_bytes.startswith(b"\xff\xd8\xff")
    serialized = repr(briefing)
    for forbidden in [
        "FriendlyHumanNPCPath",
        "HumanMeetingRoomStart",
        "ConferenceDoor",
        "round_seed",
        "_route_index",
    ]:
        assert forbidden not in serialized


def test_daily_routine_cleanup_briefing_is_public_and_bounded():
    briefing, image_bytes = load_scenario_briefing("daily_routine_cleanup")

    assert image_bytes is None
    assert briefing["game_id"] == "daily_routine_cleanup"
    assert "客厅垃圾桶" in briefing["objective"]
    assert briefing["success_condition"] == "所有目标垃圾都已扔进客厅垃圾桶，并点击完成按钮。"
    serialized = repr(briefing)
    for forbidden in [
        "DailyRoutineManager",
        "TrashRandomizer",
        "routine_completed",
        "dailyroutine/scripts",
        "home_daily_routine.tscn",
    ]:
        assert forbidden not in serialized


def test_all_scenario_briefings_include_shared_control_rules():
    for scenario_id in [
        "find_contract",
        "find_key",
        "put_book",
        "greet_npc_meeting",
        "daily_routine_cleanup",
    ]:
        briefing, _image_bytes = load_scenario_briefing(scenario_id)
        for rule in COMMON_CONTROL_RULES:
            assert rule in briefing["rules"]
