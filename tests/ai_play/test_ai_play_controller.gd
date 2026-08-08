extends SceneTree

var _failures: Array[String] = []


class FakeObserver extends Node:
	var capture_count: int = 0
	var capture_events: Array = []
	var next_observation_id: int = 17

	func get_bindings() -> Dictionary:
		return {"forward": "W", "interact": "F"}

	func get_available_interactions() -> Array[Dictionary]:
		return [{"action": "interact"}]

	func capture_observation(last_results: Array) -> Dictionary:
		capture_count += 1
		capture_events.append(last_results.duplicate(true))
		return {
			"observation_id": next_observation_id,
			"interface": {"is_open": false, "available_interactions": []},
			"last_action_results": last_results.duplicate(true),
		}


class FakeBridge extends Node:
	signal connected
	signal disconnected(reason: String)
	signal action_batch_received(batch: Dictionary)
	signal recover_action_received(request: Dictionary)
	signal stop_request_received(request: Dictionary)
	signal end_game_received(request: Dictionary)
	signal game_over_ack_received(ack: Dictionary)
	signal remote_error(error: Dictionary)

	var connect_calls: Array[Dictionary] = []
	var sent_packets: Array[Dictionary] = []
	var disconnect_calls: int = 0

	func connect_to_server(host: String, port: int) -> Error:
		connect_calls.append({"host": host, "port": port})
		return OK

	func send_packet(packet: Dictionary) -> Error:
		sent_packets.append(packet.duplicate(true))
		return OK

	func disconnect_from_server() -> void:
		disconnect_calls += 1


class FakeExecutor extends Node:
	signal batch_finished(results: Array)

	var player: Node3D
	var interaction_probe: Node
	var execute_calls: Array[Dictionary] = []
	var cancel_reasons: Array[String] = []

	func execute_batch(actions: Array, context: Dictionary) -> void:
		execute_calls.append({"actions": actions.duplicate(true), "context": context.duplicate(true)})

	func cancel_all(reason: String) -> void:
		cancel_reasons.append(reason)


class FakeInteractionProbe extends Node:
	var player: Node
	var interaction_provider: Callable


class FakeTerminalMonitor extends Node:
	signal game_finished(outcome: String, reason: String)
	var scenario_id: String = "find_contract"
	var act_request_limit: int = 100

	var shown_results: Array[Dictionary] = []

	func get_act_request_limit() -> int:
		return act_request_limit

	func show_result(outcome: String, reason: String) -> void:
		shown_results.append({"outcome": outcome, "reason": reason})


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	var controller_script: GDScript = load("res://addons/cogito/AIPlay/ai_play_controller.gd")
	_assert(controller_script != null, "controller script exists")
	if controller_script == null:
		_finish()
		return

	_test_bridge_raw_json_packets()
	_test_bridge_accepts_protocol_four_and_emits_stop_request()
	_test_bridge_emits_only_exact_request_limit_terminal()
	_test_bridge_configures_large_packet_buffers()
	_test_user_arg_opt_in(controller_script)
	_test_find_key_round_seed_parser(controller_script)
	_test_exit_on_game_over_opt_in(controller_script)
	_test_bridge_requires_exact_loopback()
	await _test_enable_and_hello(controller_script)
	await _test_mouse_guard_lifecycle(controller_script)
	await _test_recovery_cancels_executing_action(controller_script)
	await _test_recovery_forces_capture_after_completed_action(controller_script)
	await _test_late_recovery_after_fresh_observation_is_idempotent(controller_script)
	await _test_find_key_hello_includes_round_request_limit(
		controller_script
	)
	await _test_find_key_hello_rejects_invalid_round_request_limit(
		controller_script
	)
	await _test_action_batch_requires_exact_mcp_fields(controller_script)
	await _test_remote_stop_releases_and_acknowledges(controller_script)
	await _test_action_results_are_reported(controller_script)
	await _test_interval_recapture_waits_for_rendering(controller_script)
	await _test_interval_recapture_force_draws_after_render_timeout(controller_script)
	await _test_async_terminal_uses_completed_action_observation_id(controller_script)
	await _test_terminal_outcomes(controller_script)
	await _test_supervised_exit_waits_for_game_over_ack(controller_script)
	await _test_remote_request_limit_terminal(controller_script)
	await _test_remote_request_limit_terminal_without_observation(controller_script)
	await _test_invalid_remote_request_limit_terminal(controller_script)
	await _test_observation_id_gate(controller_script)
	await _test_stopped_batch_disables_without_recapture(controller_script)
	await _test_blocked_batch_recaptures_immediately(controller_script)
	await _test_context_change_recaptures_immediately(controller_script)
	await _test_probe_recaptures_immediately(controller_script)
	await _test_deferred_recapture_is_cancelled_by_teardown(controller_script)
	await _test_transport_failures_cancel(controller_script)
	await _test_remote_error_disables(controller_script)
	await _test_non_escape_input_keeps_ai(controller_script)
	await _test_escape_stops_ai(controller_script)
	await _test_reusable_scene()
	await _test_teardown_releases_without_late_signal()
	await _test_bridge_teardown_disconnects()
	_finish()


func _test_recovery_cancels_executing_action(
	controller_script: GDScript,
) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	fixture.bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 17,
		"actions": [{"type": "probe_interaction", "target_x": 0.5, "target_y": 0.5}],
	})
	fixture.observer.next_observation_id = 18
	fixture.bridge.recover_action_received.emit(_recovery_request(17))

	_assert(
		fixture.executor.cancel_reasons == ["action_timeout"],
		"recovery cancels and releases the executing action",
	)
	_assert(
		fixture.controller.get_state() == fixture.controller.State.EXECUTING,
		"recovery waits for executor cancellation without disabling",
	)
	fixture.executor.batch_finished.emit([{
		"status": "cancelled",
		"reason": "action_timeout",
	}])
	await _flush_deferred_capture()
	var result_packets: Array = fixture.bridge.sent_packets.filter(
		func(packet: Dictionary) -> bool: return packet.get("type") == "action_results"
	)
	_assert(result_packets.is_empty(), "recovery suppresses stale action results")
	_assert(
		fixture.controller.get_state() == fixture.controller.State.WAITING_FOR_DECISION,
		"recovery captures a fresh observation without disabling",
	)
	_assert(
		fixture.bridge.sent_packets[-1].get("observation_id") == 18,
		"executing recovery sends a fresh observation ID",
	)
	await _free_fixture(fixture)


func _test_recovery_forces_capture_after_completed_action(
	controller_script: GDScript,
) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	fixture.bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 17,
		"actions": [{"type": "wait", "duration_ms": 50}],
	})
	fixture.executor.batch_finished.emit([{"status": "completed", "type": "wait"}])
	fixture.observer.next_observation_id = 18
	fixture.bridge.recover_action_received.emit(_recovery_request(17))
	await _flush_deferred_capture()

	_assert(
		fixture.controller.get_state() == fixture.controller.State.WAITING_FOR_DECISION,
		"capture-pending recovery keeps the same controller alive",
	)
	_assert(
		fixture.bridge.sent_packets[-1].get("observation_id") == 18,
		"capture-pending recovery forces a fresh observation",
	)
	await _free_fixture(fixture)


func _test_late_recovery_after_fresh_observation_is_idempotent(
	controller_script: GDScript,
) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	fixture.bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 17,
		"actions": [{"type": "move", "forward": 1.0, "right": 0.0, "duration_ms": 50}],
	})
	fixture.observer.next_observation_id = 18
	fixture.executor.batch_finished.emit([{"status": "blocked", "type": "move"}])
	await _flush_deferred_capture()
	var packets_before_recovery: int = fixture.bridge.sent_packets.size()
	fixture.bridge.recover_action_received.emit(_recovery_request(17))

	_assert(
		fixture.controller.get_state() == fixture.controller.State.WAITING_FOR_DECISION,
		"late recovery does not disable a controller with a fresh observation",
	)
	_assert(
		fixture.bridge.sent_packets.size() == packets_before_recovery,
		"late recovery is an idempotent no-op",
	)
	await _free_fixture(fixture)


