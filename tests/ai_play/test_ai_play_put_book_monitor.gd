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
	var slot_root: Node3D = lobby.get_node_or_null("ARCHIVE/PutBookShelfSlots")
	_assert(slot_root != null, "archive exposes put-book shelf slots")
	var slots: Array[Marker3D] = []
	if slot_root != null:
		for child: Node in slot_root.get_children():
			if child is Marker3D:
				slots.append(child as Marker3D)
	_assert(slots.size() == 9, "three shelves expose three height slots each")

	var seen_layouts: Dictionary = {}
	var seen_slot_ids: Dictionary = {}
	for seed_value: int in range(1, 129):
		var rng := RandomNumberGenerator.new()
		rng.seed = seed_value
		var selected := AIPlayPutBookLayout.select_slots(slots, rng)
		_assert(selected.size() == 6, "layout selects six slots")
		_assert(_count_tier(selected, "low") == 2, "layout has two low slots")
		_assert(_count_tier(selected, "middle") == 2, "layout has two middle slots")
		_assert(_count_tier(selected, "high") == 2, "layout has two high slots")
		for shelf_name: String in ["open_a", "open_b", "open_c"]:
			_assert(_count_shelf(selected, shelf_name) == 2, "layout balances shelf books")
		var layout_ids: Array[String] = []
		for slot: Marker3D in selected:
			var id := AIPlayPutBookLayout.slot_id(slot)
			layout_ids.append(id)
			seen_slot_ids[id] = true
		layout_ids.sort()
		seen_layouts["|".join(layout_ids)] = true

	_assert(seen_layouts.size() > 1, "seed sample produces multiple layouts")
	_assert(seen_slot_ids.size() == slots.size(), "seed sample reaches every slot")
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
		_assert(snapshot["books"].size() == 3, "round selects three books")
		_assert(snapshot["boxes"].size() == 3, "round selects three ground boxes")
		_assert(snapshot["assignments"].size() == 3, "round assigns one target box per book")
		_assert(
			String(snapshot["task_text"]).contains("三本"),
			"task card describes the three-book objective",
		)
		_assert(monitor._active_books.size() == 3, "three carryable books are active")
		_assert(monitor._drop_box_areas.size() == 3, "three box areas are active")
		_assert(_visible_boxes(monitor).size() == 3, "only three of five boxes are visible")
		_assert(_hidden_boxes(monitor).size() == 2, "two of five boxes are hidden")
		_assert(_round_has_posture(monitor, "jump"), "round includes a high book")
		_assert(_round_has_posture(monitor, "crouch"), "round includes a low book")
		for box: RigidBody3D in _visible_boxes(monitor):
			_assert(
				_box_position_is_in_candidate_set(monitor, box.position),
				"visible boxes stay in archive-local ground positions",
			)
			_assert(
				_box_position_is_inside_archive_room(box.position),
				"visible boxes are inside the archive room",
			)
		for book_name: String in snapshot["books"]:
			if book_name not in seen_books:
				seen_books.append(book_name)
		for box_name: String in snapshot["boxes"]:
			if box_name not in seen_boxes:
				seen_boxes.append(box_name)
		for book: RigidBody3D in monitor._active_books:
			var source_book: Node3D = monitor._book_source_by_instance[book] as Node3D
			var expected_area: Area3D = monitor._nearest_box_area_to_position(
				source_book.global_position,
				monitor._drop_box_areas,
			)
			_assert(
				monitor._correct_box_by_book[book] == expected_area,
				"book target is the nearest visible ground box",
			)
		for box_area: Area3D in monitor._drop_box_areas:
			_assert(monitor._is_ground_box_area(box_area), "active box is on the ground")
			var box: Node = box_area.get_parent()
			_assert(box.is_in_group("interactable"), "ground drop box is interactable")
			var interactions: Array = box.get("interaction_nodes")
			_assert(not interactions.is_empty(), "ground drop box exposes interactions")
			if not interactions.is_empty():
				var box_interaction: Node = interactions[0]
				_assert(
					box_interaction.get("prefer_while_carrying") == true,
					"box drop interaction takes priority while carrying",
				)
				_assert(
					box_interaction.get("interaction_text") == "放入箱子",
					"box drop interaction names the box drop action",
				)
				monitor.player.global_position = box_area.global_position
				monitor._book_has_been_carried = false
				_assert(
					not box_interaction.set_disabled(monitor.player),
					"ground box interaction is visible before carrying a book",
				)

	_assert(seen_books.size() == 6, "fixed seed sample reaches all six book anchors")
	_assert(seen_boxes.size() == 5, "fixed seed sample reaches all five box anchors")
	_assert(
		monitor._required_posture_for_book(monitor.book_a) == "jump",
		"book_a requires jump posture",
	)
	_assert(
		monitor._required_posture_for_book(monitor.book_b) == "jump",
		"book_b requires jump posture",
	)
	_assert(
		monitor._required_posture_for_book(monitor.book_d) == "jump",
		"book_d requires jump posture",
	)
	_assert(
		monitor._required_posture_for_book(monitor.book_c) == "crouch",
		"book_c requires crouch posture",
	)
	_assert(
		monitor._required_posture_for_book(monitor.book_e) == "crouch",
		"book_e requires crouch posture",
	)
	_assert(
		monitor._required_posture_for_book(monitor.book_f) == "crouch",
		"book_f requires crouch posture",
	)

	monitor.configure_round(123456)
	var first_book: RigidBody3D = monitor._active_books[0]
	var carry_component: Variant = first_book.get_node_or_null("CarryableComponent")
	_assert(carry_component != null, "active book exposes carry component")
	if carry_component != null:
		_assert(
			carry_component.drop_distance == 100.0,
			"put_book books stay carried until the player drops them",
		)
		monitor._book_posture_by_instance[first_book] = "crouch"
		monitor.player.is_crouching = false
		monitor._update_book_pickup_gate()
		_assert(carry_component.is_disabled, "crouch book cannot be picked up while standing")
		monitor.player.is_crouching = true
		monitor._update_book_pickup_gate()
		_assert(not carry_component.is_disabled, "crouch book can be picked up while crouching")
		monitor.player.is_crouching = false
		monitor.player.is_jumping = false
		monitor._jump_pickup_window_until_ms = 0
		monitor._book_posture_by_instance[first_book] = "jump"
		monitor._update_book_pickup_gate()
		_assert(carry_component.is_disabled, "jump book cannot be picked up without jumping")
		monitor.player.is_jumping = true
		monitor._update_jump_pickup_window()
		monitor.player.is_jumping = false
		monitor._update_book_pickup_gate()
		_assert(not carry_component.is_disabled, "jump book can be picked up after jumping")
		monitor._on_book_carry_state_changed(true, first_book, carry_component)
		monitor._update_book_pickup_gate()
		_assert(not carry_component.is_disabled, "dropped book can be picked up again normally")

	var terminal_results: Array[Dictionary] = []
	monitor.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_results.append({
				"outcome": outcome,
				"reason": reason,
			})
	)

	terminal_results.clear()
	for index: int in range(monitor._active_books.size()):
		var book: RigidBody3D = monitor._active_books[index]
		var correct_area: Area3D = monitor._correct_box_by_book[book] as Area3D
		monitor._finish_book_in_box(book, correct_area)
		if index < monitor._active_books.size() - 1:
			_assert(terminal_results.is_empty(), "partial correct sorting does not end the round")
	_assert(
		terminal_results == [{
			"outcome": "success",
			"reason": "book_in_box",
		}],
		"all three books in their nearest boxes ends the round successfully",
	)

	monitor.configure_round(234567)
	terminal_results.clear()
	var wrong_book: RigidBody3D = monitor._active_books[0]
	var wrong_area: Area3D = _wrong_area_for_book(monitor, wrong_book)
	_assert(wrong_area != null, "wrong target area exists")
	if wrong_area != null:
		monitor._finish_book_in_box(wrong_book, wrong_area)
	_assert(
		terminal_results == [{
			"outcome": "failure",
			"reason": "book_in_wrong_box",
		}],
		"a book in a non-nearest box ends the round as wrong",
	)

	monitor.configure_round(345678)
	terminal_results.clear()
	var interaction_area: Area3D = monitor._drop_box_areas[0]
	monitor.player.global_position = interaction_area.global_position
	var box_interaction: Node = interaction_area.get_parent().get("interaction_nodes")[0]
	box_interaction.interact(monitor._player_interaction_component())
	_assert(
		terminal_results.is_empty(),
		"interacting with a box before carrying a book does not finish the round",
	)

	monitor.configure_round(456789)
	terminal_results.clear()
	for book: RigidBody3D in monitor._active_books:
		var correct_area: Area3D = monitor._correct_box_by_book[book] as Area3D
		monitor.player.global_position = correct_area.global_position
		monitor._book_has_been_carried = true
		monitor._current_carried_book = book
		var book_carry_component: Variant = book.get_node_or_null("CarryableComponent")
		book_carry_component.is_being_carried = true
		monitor.assisted_drop_into_box_area(correct_area)
	_assert(
		terminal_results == [{
			"outcome": "success",
			"reason": "book_in_box",
		}],
		"assisted drops can sort all three books successfully",
	)

	lobby.queue_free()
	if _test_scene_root != null:
		_test_scene_root.queue_free()
	await process_frame
	_finish()


