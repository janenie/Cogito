import base64
import json
import socket
import threading
import time

import pytest
from websockets.sync.client import connect

from ai_play.bridge_server import start
from ai_play.config import Config
from ai_play.game_session import GameSession, SessionResult


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_test_bridge(session):
    config = Config(ws_port=_free_port())
    handle = start(config, session)
    return f"ws://127.0.0.1:{config.ws_port}", handle


def _send(connection, packet):
    connection.send(json.dumps(packet, separators=(",", ":")))
    return json.loads(connection.recv())


def _hello(scenario_id="find_contract"):
    return {
        "type": "hello",
        "protocol_version": 3,
        "scenario_id": scenario_id,
    }


def _observation(observation_id=7):
    image = b"\xff\xd8\xffbridge-image\xff\xd9"
    bindings = {
        "forward": "W",
        "back": "S",
        "left": "A",
        "right": "D",
        "jump": "Space",
        "sprint": "Shift",
        "crouch": "Ctrl",
        "interact": "E",
        "interact2": "F",
        "menu": "Escape",
    }
    return {
        "type": "observation",
        "protocol_version": 3,
        "observation_id": observation_id,
        "captured_at_ms": 123,
        "image": {
            "mime_type": "image/jpeg",
            "base64": base64.b64encode(image).decode("ascii"),
            "width": 1024,
            "height": 576,
        },
        "player": {
            "position": [0, 0, 0],
            "yaw_degrees": 0,
            "pitch_degrees": 0,
            "planar_velocity": [0, 0],
            "on_floor": True,
        },
        "interface": {
            "is_open": False,
            "visible_object_text": "",
            "available_interactions": [],
        },
        "bindings": bindings,
        "last_action_results": [],
    }


def _home_observation(observation_id=7):
    observation = _observation(observation_id)
    observation["routine"] = {
        "objective": "把全部垃圾扔进客厅垃圾桶。",
        "trash_collected": 0,
        "trash_required": 2,
        "held_item": "空",
        "completed": False,
        "failed": False,
    }
    return observation


def _garden_observation(observation_id=7):
    observation = _observation(observation_id)
    observation["garden"] = {
        "objective": "给目标花园浇水。",
        "time": "08:29",
        "weather": "sunny",
        "has_watering_can": False,
        "can_has_water": True,
        "watered_lawns": 0,
        "required_lawns": 4,
        "rain_alarm_pressed": False,
        "completed": False,
        "failed": False,
    }
    return observation


def _wait_until(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("condition was not reached before timeout")
        time.sleep(0.005)


def test_bridge_accepts_exact_protocol_three_hello():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)

    try:
        with connect(uri, proxy=None) as connection:
            assert _send(connection, _hello()) == {
                "type": "hello",
                "protocol_version": 3,
                "scenario_id": "find_contract",
            }
    finally:
        handle.close()


@pytest.mark.parametrize("version", [1, 2, 4, True, 3.0, "3"])
def test_bridge_rejects_non_integer_protocol_three(version):
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)

    try:
        with connect(uri, proxy=None) as connection:
            result = _send(connection, {
                "type": "hello",
                "protocol_version": version,
            })
    finally:
        handle.close()

    assert result["code"] == "unsupported_protocol"


def test_bridge_routes_valid_observation_to_game_session():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)

    try:
        with connect(uri, proxy=None) as connection:
            assert _send(connection, _hello())["type"] == "hello"
            connection.send(json.dumps(_observation()))
            result = session.observe(timeout=0.5)
    finally:
        handle.close()

    assert result.status == "ready"
    assert result.observation["observation_id"] == 7


def test_bridge_routes_home_routine_observation_to_game_session():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)

    try:
        with connect(uri, proxy=None) as connection:
            assert _send(connection, _hello("daily_routine_cleanup"))["type"] == "hello"
            connection.send(json.dumps(_home_observation()))
            result = session.observe(timeout=0.5)
    finally:
        handle.close()

    assert result.status == "ready"
    assert result.observation["routine"]["trash_required"] == 2


def test_bridge_routes_garden_observation_to_game_session():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)

    try:
        with connect(uri, proxy=None) as connection:
            assert _send(connection, _hello("garden_watering"))["type"] == "hello"
            connection.send(json.dumps(_garden_observation()))
            result = session.observe(timeout=0.5)
    finally:
        handle.close()

    assert result.status == "ready"
    assert result.observation["garden"]["required_lawns"] == 4


def test_bridge_rejects_second_controller_as_busy():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)

    try:
        with connect(uri, proxy=None) as first:
            assert _send(first, _hello())["type"] == "hello"
            with connect(uri, proxy=None) as second:
                result = _send(second, _hello())
                assert result["code"] == "controller_busy"
    finally:
        handle.close()


def test_invalid_connection_does_not_consume_later_valid_connection():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)

    try:
        with connect(uri, proxy=None) as invalid:
            assert _send(invalid, {
                "type": "observation",
                "protocol_version": 3,
            })["code"] == "hello_required"
        with connect(uri, proxy=None) as valid:
            assert _send(valid, _hello())["type"] == "hello"
    finally:
        handle.close()


