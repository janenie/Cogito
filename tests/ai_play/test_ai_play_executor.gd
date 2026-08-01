extends SceneTree

const AIPlayExecutor = preload("res://addons/cogito/AIPlay/ai_play_executor.gd")
const HomeRobotPlayerScript = preload("res://dailyroutine/scripts/home_robot_player.gd")

var _failures: Array[String] = []


class InputRecorder extends Node:
	var events: Array[InputEvent] = []

	func _input(event: InputEvent) -> void:
		events.append(event)


class FakeCogitoPlayer extends Node3D:
	var MOUSE_SENS := 0.25
	var INVERT_Y_AXIS := true


class FakeSemanticActionProvider extends Node:
	var received: Array[Dictionary] = []

	func execute_semantic_action(action: Dictionary) -> Dictionary:
		received.append(action.duplicate(true))
		var result := {
			"status": "completed",
			"type": action["type"],
			"outcome": "selected" if action["type"] == "select_ingredient" else "accepted",
		}
		if action["type"] == "select_ingredient":
			result["ingredient"] = action["ingredient"]
		return result


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	var executor: Node = AIPlayExecutor.new()
	root.add_child(executor)
	var recorder := InputRecorder.new()
	root.add_child(recorder)
	await process_frame

	_assert_invalid(executor, {"type": "teleport"}, {}, "unknown action")
	_assert_invalid(executor, {
		"type": "look",
		"yaw": 15.0,
		"pitch": 0.0,
	}, {}, "legacy numeric look")
	_assert_invalid(executor, {
		"type": "look",
		"direction": "left",
		"degrees": 0.0,
	}, {}, "zero-degree semantic look")
	_assert_invalid(executor, {
		"type": "look",
		"direction": "left",
		"degrees": 45.1,
	}, {}, "semantic look over 45 degrees")
	_assert_invalid(executor, {
		"type": "look",
		"direction": "north",
		"degrees": 15.0,
	}, {}, "unknown semantic look direction")
	var semantic_look_cases: Array[Dictionary] = [
		{"action": {"type": "look", "direction": "left", "degrees": 30}, "delta": Vector2(-30, 0)},
		{"action": {"type": "look", "direction": "right", "degrees": 30}, "delta": Vector2(30, 0)},
		{"action": {"type": "look", "direction": "up", "degrees": 15}, "delta": Vector2(0, -15)},
		{"action": {"type": "look", "direction": "down", "degrees": 15}, "delta": Vector2(0, 15)},
	]
	for test_case: Dictionary in semantic_look_cases:
		var action: Dictionary = test_case["action"]
		_assert(executor.validate_action(action, {}).get("valid", false), "accepts semantic look")
		_assert(
			executor._semantic_look_delta(action["direction"], action["degrees"]) == test_case["delta"],
			"maps semantic look direction",
		)
	_assert_invalid(executor, {
		"type": "move",
		"forward": 1.0,
		"right": 0.0,
		"duration_ms": 251,
	}, {}, "movement over 250 ms")
	_assert_invalid(executor, {
		"type": "sprint",
		"forward": 1.0,
		"right": 0.0,
		"duration_ms": 251,
	}, {}, "sprint over 250 ms")
	_assert_invalid(executor, {
		"type": "interact",
		"action": "interact",
	}, {"available_interactions": ["interact2"]}, "non-visible interaction")
	_assert_invalid(executor, {
		"type": "enter_digits",
		"digits": "1234",
	}, {"interface_open": false}, "digits with closed interface")
	var probe_action := {
		"type": "probe_interaction",
		"target_x": 0.25,
		"target_y": 0.75,
	}
	_assert(
		executor.validate_batch([probe_action], {"interface_open": false}) == {"valid": true},
		"accepts one normalized probe with closed interface",
	)
	_assert_invalid(executor, {
		"type": "probe_interaction",
		"target_x": -0.1,
		"target_y": 0.5,
	}, {"interface_open": false}, "probe coordinate outside image")
	_assert_invalid(
		executor,
		probe_action,
		{"interface_open": true},
		"probe with open interface",
	)
	_assert(
		not executor.validate_batch(
			[probe_action, {"type": "wait", "duration_ms": 50}],
			{"interface_open": false},
		).get("valid", false),
		"probe must be the only action",
	)
	_test_batch_validation(executor, recorder)
	await _test_conveyor_semantic_actions(executor)
	_test_terminal_stop(executor)
	await _test_blocked_movement(executor, recorder)
	await _test_look_angles_scale_for_home_player(executor, recorder)
	await _test_home_player_look_is_applied_directly(executor, recorder)
	await _test_look_angles_scale_for_cogito_player(executor)
	await _test_teardown_releases_without_signal()

	for action_name: String in ["forward", "back", "left", "right", "sprint"]:
		Input.action_press(action_name)
		executor.held_actions[action_name] = true
	executor.cancel_all("test cancellation")
	for action_name: String in ["forward", "back", "left", "right", "sprint"]:
		_assert(not Input.is_action_pressed(action_name), "cancel_all releases %s" % action_name)

	recorder.events.clear()
	executor.execute_batch([{"type": "look", "direction": "up", "degrees": 2.0}], {})
	await process_frame
	_assert(
		_all_events_of_type_use_device(recorder.events, InputEventMouseMotion, executor.SYNTHETIC_DEVICE_ID),
		"synthetic mouse events use the dedicated device ID",
	)
	recorder.events.clear()
	executor._emit_action_pair("jump")
	await process_frame
	_assert(
		_all_events_of_type_use_device(recorder.events, InputEventAction, executor.SYNTHETIC_DEVICE_ID),
		"synthetic action events use the dedicated device ID",
	)
	recorder.events.clear()
	executor._emit_digit_pair("7")
	await process_frame
	_assert(
		_all_events_of_type_use_device(recorder.events, InputEventKey, executor.SYNTHETIC_DEVICE_ID),
		"synthetic key events use the dedicated device ID",
	)

	executor.queue_free()
	recorder.queue_free()
	if _failures.is_empty():
		print("AIPlay executor tests passed")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _assert_invalid(executor: Node, action: Dictionary, context: Dictionary, label: String) -> void:
	var result: Dictionary = executor.validate_action(action, context)
	_assert(not result.get("valid", false), "rejects %s" % label)


