import base64
import struct
import threading
import time
import zlib

import pytest

from ai_play.config import Config
from ai_play.game_session import GameSession, SessionError, SessionResult
from ai_play.trajectory_logger import LogPersistenceError


def _depth_png():
    def chunk(kind, data):
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", checksum)
        )

    header = struct.pack(">IIBBBBB", 1024, 576, 8, 2, 0, 0, 0)
    rows = (b"\x00" + b"\xff\xff\xff" * 1024) * 576
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


DEPTH_PNG = _depth_png()


def observation(observation_id, include_depth=False):
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
    result = {
        "observation_id": observation_id,
        "captured_at_ms": observation_id * 10,
        "image": {
            "mime_type": "image/jpeg",
            "base64": base64.b64encode(image_bytes).decode("ascii"),
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
    if include_depth:
        result["depth_image"] = {
            "mime_type": "image/png",
            "base64": base64.b64encode(DEPTH_PNG).decode("ascii"),
            "width": 1024,
            "height": 576,
            "encoding": "linear_depth_normalized_8bit",
            "near_meters": 0.05,
            "far_meters": 20.0,
        }
    return result


class RecordingLogger:
    def __init__(self, fail_start=False):
        self.fail_start = fail_start
        self.events = []

    def start_attempt(self, scenario_id):
        if self.fail_start:
            raise LogPersistenceError("logging_failed")
        self.events.append(("start", scenario_id))

    def finish_attempt(self, status, terminal_reason):
        self.events.append(("finish", status, terminal_reason))

    def close(self):
        self.events.append(("close", None))


class RecordingAttemptObserver:
    def __init__(self):
        self.events = []

    def start_attempt(self, scenario_id):
        self.events.append(("start", scenario_id))

    def finish_attempt(self, status, terminal_reason):
        self.events.append(("finish", status, terminal_reason))


def make_session(
    max_act_requests=500,
    trajectory_logger=None,
    attempt_observer=None,
    scenario_id="find_contract",
):
    sent = []
    session = GameSession(
        Config(
            wait_timeout_seconds=0.2,
            stop_timeout_seconds=0.2,
            max_act_requests=max_act_requests,
        ),
        trajectory_logger=trajectory_logger,
        attempt_observer=attempt_observer,
    )
    session.attach(
        lambda packet: sent.append(packet) or True,
        scenario_id=scenario_id,
    )
    return session, sent


def make_scenario_session(scenario_id, configured_limit=500):
    sent = []
    session = GameSession(
        Config(
            wait_timeout_seconds=0.2,
            stop_timeout_seconds=0.2,
            max_act_requests=configured_limit,
        )
    )
    session.attach(
        lambda packet: sent.append(packet) or True,
        scenario_id=scenario_id,
    )
    return session, sent


def test_session_records_scenario_and_rejects_mismatched_reconnect():
    session = GameSession(Config())
    session.attach(lambda packet: True, "find_contract")

    assert session.wait_for_scenario(timeout=0.1) == "find_contract"

    session.detach("test")
    with pytest.raises(SessionError, match="scenario_mismatch"):
        session.attach(lambda packet: True, "other_scenario")


def test_wait_for_scenario_times_out_before_game_connects():
    session = GameSession(Config(wait_timeout_seconds=0.1))

    with pytest.raises(SessionError, match="game_not_connected"):
        session.wait_for_scenario(timeout=0.01)


def test_find_key_uses_150_request_hard_cap():
    session, _ = make_scenario_session("find_key", configured_limit=500)

    assert session.act_request_limit == 150


def test_find_contract_uses_150_request_hard_cap():
    session, _ = make_scenario_session("find_contract", configured_limit=500)

    assert session.act_request_limit == 150


def test_find_key_round_request_limit_is_locked_across_reconnect():
    session = GameSession(Config(max_act_requests=500))
    session.attach(
        lambda packet: True,
        "find_key",
        act_request_limit=50,
    )

    assert session.act_request_limit == 50

    session.detach("test")
    session.attach(
        lambda packet: True,
        "find_key",
        act_request_limit=50,
    )

    assert session.act_request_limit == 50

    session.detach("test")
    with pytest.raises(SessionError, match="scenario_mismatch"):
        session.attach(
            lambda packet: True,
            "find_key",
            act_request_limit=100,
        )


def test_global_limit_can_tighten_find_key_round_cap():
    session = GameSession(Config(max_act_requests=40))
    session.attach(
        lambda packet: True,
        "find_key",
        act_request_limit=50,
    )

    assert session.act_request_limit == 40


def test_global_limit_can_tighten_find_key_cap():
    session, _ = make_scenario_session("find_key", configured_limit=75)

    assert session.act_request_limit == 75


def test_put_book_uses_150_request_hard_cap():
    session, _ = make_scenario_session("put_book", configured_limit=500)

    assert session.act_request_limit == 150


def test_greet_npc_meeting_uses_150_request_hard_cap():
    session, _ = make_scenario_session(
        "greet_npc_meeting",
        configured_limit=500,
    )

    assert session.act_request_limit == 150


def test_global_limit_can_tighten_put_book_cap():
    session, _ = make_scenario_session("put_book", configured_limit=80)

    assert session.act_request_limit == 80


def test_global_limit_can_tighten_greet_npc_meeting_cap():
    session, _ = make_scenario_session(
        "greet_npc_meeting",
        configured_limit=75,
    )

    assert session.act_request_limit == 75


def test_garden_watering_uses_scenario_request_cap():
    session, _ = make_scenario_session("garden_watering")

    assert session.act_request_limit == 150


def test_loop_staircase_anomaly_uses_scenario_request_cap():
    session, _ = make_scenario_session("loop_staircase_anomaly")

    assert session.act_request_limit == 150


def test_repair_lighting_circuit_uses_150_request_hard_cap():
    session, _ = make_scenario_session(
        "repair_lighting_circuit",
        configured_limit=500,
    )

    assert session.act_request_limit == 150


def test_arrange_meeting_briefings_uses_150_request_hard_cap():
    session, _ = make_scenario_session(
        "arrange_meeting_briefings",
        configured_limit=500,
    )
    tightened, _ = make_scenario_session(
        "arrange_meeting_briefings",
        configured_limit=80,
    )

    assert session.act_request_limit == 150
    assert tightened.act_request_limit == 80


def test_find_key_accepts_only_key_success_terminal():
    session, _ = make_scenario_session("find_key")
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "success",
        "reason": "key_picked_up",
    }

    session.receive_game_over(terminal)

    assert session.observe(timeout=0.1).game_over == terminal


def test_find_key_accepts_security_lockout_terminal():
    session, _ = make_scenario_session("find_key")
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "failure",
        "reason": "security_lockout",
    }

    session.receive_game_over(terminal)

    assert session.observe(timeout=0.1).game_over == terminal