func _recovery_request(observation_id: int) -> Dictionary:
	return {
		"type": "recover_action",
		"protocol_version": 4,
		"observation_id": observation_id,
		"reason": "action_timeout",
	}


func _flush_deferred_capture() -> void:
	await process_frame
	RenderingServer.emit_signal("frame_post_draw")
	await process_frame
	RenderingServer.emit_signal("frame_post_draw")
	await process_frame


func _test_user_arg_opt_in(controller_script: GDScript) -> void:
	var controller: Node = controller_script.new()
	_assert(controller.has_method("_should_enable_for_user_args"), "controller exposes opt-in predicate")
	if controller.has_method("_should_enable_for_user_args"):
		_assert(not controller._should_enable_for_user_args([]), "ordinary launch stays disabled")
		_assert(controller._should_enable_for_user_args(["--ai-play"]), "exact user arg enables AI")
		for args: Array in [["ai-play"], ["--ai-play=true"], ["--AI-PLAY"]]:
			_assert(not controller._should_enable_for_user_args(args), "similar user arg does not enable AI")
	_assert(
		controller.get_requested_scenario_id([]) == "find_contract",
		"default scenario is find_contract",
	)
	_assert(
		controller.get_requested_scenario_id(
			["--ai-play-scenario=find_contract"]
		) == "find_contract",
		"explicit allowlisted scenario id parses",
	)
	_assert(
		controller.get_requested_scenario_id(
			["--ai-play-scenario=arrange_meeting_briefings"]
		) == "arrange_meeting_briefings",
		"meeting briefing scenario id parses",
	)
	_assert(
		controller.get_requested_scenario_id(
			["--ai-play-scenario=loop_staircase_anomaly"]
		) == "loop_staircase_anomaly",
		"loop staircase scenario id parses",
	)
	for args: Array in [
		["--ai-play-scenario="],
		["--ai-play-scenario=FindContract"],
		["--ai-play-scenario=../secret"],
		[
			"--ai-play-scenario=find_contract",
			"--ai-play-scenario=find_contract",
		],
	]:
		_assert(
			controller.get_requested_scenario_id(args).is_empty(),
			"invalid scenario argument is rejected",
		)
	var find_contract_monitor := FakeTerminalMonitor.new()
	var other_monitor := FakeTerminalMonitor.new()
	other_monitor.scenario_id = "other_scenario"
	controller.add_child(find_contract_monitor)
	controller.add_child(other_monitor)
	_assert(
		controller._find_scenario_monitor("find_contract")
			== find_contract_monitor,
		"scenario registry selects the matching monitor",
	)
	_assert(
		controller._find_scenario_monitor("other_scenario") == other_monitor,
		"scenario registry supports another script in the same scene",
	)
	_assert(
		controller._find_scenario_monitor("unknown") == null,
		"unknown scenario has no active monitor",
	)
	controller.free()


func _test_find_key_round_seed_parser(controller_script: GDScript) -> void:
	var controller: Node = controller_script.new()
	var parser: GDScript = load(
		"res://addons/cogito/AIPlay/ai_play_round_seed.gd"
	)
	_assert(
		controller.get_requested_round_seed([
			"--ai-play",
			"--ai-play-scenario=find_key",
			"--ai-play-round-seed=0",
		]) == {"valid": true, "provided": true, "value": 0},
		"zero round seed is deterministic",
	)
	_assert(
		controller.get_runtime_round_seed(0) == 9_007_199_254_740_992,
		"CLI seed zero maps to a deterministic non-sentinel runtime seed",
	)
	_assert(
		controller.get_runtime_round_seed(42) == 42,
		"nonzero CLI seeds retain their runtime value",
	)
	_assert(
		controller.get_requested_round_seed([
			"--ai-play",
			"--ai-play-scenario=greet_npc_meeting",
			"--ai-play-round-seed=42",
		]) == {"valid": true, "provided": true, "value": 42},
		"round seed is accepted for every registered benchmark scenario",
	)
	_assert(
		controller.get_requested_round_seed([
			"--ai-play",
			"--ai-play-scenario=daily_routine_cleanup",
			"--ai-play-seed=7",
		]) == {"valid": true, "provided": true, "value": 7},
		"legacy seed is validated for its allowlisted standalone scenarios",
	)
	_assert(
		controller.get_requested_round_seed([
			"--ai-play",
			"--ai-play-scenario=find_key",
		]) == {"valid": true, "provided": false, "value": 0},
		"missing round seed remains valid",
	)
	for args: Array in [
		["--ai-play", "--ai-play-scenario=find_key", "--ai-play-round-seed=-1"],
		["--ai-play", "--ai-play-scenario=find_key", "--ai-play-round-seed=one"],
		[
			"--ai-play",
			"--ai-play-scenario=find_key",
			"--ai-play-round-seed=1",
			"--ai-play-round-seed=2",
		],
		["--ai-play-scenario=find_key", "--ai-play-round-seed=1"],
		["--ai-play", "--ai-play-scenario=unknown", "--ai-play-round-seed=1"],
		[
			"--ai-play",
			"--ai-play-scenario=find_key",
			"--ai-play-round-seed=9007199254740992",
		],
		[
			"--ai-play",
			"--ai-play-scenario=garden_watering",
			"--ai-play-seed=-1",
		],
		[
			"--ai-play",
			"--ai-play-scenario=garden_watering",
			"--ai-play-round-seed=1",
			"--ai-play-seed=1",
		],
	]:
		_assert(
			not controller.get_requested_round_seed(args)["valid"],
			"invalid or misplaced round seed is rejected",
		)
	_assert(
		parser.parse(["--ai-play-seed=7"], true)
			== {"valid": true, "provided": true, "value": 7, "legacy": true},
		"legacy seed remains available only to opted-in standalone scenarios",
	)
	_assert(
		not parser.parse([
			"--ai-play-round-seed=7",
			"--ai-play-seed=7",
		], true)["valid"],
		"mixed generic and legacy seed arguments are rejected as duplicates",
	)
	controller.free()


func _test_exit_on_game_over_opt_in(controller_script: GDScript) -> void:
	var controller: Node = controller_script.new()
	_assert(
		controller.has_method("_should_exit_on_game_over_for_user_args"),
		"controller exposes game-over exit predicate",
	)
	if controller.has_method("_should_exit_on_game_over_for_user_args"):
		_assert(
			not controller._should_exit_on_game_over_for_user_args([]),
			"ordinary launch does not exit on game over",
		)
		_assert(
			not controller._should_exit_on_game_over_for_user_args(
				["--ai-play-exit-on-game-over"],
			),
			"exit flag alone does not enable supervised exit",
		)
		_assert(
			controller._should_exit_on_game_over_for_user_args(
				["--ai-play", "--ai-play-exit-on-game-over"],
			),
			"AI launch with supervisor flag exits on game over",
		)
		_assert(
			not controller._should_exit_on_game_over_for_user_args(
				["--ai-play", "--ai-play-exit-on-game-over=true"],
			),
			"similar supervisor flag is ignored",
		)
	controller.free()


func _test_bridge_requires_exact_loopback() -> void:
	var bridge_script: GDScript = load("res://addons/cogito/AIPlay/ai_play_bridge.gd")
	var bridge: Node = bridge_script.new()
	_assert(bridge.has_method("_is_loopback_host"), "bridge exposes strict loopback predicate")
	if bridge.has_method("_is_loopback_host"):
		_assert(bridge._is_loopback_host("127.0.0.1"), "numeric IPv4 loopback is allowed")
		for host: String in ["localhost", "::1", "192.0.2.1"]:
			_assert(not bridge._is_loopback_host(host), "%s is rejected" % host)
			_assert(bridge.connect_to_server(host, 8765) == ERR_INVALID_PARAMETER, "connect boundary rejects %s" % host)
	bridge.free()


