extends SceneTree

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	var scene_host := Node.new()
	scene_host.name = "KeypadTestScene"
	root.add_child(scene_host)
	current_scene = scene_host
	var keypad_scene: PackedScene = load("res://addons/cogito/PackedScenes/keypad_prefab.tscn")
	_assert(keypad_scene != null, "keypad scene loads")
	if keypad_scene == null:
		_finish()
		return

	var correct_keypad: Node = keypad_scene.instantiate()
	correct_keypad.passcode = "12"
	root.add_child(correct_keypad)
	await process_frame
	_assert(correct_keypad.has_signal("code_checked"), "keypad exposes code_checked signal")
	var correct_results: Array[bool] = []
	if correct_keypad.has_signal("code_checked"):
		correct_keypad.code_checked.connect(
			func(is_correct: bool) -> void: correct_results.append(is_correct)
		)
		correct_keypad.entered_code = "12"
		correct_keypad.check_entered_code()
	_assert(correct_results == [true], "correct code emits true exactly once")

	var wrong_keypad: Node = keypad_scene.instantiate()
	wrong_keypad.passcode = "12"
	root.add_child(wrong_keypad)
	await process_frame
	var wrong_results: Array[bool] = []
	if wrong_keypad.has_signal("code_checked"):
		wrong_keypad.code_checked.connect(
			func(is_correct: bool) -> void: wrong_results.append(is_correct)
		)
		wrong_keypad.entered_code = "34"
		wrong_keypad.check_entered_code()
	_assert(wrong_results == [false], "wrong code emits false exactly once")

	correct_keypad.queue_free()
	wrong_keypad.queue_free()
	await process_frame
	scene_host.queue_free()
	await process_frame
	_finish()


func _finish() -> void:
	if _failures.is_empty():
		print("Cogito keypad result tests passed")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
