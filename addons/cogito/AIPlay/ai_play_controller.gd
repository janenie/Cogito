class_name AIPlayController
extends Node

enum State { DISABLED, CONNECTING, READY, WAITING_FOR_DECISION, EXECUTING }

const PROTOCOL_VERSION: int = 1
const EXECUTOR_DEVICE_ID: int = AIPlayExecutor.SYNTHETIC_DEVICE_ID
const RECONNECT_DELAY_SECONDS: float = 1.0
const MAX_SAFE_JSON_INTEGER: int = 9_007_199_254_740_991

@export var player: CogitoPlayer
@export var auto_start: bool = false
@export var host: String = "127.0.0.1"
@export_range(1, 65535, 1) var port: int = 8765
@export_range(0.0, 60.0, 0.05) var observation_interval: float = 0.25
@export var stop_key: Key = KEY_ESCAPE

var _state: State = State.DISABLED
var _pending_observation_id: int = -1
var _executing_observation_id: int = -1
var _pending_context: Dictionary = {}
var _last_results: Array = []
var _reconnect_remaining: float = -1.0
var _capture_generation: int = 0
var _stop_delivery_pending: bool = false
var _active_request_count: int = 0
var _active_request_limit: int = 0
var _game_finished: bool = false

var _observer: Node
var _executor: Node
var _interaction_probe: Node
var _terminal_monitor: Node
var _bridge: Node
var _observation_timer: Timer


func _ready() -> void:
	_observer = get_node("Observer")
	_executor = get_node("Executor")
	_interaction_probe = get_node("InteractionProbe")
	_terminal_monitor = get_node_or_null("TerminalMonitor")
	_bridge = get_node("Bridge")
	_observation_timer = get_node("ObservationTimer")
	if "player" in _observer:
		_observer.player = player
	if "player" in _executor:
		_executor.player = player
	if "player" in _interaction_probe:
		_interaction_probe.player = player
	if "interaction_provider" in _interaction_probe:
		_interaction_probe.interaction_provider = Callable(
			_observer,
			"get_available_interactions",
		)
	if "interaction_probe" in _executor:
		_executor.interaction_probe = _interaction_probe
	_bridge.connected.connect(_on_bridge_connected)
	_bridge.disconnected.connect(_on_bridge_disconnected)
	_bridge.action_batch_received.connect(_on_action_batch_received)
	_bridge.game_over_received.connect(_on_remote_game_over)
	_bridge.remote_error.connect(_on_remote_error)
	_executor.batch_finished.connect(_on_batch_finished)
	if _terminal_monitor != null and _terminal_monitor.has_signal("game_finished"):
		_terminal_monitor.game_finished.connect(_on_game_finished)
	_observation_timer.timeout.connect(_on_observation_timer_timeout)
	print("AI_PLAY controller ready; user_args=%s auto_start=%s" % [OS.get_cmdline_user_args(), auto_start])
	if auto_start or _should_enable_for_user_args(OS.get_cmdline_user_args()):
		enable_ai()


func _should_enable_for_user_args(user_args: Array) -> bool:
	return "--ai-play" in user_args


func get_state() -> State:
	return _state


func enable_ai() -> void:
	print("AI_PLAY enabling; target=ws://%s:%d" % [host, port])
	_stop_delivery_pending = false
	_game_finished = false
	_active_request_count = 0
	_active_request_limit = 0
	_reconnect_remaining = -1.0
	if _state != State.DISABLED:
		_bridge.disconnect_from_server()
	_state = State.CONNECTING
	_pending_observation_id = -1
	_executing_observation_id = -1
	var error: Error = _bridge.connect_to_server(host, port)
	if error != OK:
		_on_bridge_disconnected("connect_error:%d" % error)


func disable_ai(reason: String = "disabled", disconnect_bridge: bool = true) -> void:
	print("AI_PLAY disabled; reason=%s" % reason)
	_capture_generation += 1
	_state = State.DISABLED
	_pending_observation_id = -1
	_executing_observation_id = -1
	_reconnect_remaining = -1.0
	if _observation_timer != null:
		_observation_timer.stop()
	if _executor != null:
		_executor.cancel_all(reason)
	if _bridge != null and disconnect_bridge:
		_bridge.disconnect_from_server()


func _process(delta: float) -> void:
	if _state != State.CONNECTING or _reconnect_remaining < 0.0:
		return
	_reconnect_remaining -= delta
	if _reconnect_remaining <= 0.0:
		_reconnect_remaining = -1.0
		var error: Error = _bridge.connect_to_server(host, port)
		if error != OK:
			_reconnect_remaining = RECONNECT_DELAY_SECONDS


