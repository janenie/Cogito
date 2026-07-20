import json
import socket
import threading
import time

import pytest
from websockets.sync.client import connect

from ai_play.bridge_server import serve
from ai_play.config import Config


class FakeAgentLoop:
    def __init__(self):
        self.memory_paths = []
        self.observations = []

    def configure_memory(self, path):
        self.memory_paths.append(path)

    def handle_observation(self, observation):
        self.observations.append(observation)
        return {
            "type": "action_batch",
            "protocol_version": 1,
            "observation_id": observation["observation_id"],
            "reason": "fake",
            "actions": [{"type": "wait", "duration_ms": 100}],
        }


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_server(tmp_path, configured_data_dir=None):
    port = _free_port()
    test_key = "test-key"
    config = Config(
        api_key=test_key,
        ws_port=port,
        data_dir=configured_data_dir,
    )
    agent = FakeAgentLoop()
    errors = []

    def run():
        try:
            serve(config, agent)
        except Exception as exc:  # pragma: no cover - asserted by startup below
            errors.append(exc)

    threading.Thread(target=run, daemon=True).start()
    uri = f"ws://127.0.0.1:{port}"
    deadline = time.monotonic() + 2
    while True:
        try:
            connection = connect(uri, proxy=None)
            connection.close()
            break
        except Exception:
            if errors or time.monotonic() >= deadline:
                pytest.fail(f"server did not start: {errors}")
            time.sleep(0.01)
    return uri, agent


def _send(connection, packet):
    connection.send(json.dumps(packet))
    return json.loads(connection.recv())


def _hello(data_dir, protocol_version=1):
    return {
        "type": "hello",
        "protocol_version": protocol_version,
        "data_dir": str(data_dir),
    }


def test_rejects_observation_before_hello(tmp_path):
    uri, agent = _start_server(tmp_path)
    with connect(uri, proxy=None) as connection:
        result = _send(
            connection,
            {"type": "observation", "protocol_version": 1, "observation_id": 3},
        )

    assert result["type"] == "error"
    assert result["code"] == "hello_required"
    assert agent.observations == []


@pytest.mark.parametrize("protocol_version", [0, 2, "1", True, 1.0])
def test_accepts_exactly_protocol_version_one(tmp_path, protocol_version):
    uri, _ = _start_server(tmp_path)
    with connect(uri, proxy=None) as connection:
        result = _send(connection, _hello(tmp_path, protocol_version))

    assert result["type"] == "error"
    assert result["code"] == "unsupported_protocol"


@pytest.mark.parametrize("use_config_dir", [False, True])
def test_config_data_dir_takes_priority_over_hello_data_dir(tmp_path, use_config_dir):
    config_dir = tmp_path / "configured"
    hello_dir = tmp_path / "godot"
    uri, agent = _start_server(
        tmp_path,
        configured_data_dir=config_dir if use_config_dir else None,
    )
    with connect(uri, proxy=None) as connection:
        result = _send(connection, _hello(hello_dir))

    assert result == {"type": "hello", "protocol_version": 1}
    selected = config_dir if use_config_dir else hello_dir
    assert agent.memory_paths == [selected / "ai_play" / "memory.json"]
    assert (selected / "ai_play").is_dir()
    assert not (hello_dir / "ai_play").exists() if use_config_dir else True


def test_returns_agent_batch_for_valid_observation(tmp_path):
    uri, agent = _start_server(tmp_path)
    observation = {
        "type": "observation",
        "protocol_version": 1,
        "observation_id": 14,
    }
    with connect(uri, proxy=None) as connection:
        assert _send(connection, _hello(tmp_path))["type"] == "hello"
        result = _send(connection, observation)

    assert result == {
        "type": "action_batch",
        "protocol_version": 1,
        "observation_id": 14,
        "reason": "fake",
        "actions": [{"type": "wait", "duration_ms": 100}],
    }
    assert agent.observations == [observation]
