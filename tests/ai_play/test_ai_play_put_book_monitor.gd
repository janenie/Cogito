extends SceneTree

var _failures: Array[String] = []
var _test_scene_root: Node


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	_ensure_current_scene()
	var lobby_scene: PackedScene = load(
		"res://addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
	)
	_assert(lobby_scene != null, "Lobby scene loads")
	if lobby_scene == null:
		_finish()
		return

	var lobby: Node = lobby_scene.instantiate()
	root.add_child(lobby)
	await process_frame

	var monitor: Node = lobby.get_node_or_null(
		"AIPlayController/PutBookMonitor"
	)
	_assert(monitor != null, "Lobby includes PutBookMonitor")
	if monitor == null:
		lobby.queue_free()
		await process_frame
		_finish()
		return

	var seen_books: Array[String] = []
	var seen_boxes: Array[String] = []
	for seed_value: int in range(1, 129):
		monitor.configure_round(seed_value)
		var snapshot: Dictionary = monitor.get_round_snapshot()
		_assert(snapshot["book"] != "", "a visible archive book is selected")
		_assert(snapshot["box"] in ["near", "far"], "target box is near or far")
		_assert(
			String(snapshot["task_text"]).contains("纸箱"),
			"task card describes the box objective",
		)
		_assert(
			monitor.carried_book.visible,
			"selected book is represented by one carryable book",
		)
		for static_book: Node3D in monitor._book_candidates():
			_assert(
				not static_book.visible,
				"static book candidates are hidden after selection",
			)
		_assert(
			not monitor.archive_door.is_locked and monitor.archive_door.is_open,
			"archive door is open for put_book",
		)
		var task_distance: float = (
			monitor.player.global_position.distance_to(
				monitor.task_card.get_parent_node_3d().global_position
			)
		)
		_assert(
			task_distance >= 1.0 and task_distance <= 2.0,
			"the task card remains one to two meters from spawn",
		)
		if snapshot["book"] not in seen_books:
			seen_books.append(snapshot["book"])
		if snapshot["box"] not in seen_boxes:
			seen_boxes.append(snapshot["box"])

	_assert(seen_boxes.size() == 2, "fixed seed sample reaches both box anchors")
	_assert(seen_books.size() >= 2, "fixed seed sample selects multiple books")

	monitor.configure_round(123456)
	var terminal_results: Array[Dictionary] = []
	monitor.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_results.append({
				"outcome": outcome,
				"reason": reason,
			})
	)
	monitor._on_target_box_body_entered(monitor.carried_book)
	monitor._on_target_box_body_entered(monitor.carried_book)
	_assert(
		terminal_results == [{
			"outcome": "success",
			"reason": "book_in_box",
		}],
		"book entering the target box ends the round exactly once",
	)

	lobby.queue_free()
	if _test_scene_root != null:
		_test_scene_root.queue_free()
	await process_frame
	_finish()


func _ensure_current_scene() -> void:
	if current_scene != null:
		return
	_test_scene_root = Node.new()
	_test_scene_root.name = "AIPlayHeadlessTestScene"
	root.add_child(_test_scene_root)
	current_scene = _test_scene_root


func _finish() -> void:
	if _failures.is_empty():
		print("AIPlay put-book monitor test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
