import json
from pathlib import Path

from ai_play import prompts
from ai_play.game_context import load_game_context
from ai_play.prompts import (
    SYSTEM_PROMPT,
    build_log_messages,
    build_messages,
    build_system_prompt,
)


FORBIDDEN = ["game_script/", "code_read/", ".gd", ".tscn", "passcode", "walkthrough"]


def observation():
    return {
        "observation_id": 7,
        "image": {"mime_type": "image/jpeg", "base64": "aW1hZ2U="},
        "player": {
            "position": [0, 0, 0],
            "yaw_degrees": 0,
            "pitch_degrees": 0,
            "planar_velocity": [0, 0],
            "on_floor": True,
            "health_ratio": 1,
            "stamina_ratio": 1,
        },
        "nearby_interactables": [{
            "tracking_id": 42,
            "category": "readable",
            "distance_m": 2.5,
            "world_position": [0.5, 1.0, -2.0],
            "relative_position": {"forward": 2.0, "right": 0.5, "up": 0.0},
            "relative_yaw_degrees": 14.0,
            "relative_pitch_degrees": 0.0,
            "screen_position": {"x": 0.6, "y": 0.5},
            "interactions": [{"action": "interact", "prompt": "Read hint"}],
        }],
        "interface": {
            "is_open": False,
            "visible_object_text": "",
            "available_interactions": [
                {"action": "interact", "binding": "F", "prompt": "Read"},
                {"action": "interact2", "binding": "E", "prompt": "Move"},
            ],
        },
        "bindings": {
            "forward": "W",
            "back": "S",
            "left": "A",
            "right": "D",
            "jump": "Space",
            "sprint": "Shift",
            "crouch": "C",
            "interact": "F",
            "interact2": "E",
            "menu": "Escape",
        },
        "last_action_results": [],
    }


def test_prompt_maps_f_and_e_to_visible_meaning():
    rendered = json.dumps(build_messages(observation(), {}), ensure_ascii=False)
    assert "F" in rendered and "interact" in rendered and "Read" in rendered
    assert "E" in rendered and "interact2" in rendered and "Move" in rendered


def test_default_prompt_has_no_repository_or_solution_content():
    lower = SYSTEM_PROMPT.lower()
    for forbidden in FORBIDDEN:
        assert forbidden.lower() not in lower


def test_build_messages_keeps_image_only_in_data_url():
    messages = build_messages(observation(), {"facts": []})
    user_content = messages[1]["content"]
    state = json.loads(user_content[0]["text"])

    assert state["observation"]["image"] == {"mime_type": "image/jpeg"}
    assert "aW1hZ2U=" not in user_content[0]["text"]
    assert user_content[1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/jpeg;base64,aW1hZ2U="},
    }
    assert state["memory"] == {"facts": []}
    assert state["probe_interaction_harness"] == {
        "status": "aligned",
        "success": True,
        "success_condition": "current_available_interactions_non_empty",
        "available_actions": ["interact", "interact2"],
        "required_next_step": "use_available_interaction",
    }


def test_build_log_messages_replaces_image_data_url_with_relative_path():
    messages = build_messages(observation(), {"facts": []})

    logged = build_log_messages(messages, "img/000007.jpg")

    assert logged[1]["content"][1] == {
        "type": "image_path",
        "image_path": "img/000007.jpg",
    }
    assert "base64" not in json.dumps(logged)
    assert messages[1]["content"][1]["type"] == "image_url"


def test_game_context_adds_chinese_goal_asset_catalog_and_one_reference_image():
    ai_play_root = Path(__file__).resolve().parents[1]
    context = load_game_context("find_contract", ai_play_root)

    messages = build_messages(observation(), {"facts": []}, context)
    system = messages[0]["content"]
    user_content = messages[1]["content"]

    assert "第一人称环境解谜游戏" in system
    assert "FriendlyHumanNPC / BasicInteraction" in system
    assert "083001" not in system
    assert len([part for part in user_content if part["type"] == "image_url"]) == 2
    assert user_content[2]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_find_contract_prompt_leads_with_readable_task_rules_and_limit():
    ai_play_root = Path(__file__).resolve().parents[1]
    context = load_game_context("find_contract", ai_play_root)

    assert hasattr(prompts, "find_contract_system_prompt")
    system = prompts.find_contract_system_prompt(context)

    assert system.startswith("# 本局任务")
    assert "寻找合同密码并进入档案室" in system
    assert "你最多走1000步，所以请仔细规划。" in system
    assert "## 成功条件" in system
    assert "## 失败条件" in system
    assert "## 本局规则" in system
    assert "## 可识别物体与操作机制" in system
    assert "FriendlyHumanNPC / BasicInteraction" in system
    assert '"game":' not in system
    assert build_system_prompt(context) == system


