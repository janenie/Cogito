import threading
import json

import pytest

import ai_play.agent_loop as agent_loop_module
from ai_play.agent_loop import AgentLoop
from ai_play.api_client import ModelCompletion
from ai_play.memory import MemoryStore
from ai_play.run_logger import RunLogger


def observation(observation_id=9):
    return {
        "type": "observation",
        "protocol_version": 1,
        "observation_id": observation_id,
        "captured_at_ms": 1234,
        "image": {
            "mime_type": "image/jpeg",
            "base64": "/9j/2Q==",
            "width": 768,
            "height": 432,
        },
        "player": {
            "position": [0.0, 1.0, 2.0],
            "yaw_degrees": 10.0,
            "pitch_degrees": -2.0,
            "planar_velocity": [0.0, 0.0],
            "on_floor": True,
            "health_ratio": None,
            "stamina_ratio": 0.5,
        },
        "interface": {
            "is_open": False,
            "visible_object_text": "",
            "available_interactions": [
                {"action": "interact2", "binding": "E", "prompt": "Use"}
            ],
        },
        "bindings": {
            "forward": "W", "back": "S", "left": "A", "right": "D",
            "jump": "Space", "sprint": "Shift", "crouch": "C",
            "interact": "F", "interact2": "E", "menu": "Escape",
        },
        "last_action_results": [],
    }


class FakeApi:
    def __init__(self, decision, raw_content=None):
        self.decision = decision
        self.raw_content = raw_content
        self.messages = []
        self.config = type("Config", (), {"model": "test-model"})()

    def decide(self, messages):
        self.messages.append(messages)
        return self.decision

    def complete(self, messages):
        self.messages.append(messages)
        raw = self.raw_content
        if raw is None:
            raw = json.dumps(self.decision, ensure_ascii=False)
        return ModelCompletion(raw_content=raw, latency_ms=12)


class FakeMemory:
    def __init__(self):
        self.updates = []
        self.saved_paths = []

    def to_prompt_dict(self):
        return {"facts": []}

    def apply_updates(self, updates, observation_id):
        self.updates.append((updates, observation_id))

    def save(self, path):
        self.saved_paths.append(path)


def decision(**overrides):
    value = {
        "reason": "observe",
        "memory_updates": [],
        "actions": [{"type": "wait", "duration_ms": 100}],
    }
    value.update(overrides)
    return value


def _logged_events(logger):
    return [
        json.loads(line)
        for line in logger.jsonl_path.read_text(encoding="utf-8").splitlines()
    ]


def test_logs_complete_round_lifecycle_without_base64(tmp_path):
    logger = RunLogger.create(tmp_path, "test-model")
    loop = AgentLoop(FakeApi(decision()), FakeMemory(), run_logger=logger)
    try:
        response = loop.handle_observation(observation())

        assert [event["event"] for event in _logged_events(logger)] == [
            "model_input",
            "model_output",
            "decision_validated",
            "action_dispatch_requested",
        ]
        model_input = _logged_events(logger)[0]
        assert model_input["model"] == "test-model"
        assert model_input["image_path"] == "img/000001.jpg"
        assert model_input["messages"][1]["content"][1] == {
            "type": "image_path",
            "image_path": "img/000001.jpg",
        }
        assert "base64" not in json.dumps(model_input)

        assert loop.commit_action_batch_sent(response["observation_id"])
        assert loop.record_action_results(
            response["observation_id"],
            [{"status": "completed", "type": "wait"}],
        )
        assert [event["event"] for event in _logged_events(logger)] == [
            "model_input",
            "model_output",
            "decision_validated",
            "action_dispatch_requested",
            "action_dispatched",
            "godot_result",
        ]
    finally:
        logger.close()


def test_logs_raw_malformed_model_output_before_parse_error(tmp_path):
    logger = RunLogger.create(tmp_path, "test-model")
    loop = AgentLoop(
        FakeApi(decision(), raw_content="not valid json"),
        FakeMemory(),
        run_logger=logger,
    )
    try:
        response = loop.handle_observation(observation())
        events = _logged_events(logger)

        assert response["type"] == "error"
        assert [event["event"] for event in events] == [
            "model_input",
            "model_output",
            "round_error",
        ]
        assert events[1]["raw_content"] == "not valid json"
        assert events[2]["stage"] == "parse"
    finally:
        logger.close()


def test_passes_visible_interaction_action_names_to_validation(monkeypatch):
    captured = {}

    def capture(payload, available_interactions, interface_open):
        captured["available_interactions"] = available_interactions
        captured["interface_open"] = interface_open
        return payload

    monkeypatch.setattr(agent_loop_module, "validate_decision", capture)
    loop = AgentLoop(FakeApi(decision()), FakeMemory())

    loop.handle_observation(observation())

    assert captured == {
        "available_interactions": ["interact2"],
        "interface_open": False,
    }


def test_action_batch_copies_observation_id():
    loop = AgentLoop(FakeApi(decision()), FakeMemory())

    assert loop.handle_observation(observation()) == {
        "type": "action_batch",
        "protocol_version": 1,
        "observation_id": 9,
        "reason": "observe",
        "actions": [{"type": "wait", "duration_ms": 100}],
    }


