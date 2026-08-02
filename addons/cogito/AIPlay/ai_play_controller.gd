class_name AIPlayController
extends Node

signal supervised_exit_requested(exit_code: int)

enum State { DISABLED, CONNECTING, READY, WAITING_FOR_DECISION, EXECUTING }

const PROTOCOL_VERSION: int = 4
const EXECUTOR_DEVICE_ID: int = AIPlayExecutor.SYNTHETIC_DEVICE_ID
const RECONNECT_DELAY_SECONDS: float = 1.0
const MAX_SAFE_JSON_INTEGER: int = 9_007_199_254_740_991
const DEFAULT_SCENARIO_ID: String = "find_contract"
const SCENARIO_ARG_PREFIX: String = "--ai-play-scenario="
const EXIT_ON_GAME_OVER_ARG: String = "--ai-play-exit-on-game-over"
const GAME_OVER_ACK_TIMEOUT_SECONDS: float = 1.0
const FIND_KEY_ACT_REQUEST_LIMITS: Array[int] = [50, 100]
const SCENARIO_TERMINAL_RESULTS := {
	"find_contract": [
		["success", "correct_password"],
		["failure", "wrong_password"],
		["failure", "max_requests"],
	],
	"find_key": [
		["success", "key_picked_up"],
		["failure", "max_requests"],
	],
	"put_book": [
		["success", "books_in_ceo_office"],
		["failure", "wrong_book_pickup"],
		["failure", "max_requests"],
	],
	"greet_npc_meeting": [
		["success", "meeting_door_closed"],
		["failure", "max_requests"],
	],
	"daily_routine_cleanup": [
		["success", "cleanup_complete"],
		["failure", "cleanup_incomplete"],
		["failure", "max_requests"],
	],
	"garden_watering": [
		["success", "garden_tasks_complete"],
		["failure", "garden_task_failed"],
		["failure", "max_requests"],
	],
	"repair_lighting_circuit": [
		["success", "circuit_repaired"],
		["failure", "wrong_breaker"],
		["failure", "incorrect_circuit_configuration"],
		["failure", "max_requests"],
	],
	"arrange_meeting_briefings": [
		["success", "meeting_prepared"],
		["failure", "incorrect_seating_assignment"],
		["failure", "max_requests"],
	],
	"conveyor_profit": [
		["success", "efficiency_target_reached"],
		["failure", "efficiency_below_target"],
		["failure", "max_requests"],
	],
}

@export var player: Node3D
@export var auto_start: bool = false
@export var host: String = "127.0.0.1"
@export_range(1, 65535, 1) var port: int = 8765
@export_range(0.0, 60.0, 0.05) var observation_interval: float = 0.25
@export var stop_key: Key = KEY_ESCAPE

var _state: State = State.DISABLED
var _pending_observation_id: int = -1
var _executing_observation_id: int = -1
var _last_completed_observation_id: int = -1
var _recovering_observation_id: int = -1
var _pending_context: Dictionary = {}
var _last_results: Array = []
var _reconnect_remaining: float = -1.0
var _capture_generation: int = 0
var _stop_delivery_pending: bool = false
var _game_finished: bool = false
var _active_scenario_id: String = ""
var _exit_on_game_over: bool = false
var _render_frame_wait_timeout_msec: int = 1000
var _pending_game_over_ack_id: Variant = null
var _pending_game_over_outcome: String = ""
var _game_over_ack_generation: int = 0

var _observer: Node
var _executor: Node
var _interaction_probe: Node
var _terminal_monitor: Node
var _bridge: Node
var _observation_timer: Timer


