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