func _test_bridge_configures_large_packet_buffers() -> void:
	var bridge_script: GDScript = load("res://addons/cogito/AIPlay/ai_play_bridge.gd")
	var bridge: Node = bridge_script.new()
	var socket := WebSocketPeer.new()
	bridge._configure_socket_buffers(socket)
	_assert(
		socket.inbound_buffer_size == bridge.MAX_PACKET_SIZE,
		"bridge inbound buffer matches packet limit",
	)
	_assert(
		socket.outbound_buffer_size == bridge.MAX_PACKET_SIZE,
		"bridge outbound buffer matches packet limit",
	)
	bridge.free()


func _test_bridge_raw_json_packets() -> void:
	var bridge_script: GDScript = load("res://addons/cogito/AIPlay/ai_play_bridge.gd")
	var bridge: Node = bridge_script.new()
	var batches: Array[Dictionary] = []
	var recoveries: Array[Dictionary] = []
	var game_over_acks: Array[Dictionary] = []
	var errors: Array[Dictionary] = []
	bridge.action_batch_received.connect(func(batch: Dictionary) -> void: batches.append(batch))
	_assert(bridge.has_signal("recover_action_received"), "bridge exposes recovery signal")
	if bridge.has_signal("recover_action_received"):
		bridge.recover_action_received.connect(
			func(request: Dictionary) -> void: recoveries.append(request)
		)
	_assert(bridge.has_signal("game_over_ack_received"), "bridge exposes game-over ACK signal")
	if bridge.has_signal("game_over_ack_received"):
		bridge.game_over_ack_received.connect(
			func(ack: Dictionary) -> void: game_over_acks.append(ack)
		)
	bridge.remote_error.connect(func(error: Dictionary) -> void: errors.append(error))
	bridge._handle_text_packet('{"type":"hello","protocol_version":4}')
	_assert(errors.is_empty(), "raw JSON hello accepts numeric protocol version four")
	bridge._handle_text_packet('{"type":"hello","protocol_version":4.0}')
	_assert(errors.is_empty(), "raw JSON hello accepts normalized numeric protocol version four")
	bridge._handle_text_packet(
		'{"type":"action_batch","protocol_version":4,"observation_id":7,"actions":[]}'
	)
	_assert(batches.size() == 1, "raw JSON action batch emits through bridge")
	bridge._handle_text_packet(
		'{"type":"recover_action","protocol_version":4,"observation_id":7,"reason":"action_timeout"}'
	)
	_assert(recoveries.size() == 1, "exact recovery request emits through bridge")
	bridge._handle_text_packet(
		'{"type":"game_over_ack","protocol_version":4,"observation_id":7}'
	)
	_assert(game_over_acks == [{
		"type": "game_over_ack",
		"protocol_version": 4,
		"observation_id": 7,
	}], "exact game-over ACK emits through bridge")
	for invalid_recovery: String in [
		'{"type":"recover_action","protocol_version":4,"observation_id":7,"reason":"other"}',
		'{"type":"recover_action","protocol_version":4,"observation_id":true,"reason":"action_timeout"}',
		'{"type":"recover_action","protocol_version":4,"observation_id":7,"reason":"action_timeout","extra":1}',
	]:
		var previous_recoveries: int = recoveries.size()
		bridge._handle_text_packet(invalid_recovery)
		_assert(recoveries.size() == previous_recoveries, "invalid recovery request is rejected")
	for invalid_packet: String in [
		'{"type":"hello","protocol_version":true}',
		'{"type":"hello","protocol_version":"3"}',
		'{"type":"hello","protocol_version":2.5}',
		'{"type":"hello","protocol_version":3}',
		'{"type":"hello","protocol_version":1}',
		'{"type":"hello","protocol_version":NaN}',
	]:
		var previous_errors: int = errors.size()
		bridge._handle_text_packet(invalid_packet)
		_assert(errors.size() == previous_errors + 1, "raw JSON rejects invalid protocol version")
	bridge.free()


func _test_bridge_accepts_protocol_four_and_emits_stop_request() -> void:
	var bridge_script: GDScript = load("res://addons/cogito/AIPlay/ai_play_bridge.gd")
	var bridge: Node = bridge_script.new()
	var requests: Array[Dictionary] = []
	var errors: Array[Dictionary] = []
	bridge.stop_request_received.connect(
		func(request: Dictionary) -> void: requests.append(request)
	)
	bridge.remote_error.connect(
		func(error: Dictionary) -> void: errors.append(error)
	)
	bridge._handle_text_packet(JSON.stringify({
		"type": "stop_request",
		"protocol_version": 4,
		"observation_id": 9,
		"reason": "mcp_stop",
	}))

	_assert(requests == [{
		"type": "stop_request",
		"protocol_version": 4,
		"observation_id": 9,
		"reason": "mcp_stop",
	}], "bridge emits validated MCP stop request")
	for invalid_packet: Dictionary in [
		{
			"type": "stop_request",
			"protocol_version": 1,
			"observation_id": 9,
			"reason": "mcp_stop",
		},
		{
			"type": "stop_request",
			"protocol_version": 4,
			"observation_id": 9,
			"reason": "mcp_stop",
			"extra": true,
		},
		{
			"type": "stop_request",
			"protocol_version": 4,
			"observation_id": 9,
			"reason": "escape_stop",
		},
		{
			"type": "unknown",
			"protocol_version": 4,
		},
	]:
		var previous_errors: int = errors.size()
		bridge._handle_text_packet(JSON.stringify(invalid_packet))
		_assert(errors.size() == previous_errors + 1, "bridge rejects invalid incoming packet")
	bridge.free()


func _test_bridge_emits_only_exact_request_limit_terminal() -> void:
	var bridge_script: GDScript = load("res://addons/cogito/AIPlay/ai_play_bridge.gd")
	var bridge: Node = bridge_script.new()
	var requests: Array[Dictionary] = []
	var errors: Array[Dictionary] = []
	bridge.end_game_received.connect(
		func(request: Dictionary) -> void: requests.append(request)
	)
	bridge.remote_error.connect(
		func(error: Dictionary) -> void: errors.append(error)
	)
	var valid_request: Dictionary = {
		"type": "end_game",
		"protocol_version": 4,
		"observation_id": 9,
		"outcome": "failure",
		"reason": "max_requests",
	}
	bridge._handle_text_packet(JSON.stringify(valid_request))
	_assert(requests == [valid_request], "bridge emits exact request-limit terminal")

	for invalid_packet: Dictionary in [
		{
			"type": "end_game",
			"protocol_version": 2,
			"observation_id": 9,
			"outcome": "failure",
			"reason": "max_requests",
		},
		{
			"type": "end_game",
			"protocol_version": 4,
			"observation_id": 9.5,
			"outcome": "failure",
			"reason": "max_requests",
		},
		{
			"type": "end_game",
			"protocol_version": 4,
			"observation_id": 9,
			"outcome": "success",
			"reason": "max_requests",
		},
		{
			"type": "end_game",
			"protocol_version": 4,
			"observation_id": 9,
			"outcome": "failure",
			"reason": "max_requests",
			"extra": true,
		},
	]:
		var previous_errors: int = errors.size()
		bridge._handle_text_packet(JSON.stringify(invalid_packet))
		_assert(
			errors.size() == previous_errors + 1,
			"bridge rejects invalid request-limit terminal",
		)
	_assert(requests == [valid_request], "invalid terminal packets are never emitted")
	bridge.free()