def test_put_book_accepts_only_ceo_office_success_terminal():
    session, _ = make_scenario_session("put_book")
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "success",
        "reason": "books_in_ceo_office",
    }
    session.receive_game_over(terminal)
    assert session.observe(timeout=0.1).game_over == terminal


def test_put_book_accepts_wrong_book_pickup_failure_terminal():
    session, _ = make_scenario_session("put_book")
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "failure",
        "reason": "wrong_book_pickup",
    }

    session.receive_game_over(terminal)

    assert session.observe(timeout=0.1).game_over == terminal


def test_greet_npc_meeting_accepts_only_meeting_door_success_terminal():
    session, _ = make_scenario_session("greet_npc_meeting")
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "success",
        "reason": "meeting_door_closed",
    }
    session.receive_game_over(terminal)
    assert session.observe(timeout=0.1).game_over == terminal


def test_greet_npc_meeting_accepts_wrong_npc_limit_failure_terminal():
    session, _ = make_scenario_session("greet_npc_meeting")
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "failure",
        "reason": "wrong_npc_limit",
    }
    session.receive_game_over(terminal)
    assert session.observe(timeout=0.1).game_over == terminal


def test_garden_watering_accepts_garden_success_terminal():
    session, _ = make_scenario_session("garden_watering")
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "success",
        "reason": "garden_tasks_complete",
    }
    session.receive_game_over(terminal)
    assert session.observe(timeout=0.1).game_over == terminal


