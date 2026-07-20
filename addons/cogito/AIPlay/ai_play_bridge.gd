class_name AIPlayBridge
extends Node

signal connected
signal disconnected(reason: String)
signal action_batch_received(batch: Dictionary)
signal remote_error(error: Dictionary)

const PROTOCOL_VERSION: int = 1
const MAX_PACKET_SIZE: int = 4 * 1024 * 1024

var _socket: WebSocketPeer
var _reported_open: bool = false


func _exit_tree() -> void:
	disconnect_from_server()


func connect_to_server(host: String, port: int) -> Error:
	if not _is_loopback_host(host):
		return ERR_INVALID_PARAMETER
	disconnect_from_server()
	_socket = WebSocketPeer.new()
	_reported_open = false
	var error: Error = _socket.connect_to_url("ws://%s:%d" % [host, port])
	if error != OK:
		_socket = null
	return error


func _is_loopback_host(host: String) -> bool:
	return host == "127.0.0.1"


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
	if json.parse(raw_packet) != OK:
		_protocol_error("invalid_packet", "packet must be valid JSON")
		return
	var parsed: Variant = json.data
	if not parsed is Dictionary:
		_protocol_error("invalid_packet", "packet must be a JSON object")
		return
	var packet: Dictionary = parsed
	if not _is_protocol_version_one(packet.get("protocol_version")):
		_protocol_error("unsupported_protocol", "protocol version must be 1")
		return
	match packet.get("type"):
		"hello":
			pass
		"action_batch":
			action_batch_received.emit(packet)
		"error":
			remote_error.emit(packet)
		_:
			_protocol_error("unexpected_packet", "unexpected packet type")


func _is_protocol_version_one(value: Variant) -> bool:
	if typeof(value) == TYPE_INT:
		return value == PROTOCOL_VERSION
	if typeof(value) == TYPE_FLOAT:
		return is_finite(value) and value == float(PROTOCOL_VERSION)
	return false


func _protocol_error(code: String, message: String) -> void:
	remote_error.emit({
		"type": "error",
		"protocol_version": PROTOCOL_VERSION,
		"code": code,
		"message": message,
	})