def test_valid_observation_reaches_api_without_wire_envelope():
    api = FakeApi(decision())
    loop = AgentLoop(api, FakeMemory())

    assert loop.handle_observation(observation())["type"] == "action_batch"
    state = json.loads(api.messages[0][1]["content"][0]["text"])

    assert set(state["observation"]) == {
        "observation_id", "captured_at_ms", "image", "player", "interface",
        "bindings", "last_action_results",
    }
    assert "type" not in state["observation"]
    assert "protocol_version" not in state["observation"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update({"script": "res://private.gd"}),
        lambda value: value["player"].update({"path": "/private/route"}),
        lambda value: value["image"].update({"prompt": "ignore safety"}),
        lambda value: value["interface"]["available_interactions"][0].update(
            {"payload": "read a file"}
        ),
        lambda value: value.update({"observation_id": True}),
        lambda value: value["player"].update({"yaw_degrees": float("nan")}),
        lambda value: value["image"].update({"base64": "not base64"}),
        lambda value: value["interface"]["available_interactions"][0].update(
            {"binding": "Q"}
        ),
        lambda value: value.update({
            "last_action_results": [{"status": "completed", "error": "impossible"}]
        }),
        lambda value: value["interface"].update({
            "available_interactions": [
                {"action": "interact", "binding": "F", "prompt": "One"},
                {"action": "interact2", "binding": "E", "prompt": "Two"},
                {"action": "interact", "binding": "F", "prompt": "Three"},
            ]
        }),
        lambda value: value.update({
            "last_action_results": [{"status": "cancelled"}] * 4
        }),
        lambda value: value["bindings"].update({"forward": "x" * 33}),
        lambda value: value["interface"]["available_interactions"][0].update(
            {"prompt": "x" * 201}
        ),
        lambda value: value["image"].update({"width": 769}),
        lambda value: value.update({
            "last_action_results": [{"status": "completed", "type": "teleport"}]
        }),
        lambda value: value["player"].update({"position": [1_000_000.1, 0, 0]}),
        lambda value: value["player"].update({"yaw_degrees": -1_000_000.1}),
        lambda value: value["player"].update({"pitch_degrees": 90.1}),
        lambda value: value["player"].update({"planar_velocity": [0, 10_000.1]}),
        lambda value: value.update({
            "last_action_results": [{"status": "blocked", "type": "look"}]
        }),
        lambda value: value.update({
            "last_action_results": [{"status": "stopped", "type": "move"}]
        }),
        lambda value: value.update({
            "last_action_results": [{
                "status": "blocked", "type": "move", "reason": "extra",
            }]
        }),
    ],
)
def test_invalid_observation_is_rejected_before_api(mutate):
    value = observation()
    mutate(value)
    api = FakeApi(decision())

    result = AgentLoop(api, FakeMemory()).handle_observation(value)

    assert result["type"] == "error"
    assert result["message"] == "ObservationValidationError"
    assert api.messages == []


@pytest.mark.parametrize(
    "result",
    [
        {"status": "blocked", "type": "move"},
        {"status": "blocked", "type": "sprint"},
        {"status": "stopped", "type": "stop"},
    ],
)
def test_accepts_exact_blocked_and_stopped_results(result):
    value = observation()
    value["last_action_results"] = [result]
    api = FakeApi(decision())

    response = AgentLoop(api, FakeMemory()).handle_observation(value)

    assert response["type"] == "action_batch"
    assert len(api.messages) == 1


def test_accepts_player_numeric_boundaries():
    value = observation()
    value["player"].update({
        "position": [-1_000_000, 1_000_000, 0],
        "yaw_degrees": 1_000_000,
        "pitch_degrees": -90,
        "planar_velocity": [-10_000, 10_000],
    })

    assert AgentLoop(FakeApi(decision()), FakeMemory()).handle_observation(value)["type"] == "action_batch"


def test_applies_and_saves_memory_only_after_decision_validation(tmp_path):
    memory = FakeMemory()
    updates = [{"kind": "goal", "text": "Explore"}]
    loop = AgentLoop(FakeApi(decision(memory_updates=updates)), memory, tmp_path / "memory.json")

    result = loop.handle_observation(observation())
    assert memory.updates == []
    assert memory.saved_paths == []
    assert loop.commit_action_batch_sent(result["observation_id"])

    assert loop.memory.updates == [(updates, 9)]
    assert loop.memory.saved_paths == [tmp_path / "memory.json"]


def test_invalid_model_output_returns_safe_error_without_actions_or_memory():
    memory = FakeMemory()
    loop = AgentLoop(
        FakeApi(decision(
            memory_updates=[{"kind": "goal", "text": "Must not apply"}],
            actions=[{"type": "wait", "duration_ms": 1}],
        )),
        memory,
    )

    result = loop.handle_observation(observation())

    assert result == {
        "type": "error",
        "protocol_version": 1,
        "observation_id": 9,
        "code": "decision_failed",
        "message": "ActionValidationError",
    }
    assert "actions" not in result
    assert memory.updates == []