def test_arrange_meeting_briefings_accepts_meeting_success_terminal():
    session, _ = make_scenario_session("arrange_meeting_briefings")
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "success",
        "reason": "meeting_prepared",
    }

    session.receive_game_over(terminal)

    assert session.observe(timeout=0.1).game_over == terminal


def test_loop_staircase_anomaly_accepts_correct_floor_terminal():
    session, _ = make_scenario_session("loop_staircase_anomaly")
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "success",
        "reason": "correct_floor_selected",
    }
    session.receive_game_over(terminal)
    assert session.observe(timeout=0.1).game_over == terminal


def test_loop_staircase_anomaly_accepts_wrong_floor_terminal():
    session, _ = make_scenario_session("loop_staircase_anomaly")
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "failure",
        "reason": "wrong_floor_selected",
    }
    session.receive_game_over(terminal)
    assert session.observe(timeout=0.1).game_over == terminal


def test_terminal_success_cannot_cross_scenarios():
    contract, _ = make_scenario_session("find_contract")
    contract.receive_observation(observation(7))
    with pytest.raises(SessionError, match="invalid_game_over"):
        contract.receive_game_over({
            "type": "game_over",
            "protocol_version": 4,
            "observation_id": 7,
            "outcome": "success",
            "reason": "key_picked_up",
        })

    find_key, _ = make_scenario_session("find_key")
    find_key.receive_observation(observation(7))
    with pytest.raises(SessionError, match="invalid_game_over"):
        find_key.receive_game_over({
            "type": "game_over",
            "protocol_version": 4,
            "observation_id": 7,
            "outcome": "success",
            "reason": "correct_password",
        })

    put_book, _ = make_scenario_session("put_book")
    put_book.receive_observation(observation(7))
    with pytest.raises(SessionError, match="invalid_game_over"):
        put_book.receive_game_over({
            "type": "game_over",
            "protocol_version": 4,
            "observation_id": 7,
            "outcome": "success",
            "reason": "key_picked_up",
        })

    greet_npc_meeting, _ = make_scenario_session("greet_npc_meeting")
    greet_npc_meeting.receive_observation(observation(7))
    with pytest.raises(SessionError, match="invalid_game_over"):
        greet_npc_meeting.receive_game_over({
            "type": "game_over",
            "protocol_version": 4,
            "observation_id": 7,
            "outcome": "success",
            "reason": "book_in_box",
        })


def test_successful_attach_starts_log_for_selected_scenario():
    logger = RecordingLogger()
    session = GameSession(Config(), trajectory_logger=logger)

    session.attach(lambda packet: True, "put_book")

    assert logger.events == [("start", "put_book")]


def test_logging_failure_rejects_attach_without_controller():
    logger = RecordingLogger(fail_start=True)
    session = GameSession(Config(), trajectory_logger=logger)

    with pytest.raises(SessionError, match="logging_failed"):
        session.attach(lambda packet: True, "find_key")

    assert session._send_packet is None
    assert session._scenario_id is None


@pytest.mark.parametrize(
    ("scenario_id", "outcome", "reason", "expected"),
    [
        ("find_contract", "success", "correct_password", "success"),
        ("find_key", "success", "key_picked_up", "success"),
        ("put_book", "success", "books_in_ceo_office", "success"),
        ("put_book", "failure", "wrong_book_pickup", "failure"),
        (
            "greet_npc_meeting",
            "success",
            "meeting_door_closed",
            "success",
        ),
        (
            "greet_npc_meeting",
            "failure",
            "wrong_npc_limit",
            "failure",
        ),
        (
            "garden_watering",
            "success",
            "garden_tasks_complete",
            "success",
        ),
        (
            "arrange_meeting_briefings",
            "success",
            "meeting_prepared",
            "success",
        ),
        (
            "loop_staircase_anomaly",
            "success",
            "correct_floor_selected",
            "success",
        ),
        ("find_contract", "failure", "wrong_password", "failure"),
        ("find_key", "failure", "max_requests", "failure"),
    ],
)
def test_game_over_finishes_log_without_later_tool_call(
    scenario_id,
    outcome,
    reason,
    expected,
):
    logger = RecordingLogger()
    session, _ = make_session(
        trajectory_logger=logger,
        scenario_id=scenario_id,
    )
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": outcome,
        "reason": reason,
    }

    session.receive_game_over(terminal)
    session.receive_game_over(terminal)

    assert logger.events == [
        ("start", scenario_id),
        ("finish", expected, reason),
    ]