func _ready() -> void:
	var user_args: Array = OS.get_cmdline_user_args()
	_active_scenario_id = get_requested_scenario_id(user_args)
	_exit_on_game_over = _should_exit_on_game_over_for_user_args(user_args)
	_observer = get_node("Observer")
	_executor = get_node("Executor")
	_interaction_probe = get_node("InteractionProbe")
	_terminal_monitor = _find_scenario_monitor(_active_scenario_id)
	_bridge = get_node("Bridge")
	_observation_timer = get_node("ObservationTimer")
	if "player" in _observer:
		_observer.player = player
	if "manager" in _observer:
		_observer.manager = get_node_or_null("../DailyRoutineManager")
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
	if "active_scenario_id" in _executor:
		_executor.active_scenario_id = _active_scenario_id
	if (
		_terminal_monitor != null
		and "semantic_action_provider" in _executor
		and _terminal_monitor.has_method("execute_semantic_action")
	):
		_executor.semantic_action_provider = _terminal_monitor
	if (
		_terminal_monitor != null
		and "gameplay" in _observer
		and "gameplay" in _terminal_monitor
	):
		_observer.gameplay = _terminal_monitor.gameplay
	_bridge.connected.connect(_on_bridge_connected)
	_bridge.disconnected.connect(_on_bridge_disconnected)
	_bridge.action_batch_received.connect(_on_action_batch_received)
	_bridge.recover_action_received.connect(_on_recover_action_received)
	_bridge.stop_request_received.connect(_on_stop_request_received)
	_bridge.end_game_received.connect(_on_end_game_received)
	_bridge.game_over_ack_received.connect(_on_game_over_ack_received)
	_bridge.remote_error.connect(_on_remote_error)
	supervised_exit_requested.connect(_quit_tree_for_supervised_exit)
	_executor.batch_finished.connect(_on_batch_finished)
	if _terminal_monitor != null and _terminal_monitor.has_signal("game_finished"):
		_terminal_monitor.game_finished.connect(_on_game_finished)
	_observation_timer.timeout.connect(_on_observation_timer_timeout)
	print(
		"AI_PLAY controller ready; scenario=%s user_args=%s auto_start=%s"
		% [_active_scenario_id, user_args, auto_start]
	)
	if _active_scenario_id.is_empty():
		push_error("AI_PLAY requested scenario is invalid or unavailable")
		return
	_prepare_lobby_task_presentation.call_deferred()
	if auto_start or _should_enable_for_user_args(user_args):
		enable_ai()


func _prepare_lobby_task_presentation() -> void:
	if _active_scenario_id == DEFAULT_SCENARIO_ID or _terminal_monitor == null:
		return
	var scene_root := get_parent() as Node3D
	if scene_root == null:
		return
	var demo_hints := scene_root.get_node_or_null("DEMO_HINTS") as Node3D
	if demo_hints == null:
		return
	var task_card: Node = null
	if "task_card" in _terminal_monitor:
		task_card = _terminal_monitor.get("task_card") as Node
	demo_hints.visible = false
	demo_hints.process_mode = Node.PROCESS_MODE_DISABLED
	for child: Node in scene_root.find_children("*", "", true, false):
		if (
			child == task_card
			or not "interaction_text" in child
			or not "is_disabled" in child
			or str(child.get("interaction_text")).strip_edges().to_lower()
			!= "read hint"
		):
			continue
		child.set("is_disabled", true)
		var hint_object: Node3D = child.get_parent_node_3d()
		if hint_object != null:
			hint_object.visible = false
		var collision_object := hint_object as CollisionObject3D
		if collision_object != null:
			collision_object.collision_layer = 0
			collision_object.collision_mask = 0
	for child: Node in demo_hints.find_children(
		"*",
		"CollisionObject3D",
		true,
		false,
	):
		var collision_object := child as CollisionObject3D
		collision_object.collision_layer = 0
		collision_object.collision_mask = 0


func _should_enable_for_user_args(user_args: Array) -> bool:
	return "--ai-play" in user_args


func _should_exit_on_game_over_for_user_args(user_args: Array) -> bool:
	return _should_enable_for_user_args(user_args) and EXIT_ON_GAME_OVER_ARG in user_args


