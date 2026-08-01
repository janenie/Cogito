class_name AIPlayPutBookMonitor
extends Node

signal game_finished(outcome: String, reason: String)

const TASK_TITLE := "按低→中→高搬运 3 本任务书"
const TASK_CONTENT := (
	"任务目标：档案室（ARCHIVE）中分散在三组书架上的 6 本书里，只有 3 本带“任务书”标记；只搬运这三本。\n\n"
	+ "搬运顺序：先比较三本任务书所在层，必须严格按 ①低层 → ②中层 → ③高层。"
	+ "每次只能拿一本，当前一本送达后再拿下一本。\n\n"
	+ "目的地：把每本任务书送到 CEO OFFICE 的青色“书籍放置点”。"
	+ "拿起普通书，或提前拿中层/高层任务书，都会立即失败。"
)
const ROUND_BOOK_COUNT := 6
const TARGET_BOOK_COUNT := 3
const HEIGHT_TIERS: Array[String] = ["low", "middle", "high"]
const BOOK_CARRY_DISTANCE_OFFSET := -0.75
const BOOK_CARRYING_VELOCITY_MULTIPLIER := 12.0
const BOOK_DROP_DISTANCE := 2.5
const ASSISTED_DROP_RANGE := 2.0

@export var scenario_id: String = "put_book"
@export var game_over_screen: Node
@export var player: Node3D
@export var task_card: Node
@export var archive_door: Node
@export var carried_book: RigidBody3D
@export var archive_root: Node3D
@export var shelf_slots_root: Node3D
@export var archive_spawn: Marker3D
@export var archive_task_card_anchor: Marker3D
@export var ceo_door: CogitoDoor
@export var destination: StaticBody3D
@export var destination_area: Area3D
@export var destination_slots_root: Node3D
@export var round_seed: int = 0

var _round_finished := false
var _effective_seed: int = 0
var _runtime_books: Array[RigidBody3D] = []
var _runtime_book_parent: Node3D = null
var _active_books: Array[RigidBody3D] = []
var _target_books: Array[RigidBody3D] = []
var _slot_by_book: Dictionary = {}
var _current_target_index := 0
var _current_carried_book: RigidBody3D = null
var _completed_books: Array[RigidBody3D] = []
var _books_carried_once: Dictionary = {}
var _delivery_in_progress := false


func _ready() -> void:
	var controller: Node = get_parent()
	if (
		controller != null
		and controller.has_method("is_requested_scenario")
		and not controller.is_requested_scenario(scenario_id)
	):
		return
	if not _has_required_nodes():
		return
	_ensure_runtime_books()
	configure_round(round_seed)


func configure_round(seed_value: int = 0) -> void:
	if not _has_required_nodes():
		return
	_ensure_runtime_books()
	if _runtime_books.size() != ROUND_BOOK_COUNT:
		push_error("AIPlayPutBookMonitor needs six runtime book instances")
		return
	var rng := RandomNumberGenerator.new()
	if seed_value == 0:
		rng.randomize()
	else:
		rng.seed = seed_value
	_effective_seed = rng.seed
	_round_finished = true
	_current_target_index = 0
	_current_carried_book = null
	_completed_books.clear()
	_books_carried_once.clear()
	_delivery_in_progress = false
	_hide_decorative_archive_items()
	_reset_runtime_books()
	var selected_slots := AIPlayPutBookLayout.select_slots(_shelf_slots(), rng)
	if selected_slots.size() != ROUND_BOOK_COUNT:
		push_error("AIPlayPutBookMonitor needs six valid authored shelf slots")
		return
	_place_round_books(selected_slots)
	_select_target_books(rng)
	_place_player_and_task_card()
	_write_task_card()
	_open_archive_door()
	_activate_destination()
	_round_finished = false


func _shelf_slots() -> Array[Marker3D]:
	var result: Array[Marker3D] = []
	for child: Node in shelf_slots_root.get_children():
		if child is Marker3D:
			result.append(child as Marker3D)
	return result