def test_disconnect_finishes_attempt_once():
    logger = RecordingLogger()
    session, _ = make_session(trajectory_logger=logger)

    session.detach("connection_closed")
    session.detach("connection_closed")

    assert logger.events == [
        ("start", "find_contract"),
        ("finish", "stopped", "bridge_disconnected"),
    ]


def test_mcp_shutdown_closes_log():
    logger = RecordingLogger()
    session, _ = make_session(trajectory_logger=logger)

    session.detach("mcp_shutdown")

    assert logger.events == [
        ("start", "find_contract"),
        ("finish", "stopped", "mcp_shutdown"),
        ("close", None),
    ]


def test_escape_stop_finishes_log_as_stopped():
    logger = RecordingLogger()
    session, _ = make_session(trajectory_logger=logger)
    session.receive_observation(observation(7))

    session.receive_stop({
        "type": "stop",
        "protocol_version": 4,
        "observation_id": 7,
        "reason": "escape_stop",
        "results": [],
    })

    session.detach("connection_closed")

    assert logger.events == [
        ("start", "find_contract"),
        ("finish", "stopped", "escape_stop"),
    ]


def test_mcp_stop_ack_finishes_log_as_stopped():
    logger = RecordingLogger()
    session, _ = make_session(trajectory_logger=logger)
    session.receive_observation(observation(7))

    session.receive_stop_ack({
        "type": "stop_ack",
        "protocol_version": 4,
        "observation_id": 7,
        "results": [],
    })

    session.detach("connection_closed")

    assert logger.events == [
        ("start", "find_contract"),
        ("finish", "stopped", "mcp_stop"),
    ]


def test_attach_starts_attempt_observer_without_logger():
    observer = RecordingAttemptObserver()

    make_session(attempt_observer=observer)

    assert observer.events == [("start", "find_contract")]


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        ("success", "correct_password"),
        ("failure", "wrong_password"),
    ],
)
def test_game_over_finishes_attempt_observer_once(outcome, reason):
    observer = RecordingAttemptObserver()
    session, _ = make_session(attempt_observer=observer)
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": outcome,
        "reason": reason,
    }

    session.receive_game_over(terminal)
    session.receive_game_over(terminal)
    session.detach("connection_closed")

    assert observer.events == [
        ("start", "find_contract"),
        ("finish", outcome, reason),
    ]


@pytest.mark.parametrize(
    ("detach_reason", "status", "terminal_reason"),
    [
        ("connection_closed", "disconnected", "bridge_disconnected"),
        ("mcp_shutdown", "shutdown", "mcp_shutdown"),
    ],
)
def test_detach_finishes_attempt_observer_once(
    detach_reason,
    status,
    terminal_reason,
):
    observer = RecordingAttemptObserver()
    session, _ = make_session(attempt_observer=observer)

    session.detach(detach_reason)
    session.detach(detach_reason)

    assert observer.events == [
        ("start", "find_contract"),
        ("finish", status, terminal_reason),
    ]


def test_escape_stop_finishes_attempt_observer_once():
    observer = RecordingAttemptObserver()
    session, _ = make_session(attempt_observer=observer)
    session.receive_observation(observation(7))

    session.receive_stop({
        "type": "stop",
        "protocol_version": 4,
        "observation_id": 7,
        "reason": "escape_stop",
        "results": [],
    })
    session.detach("connection_closed")

    assert observer.events == [
        ("start", "find_contract"),
        ("finish", "stopped", "escape_stop"),
    ]


def test_mcp_stop_ack_finishes_attempt_observer_once():
    observer = RecordingAttemptObserver()
    session, _ = make_session(attempt_observer=observer)
    session.receive_observation(observation(7))

    session.receive_stop_ack({
        "type": "stop_ack",
        "protocol_version": 4,
        "observation_id": 7,
        "results": [],
    })
    session.detach("connection_closed")

    assert observer.events == [
        ("start", "find_contract"),
        ("finish", "stopped", "mcp_stop"),
    ]


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


