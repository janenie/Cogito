class_name AIPlayController
extends Node

enum State { DISABLED, CONNECTING, READY, WAITING_FOR_DECISION, EXECUTING }

const PROTOCOL_VERSION: int = 1
const EXECUTOR_DEVICE_ID: int = AIPlayExecutor.SYNTHETIC_DEVICE_ID
const RECONNECT_DELAY_SECONDS: float = 1.0

@export var player: CogitoPlayer
@export var auto_start: bool = false
@export var host: String = "127.0.0.1"
@export_range(1, 65535, 1) var port: int = 8765
@export_range(0.0, 60.0, 0.05) var observation_interval: float = 0.25
@export var emergency_stop_key: Key = KEY_F12

var _state: State = State.DISABLED
var _pending_observation_id: int = -1
var _pending_context: Dictionary = {}
var _last_results: Array = []
var _emergency_stopped: bool = false
var _reconnect_remaining: float = -1.0

var _observer: Node
var _executor: Node
var _bridge: Node
var _observation_timer: Timer


func _ready() -> void:
	_observer = get_node("Observer")
	_executor = get_node("Executor")
	_bridge = get_node("Bridge")
	_observation_timer = get_node("ObservationTimer")
	if "player" in _observer:
		_observer.player = player
	_bridge.connected.connect(_on_bridge_connected)
	_bridge.disconnected.connect(_on_bridge_disconnected)
	_bridge.action_batch_received.connect(_on_action_batch_received)
	_bridge.remote_error.connect(_on_remote_error)
	_executor.batch_finished.connect(_on_batch_finished)
	_observation_timer.timeout.connect(_on_observation_timer_timeout)
	if auto_start:
		enable_ai()


func get_state() -> State:
	return _state


func enable_ai() -> void:
	_emergency_stopped = false
	_reconnect_remaining = -1.0
	if _state != State.DISABLED:
		_bridge.disconnect_from_server()
	_state = State.CONNECTING
	_pending_observation_id = -1
	var error: Error = _bridge.connect_to_server(host, port)
	if error != OK:
		_on_bridge_disconnected("connect_error:%d" % error)


func disable_ai(reason: String = "disabled") -> void:
	_state = State.DISABLED
	_pending_observation_id = -1
	_reconnect_remaining = -1.0
	if _observation_timer != null:
		_observation_timer.stop()
	if _executor != null:
		_executor.cancel_all(reason)
	if _bridge != null:
		_bridge.disconnect_from_server()


func _process(delta: float) -> void:
	if _state != State.CONNECTING or _emergency_stopped or _reconnect_remaining < 0.0:
		return
	_reconnect_remaining -= delta
	if _reconnect_remaining <= 0.0:
		_reconnect_remaining = -1.0
		var error: Error = _bridge.connect_to_server(host, port)
		if error != OK:
			_reconnect_remaining = RECONNECT_DELAY_SECONDS


func _input(event: InputEvent) -> void:
	if event.device == EXECUTOR_DEVICE_ID or event is InputEventAction:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == emergency_stop_key or event.physical_keycode == emergency_stop_key:
			_emergency_stopped = true
			disable_ai("emergency_stop")
			return
	if _state == State.DISABLED or not _is_human_control_event(event):
		return
	disable_ai("human_takeover")


func _on_bridge_connected() -> void:
	if _state != State.CONNECTING:
		return
	_reconnect_remaining = -1.0
	var hello: Dictionary = {
		"type": "hello",
		"protocol_version": PROTOCOL_VERSION,
		"bindings": _observer.get_bindings(),
		"data_dir": OS.get_user_data_dir(),
	}
	if _bridge.send_packet(hello) != OK:
		_pause_for_error("hello_send_failed")
		return
	_state = State.READY
	_capture_observation(_last_results)


func _capture_observation(results: Array) -> void:
	if _state != State.READY:
		return
	if player == null and _observer is AIPlayObserver:
		_pause_for_error("player_not_configured")
		return
	var observation: Dictionary = _observer.capture_observation(results)
	var observation_id: Variant = observation.get("observation_id")
	if typeof(observation_id) != TYPE_INT:
		_pause_for_error("invalid_observation")
		return
	observation["type"] = "observation"
	observation["protocol_version"] = PROTOCOL_VERSION
	_pending_observation_id = observation_id
	var interface: Dictionary = observation.get("interface", {})
	_pending_context = {
		"interface_open": interface.get("is_open", false),
		"available_interactions": _interaction_actions(interface.get("available_interactions", [])),
	}
	_state = State.WAITING_FOR_DECISION
	if _bridge.send_packet(observation) != OK:
		_pause_for_error("observation_send_failed")


func _on_action_batch_received(batch: Dictionary) -> void:
	if _state != State.WAITING_FOR_DECISION:
		_pause_for_error("unexpected_action_batch")
		return
	var observation_id: Variant = batch.get("observation_id")
	if typeof(observation_id) != TYPE_INT or observation_id != _pending_observation_id:
		_pause_for_error("stale_observation")
		return
	var actions: Variant = batch.get("actions")
	if not actions is Array:
		_pause_for_error("invalid_action_batch")
		return
	_pending_observation_id = -1
	_state = State.EXECUTING
	_executor.execute_batch(actions, _pending_context)


func _on_batch_finished(results: Array) -> void:
	if _state != State.EXECUTING:
		return
	_last_results = results.duplicate(true)
	_state = State.READY
	_observation_timer.start(observation_interval)


func _on_observation_timer_timeout() -> void:
	_capture_observation(_last_results)


func _on_bridge_disconnected(reason: String) -> void:
	if _state == State.DISABLED:
		return
	_state = State.CONNECTING
	_pending_observation_id = -1
	_observation_timer.stop()
	_executor.cancel_all(reason)
	if not _emergency_stopped:
		_reconnect_remaining = RECONNECT_DELAY_SECONDS


func _on_remote_error(error: Dictionary) -> void:
	_pause_for_error("remote_error:%s" % str(error.get("code", "unknown")))


func _pause_for_error(reason: String) -> void:
	disable_ai(reason)


func _interaction_actions(interactions: Variant) -> Array[String]:
	var actions: Array[String] = []
	if interactions is Array:
		for interaction: Variant in interactions:
			if interaction is Dictionary and interaction.get("action") is String:
				actions.append(interaction["action"])
	return actions


func _is_human_control_event(event: InputEvent) -> bool:
	if event is InputEventMouseMotion:
		return event.relative != Vector2.ZERO
	if event is InputEventMouseButton:
		return event.pressed
	if event is InputEventJoypadButton:
		return event.pressed
	if event is InputEventJoypadMotion:
		return absf(event.axis_value) > 0.1
	if event is InputEventKey:
		return event.pressed and not event.echo
	return false
