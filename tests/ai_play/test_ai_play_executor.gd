extends SceneTree

const AIPlayExecutor = preload("res://addons/cogito/AIPlay/ai_play_executor.gd")

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	var executor: Node = AIPlayExecutor.new()
	root.add_child(executor)

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

	executor.queue_free()
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


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
