import json
import socket
import threading
import time

import pytest
from websockets.sync.client import connect
from websockets.exceptions import ConnectionClosedOK

from ai_play.bridge_server import _handler, serve
from ai_play.config import Config


class FakeAgentLoop:
    def __init__(self):
        self.memory_paths = []
        self.observations = []
        self.commits = []
        self.discards = []
        self.action_results = []
        self.stops = []
        self.commit_result = True

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

    def commit_action_batch_sent(self, observation_id):
        self.commits.append(observation_id)
        return self.commit_result

    def discard_action_batch(self, observation_id):
        self.discards.append(observation_id)
        return True

    def record_action_results(self, observation_id, results):
        self.action_results.append((observation_id, results))
        return True

    def record_stop(self, reason, observation_id=None, results=None):
        self.stops.append((reason, observation_id, results))


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


class ClosedReceiveConnection(FakeConnection):
    def __init__(self):
        super().__init__([])

    def recv(self, timeout=None):
        raise ConnectionClosedOK(None, None)


class ClosedSendConnection(IdleConnection):
    def send(self, packet):
        raise ConnectionClosedOK(None, None)


class FailingActionSendConnection(FakeConnection):
    def __init__(self, packets):
        super().__init__(packets)
        self.send_count = 0

    def send(self, packet):
        self.send_count += 1
        if self.send_count == 2:
            raise OSError("transport secret")
        super().send(packet)


@pytest.mark.parametrize("connection", [ClosedReceiveConnection(), ClosedSendConnection()])
def test_closed_peer_during_initial_handshake_returns_quietly(connection):
    lock = threading.Lock()
    test_key = "test-key"

    _handler(connection, Config(api_key=test_key), FakeAgentLoop(), lock)

    assert lock.acquire(blocking=False)
    lock.release()


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


def test_routes_action_results_to_the_correlated_round(tmp_path):
    agent = FakeAgentLoop()
    test_key = "test-key"
    results = [{"status": "completed", "type": "move"}]
    connection = FakeConnection([
        _hello(tmp_path),
        {
            "type": "action_results",
            "protocol_version": 1,
            "observation_id": 17,
            "results": results,
        },
    ])

    _handler(connection, Config(api_key=test_key), agent, threading.Lock())

    assert agent.action_results == [(17, results)]
    assert [packet["type"] for packet in connection.sent] == ["hello"]


def test_routes_escape_stop_and_ends_the_session(tmp_path):
    agent = FakeAgentLoop()
    test_key = "test-key"
    results = [{"status": "cancelled", "reason": "escape_stop"}]
    connection = FakeConnection([
        _hello(tmp_path),
        {
            "type": "stop",
            "protocol_version": 1,
            "observation_id": 17,
            "reason": "escape_stop",
            "results": results,
        },
        {"type": "observation", "protocol_version": 1, "observation_id": 18},
    ])

    _handler(connection, Config(api_key=test_key), agent, threading.Lock())

    assert agent.stops == [("escape_stop", 17, results)]
    assert agent.observations == []


def test_action_batch_send_failure_discards_and_ends_session(tmp_path):
    agent = FakeAgentLoop()
    observation = {"type": "observation", "protocol_version": 1, "observation_id": 7}
    connection = FailingActionSendConnection([_hello(tmp_path), observation])
    test_key = "test-key"

    _handler(connection, Config(api_key=test_key), agent, threading.Lock())

    assert agent.discards == [7]
    assert agent.commits == []


def test_commit_failure_ends_session_after_successful_send(tmp_path):
    agent = FakeAgentLoop()
    agent.commit_result = False
    observation = {"type": "observation", "protocol_version": 1, "observation_id": 8}
    connection = FakeConnection([_hello(tmp_path), observation])
    test_key = "test-key"

    _handler(connection, Config(api_key=test_key), agent, threading.Lock())

    assert agent.commits == [8]


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