func _test_enable_and_hello(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _make_fixture(controller_script)
	var controller: Node = fixture.controller
	var bridge: FakeBridge = fixture.bridge
	controller.enable_ai()
	_assert(fixture.executor.player == fixture.player, "controller wires real player into executor")
	_assert(
		fixture.interaction_probe.player == fixture.player,
		"controller wires real player into interaction probe",
	)
	_assert(
		fixture.executor.interaction_probe == fixture.interaction_probe,
		"controller wires interaction probe into executor",
	)
	_assert(
		fixture.interaction_probe.interaction_provider.call()
			== [{"action": "interact"}],
		"interaction probe reads observer-approved interactions",
	)
	_assert(bridge.connect_calls == [{"host": "127.0.0.1", "port": 8765}], "enabling connects")
	bridge.connected.emit()
	_assert(not bridge.sent_packets.is_empty(), "connection sends hello")
	if not bridge.sent_packets.is_empty():
		var hello: Dictionary = bridge.sent_packets[0]
		_assert(hello.get("type") == "hello", "first packet is hello")
		_assert(
			hello == {
				"type": "hello",
				"protocol_version": 4,
				"scenario_id": "find_contract",
			},
			"hello identifies the active scenario",
		)
	await _free_fixture(fixture)


func _test_mouse_guard_lifecycle(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _make_fixture(controller_script)
	_assert(
		fixture.player._ai_play_mouse_motion_device == -1,
		"AI mouse guard starts disabled",
	)
	fixture.controller.enable_ai()
	_assert(
		fixture.player._ai_play_mouse_motion_device == fixture.controller.EXECUTOR_DEVICE_ID,
		"enabling AI accepts only the executor mouse device",
	)
	fixture.bridge.disconnected.emit("test_reconnect")
	_assert(
		fixture.player._ai_play_mouse_motion_device == fixture.controller.EXECUTOR_DEVICE_ID,
		"transient reconnect keeps the AI mouse guard",
	)
	fixture.controller.disable_ai("test_disable")
	_assert(
		fixture.player._ai_play_mouse_motion_device == -1,
		"disabling AI restores human mouse motion",
	)
	fixture.controller.enable_ai()
	fixture.controller._exit_tree()
	_assert(
		fixture.player._ai_play_mouse_motion_device == -1,
		"controller teardown restores human mouse motion",
	)
	await _free_fixture(fixture)


func _test_find_key_hello_includes_round_request_limit(
	controller_script: GDScript,
) -> void:
	var fixture: Dictionary = await _make_fixture(controller_script)
	fixture.controller._active_scenario_id = "find_key"
	fixture.terminal_monitor.scenario_id = "find_key"
	fixture.terminal_monitor.act_request_limit = 100
	fixture.controller.enable_ai()
	fixture.bridge.connected.emit()

	_assert(
		not fixture.bridge.sent_packets.is_empty(),
		"find_key connection sends hello",
	)
	if fixture.bridge.sent_packets.is_empty():
		await _free_fixture(fixture)
		return
	_assert(
		fixture.bridge.sent_packets[0] == {
			"type": "hello",
			"protocol_version": 4,
			"scenario_id": "find_key",
			"act_request_limit": 100,
		},
		"find_key hello includes the allowlisted round request limit",
	)
	await _free_fixture(fixture)


func _test_find_key_hello_rejects_invalid_round_request_limit(
	controller_script: GDScript,
) -> void:
	var fixture: Dictionary = await _make_fixture(controller_script)
	fixture.controller._active_scenario_id = "find_key"
	fixture.terminal_monitor.scenario_id = "find_key"
	fixture.terminal_monitor.act_request_limit = 150
	fixture.controller.enable_ai()
	fixture.bridge.connected.emit()

	_assert(
		fixture.bridge.sent_packets.is_empty(),
		"legacy find_key limit above the current cap is not sent by Godot",
	)
	_assert(
		fixture.controller.get_state() == fixture.controller.State.DISABLED,
		"invalid find_key round request limit disables AI",
	)
	await _free_fixture(fixture)


func _test_remote_stop_releases_and_acknowledges(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	fixture.controller._state = fixture.controller.State.EXECUTING
	fixture.bridge.stop_request_received.emit({
		"type": "stop_request",
		"protocol_version": 4,
		"observation_id": 17,
		"reason": "mcp_stop",
	})
	await process_frame

	_assert(
		fixture.executor.cancel_reasons == ["mcp_stop"],
		"remote stop cancels executor",
	)
	_assert(
		fixture.controller.get_state() == fixture.controller.State.DISABLED,
		"remote stop disables controller",
	)
	_assert(
		fixture.bridge.sent_packets[-1] == {
			"type": "stop_ack",
			"protocol_version": 4,
			"observation_id": 17,
			"results": [{
				"status": "cancelled",
				"reason": "mcp_stop",
			}],
		},
		"remote stop sends ack",
	)
	await _free_fixture(fixture)


func _test_action_batch_requires_exact_mcp_fields(controller_script: GDScript) -> void:
	for extra_field: String in ["request_" + "count", "request_" + "limit", "reason"]:
		var fixture: Dictionary = await _connected_fixture(controller_script)
		var batch: Dictionary = {
			"type": "action_batch",
			"protocol_version": 4,
			"observation_id": 17,
			"actions": [{"type": "wait", "duration_ms": 50}],
		}
		batch[extra_field] = 1 if extra_field != "reason" else "legacy"
		fixture.bridge.action_batch_received.emit(batch)
		_assert(
			fixture.executor.execute_calls.is_empty(),
			"action batch rejects legacy field %s" % extra_field,
		)
		_assert(
			"invalid_action_batch" in fixture.executor.cancel_reasons,
			"invalid action batch releases input for %s" % extra_field,
		)
		await _free_fixture(fixture)


func _test_stopped_batch_disables_without_recapture(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var initial_capture_count: int = fixture.observer.capture_count
	var initial_disconnect_count: int = fixture.bridge.disconnect_calls
	fixture.bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 17,
		"actions": [{"type": "stop"}],
	})
	fixture.executor.batch_finished.emit([{"status": "stopped", "type": "stop"}])
	_assert(
		fixture.controller.get_state() == fixture.controller.State.DISABLED,
		"stopped result disables controller",
	)
	_assert(fixture.timer.is_stopped(), "stopped result leaves observation timer stopped")
	_assert(
		fixture.bridge.disconnect_calls == initial_disconnect_count + 1,
		"stopped result disconnects bridge once",
	)
	_assert(fixture.executor.cancel_reasons.is_empty(), "stopped result does not emit a second cancel batch")
	await process_frame
	_assert(
		fixture.observer.capture_count == initial_capture_count,
		"stopped result does not capture another observation",
	)
	await _free_fixture(fixture)


func _test_action_results_are_reported(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	fixture.bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 17,
		"actions": [{"type": "wait", "duration_ms": 50}],
	})
	var results: Array = [{"status": "completed", "type": "wait"}]
	fixture.executor.batch_finished.emit(results)
	var result_packets: Array = fixture.bridge.sent_packets.filter(
		func(packet: Dictionary) -> bool: return packet.get("type") == "action_results"
	)
	_assert(result_packets.size() == 1, "completed batch sends one action-results packet")
	if result_packets.size() == 1:
		_assert(result_packets[0] == {
			"type": "action_results",
			"protocol_version": 4,
			"observation_id": 17,
			"results": results,
		}, "action-results packet preserves observation correlation and results")
	await _free_fixture(fixture)


func _test_interval_recapture_waits_for_rendering(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var initial_capture_count: int = fixture.observer.capture_count
	fixture.bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 17,
		"actions": [{"type": "move", "forward": 1.0, "right": 0.0, "duration_ms": 50}],
	})
	fixture.executor.batch_finished.emit([{"status": "completed", "type": "move"}])
	_assert(not fixture.timer.is_stopped(), "completed move starts observation interval timer")
	fixture.timer.stop()
	fixture.timer.timeout.emit()
	_assert(
		fixture.observer.capture_count == initial_capture_count,
		"interval recapture does not read the viewport before a rendered frame",
	)
	await process_frame
	_assert(
		fixture.observer.capture_count == initial_capture_count,
		"interval recapture waits for rendering after the timer",
	)
	RenderingServer.emit_signal("frame_post_draw")
	await process_frame
	_assert(
		fixture.observer.capture_count == initial_capture_count,
		"interval recapture waits one full process frame before rendering",
	)
	RenderingServer.emit_signal("frame_post_draw")
	await process_frame
	_assert(
		fixture.observer.capture_count == initial_capture_count + 1,
		"interval recapture captures exactly once after rendering",
	)
	await _free_fixture(fixture)


