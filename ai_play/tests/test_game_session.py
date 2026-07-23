import base64
import threading
import time

import pytest

from ai_play.config import Config
from ai_play.game_session import GameSession, SessionError, SessionResult


def observation(observation_id):
    image_bytes = b"\xff\xd8\xffsession-image\xff\xd9"
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
        "observation_id": observation_id,
        "captured_at_ms": observation_id * 10,
        "image": {
            "mime_type": "image/jpeg",
            "base64": base64.b64encode(image_bytes).decode("ascii"),
            "width": 768,
            "height": 432,
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


def make_session():
    sent = []
    session = GameSession(
        Config(wait_timeout_seconds=0.2, stop_timeout_seconds=0.2)
    )
    session.attach(lambda packet: sent.append(packet) or True)
    return session, sent


def wait_until(predicate, timeout=0.5):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("condition was not reached before timeout")
        time.sleep(0.005)


def wait_action_results(observation_id=7):
    return [{"status": "completed", "type": "wait"}]


def test_observe_waits_for_and_returns_latest_observation():
    session, sent = make_session()
    result_holder = []

    thread = threading.Thread(
        target=lambda: result_holder.append(session.observe(timeout=0.5))
    )
    thread.start()
    time.sleep(0.02)
    session.receive_observation(observation(7))
    thread.join()

    assert result_holder == [
        SessionResult(status="ready", observation=observation(7))
    ]
    assert sent == []


def test_act_rejects_stale_observation_without_sending_to_godot():
    session, sent = make_session()
    session.receive_observation(observation(7))

    with pytest.raises(SessionError, match="stale_observation"):
        session.act(
            6,
            [{"type": "wait", "duration_ms": 50}],
            timeout=0.5,
        )

    assert sent == []


def test_act_sends_valid_batch_and_waits_for_results_and_next_observation():
    session, sent = make_session()
    session.receive_observation(observation(7))
    actions = [{"type": "wait", "duration_ms": 50}]
    result_holder = []

    thread = threading.Thread(
        target=lambda: result_holder.append(session.act(7, actions, timeout=0.5))
    )
    thread.start()
    wait_until(lambda: len(sent) == 1)

    assert sent == [{
        "type": "action_batch",
        "protocol_version": 2,
        "observation_id": 7,
        "actions": actions,
    }]

    session.receive_action_results(7, wait_action_results())
    session.receive_observation(observation(8))
    thread.join()

    assert result_holder == [SessionResult(
        status="ready",
        observation=observation(8),
        action_results=wait_action_results(),
    )]


def test_act_rejects_second_in_flight_batch():
    session, sent = make_session()
    session.receive_observation(observation(7))
    result_holder = []
    thread = threading.Thread(
        target=lambda: result_holder.append(
            session.act(7, [{"type": "wait", "duration_ms": 50}], timeout=0.5)
        )
    )
    thread.start()
    wait_until(lambda: len(sent) == 1)

    with pytest.raises(SessionError, match="action_in_flight"):
        session.act(7, [{"type": "wait", "duration_ms": 50}], timeout=0.1)

    session.receive_action_results(7, wait_action_results())
    session.receive_observation(observation(8))
    thread.join()
    assert result_holder[0].status == "ready"


def test_act_returns_game_over_when_terminal_packet_precedes_next_observation():
    session, sent = make_session()
    session.receive_observation(observation(7))
    result_holder = []
    thread = threading.Thread(
        target=lambda: result_holder.append(
            session.act(7, [{"type": "wait", "duration_ms": 50}], timeout=0.5)
        )
    )
    thread.start()
    wait_until(lambda: len(sent) == 1)

    results = wait_action_results()
    terminal = {
        "type": "game_over",
        "protocol_version": 2,
        "observation_id": 7,
        "outcome": "success",
        "reason": "correct_password",
    }
    session.receive_action_results(7, results)
    session.receive_game_over(terminal)
    thread.join()

    assert result_holder == [SessionResult(
        status="game_over",
        action_results=results,
        game_over=terminal,
    )]
    with pytest.raises(SessionError, match="game_over"):
        session.act(7, [{"type": "wait", "duration_ms": 50}], timeout=0.1)


def test_session_rejects_invalid_action_results():
    session, sent = make_session()
    session.receive_observation(observation(7))
    errors = []
    thread = threading.Thread(
        target=lambda: _capture_session_error(
            errors,
            session.act,
            7,
            [{"type": "wait", "duration_ms": 50}],
            timeout=0.1,
        )
    )
    thread.start()
    wait_until(lambda: len(sent) == 1)

    with pytest.raises(SessionError, match="invalid_action_results"):
        session.receive_action_results(7, [{"status": "unknown"}])
    thread.join()
    assert str(errors[0]) == "action_timeout"


def test_stop_sends_mcp_stop_and_acknowledges_cancellation():
    session, sent = make_session()
    session.receive_observation(observation(7))

    result_holder = []
    thread = threading.Thread(target=lambda: result_holder.append(session.stop()))
    thread.start()
    wait_until(lambda: len(sent) == 1)

    assert sent == [{
        "type": "stop_request",
        "protocol_version": 2,
        "observation_id": 7,
        "reason": "mcp_stop",
    }]
    results = [{"status": "cancelled", "reason": "mcp_stop"}]
    session.receive_stop_ack({
        "type": "stop_ack",
        "protocol_version": 2,
        "observation_id": 7,
        "results": results,
    })
    thread.join()

    assert result_holder == [SessionResult(status="stopped", action_results=results)]
    assert session.stop() == result_holder[0]
    assert len(sent) == 1


def test_act_times_out_and_does_not_leave_an_in_flight_batch():
    session, sent = make_session()
    session.receive_observation(observation(7))

    with pytest.raises(SessionError, match="action_timeout"):
        session.act(7, [{"type": "wait", "duration_ms": 50}], timeout=0.01)

    assert len(sent) == 1


def test_detach_wakes_pending_action_without_fabricating_success():
    session, sent = make_session()
    session.receive_observation(observation(7))
    result_holder = []
    thread = threading.Thread(
        target=lambda: result_holder.append(
            _call_and_capture(session.act, 7, [{"type": "wait", "duration_ms": 50}])
        )
    )
    thread.start()
    wait_until(lambda: len(sent) == 1)
    session.detach("connection_closed")
    thread.join()

    assert isinstance(result_holder[0], SessionError)
    assert str(result_holder[0]) == "disconnected"
    assert session.observe(timeout=0.01).status == "disconnected"


def test_to_mcp_payload_separates_image_bytes_from_structured_observation():
    session, _ = make_session()
    result = SessionResult(status="ready", observation=observation(7))

    payload, image_bytes = session.to_mcp_payload(result)

    assert "base64" not in payload["observation"]["image"]
    assert image_bytes.startswith(b"\xff\xd8\xff")


def _call_and_capture(function, *args):
    try:
        return function(*args, timeout=0.5)
    except SessionError as error:
        return error


def _capture_session_error(errors, function, *args, timeout):
    try:
        function(*args, timeout=timeout)
    except SessionError as error:
        errors.append(error)
