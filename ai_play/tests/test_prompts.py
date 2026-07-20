import json

from ai_play.prompts import SYSTEM_PROMPT, build_messages


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
