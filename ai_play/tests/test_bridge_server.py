import json
import socket
import threading
import time

import pytest
from websockets.sync.client import connect

from ai_play.bridge_server import _handler, serve
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


class FakeConnection:
    def __init__(self, packets):
        self.packets = iter(json.dumps(packet) for packet in packets)
        self.sent = []

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.packets)

    def recv(self, timeout=None):
        return next(self.packets)

    def send(self, packet):
        self.sent.append(json.loads(packet))


class IdleConnection(FakeConnection):
    def __init__(self):
        super().__init__([])

    def recv(self, timeout=None):
        raise TimeoutError

    def __next__(self):
        raise AssertionError("idle handshake must use bounded recv")


def test_idle_client_times_out_without_taking_session_lock(tmp_path):
    lock = threading.Lock()
    agent = FakeAgentLoop()
    connection = IdleConnection()
    test_key = "test-key"

    _handler(connection, Config(api_key=test_key), agent, lock)

    assert connection.sent[0]["code"] == "hello_timeout"
    assert agent.memory_paths == []
    assert lock.acquire(blocking=False)
    lock.release()


@pytest.mark.parametrize(
    ("first_packet", "code"),
    [
        ({"not": "protocol"}, "unsupported_protocol"),
        ({"type": "observation", "protocol_version": 1}, "hello_required"),
        ({"type": "hello", "protocol_version": 2}, "unsupported_protocol"),
    ],
)
def test_invalid_first_packet_returns_without_consuming_later_hello(
    tmp_path, first_packet, code
):
    lock = threading.Lock()
    agent = FakeAgentLoop()
    connection = FakeConnection([first_packet, _hello(tmp_path)])
    test_key = "test-key"

    _handler(connection, Config(api_key=test_key), agent, lock)

    assert [packet["code"] for packet in connection.sent] == [code]
    assert agent.memory_paths == []
    assert lock.acquire(blocking=False)
    lock.release()


def test_busy_second_controller_cannot_reconfigure_memory(tmp_path):
    lock = threading.Lock()
    lock.acquire()
    agent = FakeAgentLoop()
    connection = FakeConnection([_hello(tmp_path)])
    test_key = "test-key"

    _handler(connection, Config(api_key=test_key), agent, lock)

    assert connection.sent == [{
        "type": "error", "protocol_version": 1, "observation_id": None,
        "code": "controller_busy", "message": "controller_busy",
    }]
    assert agent.memory_paths == []
    assert lock.locked()
    lock.release()


def test_hello_canonicalizes_memory_directory(tmp_path):
    selected = tmp_path / "parent" / ".." / "selected"
    agent = FakeAgentLoop()
    connection = FakeConnection([_hello(selected), {"type": "stop", "protocol_version": 1}])
    test_key = "test-key"

    _handler(connection, Config(api_key=test_key), agent, threading.Lock())

    assert agent.memory_paths == [selected.resolve() / "ai_play" / "memory.json"]


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


def test_idle_connection_does_not_starve_valid_controller(tmp_path):
    uri, _ = _start_server(tmp_path)
    idle = connect(uri, proxy=None)
    with connect(uri, proxy=None) as valid_connection:
        assert _send(valid_connection, _hello(tmp_path))["type"] == "hello"
    idle.close()


def test_invalid_first_packet_does_not_starve_valid_controller(tmp_path):
    uri, _ = _start_server(tmp_path)
    with connect(uri, proxy=None) as invalid_connection:
        result = _send(
            invalid_connection,
            {"type": "observation", "protocol_version": 1},
        )
        assert result["code"] == "hello_required"
    with connect(uri, proxy=None) as valid_connection:
        assert _send(valid_connection, _hello(tmp_path))["type"] == "hello"


def test_busy_valid_second_controller_cannot_reconfigure_memory(tmp_path):
    uri, agent = _start_server(tmp_path)
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    with connect(uri, proxy=None) as first:
        assert _send(first, _hello(first_dir))["type"] == "hello"
        with connect(uri, proxy=None) as second:
            result = _send(second, _hello(second_dir))
            assert result["code"] == "controller_busy"

    assert agent.memory_paths == [first_dir.resolve() / "ai_play" / "memory.json"]