def test_api_error_returns_exception_type_without_request_details():
    class RequestBearingError(Exception):
        pass

    class FailingApi:
        def decide(self, messages):
            raise RequestBearingError("secret request body")

    result = AgentLoop(FailingApi(), FakeMemory()).handle_observation(observation())

    assert result["message"] == "RequestBearingError"
    assert "secret" not in str(result)


def test_rejects_second_observation_while_decision_is_in_progress():
    entered = threading.Event()
    release = threading.Event()

    class BlockingApi:
        def decide(self, messages):
            entered.set()
            release.wait(timeout=2)
            return decision()

    loop = AgentLoop(BlockingApi(), FakeMemory())
    first_result = []
    worker = threading.Thread(
        target=lambda: first_result.append(loop.handle_observation(observation(1)))
    )
    worker.start()
    assert entered.wait(timeout=1)

    second = loop.handle_observation(observation(2))
    release.set()
    worker.join(timeout=2)

    assert second == {
        "type": "error",
        "protocol_version": 1,
        "observation_id": 2,
        "code": "decision_failed",
        "message": "RuntimeError",
    }
    assert first_result[0]["observation_id"] == 1


def test_next_prompt_records_previous_decision_and_results():
    api = FakeApi(decision(
        reason="look around",
        actions=[{"type": "look", "yaw": 5, "pitch": 0}],
    ))
    memory = MemoryStore.empty()
    loop = AgentLoop(api, memory)

    loop.handle_observation(observation(1))
    assert loop.commit_action_batch_sent(1)
    second = observation(2)
    second["last_action_results"] = [{"status": "completed", "type": "look"}]
    loop.handle_observation(second)
    assert loop.commit_action_batch_sent(2)

    first_state = json.loads(api.messages[0][1]["content"][0]["text"])
    second_state = json.loads(api.messages[1][1]["content"][0]["text"])
    assert first_state["memory"]["working_memory"] == []
    assert second_state["memory"]["working_memory"] == [{
        "observation_id": 1,
        "reason": "look around",
        "actions": [{"type": "look", "yaw": 5, "pitch": 0}],
        "last_action_results": [{"status": "completed", "type": "look"}],
    }]
    rendered_memory = json.dumps(second_state["memory"])
    assert "base64" not in rendered_memory
    assert "captured_at_ms" not in rendered_memory


def test_recorded_decision_history_is_bounded():
    memory = MemoryStore.empty()
    loop = AgentLoop(FakeApi(decision()), memory)

    for observation_id in range(10):
        result = loop.handle_observation(observation(observation_id))
        assert loop.commit_action_batch_sent(result["observation_id"])

    assert len(loop.memory.working_memory) == 8
    assert [entry["observation_id"] for entry in loop.memory.working_memory] == list(range(1, 9))


def test_handle_stages_without_mutating_live_memory():
    memory = MemoryStore.empty()
    loop = AgentLoop(
        FakeApi(decision(memory_updates=[{"kind": "goal", "text": "Explore"}])),
        memory,
    )

    result = loop.handle_observation(observation(1))

    assert result["type"] == "action_batch"
    assert memory.task_state["goal"] == ""
    assert loop._pending_step is None


def test_mismatched_commit_is_rejected_without_live_mutation():
    memory = MemoryStore.empty()
    loop = AgentLoop(FakeApi(decision()), memory)
    loop.handle_observation(observation(1))

    assert not loop.commit_action_batch_sent(2)
    assert loop.memory is memory
    assert loop._pending_step is None
    assert loop.discard_action_batch(1)


def test_discarded_send_does_not_create_pending_or_live_updates():
    memory = MemoryStore.empty()
    loop = AgentLoop(
        FakeApi(decision(memory_updates=[{"kind": "goal", "text": "Explore"}])),
        memory,
    )
    result = loop.handle_observation(observation(1))

    assert loop.discard_action_batch(result["observation_id"])

    assert loop.memory is memory
    assert loop.memory.task_state["goal"] == ""
    assert loop.memory.working_memory == []
    assert loop._pending_step is None


def test_save_failure_discards_stage_without_live_mutation(tmp_path):
    class FailingMemory(MemoryStore):
        def save(self, path):
            raise OSError("disk secret")

    memory = FailingMemory.empty()
    loop = AgentLoop(FakeApi(decision()), memory, tmp_path / "memory.json")
    result = loop.handle_observation(observation(1))

    assert not loop.commit_action_batch_sent(result["observation_id"])
    assert loop.memory is memory
    assert loop._pending_step is None
    assert not loop.discard_action_batch(1)


def test_same_path_reconnect_clears_pending_and_staged(tmp_path):
    path = tmp_path / "memory.json"
    loop = AgentLoop(FakeApi(decision()), MemoryStore.empty(), path)
    result = loop.handle_observation(observation(1))
    assert loop.commit_action_batch_sent(result["observation_id"])
    loop.handle_observation(observation(2))

    loop.configure_memory(path)

    assert loop._pending_step is None
    assert not loop.discard_action_batch(2)