func _hide_decorative_archive_items() -> void:
	for decorative_book: Node in get_tree().get_nodes_in_group("put_book_decorative_book"):
		if decorative_book is Node3D:
			var book := decorative_book as Node3D
			book.visible = false
			book.process_mode = Node.PROCESS_MODE_DISABLED
			_set_collision_enabled(book, false)
	for child: Node in archive_root.get_children():
		if String(child.name).begins_with("cardboardBox"):
			if child is Node3D:
				(child as Node3D).visible = false
			child.process_mode = Node.PROCESS_MODE_DISABLED
			_set_collision_enabled(child, false)


func _ensure_runtime_books() -> void:
	if _runtime_book_parent == null:
		_runtime_book_parent = carried_book.get_parent_node_3d()
	if _runtime_book_parent == null:
		return
	if _runtime_books.is_empty():
		_runtime_books.append(carried_book)
	for index: int in range(_runtime_books.size(), ROUND_BOOK_COUNT):
		var book_copy := carried_book.duplicate() as RigidBody3D
		book_copy.name = "PutBook_CarryableBook%d" % (index + 1)
		_runtime_book_parent.add_child(book_copy)
		_runtime_books.append(book_copy)


func _reset_runtime_books() -> void:
	_active_books.clear()
	_target_books.clear()
	_slot_by_book.clear()
	for book: RigidBody3D in _runtime_books:
		if book.get_parent_node_3d() != _runtime_book_parent:
			book.reparent(_runtime_book_parent, true)
		book.visible = false
		book.process_mode = Node.PROCESS_MODE_DISABLED
		book.freeze = true
		book.linear_velocity = Vector3.ZERO
		book.angular_velocity = Vector3.ZERO
		_set_collision_enabled(book, false)
		var carry_component: Variant = _carry_component_for_book(book)
		if carry_component != null:
			if carry_component.is_being_carried:
				carry_component.leave()
			carry_component.is_disabled = true


func _place_round_books(selected_slots: Array[Marker3D]) -> void:
	for index: int in range(selected_slots.size()):
		var slot := selected_slots[index]
		var book := _runtime_books[index]
		book.global_transform = slot.global_transform
		book.visible = true
		book.process_mode = Node.PROCESS_MODE_INHERIT
		book.freeze = true
		book.linear_velocity = Vector3.ZERO
		book.angular_velocity = Vector3.ZERO
		_set_collision_enabled(book, true)
		_active_books.append(book)
		_slot_by_book[book] = slot
		var carry_component: Variant = _carry_component_for_book(book)
		if carry_component != null:
			carry_component.carry_distance_offset = BOOK_CARRY_DISTANCE_OFFSET
			carry_component.carrying_velocity_multiplier = BOOK_CARRYING_VELOCITY_MULTIPLIER
			carry_component.drop_distance = BOOK_DROP_DISTANCE
			carry_component.enable_manual_rotating = false
			carry_component.is_disabled = false
			var callback := Callable(self, "_on_book_carry_state_changed").bind(book, carry_component)
			if carry_component.has_signal("carry_state_changed") and not (
				carry_component.carry_state_changed.is_connected(callback)
			):
				carry_component.carry_state_changed.connect(callback)


func _select_target_books(rng: RandomNumberGenerator) -> void:
	_target_books.clear()
	for tier: String in HEIGHT_TIERS:
		var candidates: Array[RigidBody3D] = []
		for book: RigidBody3D in _active_books:
			var slot := _slot_by_book.get(book) as Marker3D
			if slot != null and AIPlayPutBookLayout.height_tier(slot) == tier:
				candidates.append(book)
		if candidates.size() != 2:
			push_error("AIPlayPutBookMonitor needs two books in each height tier")
			return
		_target_books.append(candidates[rng.randi_range(0, candidates.size() - 1)])
	for book: RigidBody3D in _active_books:
		var is_target := book in _target_books
		book.set("display_name", "任务书" if is_target else "普通书")
		var marker := book.get_node_or_null("TargetMarker") as Label3D
		if marker != null:
			marker.visible = is_target


func _place_player_and_task_card() -> void:
	player.global_transform = archive_spawn.global_transform
	var task_card_object: Node3D = task_card.get_parent_node_3d()
	_reparent_to_anchor(task_card_object, archive_task_card_anchor)
	_face_player_toward(task_card_object.global_position)