func _test_batch_validation(executor: Node, recorder: InputRecorder) -> void:
	for invalid_size: Variant in [[], [{"type": "wait", "duration_ms": 50}] + [
		{"type": "stop"},
		{"type": "stop"},
		{"type": "stop"},
	]]:
		var size_result: Dictionary = executor.validate_batch(invalid_size, {})
		_assert(not size_result.get("valid", false), "batch size must be one to three")

	var context_cases: Array[Dictionary] = [
		{"actions": [{"type": "stop"}, {"type": "look", "direction": "left", "degrees": 1.0}], "context": {}},
		{
			"actions": [
				{"type": "interact", "action": "interact"},
				{"type": "wait", "duration_ms": 50},
			],
			"context": {"available_interactions": ["interact"]},
		},
		{
			"actions": [
				{"type": "enter_digits", "digits": "1"},
				{"type": "wait", "duration_ms": 50},
			],
			"context": {"interface_open": true},
		},
		{
			"actions": [{"type": "close_ui"}, {"type": "wait", "duration_ms": 50}],
			"context": {"interface_open": true},
		},
	]
	for test_case: Dictionary in context_cases:
		var batch_result: Dictionary = executor.validate_batch(
			test_case["actions"], test_case["context"]
		)
		_assert(
			batch_result == {"valid": false, "error": "context-changing action must be last"},
			"context-changing action must be last",
		)

	var emitted: Array = []
	var collect := func(results: Array) -> void: emitted.append(results.duplicate(true))
	executor.batch_finished.connect(collect)
	recorder.events.clear()
	executor.execute_batch(
		[{"type": "stop"}, {"type": "look", "direction": "left", "degrees": 1.0}],
		{},
	)
	_assert(
		emitted == [[{"status": "error", "error": "context-changing action must be last"}]],
		"invalid batch emits one exact error result",
	)
	_assert(recorder.events.is_empty(), "invalid batch performs no input")
	executor.batch_finished.disconnect(collect)


