class_name AIPlayPutBookMonitor
extends Node

signal game_finished(outcome: String, reason: String)

const TASK_TITLE := "将任务书送到 CEO OFFICE"
const TASK_CONTENT := (
	"档案室的多个书架上共有六本可搬运的书，其中三本带有“任务书”标记。\n\n"
	+ "请根据它们所在书架的高度，严格按照低层、中层、高层的顺序，一次搬运一本。\n\n"
	+ "把三本任务书依次送到 CEO OFFICE 内标有“书籍放置点”的位置。拿起普通书或顺序错误的任务书会立即失败。"
)
const ROUND_BOOK_COUNT := 6
const TARGET_BOOK_COUNT := 3
const HEIGHT_TIERS: Array[String] = ["low", "middle", "high"]
const BOOK_CARRY_DISTANCE_OFFSET := 0.0
const BOOK_CARRYING_VELOCITY_MULTIPLIER := 18.0
const BOOK_DROP_DISTANCE := 100.0

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
	_reparent_to_anchor(task_card.get_parent_node_3d(), archive_task_card_anchor)


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
		var label_content := task_card.get("label_content") as Label
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
		_snap_book_to_carry_position(book)
		_update_book_pickup_gate()
	elif _current_carried_book == book:
		_current_carried_book = null
		_update_book_pickup_gate()


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