def test_invalid_act_requests_are_counted_before_validation():
    session, sent = make_session(max_act_requests=10)
    session.receive_observation(observation(7))

    with pytest.raises(SessionError, match="stale_observation"):
        session.act(
            6,
            [{"type": "wait", "duration_ms": 50}],
            timeout=0.1,
        )
    with pytest.raises(SessionError, match="action type is not allowed"):
        session.act(
            7,
            [{"type": "not_an_action"}],
            timeout=0.1,
        )

    assert session.act_request_count == 2
    assert sent == []


def test_concurrent_act_request_is_counted_before_in_flight_validation():
    session, sent = make_session(max_act_requests=10)
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

    assert session.act_request_count == 2
    session.receive_action_results(7, wait_action_results())
    session.receive_observation(observation(8))
    thread.join()
    assert result_holder[0].status == "ready"


def test_successful_attach_resets_act_request_count():
    session, sent = make_session(max_act_requests=10)
    session.receive_observation(observation(7))
    with pytest.raises(SessionError, match="stale_observation"):
        session.act(
            6,
            [{"type": "wait", "duration_ms": 50}],
            timeout=0.1,
        )
    assert session.act_request_count == 1

    session.detach("connection_closed")
    session.attach(lambda packet: sent.append(packet) or True)

    assert session.act_request_count == 0


def test_reconnect_waits_for_first_observation_from_new_controller():
    session, sent = make_session(max_act_requests=10)
    session.receive_observation(observation(7))
    session.detach("connection_closed")

    session.attach(lambda packet: sent.append(packet) or True)

    with pytest.raises(SessionError, match="observation_timeout"):
        session.observe(timeout=0.01)
    session.receive_observation(observation(1))
    result = session.observe(timeout=0.1)
    assert result.status == "ready"
    assert result.observation["observation_id"] == 1


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
        "protocol_version": 4,
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


def test_act_waits_for_results_when_next_observation_arrives_first():
    session, sent = make_session()
    session.receive_observation(observation(7))
    result_holder = []
    thread = threading.Thread(
        target=lambda: result_holder.append(
            session.act(
                7,
                [{"type": "wait", "duration_ms": 50}],
                timeout=0.5,
            )
        )
    )
    thread.start()
    wait_until(lambda: len(sent) == 1)

    session.receive_observation(observation(8))
    assert thread.is_alive()
    session.receive_action_results(7, wait_action_results())
    thread.join()

    assert result_holder == [SessionResult(
        status="ready",
        observation=observation(8),
        action_results=wait_action_results(),
    )]


def test_act_reports_public_planar_movement_feedback():
    session, sent = make_session()
    before = observation(7)
    before["player"]["position"] = [1.0, 0.0, 2.0]
    session.receive_observation(before)
    actions = [{
        "type": "move",
        "forward": 0.25,
        "right": 0.0,
        "duration_ms": 50,
    }]
    result_holder = []

    thread = threading.Thread(
        target=lambda: result_holder.append(
            session.act(7, actions, timeout=0.5)
        )
    )
    thread.start()
    wait_until(lambda: len(sent) == 1)

    results = [{"status": "blocked", "type": "move"}]
    after = observation(8)
    after["player"]["position"] = [1.03, 0.0, 2.04]
    session.receive_action_results(7, results)
    session.receive_observation(after)
    thread.join()

    result = result_holder[0]
    assert result.movement_feedback == {
        "planar_delta_meters": [0.03, 0.04],
        "distance_moved_meters": 0.05,
        "blocked": True,
    }
    payload, _, _ = session.to_mcp_payload(result)
    assert payload["movement_feedback"] == result.movement_feedback


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
        "protocol_version": 4,
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
        "protocol_version": 4,
        "observation_id": 7,
        "reason": "mcp_stop",
    }]
    results = [{"status": "cancelled", "reason": "mcp_stop"}]
    session.receive_stop_ack({
        "type": "stop_ack",
        "protocol_version": 4,
        "observation_id": 7,
        "results": results,
    })
    thread.join()

    assert result_holder == [SessionResult(status="stopped", action_results=results)]
    assert session.stop() == result_holder[0]
    assert len(sent) == 1


