extends SceneTree

var _failures: Array[String] = []


class FakeObserver extends Node:
	var capture_count: int = 0
	var capture_events: Array = []
	var next_observation_id: int = 17

	func get_bindings() -> Dictionary:
		return {"forward": "W", "interact": "F"}

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
	var execute_calls: Array[Dictionary] = []
	var cancel_reasons: Array[String] = []

	func execute_batch(actions: Array, context: Dictionary) -> void:
		execute_calls.append({"actions": actions.duplicate(true), "context": context.duplicate(true)})

	func cancel_all(reason: String) -> void:
		cancel_reasons.append(reason)


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	var controller_script: GDScript = load("res://addons/cogito/AIPlay/ai_play_controller.gd")
	_assert(controller_script != null, "controller script exists")
	if controller_script == null:
		_finish()
		return

	_test_bridge_raw_json_packets()
	_test_user_arg_opt_in(controller_script)
	_test_bridge_requires_exact_loopback()
	await _test_enable_and_hello(controller_script)
	await _test_action_results_are_reported(controller_script)
	await _test_observation_id_gate(controller_script)
	await _test_stopped_batch_disables_without_recapture(controller_script)
	await _test_blocked_batch_recaptures_immediately(controller_script)
	await _test_context_change_recaptures_immediately(controller_script)
	await _test_deferred_recapture_is_cancelled_by_teardown(controller_script)
	await _test_transport_failures_cancel(controller_script)
	await _test_invalid_model_decision_retries(controller_script)
	await _test_non_escape_input_keeps_ai(controller_script)
	await _test_escape_stops_ai(controller_script)
	await _test_reusable_scene()
	await _test_teardown_releases_without_late_signal()
	await _test_bridge_teardown_disconnects()
	_finish()


func _test_user_arg_opt_in(controller_script: GDScript) -> void:
	var controller: Node = controller_script.new()
	_assert(controller.has_method("_should_enable_for_user_args"), "controller exposes opt-in predicate")
	if controller.has_method("_should_enable_for_user_args"):
		_assert(not controller._should_enable_for_user_args([]), "ordinary launch stays disabled")
		_assert(controller._should_enable_for_user_args(["--ai-play"]), "exact user arg enables AI")
		for args: Array in [["ai-play"], ["--ai-play=true"], ["--AI-PLAY"]]:
			_assert(not controller._should_enable_for_user_args(args), "similar user arg does not enable AI")
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


func _test_bridge_raw_json_packets() -> void:
	var bridge_script: GDScript = load("res://addons/cogito/AIPlay/ai_play_bridge.gd")
	var bridge: Node = bridge_script.new()
	var batches: Array[Dictionary] = []
	var errors: Array[Dictionary] = []
	bridge.action_batch_received.connect(func(batch: Dictionary) -> void: batches.append(batch))
	bridge.remote_error.connect(func(error: Dictionary) -> void: errors.append(error))
	bridge._handle_text_packet('{"type":"hello","protocol_version":1}')
	_assert(errors.is_empty(), "raw JSON hello accepts numeric protocol version one")
	bridge._handle_text_packet(
		'{"type":"action_batch","protocol_version":1,"observation_id":7,"actions":[]}'
	)
	_assert(batches.size() == 1, "raw JSON action batch emits through bridge")
	for invalid_packet: String in [
		'{"type":"hello","protocol_version":true}',
		'{"type":"hello","protocol_version":"1"}',
		'{"type":"hello","protocol_version":1.5}',
		'{"type":"hello","protocol_version":NaN}',
	]:
		var previous_errors: int = errors.size()
		bridge._handle_text_packet(invalid_packet)
		_assert(errors.size() == previous_errors + 1, "raw JSON rejects invalid protocol version")
	bridge.free()