func _test_interval_recapture_force_draws_after_render_timeout(
	controller_script: GDScript,
) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var initial_capture_count: int = fixture.observer.capture_count
	var has_timeout_setting: bool = "_render_frame_wait_timeout_msec" in fixture.controller
	_assert(has_timeout_setting, "controller exposes an internal bounded render wait")
	if has_timeout_setting:
		fixture.controller._render_frame_wait_timeout_msec = 20
	fixture.bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 17,
		"actions": [{"type": "look", "yaw": -45.0, "pitch": 0.0}],
	})
	fixture.executor.batch_finished.emit([{"status": "completed", "type": "look"}])
	fixture.timer.stop()
	fixture.timer.timeout.emit()
	await create_timer(0.1).timeout
	_assert(
		fixture.observer.capture_count == initial_capture_count + 1,
		"render timeout force-draws and captures without a frame_post_draw signal",
	)
	await _free_fixture(fixture)


func _test_async_terminal_uses_completed_action_observation_id(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(
		controller_script,
		"loop_staircase_anomaly",
	)
	fixture.bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 17,
		"actions": [{"type": "submit_floor"}],
	})
	var results: Array = [{"status": "completed", "type": "submit_floor"}]
	fixture.executor.batch_finished.emit(results)
	fixture.terminal_monitor.game_finished.emit(
		"success",
		"correct_floor_selected",
	)

	var packets: Array = fixture.bridge.sent_packets.filter(
		func(packet: Dictionary) -> bool: return packet.get("type") == "game_over"
	)
	_assert(
		packets.size() == 1,
		"async terminal after action_results emits one game_over packet",
	)
	if packets.size() == 1:
		_assert(packets[0] == {
			"type": "game_over",
			"protocol_version": 4,
			"observation_id": 17,
			"outcome": "success",
			"reason": "correct_floor_selected",
		}, "async terminal uses the completed action observation id")
	await _free_fixture(fixture)


func _test_terminal_outcomes(controller_script: GDScript) -> void:
	_assert(
		AIPlayController.SCENARIO_TERMINAL_RESULTS["put_book"] == [
			["success", "books_in_ceo_office"],
			["failure", "wrong_book_pickup"],
			["failure", "max_requests"],
		],
		"put_book has the exact ordered-delivery terminal allowlist",
	)
	_assert(
		AIPlayController.SCENARIO_TERMINAL_RESULTS["greet_npc_meeting"] == [
			["success", "meeting_door_closed"],
			["failure", "wrong_npc_limit"],
			["failure", "max_requests"],
		],
		"greet_npc_meeting has the exact social-task terminal allowlist",
	)
	for terminal_case: Dictionary in [
		{
			"scenario": "find_contract",
			"outcome": "success",
			"reason": "correct_password",
		},
		{
			"scenario": "find_contract",
			"outcome": "failure",
			"reason": "wrong_password",
		},
		{
			"scenario": "find_key",
			"outcome": "success",
			"reason": "key_picked_up",
		},
		{
			"scenario": "put_book",
			"outcome": "success",
			"reason": "books_in_ceo_office",
		},
		{
			"scenario": "put_book",
			"outcome": "failure",
			"reason": "wrong_book_pickup",
		},
		{
			"scenario": "greet_npc_meeting",
			"outcome": "failure",
			"reason": "wrong_npc_limit",
		},
		{
			"scenario": "garden_watering",
			"outcome": "success",
			"reason": "garden_tasks_complete",
		},
		{
			"scenario": "garden_watering",
			"outcome": "failure",
			"reason": "garden_task_failed",
		},
		{
			"scenario": "repair_lighting_circuit",
			"outcome": "success",
			"reason": "circuit_repaired",
		},
		{
			"scenario": "repair_lighting_circuit",
			"outcome": "failure",
			"reason": "wrong_breaker",
		},
		{
			"scenario": "repair_lighting_circuit",
			"outcome": "failure",
			"reason": "incorrect_circuit_configuration",
		},
		{
			"scenario": "arrange_meeting_briefings",
			"outcome": "success",
			"reason": "meeting_prepared",
		},
		{
			"scenario": "arrange_meeting_briefings",
			"outcome": "failure",
			"reason": "incorrect_seating_assignment",
		},
		{
			"scenario": "loop_staircase_anomaly",
			"outcome": "success",
			"reason": "correct_floor_selected",
		},
		{
			"scenario": "loop_staircase_anomaly",
			"outcome": "failure",
			"reason": "wrong_floor_selected",
		},
		{
			"scenario": "laboratory_experiment",
			"outcome": "success",
			"reason": "experiment_completed",
		},
		{
			"scenario": "laboratory_experiment",
			"outcome": "failure",
			"reason": "experiment_attempts_exhausted",
		},
	]:
		var fixture: Dictionary = await _connected_fixture(
			controller_script,
			terminal_case.scenario,
		)
		fixture.bridge.action_batch_received.emit({
			"type": "action_batch",
			"protocol_version": 4,
			"observation_id": 17,
			"actions": [{"type": "wait", "duration_ms": 50}],
		})
		fixture.terminal_monitor.game_finished.emit(
			terminal_case.outcome,
			terminal_case.reason,
		)
		fixture.terminal_monitor.game_finished.emit(
			terminal_case.outcome,
			terminal_case.reason,
		)
		var packets: Array = fixture.bridge.sent_packets.filter(
			func(packet: Dictionary) -> bool: return packet.get("type") == "game_over"
		)
		_assert(packets.size() == 1, "%s emits one terminal packet" % terminal_case.reason)
		if packets.size() == 1:
			_assert(packets[0] == {
				"type": "game_over",
				"protocol_version": 4,
				"observation_id": 17,
				"outcome": terminal_case.outcome,
				"reason": terminal_case.reason,
			}, "%s terminal packet has exact fields" % terminal_case.reason)
		_assert(
			fixture.controller.get_state() == fixture.controller.State.DISABLED,
			"%s disables AI" % terminal_case.reason,
		)
		_assert(
			"game_over:%s" % terminal_case.reason in fixture.executor.cancel_reasons,
			"%s cancels and releases executor input" % terminal_case.reason,
		)
		_assert(
			fixture.bridge.disconnect_calls == 0,
			"%s leaves the bridge open for queued terminal delivery" % terminal_case.reason,
		)
		_assert(
			fixture.terminal_monitor.shown_results == [{
				"outcome": terminal_case.outcome,
				"reason": terminal_case.reason,
			}],
			"%s displays one terminal result" % terminal_case.reason,
		)
		await _free_fixture(fixture)

	var contract_fixture: Dictionary = await _connected_fixture(
		controller_script,
		"find_contract",
	)
	contract_fixture.terminal_monitor.game_finished.emit(
		"success",
		"key_picked_up",
	)
	_assert(
		"invalid_game_outcome" in contract_fixture.executor.cancel_reasons,
		"find_contract rejects find-key success",
	)
	await _free_fixture(contract_fixture)

	var circuit_fixture: Dictionary = await _connected_fixture(
		controller_script,
		"find_contract",
	)
	circuit_fixture.terminal_monitor.game_finished.emit(
		"success",
		"circuit_repaired",
	)
	_assert(
		"invalid_game_outcome" in circuit_fixture.executor.cancel_reasons,
		"find_contract rejects lighting-circuit success",
	)
	await _free_fixture(circuit_fixture)

	var meeting_fixture: Dictionary = await _connected_fixture(
		controller_script,
		"find_contract",
	)
	meeting_fixture.terminal_monitor.game_finished.emit(
		"success",
		"meeting_prepared",
	)
	_assert(
		"invalid_game_outcome" in meeting_fixture.executor.cancel_reasons,
		"find_contract rejects meeting-briefing success",
	)
	await _free_fixture(meeting_fixture)

	var meeting_cross_fixture: Dictionary = await _connected_fixture(
		controller_script,
		"arrange_meeting_briefings",
	)
	meeting_cross_fixture.terminal_monitor.game_finished.emit(
		"success",
		"circuit_repaired",
	)
	_assert(
		"invalid_game_outcome" in meeting_cross_fixture.executor.cancel_reasons,
		"meeting briefing rejects lighting-circuit success",
	)
	await _free_fixture(meeting_cross_fixture)

	var find_key_fixture: Dictionary = await _connected_fixture(
		controller_script,
		"find_key",
	)
	find_key_fixture.terminal_monitor.game_finished.emit(
		"success",
		"correct_password",
	)
	_assert(
		"invalid_game_outcome" in find_key_fixture.executor.cancel_reasons,
		"find_key rejects password success",
	)
	await _free_fixture(find_key_fixture)

	var find_key_lockout_fixture: Dictionary = await _connected_fixture(
		controller_script,
		"find_key",
	)
	find_key_lockout_fixture.terminal_monitor.game_finished.emit(
		"failure",
		"security_lockout",
	)
	_assert(
		not "invalid_game_outcome" in find_key_lockout_fixture.executor.cancel_reasons,
		"find_key accepts security lockout failure",
	)
	await _free_fixture(find_key_lockout_fixture)

	for obsolete_terminal: Dictionary in [
		{"outcome": "success", "reason": "book_in_box"},
		{"outcome": "failure", "reason": "book_in_wrong_box"},
	]:
		var put_book_fixture: Dictionary = await _connected_fixture(
			controller_script,
			"put_book",
		)
		put_book_fixture.terminal_monitor.game_finished.emit(
			obsolete_terminal.outcome,
			obsolete_terminal.reason,
		)
		_assert(
			"invalid_game_outcome" in put_book_fixture.executor.cancel_reasons,
			"put_book rejects obsolete %s/%s through controller validation" % [
				obsolete_terminal.outcome,
				obsolete_terminal.reason,
			],
		)
		_assert(
			put_book_fixture.bridge.sent_packets.filter(
				func(packet: Dictionary) -> bool: return packet.get("type") == "game_over"
			).is_empty(),
			"put_book does not send obsolete %s/%s terminal packets" % [
				obsolete_terminal.outcome,
				obsolete_terminal.reason,
			],
		)
		await _free_fixture(put_book_fixture)


