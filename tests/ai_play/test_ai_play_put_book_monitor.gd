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
	var destination_scene: PackedScene = load(
		"res://addons/cogito/DemoScenes/DemoPrefabs/ai_play_put_book_destination.tscn"
	)
	_assert(destination_scene != null, "CEO destination prefab loads")
	if destination_scene != null:
		var inactive_destination := destination_scene.instantiate() as StaticBody3D
		root.add_child(inactive_destination)
		var inactive_area := inactive_destination.get_node("DestinationArea") as Area3D
		_assert(not inactive_destination.visible, "CEO destination starts hidden")
		_assert(
			inactive_destination.process_mode == Node.PROCESS_MODE_DISABLED,
			"CEO destination starts process-disabled",
		)
		_assert(inactive_destination.collision_layer == 0, "CEO destination starts collision-free")
		_assert(not inactive_area.monitoring, "CEO destination area starts inert")
		inactive_destination.queue_free()
		await process_frame

	var lobby: Node = lobby_scene.instantiate()
	root.add_child(lobby)
	await process_frame
	var slot_root := lobby.get_node_or_null("ARCHIVE/PutBookShelfSlots") as Node3D
	_assert(slot_root != null, "archive exposes put-book shelf slots")
	var slots: Array[Marker3D] = []
	if slot_root != null:
		for child: Node in slot_root.get_children():
			if child is Marker3D:
				slots.append(child as Marker3D)
	_assert(slots.size() == 9, "three shelves expose three height slots each")
	var seen_slot_ids: Dictionary = {}
	var seen_slot_layouts: Dictionary = {}
	for seed_value: int in range(1, 129):
		var rng := RandomNumberGenerator.new()
		rng.seed = seed_value
		var selected_slots := AIPlayPutBookLayout.select_slots(slots, rng)
		_assert(selected_slots.size() == 6, "layout selects six slots")
		_assert(_count_tier(selected_slots, "low") == 2, "layout has two low slots")
		_assert(_count_tier(selected_slots, "middle") == 2, "layout has two middle slots")
		_assert(_count_tier(selected_slots, "high") == 2, "layout has two high slots")
		for shelf_name: String in ["open_a", "open_b", "open_c"]:
			_assert(_count_shelf(selected_slots, shelf_name) == 2, "layout balances shelf books")
		var selected_ids: Array[String] = []
		var unique_selected_ids: Dictionary = {}
		for slot: Marker3D in selected_slots:
			var slot_id := AIPlayPutBookLayout.slot_id(slot)
			selected_ids.append(slot_id)
			unique_selected_ids[slot_id] = true
			seen_slot_ids[slot_id] = true
		_assert(unique_selected_ids.size() == 6, "layout selects six unique slot IDs")
		selected_ids.sort()
		seen_slot_layouts["|".join(selected_ids)] = true
	_assert(seen_slot_layouts.size() > 1, "seed sample produces multiple layouts")
	_assert(seen_slot_ids.size() == slots.size(), "seed sample reaches every authored slot")

	var monitor: Node = lobby.get_node_or_null("AIPlayController/PutBookMonitor")
	_assert(monitor != null, "Lobby includes PutBookMonitor")
	if monitor == null:
		lobby.queue_free()
		await process_frame
		_finish()
		return
	_assert(monitor.ceo_door != null, "put-book round resolves the CEO office door")
	_assert(monitor.destination != null, "put-book round resolves one CEO destination")
	_assert(monitor.destination_area != null, "CEO destination exposes an acceptance area")
	_assert(
		monitor.destination_slots_root != null,
		"CEO destination exposes internal display slots",
	)
	_assert(monitor.destination.visible, "CEO destination is visible during put-book")
	_assert(
		monitor.destination.is_in_group("interactable"),
		"CEO destination is an interactable placement point",
	)
	_assert(
		monitor.destination_slots_root.get_child_count() == 3,
		"CEO destination has three display slots",
	)
	for child: Node in monitor.destination_slots_root.get_children():
		_assert(child is Marker3D, "CEO destination display slots are authored markers")
	_assert(not monitor.ceo_door.is_locked, "CEO office door unlocks for put-book")

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
		var task_text := String(monitor.task_card.get("readable_content"))
		_assert(task_text.contains("CEO OFFICE"), "task card names CEO OFFICE")
		_assert(not task_text.contains("跳"), "task card removes jump rule")
		_assert(not task_text.contains("蹲"), "task card removes crouch rule")
		_assert(not task_text.contains("纸箱"), "task card removes box rule")
		_assert(not bool(monitor.archive_door.get("is_locked")), "archive door unlocks for delivery")
		_assert(bool(monitor.archive_door.get("is_open")), "archive door opens for delivery")
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
		var decorative_books := lobby.get_tree().get_nodes_in_group("put_book_decorative_book")
		_assert(decorative_books.size() == 6, "all six decorative books are in the scene group")
		for decorative_book: Node in decorative_books:
			_assert(not (decorative_book as Node3D).visible, "decorative books hide during the round")
		_assert(_visible_runtime_books(monitor).size() == 6, "only six runtime books are visible")

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

	var terminal_results: Array[Dictionary] = []
	monitor.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_results.append({
				"outcome": outcome,
				"reason": reason,
			})
	)
	monitor.configure_round(123456)
	var player_interaction: Variant = monitor._player_interaction_component()
	_assert(player_interaction != null, "player exposes its real interaction component")
	var expected: RigidBody3D = monitor._target_books[0]
	var later_target: RigidBody3D = monitor._target_books[1]
	var ordinary: RigidBody3D = _first_ordinary_book(monitor)
	_assert(ordinary != null, "round includes an ordinary book")
	var ordinary_carry: Variant = monitor._carry_component_for_book(ordinary)
	_assert(
		_monitor_carry_connection_count(ordinary_carry, monitor) == 1,
		"runtime book signal has one bound monitor callback",
	)
	_assert(
		await _raycast_hits_book(player_interaction.interaction_raycast, ordinary),
		"raycast fixture detects an available ordinary book",
	)
	for book: RigidBody3D in monitor._active_books:
		_assert(
			not monitor._carry_component_for_book(book).is_disabled,
			"all books start available",
		)
	_assert(terminal_results.is_empty(), "observing ordinary books does not fail")
	ordinary_carry.carry(player_interaction)
	_assert(ordinary_carry.is_being_carried, "ordinary book enters the real carried state")
	_assert(
		player_interaction.carried_object == ordinary_carry,
		"real pickup registers the carried component on the player",
	)
	_assert(
		not (await _raycast_hits_book(player_interaction.interaction_raycast, ordinary)),
		"real pickup excludes the carried book from the interaction raycast",
	)
	_assert(
		terminal_results == [{
			"outcome": "failure",
			"reason": "wrong_book_pickup",
		}],
		"ordinary pickup fails immediately",
	)
	ordinary_carry.carry_state_changed.emit(true)
	_assert(terminal_results.size() == 1, "wrong pickup ends the round exactly once")

	monitor.configure_round(123456)
	_assert(terminal_results.size() == 1, "reset callback cannot score the new round")
	_assert(not ordinary_carry.is_being_carried, "round reset leaves a genuinely carried book")
	_assert(
		player_interaction.carried_object == null,
		"round reset clears the player's carried component",
	)
	_assert(
		await _raycast_hits_book(player_interaction.interaction_raycast, ordinary),
		"round reset removes the carried book raycast exception",
	)
	_assert(
		_monitor_carry_connection_count(ordinary_carry, monitor) == 1,
		"round reset does not duplicate the bound carry callback",
	)
	for book: RigidBody3D in monitor._active_books:
		_assert(
			not monitor._carry_component_for_book(book).is_disabled,
			"all books are pickup-enabled after a carried-book reset",
		)
	terminal_results.clear()
	later_target = monitor._target_books[1]
	var later_carry: Variant = monitor._carry_component_for_book(later_target)
	later_carry.carry(player_interaction)
	_assert(
		terminal_results == [{
			"outcome": "failure",
			"reason": "wrong_book_pickup",
		}],
		"later target pickup fails immediately",
	)

	monitor.configure_round(123456)
	monitor.configure_round(123456)
	terminal_results.clear()
	expected = monitor._target_books[0]
	var expected_carry: Variant = monitor._carry_component_for_book(expected)
	for book: RigidBody3D in monitor._active_books:
		_assert(
			_monitor_carry_connection_count(
				monitor._carry_component_for_book(book),
				monitor,
			) == 1,
			"repeated round setup keeps one effective carry callback per book",
		)
	expected_carry.carry(player_interaction)
	_assert(terminal_results.is_empty(), "expected target pickup keeps the round active")
	_assert(monitor._current_carried_book == expected, "expected target becomes the carried book")
	_assert(monitor._books_carried_once.has(expected), "actual pickup is recorded")
	_assert(player_interaction.carried_object == expected_carry, "correct pickup uses real player carry state")
	for book: RigidBody3D in monitor._active_books:
		var carry_component: Variant = monitor._carry_component_for_book(book)
		_assert(
			carry_component.is_disabled == (book != expected),
			"correct carry disables every other unfinished book",
		)
	expected_carry.leave()
	_assert(monitor._current_target_index == 0, "outside drop does not advance target order")
	_assert(terminal_results.is_empty(), "outside drop remains recoverable")
	_assert(monitor._current_carried_book == null, "outside drop clears carried book")
	_assert(player_interaction.carried_object == null, "outside drop clears real player carry state")
	for book: RigidBody3D in monitor._active_books:
		_assert(
			not monitor._carry_component_for_book(book).is_disabled,
			"outside drop re-enables unfinished books",
		)

	monitor.player.global_position = monitor.destination_area.global_position
	var destination_interaction: Node = monitor.destination.get_node_or_null(
		"DestinationDropInteraction"
	)
	_assert(destination_interaction != null, "CEO destination exposes assisted placement")
	if destination_interaction != null:
		destination_interaction.interact(player_interaction)
	_assert(monitor._current_target_index == 0, "destination interaction without a book is inert")
	_assert(terminal_results.is_empty(), "empty destination interaction leaves the round active")

	expected_carry.carry(player_interaction)
	expected.global_position = monitor.destination_area.global_position
	PhysicsServer3D.body_set_state(
		expected.get_rid(),
		PhysicsServer3D.BODY_STATE_TRANSFORM,
		expected.global_transform,
	)
	expected_carry.leave()
	await physics_frame
	await physics_frame
	_assert(monitor._current_target_index == 1, "physical destination drop advances one tier")
	_assert(expected in monitor._completed_books, "physical destination drop completes the book")
	_assert(expected_carry.is_disabled, "physically delivered book is locked")
	_assert(
		expected.global_position.distance_to(
			(monitor.destination_slots_root.get_child(0) as Marker3D).global_position
		) < 0.001,
		"physical destination drop snaps to the first display slot",
	)
	_assert(terminal_results.is_empty(), "first physical delivery is nonterminal")

	monitor.configure_round(123456)
	terminal_results.clear()
	monitor.player.global_position = monitor.destination_area.global_position
	for index: int in range(3):
		var book: RigidBody3D = monitor._target_books[index]
		var carry_component: Variant = monitor._carry_component_for_book(book)
		carry_component.is_being_carried = true
		monitor._on_book_carry_state_changed(true, book, carry_component)
		_assert(
			monitor.can_assisted_drop_to_destination(),
			"current target can use CEO destination",
		)
		monitor.assisted_drop_to_destination()
		_assert(monitor._current_target_index == index + 1, "delivery advances one tier")
		_assert(book in monitor._completed_books, "delivered book is completed")
		_assert(carry_component.is_disabled, "delivered book is locked")
		var display_slot: Marker3D = monitor.destination_slots_root.get_child(index)
		_assert(
			book.global_position.distance_to(display_slot.global_position) < 0.001,
			"book snaps to its display slot",
		)
		if index < 2:
			_assert(terminal_results.is_empty(), "partial delivery is nonterminal")
	_assert(
		terminal_results == [{
			"outcome": "success",
			"reason": "books_in_ceo_office",
		}],
		"three ordered deliveries succeed",
	)

	monitor.configure_round(123456)
	for book: RigidBody3D in monitor._active_books:
		_assert(
			book.get_parent_node_3d() == monitor._runtime_book_parent,
			"round reset detaches delivered books from display slots",
		)
	terminal_results.clear()

	expected_carry.carry(player_interaction)
	_assert(monitor._books_carried_once.has(expected), "second real pickup remains tracked")
	monitor.configure_round(123456)
	_assert(terminal_results.is_empty(), "real carry reset does not finish the fresh round")
	_assert(not expected_carry.is_being_carried, "fresh round leaves the previously carried target")
	_assert(player_interaction.carried_object == null, "fresh round clears player carry ownership")
	_assert(
		await _raycast_hits_book(player_interaction.interaction_raycast, expected),
		"fresh round removes the target raycast exception",
	)
	_assert(monitor._books_carried_once.is_empty(), "fresh round clears carry-once tracking")
	for book: RigidBody3D in monitor._active_books:
		_assert(
			not monitor._carry_component_for_book(book).is_disabled,
			"fresh round ends with every unfinished book pickup-enabled",
		)

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


