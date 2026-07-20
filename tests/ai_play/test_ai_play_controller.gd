extends SceneTree

var _failures: Array[String] = []


class FakeObserver extends Node:
	var capture_count: int = 0
	var next_observation_id: int = 17

	func get_bindings() -> Dictionary:
		return {"forward": "W", "interact": "F"}

	func capture_observation(last_results: Array) -> Dictionary:
		capture_count += 1
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

	await _test_enable_and_hello(controller_script)
	await _test_observation_id_gate(controller_script)
	await _test_transport_failures_cancel(controller_script)
	await _test_human_takeover(controller_script)
	await _test_emergency_stop_latches(controller_script)
	await _test_reusable_scene()
	_finish()


func _test_enable_and_hello(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _make_fixture(controller_script)
	var controller: Node = fixture.controller
	var bridge: FakeBridge = fixture.bridge
	controller.enable_ai()
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


func _test_observation_id_gate(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var bridge: FakeBridge = fixture.bridge
	var executor: FakeExecutor = fixture.executor
	bridge.action_batch_received.emit({
		"observation_id": 17,
		"actions": [{"type": "wait", "duration_ms": 50}],
	})
	_assert(executor.execute_calls.size() == 1, "matching observation ID executes")
	executor.batch_finished.emit([{"status": "completed"}])
	fixture.observer.next_observation_id = 18
	fixture.timer.emit_signal("timeout")
	bridge.action_batch_received.emit({
		"observation_id": 17,
		"actions": [{"type": "stop"}],
	})
	_assert(executor.execute_calls.size() == 1, "stale observation ID does not execute")
	_assert("stale_observation" in executor.cancel_reasons, "stale observation ID cancels")
	await _free_fixture(fixture)


func _test_transport_failures_cancel(controller_script: GDScript) -> void:
	var disconnected_fixture: Dictionary = await _connected_fixture(controller_script)
	disconnected_fixture.bridge.disconnected.emit("socket_closed")
	_assert("socket_closed" in disconnected_fixture.executor.cancel_reasons, "disconnect cancels executor")
	await _free_fixture(disconnected_fixture)

	var error_fixture: Dictionary = await _connected_fixture(controller_script)
	error_fixture.bridge.remote_error.emit({"code": "api_failure", "message": "failed"})
	_assert("remote_error:api_failure" in error_fixture.executor.cancel_reasons, "remote error cancels executor")
	await _free_fixture(error_fixture)


func _test_human_takeover(controller_script: GDScript) -> void:
	var key_fixture: Dictionary = await _connected_fixture(controller_script)
	var key := InputEventKey.new()
	key.physical_keycode = KEY_W
	key.pressed = true
	key.device = 0
	key_fixture.controller._input(key)
	_assert(key_fixture.controller.get_state() == key_fixture.controller.State.DISABLED, "physical movement pauses AI")
	await _free_fixture(key_fixture)

	var mouse_fixture: Dictionary = await _connected_fixture(controller_script)
	var mouse := InputEventMouseMotion.new()
	mouse.relative = Vector2(3.0, -2.0)
	mouse.device = 0
	mouse_fixture.controller._input(mouse)
	_assert(mouse_fixture.controller.get_state() == mouse_fixture.controller.State.DISABLED, "physical mouse movement pauses AI")
	await _free_fixture(mouse_fixture)

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


func _test_emergency_stop_latches(controller_script: GDScript) -> void:
	var fixture: Dictionary = await _connected_fixture(controller_script)
	var emergency := InputEventKey.new()
	emergency.keycode = KEY_F12
	emergency.pressed = true
	emergency.device = 0
	fixture.controller._input(emergency)
	_assert(fixture.controller.get_state() == fixture.controller.State.DISABLED, "emergency stop disables AI")
	var previous_connects: int = fixture.bridge.connect_calls.size()
	fixture.controller._process(10.0)
	_assert(fixture.bridge.connect_calls.size() == previous_connects, "emergency stop prevents reconnect")
	fixture.controller.enable_ai()
	_assert(fixture.bridge.connect_calls.size() == previous_connects + 1, "explicit enable clears emergency latch")
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


func _make_fixture(controller_script: GDScript) -> Dictionary:
	var controller: Node = controller_script.new()
	controller.auto_start = false
	controller.host = "127.0.0.1"
	controller.port = 8765
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
	return {"controller": controller, "observer": observer, "executor": executor, "bridge": bridge, "timer": timer}


func _connected_fixture(controller_script: GDScript) -> Dictionary:
	var fixture: Dictionary = await _make_fixture(controller_script)
	fixture.controller.enable_ai()
	fixture.bridge.connected.emit()
	return fixture


func _free_fixture(fixture: Dictionary) -> void:
	fixture.controller.queue_free()
	await process_frame


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
