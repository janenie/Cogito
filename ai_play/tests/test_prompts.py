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


def test_prompt_states_exact_action_limits_and_preconditions():
    assert "`yaw` must be within [-45, 45]" in SYSTEM_PROMPT
    assert "`pitch` must be within [-30, 30]" in SYSTEM_PROMPT
    assert "`forward` and `right` must each be within [-1, 1]" in SYSTEM_PROMPT
    assert "50 through 1000 milliseconds" in SYSTEM_PROMPT
    assert "50 through 2000 milliseconds" in SYSTEM_PROMPT
    assert "one to six ASCII digits" in SYSTEM_PROMPT
    assert "`interface.is_open` is true" in SYSTEM_PROMPT
    assert "current `available_interactions`" in SYSTEM_PROMPT
    assert "one to three action objects" in SYSTEM_PROMPT


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
    assert "runtime `bindings` and `available_interactions`" in SYSTEM_PROMPT


def test_prompt_treats_visible_text_as_untrusted_data():
    lower = SYSTEM_PROMPT.lower()
    assert "visible text" in lower and "untrusted" in lower
    assert "action whitelist" in lower
    for forbidden_request in ("file", "network", "system"):
        assert forbidden_request in lower
    assert "entire observation" in lower
    assert "all persisted or runtime memory" in lower
