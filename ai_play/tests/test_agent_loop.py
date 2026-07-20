import threading

import ai_play.agent_loop as agent_loop_module
from ai_play.agent_loop import AgentLoop


def observation(observation_id=9):
    return {
        "observation_id": observation_id,
        "image": {"mime_type": "image/jpeg", "base64": "aW1hZ2U="},
        "interface": {
            "is_open": False,
            "available_interactions": [
                {"action": "interact2", "binding": "E", "prompt": "Use"}
            ],
        },
    }


class FakeApi:
    def __init__(self, decision):
        self.decision = decision

    def decide(self, messages):
        return self.decision


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


def test_applies_and_saves_memory_only_after_decision_validation(tmp_path):
    memory = FakeMemory()
    updates = [{"kind": "goal", "text": "Explore"}]
    loop = AgentLoop(FakeApi(decision(memory_updates=updates)), memory, tmp_path / "memory.json")

    loop.handle_observation(observation())

    assert memory.updates == [(updates, 9)]
    assert memory.saved_paths == [tmp_path / "memory.json"]


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