func _test_conveyor_semantic_actions(executor: Node) -> void:
	_assert("active_scenario_id" in executor, "executor exposes active scenario")
	_assert("semantic_action_provider" in executor, "executor exposes semantic provider")
	if not "active_scenario_id" in executor or not "semantic_action_provider" in executor:
		return
	var provider := FakeSemanticActionProvider.new()
	root.add_child(provider)
	executor.active_scenario_id = "conveyor_profit"
	executor.semantic_action_provider = provider
	var actions: Array = [
		{"type": "select_ingredient", "ingredient": "tomato"},
		{"type": "make"},
	]
	_assert(executor.validate_batch(actions, {}) == {"valid": true}, "conveyor batch validates")
	executor.active_scenario_id = "find_contract"
	_assert(
		not executor.validate_action({"type": "undo"}, {}).get("valid", false),
		"other scenarios reject conveyor action",
	)
	executor.active_scenario_id = "conveyor_profit"
	_assert(
		executor.validate_batch([{"type": "wait_next_window"}], {}) == {"valid": true},
		"conveyor wait-next-window validates",
	)
	_assert(
		not executor.validate_batch([
			{"type": "undo"},
			{"type": "wait_next_window"},
		], {}).get("valid", false),
		"wait-next-window must be the only action",
	)
	var emitted: Array = []
	var collect := func(results: Array) -> void: emitted.append(results.duplicate(true))
	executor.batch_finished.connect(collect)
	executor.execute_batch(actions, {})
	await process_frame
	_assert(provider.received == actions, "semantic actions preserve order")
	_assert(emitted.size() == 1 and emitted[0].size() == 2, "semantic results are emitted")
	executor.batch_finished.disconnect(collect)
	provider.queue_free()


func _test_terminal_stop(executor: Node) -> void:
	var emitted: Array = []
	var collect := func(results: Array) -> void: emitted.append(results.duplicate(true))
	executor.batch_finished.connect(collect)
	executor.execute_batch([{"type": "stop"}], {})
	_assert(
		emitted == [[{"status": "stopped", "type": "stop"}]],
		"stop emits one exact terminal result",
	)
	executor.batch_finished.disconnect(collect)


func _test_blocked_movement(executor: Node, recorder: InputRecorder) -> void:
	if not "player" in executor:
		_assert(false, "executor exposes a player for displacement checks")
		return
	_assert(
		is_equal_approx(executor.blocked_distance_threshold, 0.05),
		"blocked distance threshold defaults to 0.05",
	)
	executor.blocked_distance_threshold = 0.0
	_assert(
		executor.has_method("_effective_blocked_distance_threshold")
		and is_equal_approx(executor._effective_blocked_distance_threshold(), 0.01),
		"zero blocked threshold is clamped to a positive minimum",
	)
	executor.blocked_distance_threshold = 0.05
	var static_player := Node3D.new()
	root.add_child(static_player)
	executor.player = static_player
	var emitted: Array = []
	var collect := func(results: Array) -> void: emitted.append(results.duplicate(true))
	executor.batch_finished.connect(collect)

	for action_type: String in ["move", "sprint"]:
		emitted.clear()
		executor.execute_batch([{
			"type": action_type,
			"forward": 1.0,
			"right": 0.0,
			"duration_ms": 50,
		}], {})
		await create_timer(0.08).timeout
		_assert(
			emitted == [[{"status": "blocked", "type": action_type}]],
			"static nonzero %s reports blocked" % action_type,
		)

	emitted.clear()
	executor.execute_batch([{
		"type": "move",
		"forward": 0.0,
		"right": 0.0,
		"duration_ms": 50,
	}], {})
	await create_timer(0.08).timeout
	_assert(
		emitted == [[{"status": "completed", "type": "move"}]],
		"zero-axis movement is a completed wait, not blocked",
	)

	emitted.clear()
	recorder.events.clear()
	executor.execute_batch([
		{
			"type": "move",
			"forward": 1.0,
			"right": 0.0,
			"duration_ms": 50,
		},
		{"type": "look", "direction": "up", "degrees": 2.0},
	], {})
	await create_timer(0.08).timeout
	_assert(
		emitted == [[{"status": "blocked", "type": "move"}]],
		"blocked movement terminates the batch",
	)
	for event: InputEvent in recorder.events:
		_assert(not event is InputEventMouseMotion, "blocked movement prevents later look input")

	executor.batch_finished.disconnect(collect)
	executor.player = null
	static_player.queue_free()
	await process_frame

	var null_player_results: Array = []
	var collect_null := func(results: Array) -> void: null_player_results.append(results.duplicate(true))
	executor.batch_finished.connect(collect_null)
	executor.execute_batch([{
		"type": "move",
		"forward": 1.0,
		"right": 0.0,
		"duration_ms": 50,
	}], {})
	await create_timer(0.08).timeout
	_assert(
		null_player_results == [[{"status": "completed", "type": "move"}]],
		"movement remains completed when player is unavailable",
	)
	executor.batch_finished.disconnect(collect_null)