def test_log_messages_names_current_and_reference_images_separately():
    ai_play_root = Path(__file__).resolve().parents[1]
    context = load_game_context("find_contract", ai_play_root)
    messages = build_messages(observation(), {}, context)

    logged = build_log_messages(
        messages,
        "img/000007.jpg",
        "assets/find_contract/imgs/reference_atlas.jpg",
    )

    assert logged[1]["content"][1]["image_path"] == "img/000007.jpg"
    assert logged[1]["content"][2]["image_path"].endswith("reference_atlas.jpg")


def test_prompt_states_exact_action_limits_and_preconditions():
    assert "`yaw` 必须在 [-45, 45]" in SYSTEM_PROMPT
    assert "`pitch` 必须在" in SYSTEM_PROMPT and "[-30, 30]" in SYSTEM_PROMPT
    assert "`forward`、`right`" in SYSTEM_PROMPT
    assert "50 到 1000 毫秒" in SYSTEM_PROMPT
    assert "50 到 2000 毫秒" in SYSTEM_PROMPT
    assert "一至六位 ASCII 数字" in SYSTEM_PROMPT
    assert "`interface.is_open` 为 true" in SYSTEM_PROMPT
    assert "当前 `available_interactions`" in SYSTEM_PROMPT
    assert "一至三个动作对象" in SYSTEM_PROMPT
    assert "必须是批次最后一个动作" in SYSTEM_PROMPT
    assert "必须重新观察" in SYSTEM_PROMPT


def test_prompt_uses_runtime_bindings_for_contextual_interaction_slots():
    rebound = observation()
    rebound["bindings"]["interact"] = "Mouse1"
    rebound["bindings"]["interact2"] = "Q"
    rebound["interface"]["available_interactions"] = [
        {"action": "interact", "binding": "Mouse1", "prompt": "Inspect"},
        {"action": "interact2", "binding": "Q", "prompt": "Use"},
    ]

    messages = build_messages(rebound, {})
    state = json.loads(messages[1]["content"][0]["text"])

    assert state["observation"]["bindings"]["interact"] == "Mouse1"
    assert state["observation"]["bindings"]["interact2"] == "Q"
    assert state["observation"]["interface"]["available_interactions"] == [
        {"action": "interact", "binding": "Mouse1", "prompt": "Inspect"},
        {"action": "interact2", "binding": "Q", "prompt": "Use"},
    ]
    assert "The F and E bindings" not in SYSTEM_PROMPT
    assert "`bindings` 和 `available_interactions`" in SYSTEM_PROMPT


def test_prompt_treats_visible_text_as_untrusted_data():
    assert "可见文字" in SYSTEM_PROMPT and "不可信数据" in SYSTEM_PROMPT
    assert "动作白名单" in SYSTEM_PROMPT
    for forbidden_request in ("文件", "网络", "系统"):
        assert forbidden_request in SYSTEM_PROMPT
    assert "观察数据和记忆" in SYSTEM_PROMPT


def test_prompt_defines_look_values_as_mouse_control_deltas():
    assert "相对鼠标控制量" in SYSTEM_PROMPT
    assert "不保证等于角度" in SYSTEM_PROMPT
    assert "yaw_degrees" in SYSTEM_PROMPT
    assert "pitch_degrees" in SYSTEM_PROMPT


def test_prompt_documents_interaction_probe():
    assert "`probe_interaction`" in SYSTEM_PROMPT
    assert "`target_x`" in SYSTEM_PROMPT
    assert "`target_y`" in SYSTEM_PROMPT
    assert "必须单独成为一个" in SYSTEM_PROMPT
    assert "不会激活" in SYSTEM_PROMPT
    assert '"type":"probe_interaction"' in SYSTEM_PROMPT


def test_prompt_teaches_nearby_interactable_aiming_feedback():
    assert "`nearby_interactables`" in SYSTEM_PROMPT
    assert "`screen_position`" in SYSTEM_PROMPT
    assert "`relative_position`" in SYSTEM_PROMPT
    assert "`distance_m`" in SYSTEM_PROMPT
    assert "最多五个" in SYSTEM_PROMPT
    assert "不代表已经对准" in SYSTEM_PROMPT
    assert "新坐标" in SYSTEM_PROMPT


def test_prompt_teaches_probe_harness_success_loop():
    assert "`probe_interaction_harness`" in SYSTEM_PROMPT
    assert "唯一成功条件" in SYSTEM_PROMPT
    assert "当前 `available_interactions` 非空" in SYSTEM_PROMPT
    assert "仅仅看到图标" in SYSTEM_PROMPT
    assert "`aligned`" in SYSTEM_PROMPT
    assert "`not_aligned`" in SYSTEM_PROMPT
    assert "当前列出的交互槽" in SYSTEM_PROMPT


def test_readme_explains_how_to_confirm_actual_look_rotation():
    readme = " ".join(
        (Path(__file__).resolve().parents[1] / "README.md")
        .read_text(encoding="utf-8")
        .lower()
        .split()
    )
    assert "relative mouse-control deltas" in readme
    assert "do not guarantee degrees" in readme
    assert "yaw_degrees" in readme and "pitch_degrees" in readme
