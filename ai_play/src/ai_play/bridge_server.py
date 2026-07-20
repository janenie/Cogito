from __future__ import annotations

import json
from pathlib import Path
import threading

from websockets.sync.server import serve as websocket_serve


PROTOCOL_VERSION = 1
MAX_PACKET_SIZE = 4 * 1024 * 1024


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


def _handler(connection, config, agent_loop, session_lock):
    if not session_lock.acquire(blocking=False):
        _send(connection, _error("controller_busy"))
        return
    try:
        _exclusive_handler(connection, config, agent_loop)
    finally:
        session_lock.release()


def _exclusive_handler(connection, config, agent_loop):
    greeted = False
    for raw_packet in connection:
        try:
            if isinstance(raw_packet, bytes):
                raise ValueError
            packet = json.loads(raw_packet)
            if not isinstance(packet, dict):
                raise ValueError
        except (UnicodeError, json.JSONDecodeError, ValueError):
            _send(connection, _error("invalid_packet"))
            continue

        observation_id = packet.get("observation_id")
        protocol_version = packet.get("protocol_version")
        if type(protocol_version) is not int or protocol_version != PROTOCOL_VERSION:
            _send(connection, _error("unsupported_protocol", observation_id))
            continue

        packet_type = packet.get("type")
        if not greeted:
            if packet_type != "hello":
                _send(connection, _error("hello_required", observation_id))
                continue
            hello_data_dir = packet.get("data_dir")
            if config.data_dir is None and (
                not isinstance(hello_data_dir, str) or not hello_data_dir
            ):
                _send(connection, _error("invalid_hello"))
                continue
            data_dir = (config.data_dir or Path(hello_data_dir)).expanduser().resolve()
            memory_dir = Path(data_dir) / "ai_play"
            memory_dir.mkdir(parents=True, exist_ok=True)
            agent_loop.configure_memory(memory_dir / "memory.json")
            greeted = True
            _send(
                connection,
                {"type": "hello", "protocol_version": PROTOCOL_VERSION},
            )
        elif packet_type == "observation":
            _send(connection, agent_loop.handle_observation(packet))
        elif packet_type == "stop":
            return
        else:
            _send(connection, _error("unexpected_packet", observation_id))


def serve(config, agent_loop):
    config.validate()
    session_lock = threading.Lock()
    handler = lambda connection: _handler(connection, config, agent_loop, session_lock)
    with websocket_serve(
        handler,
        config.ws_host,
        config.ws_port,
        max_size=MAX_PACKET_SIZE,
        compression=None,
    ) as server:
        server.serve_forever()