func _face_player_toward(target_position: Vector3) -> void:
	var body := player.get_node_or_null("Body") as Node3D
	var neck := player.get_node_or_null("Body/Neck") as Node3D
	var head := player.get_node_or_null("Body/Neck/Head") as Node3D
	var eyes := player.get_node_or_null("Body/Neck/Head/Eyes") as Node3D
	var camera := player.get_node_or_null("Body/Neck/Head/Eyes/Camera") as Camera3D
	if body == null or neck == null or head == null or eyes == null or camera == null:
		push_error("AIPlayPutBookMonitor player is missing its camera rig")
		return
	body.rotation = Vector3.ZERO
	neck.rotation = Vector3.ZERO
	head.rotation = Vector3.ZERO
	eyes.rotation = Vector3.ZERO
	camera.rotation = Vector3.ZERO
	var flat_direction := target_position - player.global_position
	flat_direction.y = 0.0
	if not flat_direction.is_zero_approx():
		var player_transform := player.global_transform
		player_transform.basis = Basis.looking_at(flat_direction.normalized(), Vector3.UP)
		player.global_transform = player_transform
	var camera_direction := target_position - camera.global_position
	var horizontal_distance := Vector2(camera_direction.x, camera_direction.z).length()
	if not camera_direction.is_zero_approx():
		head.rotation.x = atan2(camera_direction.y, horizontal_distance)


func _write_task_card() -> void:
	task_card.set("readable_title", TASK_TITLE)
	task_card.set("readable_content", TASK_CONTENT)
	task_card.set("interaction_text", "Read task card")
	task_card.set("is_disabled", false)
	var card_object := task_card.get_parent() as CollisionObject3D
	if card_object != null:
		card_object.collision_layer = 2
	if task_card.is_node_ready():
		var label_title := task_card.get("label_title") as Label
		var label_content := task_card.get("label_content") as RichTextLabel
		if label_title == null or label_content == null:
			push_error("AIPlayPutBookMonitor task card is missing readable labels")
			return
		label_title.text = TASK_TITLE
		label_content.text = TASK_CONTENT


func _open_archive_door() -> void:
	archive_door.set("is_locked", false)
	if not bool(archive_door.get("is_open")):
		archive_door.set("is_open", true)
		archive_door.call("set_state")


func _activate_destination() -> void:
	destination.visible = true
	destination.process_mode = Node.PROCESS_MODE_INHERIT
	destination.collision_layer = 3
	destination.collision_mask = 3
	destination_area.monitoring = true
	var interaction := destination.get_node(
		"DestinationDropInteraction"
	) as AIPlayPutBookDestinationDropInteraction
	interaction.monitor = self
	destination.set("interaction_nodes", [interaction])
	var callback := Callable(self, "_on_destination_body_entered")
	if not destination_area.body_entered.is_connected(callback):
		destination_area.body_entered.connect(callback)
	_reset_ceo_door()


func _reset_ceo_door() -> void:
	ceo_door.is_locked = false
	ceo_door.is_open = false
	ceo_door.is_moving = false
	ceo_door.set_state()


func can_assisted_drop_to_destination() -> bool:
	var carry_component: Variant = _carry_component_for_book(_current_carried_book)
	return (
		not _round_finished
		and _current_carried_book == _expected_target_book()
		and carry_component != null
		and carry_component.is_being_carried
		and player.global_position.distance_to(destination_area.global_position)
			<= ASSISTED_DROP_RANGE
	)


func can_show_destination_interaction() -> bool:
	return (
		not _round_finished
		and player != null
		and player.global_position.distance_to(destination_area.global_position)
			<= ASSISTED_DROP_RANGE
	)


func assisted_drop_to_destination() -> void:
	if not can_assisted_drop_to_destination():
		return
	var book := _current_carried_book
	var carry_component: Variant = _carry_component_for_book(book)
	if carry_component.has_method("leave"):
		carry_component.leave()
	_complete_current_delivery(book)