func get_requested_scenario_id(user_args: Array) -> String:
	var scenario_id: String = DEFAULT_SCENARIO_ID
	var scenario_arg_seen: bool = false
	for value: Variant in user_args:
		if not value is String:
			continue
		var argument := value as String
		if not argument.begins_with(SCENARIO_ARG_PREFIX):
			continue
		if scenario_arg_seen:
			return ""
		scenario_arg_seen = true
		scenario_id = argument.trim_prefix(SCENARIO_ARG_PREFIX)
		if not _is_valid_scenario_id(scenario_id):
			return ""
	return scenario_id


func is_requested_scenario(scenario_id: String) -> bool:
	return get_requested_scenario_id(OS.get_cmdline_user_args()) == scenario_id


func get_active_scenario_id() -> String:
	return _active_scenario_id


func _is_valid_scenario_id(scenario_id: String) -> bool:
	if scenario_id.is_empty() or scenario_id.length() > 64:
		return false
	for index: int in range(scenario_id.length()):
		var character: int = scenario_id.unicode_at(index)
		if (
			not (character >= 97 and character <= 122)
			and not (character >= 48 and character <= 57)
			and character != 95
		):
			return false
	return true


func _find_scenario_monitor(scenario_id: String) -> Node:
	if scenario_id.is_empty():
		return null
	for child: Node in get_children():
		if "scenario_id" in child and child.scenario_id == scenario_id:
			return child
	var legacy_monitor: Node = get_node_or_null("TerminalMonitor")
	if (
		scenario_id == DEFAULT_SCENARIO_ID
		and legacy_monitor != null
		and not "scenario_id" in legacy_monitor
	):
		return legacy_monitor
	return null


func get_state() -> State:
	return _state


func enable_ai() -> void:
	print("AI_PLAY enabling; target=ws://%s:%d" % [host, port])
	_set_scenario_ai_control_active(true)
	_set_ai_mouse_guard(true)
	_stop_delivery_pending = false
	_game_finished = false
	_reconnect_remaining = -1.0
	if _state != State.DISABLED:
		_bridge.disconnect_from_server()
	_state = State.CONNECTING
	_pending_observation_id = -1
	_executing_observation_id = -1
	_last_completed_observation_id = -1
	_recovering_observation_id = -1
	var error: Error = _bridge.connect_to_server(host, port)
	if error != OK:
		_on_bridge_disconnected("connect_error:%d" % error)


func disable_ai(reason: String = "disabled", disconnect_bridge: bool = true) -> void:
	print("AI_PLAY disabled; reason=%s" % reason)
	_set_scenario_ai_control_active(false)
	_set_ai_mouse_guard(false)
	_capture_generation += 1
	_state = State.DISABLED
	_pending_observation_id = -1
	_executing_observation_id = -1
	_last_completed_observation_id = -1
	_recovering_observation_id = -1
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
		"scenario_id": _active_scenario_id,
	}
	if _active_scenario_id == "find_key":
		if (
			_terminal_monitor == null
			or not _terminal_monitor.has_method(
				"get_act_request_limit"
			)
		):
			_pause_for_error("invalid_act_request_limit")
			return
		var request_limit: Variant = (
			_terminal_monitor.get_act_request_limit()
		)
		if (
			not request_limit is int
			or request_limit not in FIND_KEY_ACT_REQUEST_LIMITS
		):
			_pause_for_error("invalid_act_request_limit")
			return
		hello["act_request_limit"] = request_limit
	if _bridge.send_packet(hello) != OK:
		_pause_for_error("hello_send_failed")
		return
	_state = State.READY
	_capture_observation(_last_results)


