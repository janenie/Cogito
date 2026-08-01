extends SceneTree

var failures: Array[String] = []
var _test_scene_root: Node


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	_ensure_current_scene()
	var probe_script := load("res://addons/cogito/AIPlay/ai_play_home_interaction_probe.gd")
	var probe: Node = probe_script.new()
	root.add_child(probe)
	var rotation: Vector2 = probe.target_rotation_degrees(0.5, 0.5, 75.0, 16.0 / 9.0)
	_assert(rotation.length() < 0.001, "center target has zero rotation")
	probe.queue_free()
	if _test_scene_root != null:
		_test_scene_root.queue_free()
	await process_frame
	_finish()


func _ensure_current_scene() -> void:
	if current_scene != null:
		return
	_test_scene_root = Node.new()
	_test_scene_root.name = "HomeAIPlayProbeHeadlessTestScene"
	root.add_child(_test_scene_root)
	current_scene = _test_scene_root


func _finish() -> void:
	if failures.is_empty():
		print("Home AI Play interaction probe test passed")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)
