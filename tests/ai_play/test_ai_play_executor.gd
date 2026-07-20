extends SceneTree

const AIPlayExecutor = preload("res://addons/cogito/AIPlay/ai_play_executor.gd")

var _failures: Array[String] = []


class InputRecorder extends Node:
	var events: Array[InputEvent] = []

	func _input(event: InputEvent) -> void:
		events.append(event)


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
		"type": "move",
		"forward": 1.0,
		"right": 0.0,
		"duration_ms": 1001,
	}, {}, "movement over 1000 ms")
	_assert_invalid(executor, {
		"type": "interact",
		"action": "interact",
	}, {"available_interactions": ["interact2"]}, "non-visible interaction")
	_assert_invalid(executor, {
		"type": "enter_digits",
		"digits": "1234",
	}, {"interface_open": false}, "digits with closed interface")
	_test_batch_validation(executor, recorder)
	_test_terminal_stop(executor)
	await _test_blocked_movement(executor, recorder)
	await _test_teardown_releases_without_signal()

	for action_name: String in ["forward", "back", "left", "right", "sprint"]:
		Input.action_press(action_name)
		executor.held_actions[action_name] = true
	executor.cancel_all("test cancellation")
	for action_name: String in ["forward", "back", "left", "right", "sprint"]:
		_assert(not Input.is_action_pressed(action_name), "cancel_all releases %s" % action_name)

	recorder.events.clear()
	executor.execute_batch([{"type": "look", "yaw": 2.0, "pitch": -1.0}], {})
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
		{"actions": [{"type": "stop"}, {"type": "look", "yaw": 1.0, "pitch": 0.0}], "context": {}},
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
		[{"type": "stop"}, {"type": "look", "yaw": 1.0, "pitch": 0.0}],
		{},
	)
	_assert(
		emitted == [[{"status": "error", "error": "context-changing action must be last"}]],
		"invalid batch emits one exact error result",
	)
	_assert(recorder.events.is_empty(), "invalid batch performs no input")
	executor.batch_finished.disconnect(collect)


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
		{"type": "look", "yaw": 2.0, "pitch": -1.0},
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


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