func _capture_observation(results: Array) -> void:
	if is_queued_for_deletion() or not is_inside_tree() or _state != State.READY:
		return
	if player == null and _observer != null and "player" in _observer:
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
	if (
		_recovering_observation_id >= 0
		and observation_id["value"] != _recovering_observation_id
	):
		_recovering_observation_id = -1
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
	if (
		not _has_exact_keys(
			batch,
			["type", "protocol_version", "observation_id", "actions"],
		)
		or batch.get("type") != "action_batch"
		or batch.get("protocol_version") != PROTOCOL_VERSION
	):
		_pause_for_error("invalid_action_batch")
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
	_executing_observation_id = observation_id["value"]
	_pending_observation_id = -1
	_state = State.EXECUTING
	_executor.execute_batch(actions, _pending_context)


func _on_recover_action_received(request: Dictionary) -> void:
	if (
		not _has_exact_keys(
			request,
			["type", "protocol_version", "observation_id", "reason"],
		)
		or request.get("type") != "recover_action"
		or request.get("protocol_version") != PROTOCOL_VERSION
		or request.get("reason") != "action_timeout"
	):
		_pause_for_error("invalid_recover_action")
		return
	var observation_id: Dictionary = _parse_observation_id(request.get("observation_id"))
	if not observation_id["valid"]:
		_pause_for_error("invalid_recover_action")
		return
	var recovered_id: int = observation_id["value"]
	if _state == State.EXECUTING and recovered_id == _executing_observation_id:
		if _recovering_observation_id == recovered_id:
			return
		print("AI_PLAY recovering executing action observation=%d" % recovered_id)
		_recovering_observation_id = recovered_id
		_capture_generation += 1
		_observation_timer.stop()
		_executor.cancel_all("action_timeout")
		return
	if _state == State.READY and recovered_id == _last_completed_observation_id:
		if _recovering_observation_id == recovered_id:
			return
		print("AI_PLAY recovering delayed observation=%d" % recovered_id)
		_recovering_observation_id = recovered_id
		_capture_generation += 1
		_observation_timer.stop()
		var generation: int = _capture_generation
		call_deferred("_capture_observation_if_current", generation, _last_results)
		return
	if (
		_state == State.WAITING_FOR_DECISION
		and recovered_id == _last_completed_observation_id
		and _pending_observation_id != recovered_id
	):
		return
	_pause_for_error("stale_recover_action")


func _on_batch_finished(results: Array) -> void:
	if _state != State.EXECUTING:
		return
	var completed_observation_id: int = _executing_observation_id
	_executing_observation_id = -1
	_last_completed_observation_id = completed_observation_id
	if _recovering_observation_id == completed_observation_id:
		_last_results = results.duplicate(true)
		_state = State.READY
		var recovery_generation: int = _capture_generation
		call_deferred(
			"_capture_observation_if_current",
			recovery_generation,
			_last_results,
		)
		return
	if _bridge.send_packet({
		"type": "action_results",
		"protocol_version": PROTOCOL_VERSION,
		"observation_id": completed_observation_id,
		"results": results.duplicate(true),
	}) != OK:
		_pause_for_error("action_results_send_failed")
		return
	_last_results = results.duplicate(true)
	if _contains_stopped_result(results):
		_capture_generation += 1
		_set_ai_mouse_guard(false)
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
	# Synthetic input is delivered after the batch signal. Give the game one full
	# input/process frame to apply UI and interaction changes before reading pixels.
	await get_tree().process_frame
	if (
		generation != _capture_generation
		or _state != State.READY
		or is_queued_for_deletion()
		or not is_inside_tree()
	):
		return
	var rendered: bool = await _wait_for_render_frame(_render_frame_wait_timeout_msec)
	if (
		generation != _capture_generation
		or _state != State.READY
		or is_queued_for_deletion()
		or not is_inside_tree()
	):
		return
	if not rendered:
		# A background or throttled window may keep processing game state without
		# producing frame_post_draw. Force one current-state viewport redraw instead
		# of waiting until the MCP action timeout or publishing stale pixels.
		RenderingServer.force_draw(false)
	_capture_observation(results)