func _test_look_angles_scale_for_home_player(executor: Node, recorder: InputRecorder) -> void:
	var home_player := HomeRobotPlayerScript.new()
	home_player.mouse_sensitivity = 0.0025
	root.add_child(home_player)
	executor.player = home_player
	var relative: Vector2 = executor._look_degrees_to_mouse_relative(45.0, -30.0)
	_assert(
		is_equal_approx(relative.x, deg_to_rad(45.0) / 0.0025),
		"home player look yaw is converted from degrees through mouse_sensitivity",
	)
	_assert(
		is_equal_approx(relative.y, deg_to_rad(-30.0) / 0.0025),
		"home player look pitch is converted from degrees through mouse_sensitivity",
	)

	executor.player = null
	home_player.queue_free()
	await process_frame


func _test_home_player_look_is_applied_directly(executor: Node, recorder: InputRecorder) -> void:
	var home_player := HomeRobotPlayerScript.new()
	var camera := Camera3D.new()
	camera.name = "Camera3D"
	camera.rotation_degrees.x = -15.0
	home_player.add_child(camera)
	root.add_child(home_player)
	await process_frame

	executor.player = home_player
	recorder.events.clear()
	var emitted: Array = []
	var collect := func(results: Array) -> void: emitted.append(results.duplicate(true))
	executor.batch_finished.connect(collect)
	executor.execute_batch([{"type": "look", "direction": "right", "degrees": 15.0}], {})
	await process_frame
	_assert(
		emitted == [[{"status": "completed", "type": "look"}]],
		"home player direct look reports completion",
	)
	_assert(
		is_equal_approx(home_player.global_rotation_degrees.y, -15.0),
		"home player direct look changes yaw by the requested degrees",
	)
	_assert(
		is_equal_approx(camera.rotation_degrees.x, -15.0),
		"home player direct look preserves pitch when pitch delta is zero",
	)
	for event: InputEvent in recorder.events:
		_assert(not event is InputEventMouseMotion, "home player direct look does not rely on mouse event dispatch")

	executor.batch_finished.disconnect(collect)
	executor.player = null
	home_player.queue_free()
	await process_frame


func _test_look_angles_scale_for_cogito_player(executor: Node) -> void:
	var cogito_player := FakeCogitoPlayer.new()
	cogito_player.MOUSE_SENS = 0.25
	executor.player = cogito_player

	var relative: Vector2 = executor._look_degrees_to_mouse_relative(45.0, -30.0)
	_assert(
		is_equal_approx(relative.x, 45.0 / 0.25),
		"cogito player look yaw is converted from degrees through MOUSE_SENS",
	)
	_assert(
		is_equal_approx(relative.y, 30.0 / 0.25),
		"inverted Cogito controls preserve semantic pitch direction",
	)
	cogito_player.INVERT_Y_AXIS = false
	relative = executor._look_degrees_to_mouse_relative(45.0, -30.0)
	_assert(
		is_equal_approx(relative.y, -30.0 / 0.25),
		"non-inverted Cogito controls preserve semantic pitch direction",
	)

	executor.player = null
	cogito_player.free()


func _test_teardown_releases_without_signal() -> void:
	var executor := AIPlayExecutor.new()
	root.add_child(executor)
	var emitted: Array = []
	executor.batch_finished.connect(
		func(results: Array) -> void: emitted.append(results.duplicate(true))
	)
	executor.execute_batch([{
		"type": "sprint",
		"forward": 1.0,
		"right": 1.0,
		"duration_ms": 50,
	}], {})
	_assert(Input.is_action_pressed("forward"), "teardown fixture holds forward")
	_assert(Input.is_action_pressed("right"), "teardown fixture holds right")
	_assert(Input.is_action_pressed("sprint"), "teardown fixture holds sprint")
	executor.queue_free()
	await process_frame
	await create_timer(0.08).timeout
	for action_name: String in ["forward", "back", "left", "right", "sprint"]:
		_assert(not Input.is_action_pressed(action_name), "teardown releases %s" % action_name)
		Input.action_release(action_name)
	_assert(emitted.is_empty(), "teardown emits no late batch result")


func _all_events_of_type_use_device(
	events: Array[InputEvent], event_type: Variant, expected_device: int
) -> bool:
	var found: bool = false
	for event: InputEvent in events:
		if is_instance_of(event, event_type):
			found = true
			if event.device != expected_device:
				return false
	return found


func _first_mouse_motion(events: Array[InputEvent]) -> InputEventMouseMotion:
	for event: InputEvent in events:
		if event is InputEventMouseMotion:
			return event
	return null


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