def test_bridge_routes_stop_ack_to_session():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)
    result_holder = []

    try:
        with connect(uri, proxy=None) as connection:
            assert _send(connection, _hello())["type"] == "hello"
            connection.send(json.dumps(_observation()))
            assert session.observe(timeout=0.5).status == "ready"

            thread = threading.Thread(
                target=lambda: result_holder.append(session.stop(timeout=0.5))
            )
            thread.start()
            request = json.loads(connection.recv())
            assert request == {
                "type": "stop_request",
                "protocol_version": 3,
                "observation_id": 7,
                "reason": "mcp_stop",
            }
            connection.send(json.dumps({
                "type": "stop_ack",
                "protocol_version": 3,
                "observation_id": 7,
                "results": [{"status": "cancelled", "reason": "mcp_stop"}],
            }))
            thread.join()
    finally:
        handle.close()

    assert result_holder == [SessionResult(
        status="stopped",
        action_results=[{"status": "cancelled", "reason": "mcp_stop"}],
    )]


def test_bridge_routes_game_over_to_session():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)
    terminal = {
        "type": "game_over",
        "protocol_version": 3,
        "observation_id": 7,
        "outcome": "failure",
        "reason": "wrong_password",
    }

    try:
        with connect(uri, proxy=None) as connection:
            assert _send(connection, _hello())["type"] == "hello"
            connection.send(json.dumps(_observation()))
            assert session.observe(timeout=0.5).status == "ready"
            connection.send(json.dumps(terminal))
            _wait_until(lambda: session._state == "game_over")
            result = session.observe(timeout=0.5)
    finally:
        handle.close()

    assert result == SessionResult(status="game_over", game_over=terminal)


def test_bridge_routes_find_key_success_to_session():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)
    terminal = {
        "type": "game_over",
        "protocol_version": 3,
        "observation_id": 7,
        "outcome": "success",
        "reason": "key_picked_up",
    }

    try:
        with connect(uri, proxy=None) as connection:
            assert _send(connection, _hello("find_key")) == {
                "type": "hello",
                "protocol_version": 3,
                "scenario_id": "find_key",
            }
            connection.send(json.dumps(_observation()))
            assert session.observe(timeout=0.5).status == "ready"
            connection.send(json.dumps(terminal))
            _wait_until(lambda: session._state == "game_over")
            result = session.observe(timeout=0.5)
    finally:
        handle.close()

    assert result == SessionResult(status="game_over", game_over=terminal)


def test_bridge_accepts_find_key_round_request_limit_without_echoing_it():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)
    hello = _hello("find_key")
    hello["act_request_limit"] = 50

    try:
        with connect(uri, proxy=None) as connection:
            result = _send(connection, hello)
    finally:
        handle.close()

    assert result == {
        "type": "hello",
        "protocol_version": 3,
        "scenario_id": "find_key",
    }
    assert session.act_request_limit == 50


@pytest.mark.parametrize(
    ("scenario_id", "act_request_limit"),
    [
        ("find_key", True),
        ("find_key", 50.0),
        ("find_key", "50"),
        ("find_key", 49),
        ("find_key", 51),
        ("find_key", 101),
        ("find_contract", 50),
    ],
)
def test_bridge_rejects_invalid_round_request_limit(
    scenario_id,
    act_request_limit,
):
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)
    hello = _hello(scenario_id)
    hello["act_request_limit"] = act_request_limit

    try:
        with connect(uri, proxy=None) as connection:
            result = _send(connection, hello)
    finally:
        handle.close()

    assert result["code"] == "invalid_act_request_limit"


def test_bridge_rejects_exact_hello_extras_and_invalid_json():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)

    try:
        with connect(uri, proxy=None) as connection:
            result = _send(connection, {
                "type": "hello",
                "protocol_version": 3,
                "extra": True,
            })
            assert result["code"] == "invalid_hello"
        with connect(uri, proxy=None) as connection:
            connection.send("not-json")
            result = json.loads(connection.recv())
            assert result["code"] == "invalid_packet"
    finally:
        handle.close()


def test_bridge_accepts_legacy_hello_as_default_scenario():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)

    try:
        with connect(uri, proxy=None) as connection:
            result = _send(connection, {
                "type": "hello",
                "protocol_version": 3,
            })
    finally:
        handle.close()

    assert result["scenario_id"] == "find_contract"
    assert session.scenario_id == "find_contract"


def test_bridge_accepts_legacy_find_key_hello_with_default_limit():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)

    try:
        with connect(uri, proxy=None) as connection:
            result = _send(connection, _hello("find_key"))
    finally:
        handle.close()

    assert result["scenario_id"] == "find_key"
    assert session.act_request_limit == 100


def test_bridge_rejects_unknown_scenario():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)

    try:
        with connect(uri, proxy=None) as connection:
            result = _send(connection, _hello("unknown_scenario"))
    finally:
        handle.close()

    assert result["code"] == "unsupported_scenario"


def test_bridge_rejects_non_loopback_configuration():
    session = GameSession(Config())

    with pytest.raises(ValueError, match="127.0.0.1"):
        start(Config(ws_host="localhost", ws_port=_free_port()), session)