def test_attach_after_mcp_stop_starts_next_attempt():
    session, sent = make_session()
    session.receive_observation(observation(7))
    results = [{"status": "cancelled", "reason": "mcp_stop"}]
    session.receive_stop_ack({
        "type": "stop_ack",
        "protocol_version": 4,
        "observation_id": 7,
        "results": results,
    })
    session.detach("bridge_closed")

    session.attach(lambda packet: sent.append(packet) or True)
    session.receive_observation(observation(1))

    result = session.observe(timeout=0.1)
    assert result.status == "ready"
    assert result.observation["observation_id"] == 1


def test_attach_after_game_over_starts_next_attempt():
    session, sent = make_session()
    session.receive_observation(observation(7))
    session.receive_game_over({
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "success",
        "reason": "correct_password",
    })
    session.detach("bridge_closed")

    session.attach(lambda packet: sent.append(packet) or True)
    session.receive_observation(observation(1))

    result = session.observe(timeout=0.1)
    assert result.status == "ready"
    assert result.observation["observation_id"] == 1


def test_action_timeout_enters_recovery_until_a_fresh_observation_arrives():
    session, sent = make_session()
    session.receive_observation(observation(7))
    actions = [{"type": "wait", "duration_ms": 50}]

    with pytest.raises(SessionError, match="action_timeout"):
        session.act(7, actions, timeout=0.01)

    assert sent[-1] == {
        "type": "recover_action",
        "protocol_version": 4,
        "observation_id": 7,
        "reason": "action_timeout",
    }
    assert session.act_request_count == 1
    with pytest.raises(SessionError, match="action_recovery_in_progress"):
        session.act(7, actions, timeout=0.01)

    result_holder = []
    thread = threading.Thread(
        target=lambda: result_holder.append(session.observe(timeout=0.5))
    )
    thread.start()
    time.sleep(0.02)
    assert thread.is_alive()
    session.receive_action_results(7, [{
        "status": "cancelled",
        "reason": "action_timeout",
    }])
    session.receive_observation(observation(8))
    thread.join()

    assert result_holder == [SessionResult(
        status="ready",
        observation=observation(8),
    )]


def test_recovery_observe_timeout_keeps_recovering_and_resends_request():
    session, sent = make_session()
    session.receive_observation(observation(7))

    with pytest.raises(SessionError, match="action_timeout"):
        session.act(7, [{"type": "wait", "duration_ms": 50}], timeout=0.01)

    with pytest.raises(SessionError, match="action_recovery_timeout"):
        session.observe(timeout=0.01)

    assert sent[-2:] == [sent[-1], sent[-1]]
    assert sent[-1]["type"] == "recover_action"


def test_threshold_act_finishes_then_requests_max_requests_game_over():
    session, sent = make_session(max_act_requests=1)
    session.receive_observation(observation(7))
    result_holder = []
    thread = threading.Thread(
        target=lambda: result_holder.append(
            _call_and_capture(
                session.act,
                7,
                [{"type": "wait", "duration_ms": 50}],
            )
        )
    )
    thread.start()
    wait_until(lambda: len(sent) == 1)
    session.receive_action_results(7, wait_action_results())
    session.receive_observation(observation(8))
    wait_until(lambda: len(sent) == 2)

    assert sent[1] == {
        "type": "end_game",
        "protocol_version": 4,
        "observation_id": 8,
        "outcome": "failure",
        "reason": "max_requests",
    }
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 8,
        "outcome": "failure",
        "reason": "max_requests",
    }
    session.receive_game_over(terminal)
    thread.join()

    assert result_holder == [SessionResult(
        status="game_over",
        action_results=wait_action_results(),
        game_over=terminal,
    )]