func _wait_for_render_frame(timeout_msec: int) -> bool:
	var render_state: Dictionary = {"completed": false}
	var mark_completed := func() -> void:
		render_state["completed"] = true
	RenderingServer.frame_post_draw.connect(mark_completed, CONNECT_ONE_SHOT)
	var deadline_msec: int = Time.get_ticks_msec() + timeout_msec
	while (
		not render_state["completed"]
		and Time.get_ticks_msec() < deadline_msec
		and not is_queued_for_deletion()
		and is_inside_tree()
	):
		await get_tree().process_frame
	if RenderingServer.frame_post_draw.is_connected(mark_completed):
		RenderingServer.frame_post_draw.disconnect(mark_completed)
	return render_state["completed"]


func _exit_tree() -> void:
	_capture_generation += 1
	_set_scenario_ai_control_active(false)
	_set_ai_mouse_guard(false)


func _set_ai_mouse_guard(enabled: bool) -> void:
	if player != null and player.has_method("set_ai_play_mouse_motion_device"):
		player.set_ai_play_mouse_motion_device(EXECUTOR_DEVICE_ID if enabled else -1)


func _set_scenario_ai_control_active(enabled: bool) -> void:
	if _terminal_monitor != null and _terminal_monitor.has_method("set_ai_control_active"):
		_terminal_monitor.set_ai_control_active(enabled)


func _on_observation_timer_timeout() -> void:
	var generation: int = _capture_generation
	call_deferred("_capture_observation_if_current", generation, _last_results)


func _on_bridge_disconnected(reason: String) -> void:
	if _state == State.DISABLED:
		_stop_delivery_pending = false
		return
	print("AI_PLAY WebSocket disconnected; reason=%s" % reason)
	_capture_generation += 1
	_state = State.CONNECTING
	_pending_observation_id = -1
	_executing_observation_id = -1
	_last_completed_observation_id = -1
	_recovering_observation_id = -1
	_observation_timer.stop()
	_executor.cancel_all(reason)
	_reconnect_remaining = RECONNECT_DELAY_SECONDS


func _on_remote_error(error: Dictionary) -> void:
	var code: String = str(error.get("code", "unknown"))
	print("AI_PLAY remote error; code=%s" % code)
	_pause_for_error("remote_error:%s" % code)


func _on_stop_request_received(request: Dictionary) -> void:
	if (
		not _has_exact_keys(
			request,
			["type", "protocol_version", "observation_id", "reason"],
		)
		or request.get("type") != "stop_request"
		or request.get("protocol_version") != PROTOCOL_VERSION
		or request.get("reason") != "mcp_stop"
	):
		_pause_for_error("invalid_stop_request")
		return
	var parsed_id: Dictionary = _parse_observation_id(request.get("observation_id"))
	var expected_id: int = _executing_observation_id
	if expected_id < 0:
		expected_id = _pending_observation_id
	if expected_id >= 0:
		if not parsed_id["valid"] or parsed_id["value"] != expected_id:
			_pause_for_error("invalid_stop_request")
			return
	elif not parsed_id["valid"] and request.get("observation_id") != null:
		_pause_for_error("invalid_stop_request")
		return
	_bridge.send_packet({
		"type": "stop_ack",
		"protocol_version": PROTOCOL_VERSION,
		"observation_id": request.get("observation_id"),
		"results": [{
			"status": "cancelled",
			"reason": "mcp_stop",
		}],
	})
	disable_ai("mcp_stop")