func _test_supervised_exit_waits_for_game_over_ack(
	controller_script: GDScript,
) -> void:
	var fixture: Dictionary = await _connected_fixture(
		controller_script,
		"find_key",
	)
	_assert(
		fixture.controller.has_method("_on_game_over_ack_received"),
		"controller handles terminal delivery acknowledgement",
	)
	_assert(
		fixture.controller.has_signal("supervised_exit_requested"),
		"controller exposes a supervised exit request signal",
	)
	if (
		not fixture.controller.has_method("_on_game_over_ack_received")
		or not fixture.controller.has_signal("supervised_exit_requested")
	):
		await _free_fixture(fixture)
		return
	var exit_codes: Array[int] = []
	var exit_handler := Callable(
		fixture.controller,
		"_quit_tree_for_supervised_exit",
	)
	if fixture.controller.supervised_exit_requested.is_connected(exit_handler):
		fixture.controller.supervised_exit_requested.disconnect(exit_handler)
	fixture.controller.supervised_exit_requested.connect(
		func(exit_code: int) -> void: exit_codes.append(exit_code)
	)
	fixture.controller._exit_on_game_over = true
	fixture.terminal_monitor.game_finished.emit("success", "key_picked_up")
	await process_frame
	_assert(exit_codes.is_empty(), "supervised game waits for terminal ACK before exit")
	fixture.bridge.game_over_ack_received.emit({
		"type": "game_over_ack",
		"protocol_version": 4,
		"observation_id": 17,
	})
	await process_frame
	_assert(exit_codes == [0], "matching terminal ACK releases supervised success exit")
	await _free_fixture(fixture)


func _test_remote_request_limit_terminal(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var request: Dictionary = {
		"type": "end_game",
		"protocol_version": 4,
		"observation_id": 17,
		"outcome": "failure",
		"reason": "max_requests",
	}
	fixture.bridge.end_game_received.emit(request)
	fixture.bridge.end_game_received.emit(request)
	fixture.terminal_monitor.game_finished.emit("success", "correct_password")
	var packets: Array = fixture.bridge.sent_packets.filter(
		func(packet: Dictionary) -> bool: return packet.get("type") == "game_over"
	)

	_assert(packets == [{
		"type": "game_over",
		"protocol_version": 4,
		"observation_id": 17,
		"outcome": "failure",
		"reason": "max_requests",
	}], "request limit sends one exact terminal acknowledgement")
	_assert(
		fixture.controller.get_state() == fixture.controller.State.DISABLED,
		"request limit disables AI",
	)
	_assert(
		fixture.executor.cancel_reasons == ["game_over:max_requests"],
		"request limit cancels and releases executor input once",
	)
	_assert(
		fixture.terminal_monitor.shown_results == [{
			"outcome": "failure",
			"reason": "max_requests",
		}],
		"request limit displays one failure result",
	)
	await _free_fixture(fixture)


func _test_remote_request_limit_terminal_without_observation(
	controller_script: GDScript,
) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	fixture.controller._state = fixture.controller.State.READY
	fixture.controller._pending_observation_id = -1
	fixture.bridge.end_game_received.emit({
		"type": "end_game",
		"protocol_version": 4,
		"observation_id": null,
		"outcome": "failure",
		"reason": "max_requests",
	})
	var packets: Array = fixture.bridge.sent_packets.filter(
		func(packet: Dictionary) -> bool: return packet.get("type") == "game_over"
	)

	_assert(packets == [{
		"type": "game_over",
		"protocol_version": 4,
		"observation_id": null,
		"outcome": "failure",
		"reason": "max_requests",
	}], "request limit preserves a null observation ID when none exists")
	await _free_fixture(fixture)


func _test_invalid_remote_request_limit_terminal(controller_script: GDScript) -> void:
	for invalid_request: Dictionary in [
		{
			"type": "end_game",
			"protocol_version": 2,
			"observation_id": 17,
			"outcome": "failure",
			"reason": "max_requests",
		},
		{
			"type": "end_game",
			"protocol_version": 4,
			"observation_id": 16,
			"outcome": "failure",
			"reason": "max_requests",
		},
		{
			"type": "end_game",
			"protocol_version": 4,
			"observation_id": 17,
			"outcome": "success",
			"reason": "max_requests",
		},
		{
			"type": "end_game",
			"protocol_version": 4,
			"observation_id": 17,
			"outcome": "failure",
			"reason": "wrong_password",
		},
		{
			"type": "end_game",
			"protocol_version": 4,
			"observation_id": 17,
			"outcome": "failure",
			"reason": "max_requests",
			"extra": true,
		},
	]:
		var fixture: Dictionary = await _connected_fixture(controller_script)
		fixture.bridge.end_game_received.emit(invalid_request)
		var packets: Array = fixture.bridge.sent_packets.filter(
			func(packet: Dictionary) -> bool: return packet.get("type") == "game_over"
		)
		_assert(packets.is_empty(), "invalid request-limit terminal is not acknowledged")
		_assert(
			"invalid_end_game" in fixture.executor.cancel_reasons,
			"invalid request-limit terminal releases input",
		)
		await _free_fixture(fixture)


func _test_blocked_batch_recaptures_immediately(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var initial_capture_count: int = fixture.observer.capture_count
	fixture.bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 17,
		"actions": [{
			"type": "move",
			"forward": 1.0,
			"right": 0.0,
			"duration_ms": 50,
		}],
	})
	fixture.executor.batch_finished.emit([{"status": "blocked", "type": "move"}])
	_assert(
		fixture.controller.get_state() == fixture.controller.State.READY,
		"blocked result keeps autonomous controller ready",
	)
	_assert(fixture.timer.is_stopped(), "blocked result does not start interval timer")
	_assert(
		fixture.observer.capture_count == initial_capture_count,
		"blocked recapture is deferred",
	)
	await process_frame
	_assert(
		fixture.observer.capture_count == initial_capture_count,
		"blocked recapture waits for rendering",
	)
	RenderingServer.emit_signal("frame_post_draw")
	await process_frame
	_assert(
		fixture.observer.capture_count == initial_capture_count,
		"blocked recapture waits one full input frame before rendering",
	)
	RenderingServer.emit_signal("frame_post_draw")
	await process_frame
	_assert(
		fixture.observer.capture_count == initial_capture_count + 1,
		"blocked result triggers immediate deferred recapture",
	)
	await _free_fixture(fixture)