def test_invalid_threshold_act_error_is_superseded_by_terminal_result():
    session, sent = make_session(max_act_requests=1)
    session.receive_observation(observation(7))
    result_holder = []
    thread = threading.Thread(
        target=lambda: result_holder.append(
            _call_and_capture(
                session.act,
                6,
                [{"type": "wait", "duration_ms": 50}],
            )
        )
    )
    thread.start()
    wait_until(lambda: len(sent) == 1)

    assert sent == [{
        "type": "end_game",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "failure",
        "reason": "max_requests",
    }]
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "failure",
        "reason": "max_requests",
    }
    session.receive_game_over(terminal)
    thread.join()

    assert result_holder == [SessionResult(
        status="game_over",
        action_results=[],
        game_over=terminal,
    )]


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        ("success", "correct_password"),
        ("failure", "wrong_password"),
    ],
)
def test_password_terminal_on_threshold_act_takes_priority(outcome, reason):
    session, sent = make_session(max_act_requests=1)
    session.receive_observation(observation(7))
    result_holder = []
    thread = threading.Thread(
        target=lambda: result_holder.append(
            _call_and_capture(
                session.act,
                7,
                [{"type": "wait", "duration_ms": 50}],
            )
        )
    )
    thread.start()
    wait_until(lambda: len(sent) == 1)
    session.receive_action_results(7, wait_action_results())
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": outcome,
        "reason": reason,
    }
    session.receive_game_over(terminal)
    thread.join()

    assert result_holder[0].game_over == terminal
    assert len(sent) == 1


def test_request_after_threshold_is_rejected_while_terminal_is_pending():
    session, sent = make_session(max_act_requests=1)
    session.receive_observation(observation(7))
    result_holder = []
    thread = threading.Thread(
        target=lambda: result_holder.append(
            _call_and_capture(
                session.act,
                6,
                [{"type": "wait", "duration_ms": 50}],
            )
        )
    )
    thread.start()
    wait_until(lambda: len(sent) == 1)

    with pytest.raises(SessionError, match="request_limit_reached"):
        session.act(
            7,
            [{"type": "wait", "duration_ms": 50}],
            timeout=0.1,
        )

    session.receive_game_over({
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": 7,
        "outcome": "failure",
        "reason": "max_requests",
    })
    thread.join()
    assert len(sent) == 1


def test_threshold_terminal_wait_wakes_on_disconnect():
    session, sent = make_session(max_act_requests=1)
    session.receive_observation(observation(7))
    result_holder = []
    thread = threading.Thread(
        target=lambda: result_holder.append(
            _call_and_capture(
                session.act,
                6,
                [{"type": "wait", "duration_ms": 50}],
            )
        )
    )
    thread.start()
    wait_until(lambda: len(sent) == 1)
    session.detach("connection_closed")
    thread.join()

    assert isinstance(result_holder[0], SessionError)
    assert str(result_holder[0]) == "disconnected"


def test_threshold_terminal_timeout_keeps_later_actions_blocked():
    session, sent = make_session(max_act_requests=1)
    session.receive_observation(observation(7))

    with pytest.raises(SessionError, match="action_timeout"):
        session.act(
            6,
            [{"type": "wait", "duration_ms": 50}],
            timeout=0.01,
        )
    with pytest.raises(SessionError, match="request_limit_reached"):
        session.act(
            7,
            [{"type": "wait", "duration_ms": 50}],
            timeout=0.01,
        )

    assert len(sent) == 1


def test_game_over_rejects_invalid_max_requests_pair():
    session, _ = make_session()
    session.receive_observation(observation(7))

    with pytest.raises(SessionError, match="invalid_game_over"):
        session.receive_game_over({
            "type": "game_over",
            "protocol_version": 4,
            "observation_id": 7,
            "outcome": "success",
            "reason": "max_requests",
        })


def test_max_requests_game_over_allows_null_id_without_an_observation():
    session, _ = make_session()
    terminal = {
        "type": "game_over",
        "protocol_version": 4,
        "observation_id": None,
        "outcome": "failure",
        "reason": "max_requests",
    }

    session.receive_game_over(terminal)

    assert session.observe(timeout=0.1) == SessionResult(
        status="game_over",
        game_over=terminal,
    )


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
    result = SessionResult(
        status="ready",
        observation=observation(7, include_depth=True),
    )

    payload, image_bytes, depth_image_bytes = session.to_mcp_payload(result)

    assert "base64" not in payload["observation"]["image"]
    assert "base64" not in payload["observation"]["depth_image"]
    assert image_bytes.startswith(b"\xff\xd8\xff")
    assert depth_image_bytes.startswith(b"\x89PNG\r\n\x1a\n")


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