func _visible_runtime_books(monitor: Node) -> Array[RigidBody3D]:
	var result: Array[RigidBody3D] = []
	for book: RigidBody3D in monitor._runtime_books:
		if book.visible:
			result.append(book)
	return result


func _first_ordinary_book(monitor: Node) -> RigidBody3D:
	for book: RigidBody3D in monitor._active_books:
		if book not in monitor._target_books:
			return book
	return null


func _monitor_carry_connection_count(
	carry_component: Variant,
	monitor: Node,
) -> int:
	var count := 0
	for connection: Dictionary in carry_component.carry_state_changed.get_connections():
		var callback: Callable = connection["callable"]
		if (
			callback.get_object() == monitor
			and callback.get_method() == &"_on_book_carry_state_changed"
		):
			count += 1
	return count


func _raycast_hits_book(raycast: RayCast3D, book: RigidBody3D) -> bool:
	var original_raycast_transform := raycast.global_transform
	var original_target := raycast.target_position
	var original_enabled := raycast.enabled
	var original_collision_mask := raycast.collision_mask
	var original_book_transform := book.global_transform
	var original_freeze := book.freeze
	var original_book_collision_layer := book.collision_layer
	var original_book_collision_mask := book.collision_mask
	var isolated_collision_layer := 1 << 19
	var carry_component: Node = book.get_node("CarryableComponent")
	var original_carry_process_mode := carry_component.process_mode
	var probe_shape := CollisionShape3D.new()
	var probe_box := BoxShape3D.new()
	probe_box.size = Vector3.ONE
	probe_shape.shape = probe_box
	book.add_child(probe_shape)
	raycast.enabled = true
	raycast.collision_mask = isolated_collision_layer
	raycast.global_transform = Transform3D(Basis.IDENTITY, Vector3(200.0, 200.0, 200.0))
	raycast.target_position = Vector3(0.0, 0.0, -4.0)
	carry_component.process_mode = Node.PROCESS_MODE_DISABLED
	book.freeze = true
	book.collision_layer = isolated_collision_layer
	book.collision_mask = 0
	book.global_transform = Transform3D(Basis.IDENTITY, Vector3(200.0, 200.0, 198.0))
	PhysicsServer3D.body_set_state(
		book.get_rid(),
		PhysicsServer3D.BODY_STATE_TRANSFORM,
		book.global_transform,
	)
	await physics_frame
	raycast.force_raycast_update()
	var hit := raycast.get_collider() == book
	book.global_transform = original_book_transform
	PhysicsServer3D.body_set_state(
		book.get_rid(),
		PhysicsServer3D.BODY_STATE_TRANSFORM,
		original_book_transform,
	)
	book.freeze = original_freeze
	carry_component.process_mode = original_carry_process_mode
	book.collision_layer = original_book_collision_layer
	book.collision_mask = original_book_collision_mask
	probe_shape.queue_free()
	raycast.global_transform = original_raycast_transform
	raycast.target_position = original_target
	raycast.collision_mask = original_collision_mask
	raycast.enabled = original_enabled
	if raycast.enabled:
		raycast.force_raycast_update()
	return hit


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