func _input(event: InputEvent) -> void:
	if event.device == EXECUTOR_DEVICE_ID or _state == State.DISABLED:
		return
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	if event.keycode != stop_key and event.physical_keycode != stop_key:
		return
	var stop_error: Error = _send_stop_packet("escape_stop")
	_stop_delivery_pending = stop_error == OK
	disable_ai("escape_stop", not _stop_delivery_pending)


func _send_stop_packet(reason: String) -> Error:
	var observation_id: Variant = null
	var results: Array = []
	if _executing_observation_id >= 0:
		observation_id = _executing_observation_id
		results = [{"status": "cancelled", "reason": reason}]
	elif _pending_observation_id >= 0:
		observation_id = _pending_observation_id
	return _bridge.send_packet({
		"type": "stop",
		"protocol_version": PROTOCOL_VERSION,
		"observation_id": observation_id,
		"reason": reason,
		"results": results,
	})


func _on_bridge_connected() -> void:
	if _state != State.CONNECTING:
		return
	print("AI_PLAY WebSocket connected")
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
	if is_queued_for_deletion() or not is_inside_tree() or _state != State.READY:
		return
	if player == null and _observer is AIPlayObserver:
		_pause_for_error("player_not_configured")
		return
	var observation: Dictionary = _observer.capture_observation(results)
	var observation_id: Dictionary = _parse_observation_id(observation.get("observation_id"))
	if not observation_id["valid"]:
		_pause_for_error("invalid_observation")
		return
	observation["type"] = "observation"
	observation["protocol_version"] = PROTOCOL_VERSION
	print("AI_PLAY sending observation=%d" % observation_id["value"])
	_pending_observation_id = observation_id["value"]
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
		if _state == State.DISABLED and _stop_delivery_pending:
			return
		_pause_for_error("unexpected_action_batch")
		return
	print("AI_PLAY received action batch for observation=%s" % str(batch.get("observation_id")))
	var observation_id: Dictionary = _parse_observation_id(batch.get("observation_id"))
	if not observation_id["valid"] or observation_id["value"] != _pending_observation_id:
		_pause_for_error("stale_observation")
		return
	var actions: Variant = batch.get("actions")
	if not actions is Array:
		_pause_for_error("invalid_action_batch")
		return
	var request_count: Dictionary = _parse_positive_integer(batch.get("request_count"))
	var request_limit: Dictionary = _parse_positive_integer(batch.get("request_limit"))
	if (
		not request_count["valid"]
		or not request_limit["valid"]
		or request_count["value"] > request_limit["value"]
	):
		_pause_for_error("invalid_request_metadata")
		return
	_active_request_count = request_count["value"]
	_active_request_limit = request_limit["value"]
	_executing_observation_id = observation_id["value"]
	_pending_observation_id = -1
	_state = State.EXECUTING
	_executor.execute_batch(actions, _pending_context)


func _on_batch_finished(results: Array) -> void:
	if _state != State.EXECUTING:
		return
	var completed_observation_id: int = _executing_observation_id
	_executing_observation_id = -1
	if _bridge.send_packet({
		"type": "action_results",
		"protocol_version": PROTOCOL_VERSION,
		"observation_id": completed_observation_id,
		"results": results.duplicate(true),
	}) != OK:
		_pause_for_error("action_results_send_failed")
		return
	_last_results = results.duplicate(true)
	if _active_request_count >= _active_request_limit:
		_finish_game(
			"failure",
			"max_requests",
			completed_observation_id,
		)
		return
	if _contains_stopped_result(results):
		_capture_generation += 1
		_state = State.DISABLED
		_pending_observation_id = -1
		_reconnect_remaining = -1.0
		_observation_timer.stop()
		_bridge.disconnect_from_server()
		return
	_state = State.READY
	if _ends_with_immediate_recapture(results):
		var generation: int = _capture_generation
		call_deferred("_capture_observation_if_current", generation, _last_results)
	else:
		_observation_timer.start(observation_interval)


func _capture_observation_if_current(generation: int, results: Array) -> void:
	if (
		generation != _capture_generation
		or _state != State.READY
		or is_queued_for_deletion()
		or not is_inside_tree()
	):
		return
	_capture_observation(results)


func _exit_tree() -> void:
	_capture_generation += 1


func _on_observation_timer_timeout() -> void:
	_capture_observation(_last_results)


