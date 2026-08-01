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

	var monitor := lobby.get_node_or_null("AIPlayController/PutBookMonitor") as AIPlayPutBookMonitor
	_assert(monitor != null, "Lobby includes PutBookMonitor")
	if monitor == null:
		lobby.queue_free()
		await process_frame
		_finish()
		return

	var seen_layouts: Dictionary = {}
	for seed_value: int in range(1, 129):
		monitor.configure_round(seed_value)
		var snapshot: Dictionary = monitor.get_round_snapshot()
		if not snapshot.has("books"):
			_assert(false, "round setup returns book snapshot")
			break
		_assert(snapshot["books"].size() == 6, "round exposes six books")
		_assert(snapshot["target_order"].size() == 3, "round selects three targets")
		_assert(monitor._active_books.size() == 6, "six runtime books are active")
		_assert(monitor._target_books.size() == 3, "three runtime books are targets")
		_assert(_snapshot_tier_count(snapshot, "low") == 2, "snapshot has two low books")
		_assert(_snapshot_tier_count(snapshot, "middle") == 2, "snapshot has two middle books")
		_assert(_snapshot_tier_count(snapshot, "high") == 2, "snapshot has two high books")
		_assert(_target_tiers(snapshot) == ["low", "middle", "high"], "targets are ordered low to high")
		_assert(String(snapshot["task_text"]).contains("CEO OFFICE"), "task card names CEO OFFICE")
		_assert(not String(snapshot["task_text"]).contains("跳"), "task card removes jump rule")
		_assert(not String(snapshot["task_text"]).contains("蹲"), "task card removes crouch rule")
		_assert(not String(snapshot["task_text"]).contains("纸箱"), "task card removes box rule")
		var slot_ids: Array[String] = []
		for entry: Dictionary in snapshot["books"]:
			slot_ids.append(String(entry["slot"]))
		slot_ids.sort()
		seen_layouts["|".join(slot_ids)] = true
		for book: RigidBody3D in monitor._active_books:
			var marker := book.get_node_or_null("TargetMarker") as Label3D
			_assert(marker != null, "runtime book exposes target marker")
			_assert(
				marker != null and marker.visible == (book in monitor._target_books),
				"only target books show the marker",
			)
			var carry_component: Variant = book.get_node_or_null("CarryableComponent")
			_assert(carry_component != null and not carry_component.is_disabled, "all books start pickup-enabled")

	_assert(seen_layouts.size() > 1, "seed sample produces multiple occupied layouts")

	monitor.configure_round(73421)
	var first_snapshot: Dictionary = monitor.get_round_snapshot()
	monitor.configure_round(73421)
	var second_snapshot: Dictionary = monitor.get_round_snapshot()
	_assert(first_snapshot["books"] == second_snapshot["books"], "same seed reproduces books")
	_assert(
		first_snapshot["target_order"] == second_snapshot["target_order"],
		"same seed reproduces target order",
	)

	monitor.configure_round(0)
	var random_snapshot: Dictionary = monitor.get_round_snapshot()
	_assert(int(random_snapshot["seed"]) != 0, "zero seed creates an effective random seed")

	lobby.queue_free()
	if _test_scene_root != null:
		_test_scene_root.queue_free()
	await process_frame
	_finish()


func _snapshot_tier_count(snapshot: Dictionary, tier: String) -> int:
	var count := 0
	for entry: Dictionary in snapshot["books"]:
		if entry["height"] == tier:
			count += 1
	return count


func _target_tiers(snapshot: Dictionary) -> Array[String]:
	var tier_by_book: Dictionary = {}
	for entry: Dictionary in snapshot["books"]:
		tier_by_book[entry["book"]] = entry["height"]
	var result: Array[String] = []
	for book_name: String in snapshot["target_order"]:
		result.append(String(tier_by_book[book_name]))
	return result


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