func _visible_boxes(monitor: Node) -> Array[RigidBody3D]:
	var result: Array[RigidBody3D] = []
	for box: RigidBody3D in monitor._box_candidates():
		if box.visible:
			result.append(box)
	return result


func _hidden_boxes(monitor: Node) -> Array[RigidBody3D]:
	var result: Array[RigidBody3D] = []
	for box: RigidBody3D in monitor._box_candidates():
		if not box.visible:
			result.append(box)
	return result


func _wrong_area_for_book(monitor: Node, book: RigidBody3D) -> Area3D:
	for box_area: Area3D in monitor._drop_box_areas:
		if monitor._correct_box_by_book[book] != box_area:
			return box_area
	return null


func _round_has_posture(monitor: Node, posture: String) -> bool:
	for book: RigidBody3D in monitor._active_books:
		if monitor._book_posture_by_instance.get(book) == posture:
			return true
	return false


func _count_tier(slots: Array[Marker3D], tier: String) -> int:
	var count := 0
	for slot: Marker3D in slots:
		if AIPlayPutBookLayout.height_tier(slot) == tier:
			count += 1
	return count


func _count_shelf(slots: Array[Marker3D], shelf_name: String) -> int:
	var count := 0
	for slot: Marker3D in slots:
		if AIPlayPutBookLayout.shelf_id(slot) == shelf_name:
			count += 1
	return count


func _box_position_is_in_candidate_set(monitor: Node, position: Vector3) -> bool:
	for candidate_position: Vector3 in monitor.GROUND_BOX_POSITIONS:
		if position.distance_to(candidate_position) < 0.001:
			return true
	return false


func _box_position_is_inside_archive_room(position: Vector3) -> bool:
	return position.x >= -0.5 and position.x <= 2.6 and position.z <= -2.0 and position.z >= -7.0


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