func _on_bridge_disconnected(reason: String) -> void:
	if _state == State.DISABLED:
		_stop_delivery_pending = false
		return
	print("AI_PLAY WebSocket disconnected; reason=%s" % reason)
	_capture_generation += 1
	_state = State.CONNECTING
	_pending_observation_id = -1
	_executing_observation_id = -1
	_observation_timer.stop()
	_executor.cancel_all(reason)
	_reconnect_remaining = RECONNECT_DELAY_SECONDS


func _on_remote_error(error: Dictionary) -> void:
	var code: String = str(error.get("code", "unknown"))
	print("AI_PLAY remote error; code=%s" % code)
	if code == "decision_failed" and _state == State.WAITING_FOR_DECISION:
		_pending_observation_id = -1
		_last_results = [{"status": "error", "error": "decision_failed"}]
		_state = State.READY
		_observation_timer.start(maxf(observation_interval, 1.0))
		return
	_pause_for_error("remote_error:%s" % code)


func _on_remote_game_over(result: Dictionary) -> void:
	if _state != State.WAITING_FOR_DECISION or _game_finished:
		_pause_for_error("unexpected_game_over")
		return
	if result.keys().size() != 6:
		_pause_for_error("invalid_game_over")
		return
	for field: String in [
		"type",
		"protocol_version",
		"observation_id",
		"outcome",
		"reason",
		"request_count",
	]:
		if not result.has(field):
			_pause_for_error("invalid_game_over")
			return
	var observation_id: Dictionary = _parse_observation_id(result.get("observation_id"))
	var request_count: Dictionary = _parse_positive_integer(result.get("request_count"))
	if (
		not observation_id["valid"]
		or observation_id["value"] != _pending_observation_id
		or not request_count["valid"]
		or result.get("outcome") != "failure"
		or result.get("reason") != "max_requests"
	):
		_pause_for_error("invalid_game_over")
		return
	_game_finished = true
	_active_request_count = request_count["value"]
	print(
		"AI_PLAY game over; outcome=failure reason=max_requests requests=%d"
		% _active_request_count
	)
	disable_ai("game_over:max_requests")
	_show_game_over_result("failure", "max_requests")


func _pause_for_error(reason: String) -> void:
	disable_ai(reason)


func _on_game_finished(outcome: String, reason: String) -> void:
	var observation_id: int = _executing_observation_id
	if observation_id < 0:
		observation_id = _pending_observation_id
	_finish_game(outcome, reason, observation_id)


func _finish_game(outcome: String, reason: String, observation_id: int) -> void:
	if _game_finished:
		return
	if (
		outcome not in ["success", "failure"]
		or reason not in ["correct_password", "wrong_password", "max_requests"]
	):
		_pause_for_error("invalid_game_outcome")
		return
	_game_finished = true
	print(
		"AI_PLAY game over; outcome=%s reason=%s requests=%d"
		% [outcome, reason, _active_request_count]
	)
	var send_error: Error = _bridge.send_packet({
		"type": "game_over",
		"protocol_version": PROTOCOL_VERSION,
		"observation_id": observation_id,
		"outcome": outcome,
		"reason": reason,
		"request_count": _active_request_count,
	})
	disable_ai("game_over:%s" % reason, send_error != OK)
	_show_game_over_result(outcome, reason)


func _show_game_over_result(outcome: String, reason: String) -> void:
	if _terminal_monitor != null and _terminal_monitor.has_method("show_result"):
		_terminal_monitor.show_result(outcome, reason)


func _interaction_actions(interactions: Variant) -> Array[String]:
	var actions: Array[String] = []
	if interactions is Array:
		for interaction: Variant in interactions:
			if interaction is Dictionary and interaction.get("action") is String:
				actions.append(interaction["action"])
	return actions


func _contains_stopped_result(results: Array) -> bool:
	for result: Variant in results:
		if result is Dictionary and result.get("status") == "stopped":
			return true
	return false


func _ends_with_immediate_recapture(results: Array) -> bool:
	if results.is_empty() or not results[-1] is Dictionary:
		return false
	var final_result: Dictionary = results[-1]
	if final_result.get("status") == "blocked":
		return final_result.get("type") in ["move", "sprint"]
	return (
		final_result.get("status") == "completed"
		and final_result.get("type") in [
			"interact",
			"enter_digits",
			"close_ui",
			"probe_interaction",
		]
	)


func _parse_observation_id(value: Variant) -> Dictionary:
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
	return {"valid": false, "value": -1}


func _parse_positive_integer(value: Variant) -> Dictionary:
	var parsed: Dictionary = _parse_observation_id(value)
	if not parsed["valid"] or parsed["value"] < 1:
		return {"valid": false, "value": -1}
	return parsed
