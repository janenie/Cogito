from __future__ import annotations

import json
import threading

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve as websocket_serve

from .game_session import GameSession, SessionError


PROTOCOL_VERSION = 2
MAX_PACKET_SIZE = 4 * 1024 * 1024
HELLO_TIMEOUT_SECONDS = 5
OBSERVATION_FIELDS = {
    "observation_id",
    "captured_at_ms",
    "image",
    "player",
    "interface",
    "bindings",
    "last_action_results",
}


class BridgeHandle:
    def __init__(self, server, thread):
        self._server = server
        self._thread = thread
        self._closed = False
        self._lock = threading.Lock()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._server.shutdown()
        self._thread.join(timeout=2.0)


def _error(code, observation_id=None):
    return {
        "type": "error",
        "protocol_version": PROTOCOL_VERSION,
        "observation_id": observation_id,
        "code": code,
        "message": code,
    }


def _send(connection, packet):
    connection.send(json.dumps(packet, ensure_ascii=False, separators=(",", ":")))


def _safe_send(connection, packet):
    try:
        _send(connection, packet)
    except (ConnectionClosed, OSError):
        return False
    return True


def start(config, session: GameSession) -> BridgeHandle:
    config.validate()
    ready = threading.Event()
    holder = {}

    def run():
        try:
            with websocket_serve(
                lambda connection: _handler(connection, config, session),
                config.ws_host,
                config.ws_port,
                max_size=MAX_PACKET_SIZE,
                compression=None,
            ) as server:
                holder["server"] = server
                ready.set()
                server.serve_forever()
        except BaseException as error:  # surfaced to the starter thread
            holder["error"] = error
            ready.set()

    thread = threading.Thread(
        target=run,
        name="ai-play-godot-bridge",
        daemon=True,
    )
    thread.start()
    if not ready.wait(timeout=2.0):
        raise RuntimeError("Godot bridge did not start")
    if "error" in holder:
        raise RuntimeError("Godot bridge did not start") from holder["error"]
    return BridgeHandle(holder["server"], thread)


def _handler(connection, config, session):
    del config
    hello = _receive_hello(connection)
    if hello is None:
        return

    try:
        session.attach(lambda packet: _safe_send(connection, packet))
    except SessionError as error:
        _safe_send(connection, _error(str(error)))
        return

    try:
        _exclusive_handler(connection, session)
    finally:
        session.detach("connection_closed")


def _receive_hello(connection):
    try:
        raw_packet = connection.recv(timeout=HELLO_TIMEOUT_SECONDS)
    except ConnectionClosed:
        return None
    except TimeoutError:
        _safe_send(connection, _error("hello_timeout"))
        return None

    packet = _decode_packet(raw_packet)
    if packet is None:
        _safe_send(connection, _error("invalid_packet"))
        return None
    if type(packet.get("protocol_version")) is not int or packet.get(
        "protocol_version"
    ) != PROTOCOL_VERSION:
        _safe_send(connection, _error("unsupported_protocol"))
        return None
    if packet.get("type") != "hello":
        _safe_send(connection, _error("hello_required"))
        return None
    if set(packet) != {"type", "protocol_version"}:
        _safe_send(connection, _error("invalid_hello"))
        return None
    return packet


def _exclusive_handler(connection, session):
    if not _safe_send(
        connection,
        {"type": "hello", "protocol_version": PROTOCOL_VERSION},
    ):
        return

    try:
        for raw_packet in connection:
            packet = _decode_packet(raw_packet)
            if packet is None:
                if not _safe_send(connection, _error("invalid_packet")):
                    return
                continue

            observation_id = packet.get("observation_id")
            if (
                type(packet.get("protocol_version")) is not int
                or packet.get("protocol_version") != PROTOCOL_VERSION
            ):
                if not _safe_send(
                    connection,
                    _error("unsupported_protocol", observation_id),
                ):
                    return
                continue

            packet_type = packet.get("type")
            try:
                if packet_type == "observation":
                    if set(packet) != OBSERVATION_FIELDS | {
                        "type",
                        "protocol_version",
                    }:
                        raise SessionError("invalid_observation")
                    session.receive_observation({
                        key: value
                        for key, value in packet.items()
                        if key not in {"type", "protocol_version"}
                    })
                elif packet_type == "action_results":
                    if set(packet) != {
                        "type",
                        "protocol_version",
                        "observation_id",
                        "results",
                    }:
                        raise SessionError("invalid_action_results")
                    session.receive_action_results(
                        packet["observation_id"],
                        packet["results"],
                    )
                elif packet_type == "stop":
                    if set(packet) != {
                        "type",
                        "protocol_version",
                        "observation_id",
                        "reason",
                        "results",
                    }:
                        raise SessionError("invalid_stop")
                    session.receive_stop(packet)
                    return
                elif packet_type == "stop_ack":
                    session.receive_stop_ack(packet)
                    return
                elif packet_type == "game_over":
                    session.receive_game_over(packet)
                    return
                else:
                    raise SessionError("unexpected_packet")
            except SessionError as error:
                if not _safe_send(
                    connection,
                    _error(str(error), observation_id),
                ):
                    return
    except ConnectionClosed:
        return


def _decode_packet(raw_packet):
    if not isinstance(raw_packet, str):
        return None
    try:
        packet = json.loads(raw_packet)
    except (UnicodeError, json.JSONDecodeError):
        return None
    return packet if isinstance(packet, dict) else None