func _test_context_change_recaptures_immediately(controller_script: GDScript) -> void:
	for action_type: String in ["interact", "enter_digits", "close_ui"]:
		var fixture: Dictionary = await _connected_fixture(controller_script)
		var initial_capture_count: int = fixture.observer.capture_count
		fixture.bridge.action_batch_received.emit({
			"type": "action_batch",
			"protocol_version": 4,
			"observation_id": 17,
			"actions": [{"type": action_type}],
		})
		fixture.executor.batch_finished.emit([{"status": "completed", "type": action_type}])
		_assert(fixture.timer.is_stopped(), "%s does not start interval timer" % action_type)
		_assert(
			fixture.observer.capture_count == initial_capture_count,
			"%s recapture is deferred" % action_type,
		)
		await process_frame
		_assert(
			fixture.observer.capture_count == initial_capture_count,
			"%s recapture waits for rendering" % action_type,
		)
		RenderingServer.emit_signal("frame_post_draw")
		await process_frame
		_assert(
			fixture.observer.capture_count == initial_capture_count,
			"%s recapture waits one full input frame before rendering" % action_type,
		)
		RenderingServer.emit_signal("frame_post_draw")
		await process_frame
		_assert(
			fixture.observer.capture_count == initial_capture_count + 1,
			"%s triggers immediate deferred recapture" % action_type,
		)
		await _free_fixture(fixture)


func _test_probe_recaptures_immediately(controller_script: GDScript) -> void:
	for outcome: String in ["aligned", "not_found"]:
		var fixture: Dictionary = await _connected_fixture(controller_script)
		var initial_capture_count: int = fixture.observer.capture_count
		fixture.bridge.action_batch_received.emit({
			"type": "action_batch",
			"protocol_version": 4,
			"observation_id": 17,
			"actions": [{
				"type": "probe_interaction",
				"target_x": 0.5,
				"target_y": 0.5,
			}],
		})
		fixture.executor.batch_finished.emit([{
			"status": "completed",
			"type": "probe_interaction",
			"outcome": outcome,
			"scan_steps": 2 if outcome == "aligned" else 9,
		}])
		_assert(fixture.timer.is_stopped(), "%s probe does not start interval timer" % outcome)
		_assert(
			fixture.observer.capture_count == initial_capture_count,
			"%s probe recapture is deferred" % outcome,
		)
		await process_frame
		_assert(
			fixture.observer.capture_count == initial_capture_count,
			"%s probe recapture waits for rendering" % outcome,
		)
		RenderingServer.emit_signal("frame_post_draw")
		await process_frame
		_assert(
			fixture.observer.capture_count == initial_capture_count,
			"%s probe waits one full input frame before rendering" % outcome,
		)
		RenderingServer.emit_signal("frame_post_draw")
		await process_frame
		_assert(
			fixture.observer.capture_count == initial_capture_count + 1,
			"%s probe triggers immediate recapture" % outcome,
		)
		await _free_fixture(fixture)


func _test_deferred_recapture_is_cancelled_by_teardown(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var capture_events: Array = fixture.observer.capture_events
	var sent_packets: Array = fixture.bridge.sent_packets
	fixture.bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 17,
		"actions": [{"type": "interact"}],
	})
	fixture.executor.batch_finished.emit([{"status": "completed", "type": "interact"}])
	var captures_before_teardown: int = capture_events.size()
	var packets_before_teardown: int = sent_packets.size()
	fixture.controller.queue_free()
	fixture.timer.timeout.emit()
	_assert(
		capture_events.size() == captures_before_teardown,
		"queued teardown blocks direct timer recapture before frame cleanup",
	)
	_assert(
		sent_packets.size() == packets_before_teardown,
		"queued teardown blocks direct timer observation send before frame cleanup",
	)
	await process_frame
	_assert(
		capture_events.size() == captures_before_teardown,
		"queued teardown invalidates deferred recapture",
	)
	_assert(
		sent_packets.size() == packets_before_teardown,
		"queued teardown prevents deferred observation send",
	)
	fixture.player.free()


func _test_observation_id_gate(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var bridge: FakeBridge = fixture.bridge
	var executor: FakeExecutor = fixture.executor
	bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 17.0,
		"actions": [{"type": "wait", "duration_ms": 50}],
	})
	_assert(executor.execute_calls.size() == 1, "matching parsed numeric observation ID executes")
	executor.batch_finished.emit([{"status": "completed"}])
	fixture.observer.next_observation_id = 18
	fixture.timer.emit_signal("timeout")
	await _flush_deferred_capture()
	bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 18.5,
		"actions": [{"type": "stop"}],
	})
	_assert(executor.execute_calls.size() == 1, "fractional observation ID does not execute")
	_assert("stale_observation" in executor.cancel_reasons, "invalid observation ID cancels")
	await _free_fixture(fixture)

	var boolean_fixture: Dictionary = await _connected_fixture(controller_script)
	boolean_fixture.bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": true,
		"actions": [],
	})
	_assert(boolean_fixture.executor.execute_calls.is_empty(), "boolean observation ID does not execute")
	_assert("stale_observation" in boolean_fixture.executor.cancel_reasons, "boolean observation ID cancels")
	await _free_fixture(boolean_fixture)

	var stale_fixture: Dictionary = await _connected_fixture(controller_script)
	stale_fixture.bridge.action_batch_received.emit({
		"type": "action_batch",
		"protocol_version": 4,
		"observation_id": 16.0,
		"actions": [],
	})
	_assert(stale_fixture.executor.execute_calls.is_empty(), "stale observation ID does not execute")
	_assert("stale_observation" in stale_fixture.executor.cancel_reasons, "stale observation ID cancels")
	await _free_fixture(stale_fixture)


func _test_transport_failures_cancel(controller_script: GDScript) -> void:
	var disconnected_fixture: Dictionary = await _connected_fixture(controller_script)
	disconnected_fixture.bridge.disconnected.emit("socket_closed")
	_assert("socket_closed" in disconnected_fixture.executor.cancel_reasons, "disconnect cancels executor")
	await _free_fixture(disconnected_fixture)

	var error_fixture: Dictionary = await _connected_fixture(controller_script)
	error_fixture.bridge.remote_error.emit({"code": "api_failure", "message": "failed"})
	_assert("remote_error:api_failure" in error_fixture.executor.cancel_reasons, "remote error cancels executor")
	await _free_fixture(error_fixture)