func _complete_current_delivery(book: RigidBody3D) -> void:
	if (
		_round_finished
		or _delivery_in_progress
		or book != _expected_target_book()
		or not _books_carried_once.has(book)
	):
		return
	_delivery_in_progress = true
	var display_slot := destination_slots_root.get_child(_current_target_index) as Marker3D
	book.reparent(display_slot, false)
	book.transform = Transform3D.IDENTITY
	book.freeze = true
	book.linear_velocity = Vector3.ZERO
	book.angular_velocity = Vector3.ZERO
	_completed_books.append(book)
	_current_carried_book = null
	_current_target_index += 1
	var carry_component: Variant = _carry_component_for_book(book)
	if carry_component != null:
		carry_component.is_being_carried = false
		carry_component.is_disabled = true
	var marker := book.get_node_or_null("TargetMarker") as Label3D
	if marker != null:
		marker.visible = false
	_update_book_pickup_gate()
	_delivery_in_progress = false
	if _current_target_index == _target_books.size():
		_finish_round("success", "books_in_ceo_office")


func _on_destination_body_entered(body: Node) -> void:
	_try_complete_destination_book(body as RigidBody3D)


func _try_complete_destination_book(book: RigidBody3D = null) -> void:
	if book == null or book != _expected_target_book():
		return
	var carry_component: Variant = _carry_component_for_book(book)
	if carry_component != null and carry_component.is_being_carried:
		return
	if not _books_carried_once.has(book):
		return
	if _destination_contains_book(book):
		_complete_current_delivery(book)


func _destination_contains_book(book: RigidBody3D) -> bool:
	if book in destination_area.get_overlapping_bodies():
		return true
	for child: Node in destination_area.get_children():
		if not child is CollisionShape3D:
			continue
		var collision_shape := child as CollisionShape3D
		if collision_shape.disabled or not collision_shape.shape is BoxShape3D:
			continue
		var box := collision_shape.shape as BoxShape3D
		var local_book_position := collision_shape.global_transform.affine_inverse() * book.global_position
		var half_size := box.size * 0.5
		if (
			absf(local_book_position.x) <= half_size.x
			and absf(local_book_position.y) <= half_size.y
			and absf(local_book_position.z) <= half_size.z
		):
			return true
	return false


func _physics_process(_delta: float) -> void:
	if _round_finished:
		return
	if _current_carried_book != null:
		var carry_component: Variant = _carry_component_for_book(_current_carried_book)
		if carry_component != null and carry_component.is_being_carried:
			_stabilize_carried_book(_current_carried_book)
	_try_complete_destination_book(_expected_target_book())


func _on_book_carry_state_changed(
	is_being_carried: bool,
	book: RigidBody3D,
	_carry_component: Variant,
) -> void:
	if _round_finished:
		return
	if is_being_carried:
		if book != _expected_target_book():
			_finish_round("failure", "wrong_book_pickup")
			return
		_current_carried_book = book
		_books_carried_once[book] = true
		_stabilize_carried_book(book)
		_update_book_pickup_gate()
	elif _current_carried_book == book:
		_restore_dropped_book_physics(book)
		_current_carried_book = null
		_update_book_pickup_gate()
		_try_complete_destination_book(book)


func _finish_round(outcome: String, reason: String) -> void:
	if _round_finished:
		return
	_round_finished = true
	game_finished.emit(outcome, reason)


func _expected_target_book() -> RigidBody3D:
	if _current_target_index < 0 or _current_target_index >= _target_books.size():
		return null
	return _target_books[_current_target_index]


func _update_book_pickup_gate() -> void:
	for book: RigidBody3D in _active_books:
		var carry_component: Variant = _carry_component_for_book(book)
		if carry_component == null:
			continue
		if book in _completed_books:
			carry_component.is_disabled = true
		elif _current_carried_book == null:
			carry_component.is_disabled = false
		else:
			carry_component.is_disabled = book != _current_carried_book


func _snap_book_to_carry_position(book: RigidBody3D = null) -> void:
	var interaction_component: Variant = _player_interaction_component()
	var target_book := book if book != null else _current_carried_book
	if interaction_component == null or target_book == null:
		return
	if not interaction_component.has_method("get_carryable_destination_point"):
		return
	var destination: Variant = interaction_component.call(
		"get_carryable_destination_point",
		BOOK_CARRY_DISTANCE_OFFSET,
	)
	if destination is Vector3:
		target_book.global_position = destination
		target_book.linear_velocity = Vector3.ZERO
		target_book.angular_velocity = Vector3.ZERO


func _stabilize_carried_book(book: RigidBody3D) -> void:
	if book == null:
		return
	book.freeze = true
	book.collision_layer = 0
	book.collision_mask = 0
	_snap_book_to_carry_position(book)


