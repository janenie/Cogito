extends SceneTree

var failures: Array[String] = []
var _test_scene_root: Node


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	_ensure_current_scene()
	var manager_script := load("res://dailyroutine/scripts/daily_routine_manager.gd")
	var monitor_script := load("res://dailyroutine/scripts/ai_play_daily_routine_monitor.gd")
	var manager: Node = manager_script.new()
	var monitor: Node = monitor_script.new()
	root.add_child(manager)
	monitor.manager = manager
	root.add_child(monitor)
	var results: Array[Dictionary] = []
	monitor.game_finished.connect(func(outcome: String, reason: String) -> void:
		results.append({"outcome": outcome, "reason": reason})
	)
	monitor._ready()
	manager.start_routine()
	manager.milk_drunk = true
	manager.collected_trash_count = manager.required_trash_count
	manager.submit_cleanup()
	_assert(
		results == [{"outcome": "success", "reason": "cleanup_complete"}],
		"routine completion emits success once",
	)
	manager.submit_cleanup()
	_assert(results.size() == 1, "monitor emits terminal result once")
	monitor.queue_free()
	manager.queue_free()
	if _test_scene_root != null:
		_test_scene_root.queue_free()
	await process_frame
	_finish()


func _ensure_current_scene() -> void:
	if current_scene != null:
		return
	_test_scene_root = Node.new()
	_test_scene_root.name = "DailyRoutineMonitorHeadlessTestScene"
	root.add_child(_test_scene_root)
	current_scene = _test_scene_root


func _finish() -> void:
	if failures.is_empty():
		print("Daily routine AI Play monitor test passed")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)