func _test_remote_error_disables(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	fixture.bridge.remote_error.emit({"code": "bridge_failure", "message": "transport failed"})
	_assert(
		fixture.controller.get_state() == fixture.controller.State.DISABLED,
		"remote bridge error disables AI",
	)
	_assert(
		"remote_error:bridge_failure" in fixture.executor.cancel_reasons,
		"remote bridge error cancels executor",
	)
	await _free_fixture(fixture)


func _test_non_escape_input_keeps_ai(controller_script: GDScript) -> void:
	var key_fixture: Dictionary = await _connected_fixture(controller_script)
	var key := InputEventKey.new()
	key.physical_keycode = KEY_W
	key.pressed = true
	key.device = 0
	key_fixture.controller._input(key)
	_assert(key_fixture.controller.get_state() != key_fixture.controller.State.DISABLED, "physical movement does not stop AI")
	await _free_fixture(key_fixture)

	var f12_fixture: Dictionary = await _connected_fixture(controller_script)
	var f12 := InputEventKey.new()
	f12.keycode = KEY_F12
	f12.pressed = true
	f12.device = 0
	f12_fixture.controller._input(f12)
	_assert(f12_fixture.controller.get_state() != f12_fixture.controller.State.DISABLED, "F12 does not stop AI")
	await _free_fixture(f12_fixture)

	var mouse_fixture: Dictionary = await _connected_fixture(controller_script)
	var mouse := InputEventMouseMotion.new()
	mouse.relative = Vector2(3.0, -2.0)
	mouse.device = 0
	mouse_fixture.controller._input(mouse)
	_assert(mouse_fixture.controller.get_state() != mouse_fixture.controller.State.DISABLED, "passive mouse movement does not pause AI")
	await _free_fixture(mouse_fixture)

	var click_fixture: Dictionary = await _connected_fixture(controller_script)
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	click.device = 0
	click_fixture.controller._input(click)
	_assert(click_fixture.controller.get_state() != click_fixture.controller.State.DISABLED, "physical mouse click does not stop AI")
	await _free_fixture(click_fixture)

	var action_fixture: Dictionary = await _connected_fixture(controller_script)
	var action := InputEventAction.new()
	action.action = &"forward"
	action.pressed = true
	action.device = 0
	action_fixture.controller._input(action)
	_assert(action_fixture.controller.get_state() != action_fixture.controller.State.DISABLED, "unmarked input action does not stop AI")
	await _free_fixture(action_fixture)

	var joypad_fixture: Dictionary = await _connected_fixture(controller_script)
	var joypad := InputEventJoypadButton.new()
	joypad.button_index = JOY_BUTTON_A
	joypad.pressed = true
	joypad.device = 0
	joypad_fixture.controller._input(joypad)
	_assert(joypad_fixture.controller.get_state() != joypad_fixture.controller.State.DISABLED, "joypad input does not stop AI")
	await _free_fixture(joypad_fixture)

	var synthetic_fixture: Dictionary = await _connected_fixture(controller_script)
	var synthetic := InputEventMouseMotion.new()
	synthetic.relative = Vector2.ONE
	synthetic.device = AIPlayExecutor.SYNTHETIC_DEVICE_ID
	synthetic_fixture.controller._input(synthetic)
	_assert(synthetic_fixture.controller.get_state() != synthetic_fixture.controller.State.DISABLED, "executor input is ignored")
	_assert(
		synthetic_fixture.controller.EXECUTOR_DEVICE_ID == AIPlayExecutor.SYNTHETIC_DEVICE_ID,
		"controller and executor share one synthetic device ID",
	)
	await _free_fixture(synthetic_fixture)


func _test_escape_stops_ai(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var disconnects_before_escape: int = fixture.bridge.disconnect_calls
	var emergency := InputEventKey.new()
	emergency.keycode = KEY_ESCAPE
	emergency.pressed = true
	emergency.device = 0
	fixture.controller._input(emergency)
	_assert(fixture.controller.get_state() == fixture.controller.State.DISABLED, "Escape disables AI")
	_assert(
		fixture.bridge.disconnect_calls == disconnects_before_escape,
		"Escape keeps transport open until queued stop reaches sidecar",
	)
	var stop_packets: Array = fixture.bridge.sent_packets.filter(
		func(packet: Dictionary) -> bool: return packet.get("type") == "stop"
	)
	_assert(stop_packets.size() == 1, "Escape sends exactly one stop packet")
	if stop_packets.size() == 1:
		_assert(stop_packets[0].get("reason") == "escape_stop", "Escape reports stable stop reason")
	var previous_connects: int = fixture.bridge.connect_calls.size()
	fixture.controller._process(10.0)
	_assert(fixture.bridge.connect_calls.size() == previous_connects, "Escape stop prevents reconnect")
	fixture.controller.enable_ai()
	_assert(fixture.bridge.connect_calls.size() == previous_connects + 1, "explicit enable resumes after Escape")
	await _free_fixture(fixture)


func _test_reusable_scene() -> void:
	var packed: PackedScene = load("res://addons/cogito/AIPlay/ai_play_controller.tscn")
	_assert(packed != null, "controller scene loads")
	if packed == null:
		return
	var controller: Node = packed.instantiate()
	_assert(controller.get_child_count() == 5, "controller scene has five children")
	_assert(
		controller.get_node_or_null("InteractionProbe") != null,
		"controller scene includes interaction probe",
	)
	_assert(controller.get_node_or_null("Observer") != null, "controller scene has observer")
	_assert(controller.get_node_or_null("Executor") != null, "controller scene has executor")
	_assert(controller.get_node_or_null("Bridge") != null, "controller scene has bridge")
	var timer: Timer = controller.get_node_or_null("ObservationTimer")
	_assert(timer != null and timer.one_shot, "controller scene has one-shot observation timer")
	_assert(controller.auto_start == false, "controller scene does not auto-start")
	_assert(controller.host == "127.0.0.1" and controller.port == 8765, "controller scene uses loopback defaults")
	_assert(controller.player == null, "controller scene requires explicit player wiring")
	controller.free()


func _test_teardown_releases_without_late_signal() -> void:
	var packed: PackedScene = load("res://addons/cogito/AIPlay/ai_play_controller.tscn")
	var controller: Node = packed.instantiate()
	root.add_child(controller)
	await process_frame
	var executor: Node = controller.get_node("Executor")
	var emitted: Array = []
	executor.batch_finished.connect(
		func(results: Array) -> void: emitted.append(results.duplicate(true))
	)
	for action_name: String in ["forward", "back", "left", "right", "sprint"]:
		Input.action_press(action_name)
		executor.held_actions[action_name] = true
	controller.queue_free()
	await process_frame
	for action_name: String in ["forward", "back", "left", "right", "sprint"]:
		_assert(not Input.is_action_pressed(action_name), "controller teardown releases %s" % action_name)
		Input.action_release(action_name)
	_assert(emitted.is_empty(), "controller teardown emits no late batch")


func _test_bridge_teardown_disconnects() -> void:
	var bridge := AIPlayBridge.new()
	root.add_child(bridge)
	await process_frame
	bridge._socket = WebSocketPeer.new()
	_assert(bridge._socket != null, "bridge teardown fixture owns a socket")
	bridge._exit_tree()
	_assert(bridge._socket == null, "bridge teardown closes its socket")
	bridge.queue_free()
	await process_frame


func _make_fixture(controller_script: GDScript) -> Dictionary:
	var controller: Node = controller_script.new()
	controller.auto_start = false
	controller.host = "127.0.0.1"
	controller.port = 8765
	var player_script: GDScript = load("res://addons/cogito/CogitoObjects/cogito_player.gd")
	var player: Node3D = player_script.new()
	controller.player = player
	var observer := FakeObserver.new()
	observer.name = "Observer"
	var executor := FakeExecutor.new()
	executor.name = "Executor"
	var interaction_probe := FakeInteractionProbe.new()
	interaction_probe.name = "InteractionProbe"
	var terminal_monitor := FakeTerminalMonitor.new()
	terminal_monitor.name = "TerminalMonitor"
	var bridge := FakeBridge.new()
	bridge.name = "Bridge"
	var timer := Timer.new()
	timer.name = "ObservationTimer"
	timer.one_shot = true
	controller.add_child(observer)
	controller.add_child(executor)
	controller.add_child(interaction_probe)
	controller.add_child(terminal_monitor)
	controller.add_child(bridge)
	controller.add_child(timer)
	root.add_child(controller)
	await process_frame
	return {
		"controller": controller,
		"observer": observer,
		"executor": executor,
		"interaction_probe": interaction_probe,
		"terminal_monitor": terminal_monitor,
		"bridge": bridge,
		"timer": timer,
		"player": player,
	}


func _connected_fixture(
	controller_script: GDScript,
	scenario_id: String = "find_contract",
) -> Dictionary:
	var fixture: Dictionary = await _make_fixture(controller_script)
	fixture.controller._active_scenario_id = scenario_id
	fixture.terminal_monitor.scenario_id = scenario_id
	fixture.controller.enable_ai()
	fixture.bridge.connected.emit()
	return fixture


func _free_fixture(fixture: Dictionary) -> void:
	fixture.controller.queue_free()
	await process_frame
	fixture.player.free()


func _finish() -> void:
	if _failures.is_empty():
		print("AIPlay controller tests passed")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