func _restore_dropped_book_physics(book: RigidBody3D) -> void:
	if book == null:
		return
	book.linear_velocity = Vector3.ZERO
	book.angular_velocity = Vector3.ZERO
	book.collision_layer = 3
	book.collision_mask = 3
	book.freeze = false


func _player_interaction_component() -> Variant:
	var interaction_component: Variant = player.get("player_interaction_component")
	if interaction_component != null:
		return interaction_component
	return player.get_node_or_null("PlayerInteractionComponent")


func _carry_component_for_book(book: RigidBody3D) -> Variant:
	if book == null:
		return null
	return book.get_node_or_null("CarryableComponent")


func _reparent_to_anchor(object: Node3D, anchor: Node3D) -> void:
	object.reparent(anchor, false)
	object.transform = Transform3D.IDENTITY


func _set_collision_enabled(root: Node, enabled: bool) -> void:
	if root is CollisionObject3D:
		var collision_object := root as CollisionObject3D
		collision_object.collision_layer = 3 if enabled else 0
		collision_object.collision_mask = 3 if enabled else 0
	for child: Node in root.find_children("*", "CollisionShape3D", true, false):
		(child as CollisionShape3D).disabled = not enabled


func get_round_snapshot() -> Dictionary:
	var book_entries: Array[Dictionary] = []
	for book: RigidBody3D in _active_books:
		var slot := _slot_by_book.get(book) as Marker3D
		book_entries.append({
			"book": String(book.name),
			"slot": AIPlayPutBookLayout.slot_id(slot),
			"shelf": AIPlayPutBookLayout.shelf_id(slot),
			"height": AIPlayPutBookLayout.height_tier(slot),
			"target": book in _target_books,
		})
	return {
		"seed": _effective_seed,
		"books": book_entries,
		"target_order": _book_names(_target_books),
		"current_target_index": _current_target_index,
		"carried_book": String(_current_carried_book.name) if _current_carried_book != null else "",
		"completed": _book_names(_completed_books),
		"task_text": String(task_card.get("readable_content")),
	}


func _book_names(books: Array[RigidBody3D]) -> Array[String]:
	var result: Array[String] = []
	for book: RigidBody3D in books:
		result.append(String(book.name))
	return result


func _has_required_nodes() -> bool:
	var required: Dictionary = {
		"game_over_screen": game_over_screen,
		"player": player,
		"task_card": task_card,
		"archive_door": archive_door,
		"carried_book": carried_book,
		"archive_root": archive_root,
		"shelf_slots_root": shelf_slots_root,
		"archive_spawn": archive_spawn,
		"archive_task_card_anchor": archive_task_card_anchor,
		"ceo_door": ceo_door,
		"destination": destination,
		"destination_area": destination_area,
		"destination_slots_root": destination_slots_root,
	}
	for required_name: String in required:
		var required_node: Node = required[required_name] as Node
		if required_node == null:
			push_error("AIPlayPutBookMonitor is missing required scene node: %s" % required_name)
			return false
	if not _has_properties(
		task_card,
		["readable_title", "readable_content", "interaction_text", "is_disabled", "label_title", "label_content"],
	):
		push_error("AIPlayPutBookMonitor task_card must implement the ReadableComponent contract")
		return false
	if not _has_properties(archive_door, ["is_locked", "is_open"]) or not archive_door.has_method("set_state"):
		push_error("AIPlayPutBookMonitor archive_door must implement the CogitoDoor contract")
		return false
	if not _has_properties(ceo_door, ["is_locked", "is_open"]) or not ceo_door.has_method("set_state"):
		push_error("AIPlayPutBookMonitor ceo_door must implement the CogitoDoor contract")
		return false
	if not game_over_screen.has_method("show_result"):
		push_error("AIPlayPutBookMonitor game_over_screen must implement show_result")
		return false
	return true


func _has_properties(node: Node, property_names: Array[String]) -> bool:
	var available: Dictionary = {}
	for property: Dictionary in node.get_property_list():
		available[String(property.get("name", ""))] = true
	for property_name: String in property_names:
		if not available.has(property_name):
			return false
	return true


func show_result(outcome: String, reason: String) -> void:
	game_over_screen.call("show_result", outcome, reason)
