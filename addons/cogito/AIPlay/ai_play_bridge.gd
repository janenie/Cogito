class_name AIPlayBridge
extends Node

signal connected
signal disconnected(reason: String)
signal action_batch_received(batch: Dictionary)
signal stop_request_received(request: Dictionary)
signal end_game_received(request: Dictionary)
signal remote_error(error: Dictionary)

const PROTOCOL_VERSION: int = 3
const MAX_PACKET_SIZE: int = 8 * 1024 * 1024
const MAX_SAFE_JSON_INTEGER: int = 9_007_199_254_740_991

var _socket: WebSocketPeer
var _reported_open: bool = false


func _exit_tree() -> void:
	disconnect_from_server()


func connect_to_server(host: String, port: int) -> Error:
	if not _is_loopback_host(host):
		return ERR_INVALID_PARAMETER
	disconnect_from_server()
	_socket = WebSocketPeer.new()
	_configure_socket_buffers(_socket)
	_reported_open = false
	var error: Error = _socket.connect_to_url("ws://%s:%d" % [host, port])
	if error != OK:
		_socket = null
	return error


func _is_loopback_host(host: String) -> bool:
	return host == "127.0.0.1"


func _configure_socket_buffers(socket: WebSocketPeer) -> void:
	socket.inbound_buffer_size = MAX_PACKET_SIZE
	socket.outbound_buffer_size = MAX_PACKET_SIZE


func send_packet(packet: Dictionary) -> Error:
	if _socket == null or _socket.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return ERR_UNCONFIGURED
	return _socket.send_text(JSON.stringify(packet))


func disconnect_from_server() -> void:
	if _socket != null:
		var state: WebSocketPeer.State = _socket.get_ready_state()
		if state == WebSocketPeer.STATE_CONNECTING or state == WebSocketPeer.STATE_OPEN:
			_socket.close(1000, "client_disconnect")
	_socket = null
	_reported_open = false


func _process(_delta: float) -> void:
	if _socket == null:
		return
	_socket.poll()
	var state: WebSocketPeer.State = _socket.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		if not _reported_open:
			_reported_open = true
			connected.emit()
		while _socket != null and _socket.get_available_packet_count() > 0:
			_receive_packet(_socket.get_packet())
	elif state == WebSocketPeer.STATE_CLOSED:
		var reason: String = _socket.get_close_reason()
		if reason.is_empty():
			reason = "connection_closed"
		_socket = null
		_reported_open = false
		disconnected.emit(reason)


func _receive_packet(bytes: PackedByteArray) -> void:
	if bytes.size() > MAX_PACKET_SIZE:
		_protocol_error("packet_too_large", "packet exceeds maximum size")
		return
	if _socket == null or not _socket.was_string_packet():
		_protocol_error("invalid_packet", "packet must be JSON text")
		return
	_handle_text_packet(bytes.get_string_from_utf8())


func _handle_text_packet(raw_packet: String) -> void:
	var json := JSON.new()
	if json.parse(raw_packet) != OK or not json.data is Dictionary:
		_protocol_error("invalid_packet", "packet must be valid JSON")
		return
	var packet: Dictionary = json.data
	if not _is_current_protocol_version(packet.get("protocol_version")):
		_protocol_error("unsupported_protocol", "protocol version must be 3")
		return
	packet["protocol_version"] = PROTOCOL_VERSION
	var normalized_observation_id: Dictionary = _normalize_observation_id(
		packet.get("observation_id")
	)
	if normalized_observation_id["valid"]:
		packet["observation_id"] = normalized_observation_id["value"]
	match packet.get("type"):
		"hello":
			pass
		"action_batch":
			action_batch_received.emit(packet)
		"stop_request":
			if _has_exact_keys(
				packet,
				["type", "protocol_version", "observation_id", "reason"],
			) and packet["reason"] == "mcp_stop":
				stop_request_received.emit(packet)
			else:
				_protocol_error("invalid_stop_request", "invalid stop request")
		"end_game":
			if (
				_has_exact_keys(
					packet,
					[
						"type",
						"protocol_version",
						"observation_id",
						"outcome",
						"reason",
					],
				)
				and (
					normalized_observation_id["valid"]
					or packet["observation_id"] == null
				)
				and packet["outcome"] == "failure"
				and packet["reason"] == "max_requests"
			):
				end_game_received.emit(packet)
			else:
				_protocol_error("invalid_end_game", "invalid end-game request")
		"error":
			remote_error.emit(packet)
		_:
			_protocol_error("unexpected_packet", "unexpected packet type")


func _has_exact_keys(packet: Dictionary, expected: Array[String]) -> bool:
	if packet.size() != expected.size():
		return false
	for key: String in expected:
		if not packet.has(key):
			return false
	return true


func _is_current_protocol_version(value: Variant) -> bool:
	return (
		(typeof(value) == TYPE_INT or typeof(value) == TYPE_FLOAT)
		and value == PROTOCOL_VERSION
	)


func _normalize_observation_id(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_INT:
		if value >= 0 and value <= MAX_SAFE_JSON_INTEGER:
			return {"valid": true, "value": value}
	elif typeof(value) == TYPE_FLOAT:
		if (
			is_finite(value)
			and value >= 0.0
			and value <= float(MAX_SAFE_JSON_INTEGER)
			and value == floor(value)
		):
			return {"valid": true, "value": int(value)}
	return {"valid": false, "value": null}


func _protocol_error(code: String, message: String) -> void:
	remote_error.emit({
		"type": "error",
		"protocol_version": PROTOCOL_VERSION,
		"code": code,
		"message": message,
	})
