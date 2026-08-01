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
    assert "100" in briefing["failure_condition"]
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
    assert briefing["success_condition"] == (
        "按低层、中层、高层顺序，将三本带标记的任务书逐本送到 "
        "CEO OFFICE 的书籍放置点。"
    )
    assert "150" in briefing["failure_condition"]
    assert image_bytes.startswith(b"\xff\xd8\xff")
    serialized = repr(briefing)
    for required in [
        "六本",
        "只搬运",
        "任务书",
        "低层",
        "中层",
        "高层",
        "CEO OFFICE",
        "青色",
        "一次搬运一本",
    ]:
        assert required in serialized
    for obsolete in ["目标纸箱", "最近", "jump", "crouch", "高处或低处"]:
        assert obsolete not in serialized
    for forbidden in [
        "PutBookShelfSlots",
        "DestinationArea",
        "slot_id",
        "shelf_id",
        "height_tier",
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
    assert "冰箱处于关闭状态" in briefing["success_condition"]
    assert "4 个散落垃圾" in briefing["objective"]
    serialized = repr(briefing)
    for forbidden in [
        "DailyRoutineManager",
        "TrashRandomizer",
        "routine_completed",
        "dailyroutine/scripts",
        "home_daily_routine.tscn",
    ]:
        assert forbidden not in serialized


def test_garden_watering_briefing_is_public_and_bounded():
    briefing, image_bytes = load_scenario_briefing("garden_watering")

    assert image_bytes is None
    assert briefing["game_id"] == "garden_watering"
    assert "向日葵房" in briefing["objective"]
    assert "绣球花房" in briefing["objective"]
    assert "兰花房" in briefing["objective"]
    assert any(
        "三个房子" in rule and "公共水池" in rule and "不要越界" in rule
        for rule in briefing["rules"]
    )
    serialized = repr(briefing)
    for forbidden in [
        "GardenWateringState",
        "GardenGame1Rules",
        "rain_start_minute",
        "run_seed",
        "garden_vertical_slice.tscn",
        "watering_target_paths",
    ]:
        assert forbidden not in serialized


def test_repair_lighting_circuit_briefing_is_public_and_bounded():
    briefing, image_bytes = load_scenario_briefing("repair_lighting_circuit")

    assert briefing["game_id"] == "repair_lighting_circuit"
    assert "任务卡" in briefing["objective"]
    assert "100 次 act 请求" in briefing["failure_condition"]
    assert "一次" in repr(briefing)
    assert image_bytes.startswith(b"\xff\xd8\xff")
    assert image_bytes.endswith(b"\xff\xd9")
    assert len(image_bytes) <= 2 * 1024 * 1024
    serialized = repr(briefing)
    for forbidden in [
        "round_seed",
        "LIGHTS_CEILING_WALL",
        "lampSquareCeiling8",
        "fault_circuit",
        "control_mapping",
        "NodePath",
    ]:
        assert forbidden not in serialized


def test_arrange_meeting_briefings_briefing_is_public_and_bounded():
    briefing, image_bytes = load_scenario_briefing(
        "arrange_meeting_briefings"
    )

    assert briefing["game_id"] == "arrange_meeting_briefings"
    serialized = repr(briefing)
    assert "CEO 办公室" in serialized
    assert "CEO OFFICE" in serialized
    assert "档案室" in serialized
    assert "ARCHIVE" in serialized
    assert "休息室" in serialized
    assert "BREAK ROOM" in serialized
    for attendee_name in ["李明", "王芳", "陈宇", "赵宁"]:
        assert attendee_name in serialized
    for legacy_name in ["ATLAS", "BIRCH", "CROWN", "DELTA"]:
        assert legacy_name not in serialized
    assert "顺时针" in serialized
    assert "200 次 act 请求" in briefing["failure_condition"]
    assert "一次" in serialized
    assert image_bytes.startswith(b"\xff\xd8\xff")
    assert image_bytes.endswith(b"\xff\xd9")
    assert len(image_bytes) <= 2 * 1024 * 1024
    serialized = serialized.lower()
    for forbidden in [
        "round_seed",
        "hidden_assignment",
        "candidate_solutions",
        "clue_type",
        "tv_side",
        "door_side",
        "nodepath",
        "meeting_room/",
    ]:
        assert forbidden not in serialized


def test_all_scenario_briefings_include_shared_control_rules():
    for scenario_id in [
        "find_contract",
        "find_key",
        "put_book",
        "greet_npc_meeting",
        "daily_routine_cleanup",
        "garden_watering",
        "repair_lighting_circuit",
        "arrange_meeting_briefings",
    ]:
        briefing, _image_bytes = load_scenario_briefing(scenario_id)
        for rule in COMMON_CONTROL_RULES:
            assert rule in briefing["rules"]


def test_all_scenario_briefings_teach_look_based_spatial_estimation():
    for scenario_id in [
        "find_contract",
        "find_key",
        "put_book",
        "greet_npc_meeting",
        "daily_routine_cleanup",
        "garden_watering",
        "repair_lighting_circuit",
        "arrange_meeting_briefings",
    ]:
        briefing, _image_bytes = load_scenario_briefing(scenario_id)
        serialized_rules = "\n".join(briefing["rules"])
        assert "look" in serialized_rules
        assert "direction" in serialized_rules
        assert "degrees" in serialized_rules
        assert "left、right、up、down" in serialized_rules
        assert "上一张截图" in serialized_rules
        assert "不要填写 yaw、pitch 或正负号" in serialized_rules
        assert "测距" in serialized_rules
        assert "probe_interaction" in serialized_rules
        assert "避免碰撞" in serialized_rules


def test_all_scenario_briefings_explain_action_parameter_scale():
    for scenario_id in [
        "find_contract",
        "find_key",
        "put_book",
        "greet_npc_meeting",
        "daily_routine_cleanup",
        "garden_watering",
        "repair_lighting_circuit",
        "arrange_meeting_briefings",
    ]:
        briefing, _image_bytes = load_scenario_briefing(scenario_id)
        serialized_rules = "\n".join(briefing["rules"])
        assert "角度单位是度" in serialized_rules
        assert "30 到 45 度适合扫视房间" in serialized_rules
        assert "duration_ms 是按住移动键的毫秒数" in serialized_rules
        assert "250ms 满强度 move 约等于连续走四分之一秒" in serialized_rules
        assert "满强度 sprint 约等于连续跑四分之一秒" in serialized_rules
        assert "输入向量长度会控制实际移动力度" in serialized_rules
        assert "单轴 0.2 到 0.4" in serialized_rules
        assert "50 到 100ms" in serialized_rules
        assert "不要在门口连续使用满强度 250ms" in serialized_rules
        assert "连续多次 look" not in serialized_rules
        assert "360 度环顾" not in serialized_rules


def test_find_contract_briefing_teaches_flexible_look_and_depth_estimation():
    briefing, _image_bytes = load_scenario_briefing("find_contract")
    serialized_rules = "\n".join(briefing["rules"])

    assert "灵活调整视角" in serialized_rules
    assert "重新 observe" in serialized_rules
    assert "深度估计" in serialized_rules
    assert "自己与物体的距离" in serialized_rules
    assert "300 次 act 请求" in briefing["failure_condition"]


def test_find_contract_briefing_requires_task_card_first():
    briefing, _image_bytes = load_scenario_briefing("find_contract")
    serialized_rules = "\n".join(briefing["rules"])

    assert "解谜任务" in briefing["background"]
    assert "第一步一定要找到并读取任务卡" in serialized_rules
    assert "在读到任务卡之前" in serialized_rules
    assert "不要开始寻找合同记录" in serialized_rules