func _on_end_game_received(request: Dictionary) -> void:
	if _game_finished:
		return
	if (
		not _has_exact_keys(
			request,
			[
				"type",
				"protocol_version",
				"observation_id",
				"outcome",
				"reason",
			],
		)
		or request.get("type") != "end_game"
		or request.get("protocol_version") != PROTOCOL_VERSION
		or request.get("outcome") != "failure"
		or request.get("reason") != "max_requests"
	):
		_pause_for_error("invalid_end_game")
		return
	var parsed_id: Dictionary = _parse_observation_id(request.get("observation_id"))
	var expected_id: int = _executing_observation_id
	if expected_id < 0:
		expected_id = _pending_observation_id
	if expected_id >= 0:
		if not parsed_id["valid"] or parsed_id["value"] != expected_id:
			_pause_for_error("invalid_end_game")
			return
	elif not parsed_id["valid"] and request.get("observation_id") != null:
		_pause_for_error("invalid_end_game")
		return
	_finish_game("failure", "max_requests", request.get("observation_id"))


func _pause_for_error(reason: String) -> void:
	disable_ai(reason)


func _on_game_finished(outcome: String, reason: String) -> void:
	var observation_id: int = _executing_observation_id
	if observation_id < 0:
		observation_id = _pending_observation_id
	_finish_game(outcome, reason, observation_id)


func _finish_game(outcome: String, reason: String, observation_id: Variant) -> void:
	if _game_finished:
		return
	var valid_outcome: bool = (
		[outcome, reason]
		in SCENARIO_TERMINAL_RESULTS.get(_active_scenario_id, [])
	)
	if not valid_outcome:
		_pause_for_error("invalid_game_outcome")
		return
	_game_finished = true
	var send_error: Error = _bridge.send_packet({
		"type": "game_over",
		"protocol_version": PROTOCOL_VERSION,
		"observation_id": observation_id,
		"outcome": outcome,
		"reason": reason,
	})
	disable_ai("game_over:%s" % reason, send_error != OK)
	_show_game_over_result(outcome, reason)
	print("AI_PLAY_GAME_OVER outcome=%s reason=%s" % [outcome, reason])
	if _exit_on_game_over:
		if send_error == OK:
			_wait_for_game_over_ack(outcome, observation_id)
		else:
			_request_supervised_exit(outcome)


func _show_game_over_result(outcome: String, reason: String) -> void:
	if _terminal_monitor != null and _terminal_monitor.has_method("show_result"):
		_terminal_monitor.show_result(outcome, reason)


func _wait_for_game_over_ack(outcome: String, observation_id: Variant) -> void:
	_pending_game_over_ack_id = observation_id
	_pending_game_over_outcome = outcome
	_game_over_ack_generation += 1
	_quit_after_game_over_ack_timeout(
		_game_over_ack_generation,
		outcome,
	)


func _quit_after_game_over_ack_timeout(generation: int, outcome: String) -> void:
	await get_tree().create_timer(GAME_OVER_ACK_TIMEOUT_SECONDS).timeout
	if (
		generation == _game_over_ack_generation
		and not _pending_game_over_outcome.is_empty()
	):
		_request_supervised_exit(outcome)


func _on_game_over_ack_received(ack: Dictionary) -> void:
	if (
		_pending_game_over_outcome.is_empty()
		or not _has_exact_keys(
			ack,
			["type", "protocol_version", "observation_id"],
		)
		or ack.get("type") != "game_over_ack"
		or ack.get("protocol_version") != PROTOCOL_VERSION
		or ack.get("observation_id") != _pending_game_over_ack_id
	):
		return
	_request_supervised_exit(_pending_game_over_outcome)


func _request_supervised_exit(outcome: String) -> void:
	if _pending_game_over_outcome.is_empty() and outcome.is_empty():
		return
	_pending_game_over_ack_id = null
	_pending_game_over_outcome = ""
	_game_over_ack_generation += 1
	supervised_exit_requested.emit(0 if outcome == "success" else 1)


func _quit_tree_for_supervised_exit(exit_code: int) -> void:
	get_tree().quit(exit_code)


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


func _has_exact_keys(packet: Dictionary, expected: Array[String]) -> bool:
	if packet.size() != expected.size():
		return false
	for key: String in expected:
		if not packet.has(key):
			return false
	return true
