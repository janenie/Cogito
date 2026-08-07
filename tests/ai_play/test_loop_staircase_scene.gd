extends SceneTree

const EXPECTED_ROOM_TYPES: Dictionary = {
	2: "lounge",
	3: "lounge",
	4: "archive",
	5: "archive",
	6: "office",
	7: "office",
	8: "meeting",
	9: "meeting",
}

var _failures: Array[String] = []
var _test_scene_root: Node


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	_ensure_current_scene()
	var scene: PackedScene = load(
		"res://addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn"
	)
	_assert(scene != null, "Loop staircase scene loads")
	if scene == null:
		_finish()
		return
	var root_node: Node = scene.instantiate()
	root.add_child(root_node)
	await process_frame
	var controller: Node = root_node.get_node_or_null("AIPlayController")
	var manager: Node = root_node.get_node_or_null("AIPlayController/LoopStaircaseManager")
	var observer: Node = root_node.get_node_or_null("AIPlayController/Observer")
	_assert(controller != null, "scene includes AIPlayController")
	_assert(manager != null, "controller includes loop staircase manager")
	_assert(observer != null, "scene includes the restricted staircase observer")
	if manager == null or observer == null:
		root_node.queue_free()
		await process_frame
		_finish()
		return
	manager.configure_round(98765)
	manager.build_scene()
	await process_frame
	_assert_public_state(observer.capture_observation([]))
	_assert(manager.get_node_or_null("GameUI") is CanvasLayer, "manager builds HUD")
	_assert(manager.get_node_or_null("SpawnPoint") is Node3D, "manager preserves a playable spawn")
	var theme_ids: Array[String] = []
	var pair_signatures: Dictionary = {}
	for floor_number: int in range(2, 10):
		manager.set_current_floor(floor_number)
		var room: Node = manager.get_node_or_null("CurrentFloorRoom")
		_assert(room != null, "%dF renders a room" % floor_number)
		if room == null:
			continue
		var theme_id: String = str(room.get_meta("theme_id", ""))
		var room_type: String = str(room.get_meta("room_type", ""))
		_assert(room_type == EXPECTED_ROOM_TYPES[floor_number], "%dF has its fixed function" % floor_number)
		_assert(not theme_id.is_empty(), "%dF has a stable theme" % floor_number)
		_assert(not theme_id in theme_ids, "%dF theme differs from every other floor" % floor_number)
		theme_ids.append(theme_id)
		var stable_theme: Node = room.get_node_or_null("StableTheme")
		_assert(stable_theme is Node3D, "%dF has stable theme furniture" % floor_number)
		if stable_theme != null:
			var names: Array[String] = []
			for child: Node in stable_theme.get_children():
				names.append(child.name)
			pair_signatures[floor_number] = names
		var visitor_record := room.get_node_or_null("Evidence/VisitorRecord") as Label3D
		_assert(visitor_record != null, "%dF has a visible visitor record" % floor_number)
		_assert(room.get_node_or_null("Evidence/ItemSlot") is Node3D, "%dF has an ordinary item slot" % floor_number)
		_assert(room.get_node_or_null("Evidence/Trash") is Node3D, "%dF has visible trash" % floor_number)
		_assert(room.get_node_or_null("Evidence/SignalLight") is MeshInstance3D, "%dF has a signal light" % floor_number)
		_assert(visitor_record == null or not "访问轮次" in visitor_record.text, "%dF hides visit time before round five" % floor_number)
		_assert(not room.has_meta("is_solution"), "%dF does not visually tag the answer" % floor_number)
	_assert(theme_ids.size() == 8, "all eight room themes are distinct")
	for lower_floor: int in [2, 4, 6, 8]:
		_assert(
			pair_signatures.get(lower_floor, []) != pair_signatures.get(lower_floor + 1, []),
			"%dF and %dF share a function but not a copied layout" % [lower_floor, lower_floor + 1],
		)
	_unlock_final_round(manager)
	manager.set_current_floor(2)
	var final_record := manager.get_node_or_null("CurrentFloorRoom/Evidence/VisitorRecord") as Label3D
	_assert(final_record != null and "访问轮次" in final_record.text, "round five reveals visitor timing")
	var terminal_results: Array[Dictionary] = []
	manager.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_results.append({"outcome": outcome, "reason": reason})
	)
	manager.set_current_floor(manager.get_round_snapshot()["true_floor"])
	manager.submit_current_floor()
	_assert(
		terminal_results == [{"outcome": "success", "reason": "correct_floor_selected"}],
		"fifth-round Space-style submit preserves the success reason",
	)
	_assert(controller.get_active_scenario_id() == _expected_scenario(), "controller selects the requested scenario")
	root_node.queue_free()
	paused = false
	if _test_scene_root != null:
		_test_scene_root.queue_free()
	await process_frame
	_finish()


func _assert_public_state(observation: Dictionary) -> void:
	_assert(observation.has("staircase"), "observer includes staircase state")
	if not observation.has("staircase"):
		return
	var state: Dictionary = observation["staircase"]
	var expected_keys: Array[String] = [
		"completed", "current_floor", "current_floor_label", "current_loop",
		"failed", "final_unlocked", "objective", "total_loops",
	]
	var actual_keys: Array[String] = []
	for key: Variant in state.keys():
		actual_keys.append(str(key))
	actual_keys.sort()
	expected_keys.sort()
	_assert(actual_keys == expected_keys, "structured state contains only public navigation fields")


func _unlock_final_round(manager: Node) -> void:
	while not manager.is_final_unlocked():
		for floor_number: int in range(2, 10):
			manager.mark_floor_observed(floor_number)
		manager.set_current_floor(9)
		manager.move_up()


func _expected_scenario() -> String:
	return "loop_staircase_anomaly" if _is_selected_scenario() else "find_contract"


func _is_selected_scenario() -> bool:
	return "--ai-play-scenario=loop_staircase_anomaly" in OS.get_cmdline_user_args()


func _ensure_current_scene() -> void:
	if current_scene != null:
		return
	_test_scene_root = Node.new()
	_test_scene_root.name = "AIPlayHeadlessTestScene"
	root.add_child(_test_scene_root)
	current_scene = _test_scene_root


func _finish() -> void:
	paused = false
	if _failures.is_empty():
		print("Loop staircase scene test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