func _test_enable_and_hello(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _make_fixture(controller_script)
	var controller: Node = fixture.controller
	var bridge: FakeBridge = fixture.bridge
	controller.enable_ai()
	_assert(fixture.executor.player == fixture.player, "controller wires real player into executor")
	_assert(bridge.connect_calls == [{"host": "127.0.0.1", "port": 8765}], "enabling connects")
	bridge.connected.emit()
	_assert(not bridge.sent_packets.is_empty(), "connection sends hello")
	if not bridge.sent_packets.is_empty():
		var hello: Dictionary = bridge.sent_packets[0]
		_assert(hello.get("type") == "hello", "first packet is hello")
		_assert(hello.get("protocol_version") == 1, "hello uses protocol version one")
		_assert(hello.get("bindings") == {"forward": "W", "interact": "F"}, "hello contains bindings")
		_assert(hello.get("data_dir") == OS.get_user_data_dir(), "hello contains user data directory")
		_assert("res://" not in JSON.stringify(hello), "hello contains no repository path")
	await _free_fixture(fixture)


func _test_stopped_batch_disables_without_recapture(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var initial_capture_count: int = fixture.observer.capture_count
	var initial_disconnect_count: int = fixture.bridge.disconnect_calls
	fixture.bridge.action_batch_received.emit({
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
			"protocol_version": 1,
			"observation_id": 17,
			"results": results,
		}, "action-results packet preserves observation correlation and results")
	await _free_fixture(fixture)


func _test_blocked_batch_recaptures_immediately(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var initial_capture_count: int = fixture.observer.capture_count
	fixture.bridge.action_batch_received.emit({
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
		fixture.observer.capture_count == initial_capture_count + 1,
		"blocked result triggers immediate deferred recapture",
	)
	await _free_fixture(fixture)


func _test_context_change_recaptures_immediately(controller_script: GDScript) -> void:
	for action_type: String in ["interact", "enter_digits", "close_ui"]:
		var fixture: Dictionary = await _connected_fixture(controller_script)
		var initial_capture_count: int = fixture.observer.capture_count
		fixture.bridge.action_batch_received.emit({
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
			fixture.observer.capture_count == initial_capture_count + 1,
			"%s triggers immediate deferred recapture" % action_type,
		)
		await _free_fixture(fixture)


func _test_deferred_recapture_is_cancelled_by_teardown(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var capture_events: Array = fixture.observer.capture_events
	var sent_packets: Array = fixture.bridge.sent_packets
	fixture.bridge.action_batch_received.emit({
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
		"observation_id": 17.0,
		"actions": [{"type": "wait", "duration_ms": 50}],
	})
	_assert(executor.execute_calls.size() == 1, "matching parsed numeric observation ID executes")
	executor.batch_finished.emit([{"status": "completed"}])
	fixture.observer.next_observation_id = 18
	fixture.timer.emit_signal("timeout")
	bridge.action_batch_received.emit({
		"observation_id": 18.5,
		"actions": [{"type": "stop"}],
	})
	_assert(executor.execute_calls.size() == 1, "fractional observation ID does not execute")
	_assert("stale_observation" in executor.cancel_reasons, "invalid observation ID cancels")
	await _free_fixture(fixture)

	var boolean_fixture: Dictionary = await _connected_fixture(controller_script)
	boolean_fixture.bridge.action_batch_received.emit({"observation_id": true, "actions": []})
	_assert(boolean_fixture.executor.execute_calls.is_empty(), "boolean observation ID does not execute")
	_assert("stale_observation" in boolean_fixture.executor.cancel_reasons, "boolean observation ID cancels")
	await _free_fixture(boolean_fixture)

	var stale_fixture: Dictionary = await _connected_fixture(controller_script)
	stale_fixture.bridge.action_batch_received.emit({"observation_id": 16.0, "actions": []})
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


func _test_invalid_model_decision_retries(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	fixture.bridge.remote_error.emit({"code": "decision_failed", "message": "JSONDecodeError"})
	_assert(
		fixture.controller.get_state() == fixture.controller.State.READY,
		"invalid model decision keeps autonomous session ready",
	)
	_assert(not fixture.timer.is_stopped(), "invalid model decision schedules another observation")
	_assert(fixture.executor.cancel_reasons.is_empty(), "invalid model decision has no action to cancel")
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
	_assert(controller.get_child_count() == 4, "controller scene has four children")
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
	var bridge := FakeBridge.new()
	bridge.name = "Bridge"
	var timer := Timer.new()
	timer.name = "ObservationTimer"
	timer.one_shot = true
	controller.add_child(observer)
	controller.add_child(executor)
	controller.add_child(bridge)
	controller.add_child(timer)
	root.add_child(controller)
	await process_frame
	return {
		"controller": controller,
		"observer": observer,
		"executor": executor,
		"bridge": bridge,
		"timer": timer,
		"player": player,
	}


func _connected_fixture(controller_script: GDScript) -> Dictionary:
	var fixture: Dictionary = await _make_fixture(controller_script)
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
