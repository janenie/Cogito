class_name AIPlayPutBookMonitor
extends Node

signal game_finished(outcome: String, reason: String)

const BoxInteractableScript = preload(
	"res://addons/cogito/AIPlay/ai_play_put_book_box_interactable.gd"
)
const BoxDropInteractionScript = preload(
	"res://addons/cogito/AIPlay/ai_play_put_book_box_drop_interaction.gd"
)
const TASK_TITLE := "整理档案室书籍"
const TASK_CONTENT := (
	"档案室里有三本需要整理的书。\n\n"
	+ "进入档案室，找到书架上三本可见的书。地上有三个可用纸箱。\n\n"
	+ "每本书都要放进离它起始位置最近的地上纸箱。高处的书需要先跳起才能拿，低处的书需要先蹲下才能拿。"
)
const POSTURE_NONE := ""
const POSTURE_JUMP := "jump"
const POSTURE_CROUCH := "crouch"
const JUMP_PICKUP_GRACE_MS := 1500
const BOOK_CARRY_DISTANCE_OFFSET := 0.0
const BOOK_CARRYING_VELOCITY_MULTIPLIER := 18.0
const BOOK_DROP_DISTANCE := 100.0
const ASSISTED_DROP_RANGE := 2.0
const ASSISTED_DROP_DEBOUNCE_MS := 250
const GROUND_BOX_AREA_MAX_HEIGHT := 0.9
const ROUND_BOOK_COUNT := 3
const ROUND_BOX_COUNT := 3
const GROUND_BOX_POSITIONS: Array[Vector3] = [
	Vector3(-0.25, 0.0, -2.35),
	Vector3(1.05, 0.0, -2.45),
	Vector3(2.25, 0.0, -3.35),
	Vector3(0.45, 0.0, -5.10),
	Vector3(2.35, 0.0, -6.65),
]

@export var scenario_id: String = "put_book"
@export var game_over_screen: AIPlayGameOverScreen
@export var player: Node3D
@export var task_card: ReadableComponent
@export var archive_door: CogitoDoor
@export var carried_book: RigidBody3D
@export var target_box: RigidBody3D
@export var target_box_area: Area3D
@export var near_box_anchor: Marker3D
@export var far_box_anchor: Marker3D
@export var archive_spawn: Marker3D
@export var archive_task_card_anchor: Marker3D
@export var book_a: Node3D
@export var book_b: Node3D
@export var book_c: Node3D
@export var book_d: Node3D
@export var book_e: Node3D
@export var book_f: Node3D
@export var round_seed: int = 0

var _round_finished: bool = false
var _selected_book_name: String = ""
var _selected_book_names: Array[String] = []
var _selected_box_names: Array[String] = []
var _book_candidate_pool: Array[Node3D] = []
var _runtime_books: Array[RigidBody3D] = []
var _active_books: Array[RigidBody3D] = []
var _book_carry_components: Array = []
var _current_carried_book: RigidBody3D = null
var _required_posture: String = POSTURE_NONE
var _jump_pickup_window_until_ms: int = 0
var _drop_box_areas: Array[Area3D] = []
var _book_has_been_carried: bool = false
var _last_book_pickup_ms: int = 0
var _book_source_by_instance: Dictionary = {}
var _book_posture_by_instance: Dictionary = {}
var _correct_box_by_book: Dictionary = {}
var _completed_books: Array[RigidBody3D] = []


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
	_capture_book_candidate_pool()
	_place_box_candidates()
	configure_round(round_seed)


func configure_round(seed_value: int = 0) -> void:
	if not _has_required_nodes():
		return
	if _book_candidate_pool.is_empty():
		_capture_book_candidate_pool()
	if _book_candidate_pool.is_empty():
		push_error("AIPlayPutBookMonitor needs at least one book candidate")
		return
	var rng := RandomNumberGenerator.new()
	if seed_value == 0:
		rng.randomize()
	else:
		rng.seed = seed_value
	_round_finished = false
	_selected_book_name = ""
	_selected_book_names.clear()
	_selected_box_names.clear()
	_jump_pickup_window_until_ms = 0
	_book_has_been_carried = false
	_last_book_pickup_ms = 0
	_current_carried_book = null
	_book_source_by_instance.clear()
	_book_posture_by_instance.clear()
	_correct_box_by_book.clear()
	_completed_books.clear()
	_hide_book_candidates()
	_reset_runtime_books()
	_place_box_candidates()
	var active_box_areas: Array[Area3D] = _select_round_boxes(rng)
	var selected_books: Array[Node3D] = _select_round_books(rng)
	_place_round_books(selected_books)
	_assign_correct_boxes(active_box_areas)
	_place_player_and_task_card()
	_write_task_card()
	_open_archive_door()


func _capture_book_candidate_pool() -> void:
	_book_candidate_pool.clear()
	for book: Node3D in _book_candidates():
		if book != null:
			_book_candidate_pool.append(book)


func _book_candidates() -> Array[Node3D]:
	return [book_a, book_b, book_c, book_d, book_e, book_f]


func _box_candidates() -> Array[RigidBody3D]:
	var archive: Node = target_box.get_parent()
	if archive == null:
		return [target_box]
	var result: Array[RigidBody3D] = []
	for child: Node in archive.get_children():
		if child is RigidBody3D and String(child.name).begins_with("cardboardBox"):
			result.append(child as RigidBody3D)
	return result


func _hide_book_candidates() -> void:
	for book: Node3D in _book_candidates():
		if book != null:
			book.visible = false
			book.process_mode = Node.PROCESS_MODE_DISABLED
			_set_collision_enabled(book, false)


func _ensure_runtime_books() -> void:
	if not _runtime_books.is_empty():
		return
	_runtime_books.append(carried_book)
	var parent := carried_book.get_parent()
	for index: int in range(1, ROUND_BOOK_COUNT):
		var book_copy := carried_book.duplicate() as RigidBody3D
		book_copy.name = "PutBook_CarryableBook%d" % (index + 1)
		parent.add_child(book_copy)
		_runtime_books.append(book_copy)


func _reset_runtime_books() -> void:
	_active_books.clear()
	_book_carry_components.clear()
	for book: RigidBody3D in _runtime_books:
		book.visible = false
		book.process_mode = Node.PROCESS_MODE_DISABLED
		book.freeze = true
		book.linear_velocity = Vector3.ZERO
		book.angular_velocity = Vector3.ZERO
		_set_collision_enabled(book, false)
		var carry_component: Variant = book.get_node_or_null("CarryableComponent")
		if carry_component != null:
			carry_component.is_being_carried = false
			carry_component.is_disabled = true


func _place_round_books(selected_books: Array[Node3D]) -> void:
	for index: int in range(selected_books.size()):
		var source_book := selected_books[index]
		var active_book := _runtime_books[index]
		active_book.visible = true
		active_book.process_mode = Node.PROCESS_MODE_INHERIT
		active_book.freeze = true
		active_book.linear_velocity = Vector3.ZERO
		active_book.angular_velocity = Vector3.ZERO
		active_book.global_transform = source_book.global_transform
		_set_collision_enabled(active_book, true)
		_active_books.append(active_book)
		_book_source_by_instance[active_book] = source_book
		_book_posture_by_instance[active_book] = _required_posture_for_book(source_book)
		_selected_book_names.append(source_book.name)
		var carry_component: Variant = active_book.get_node_or_null("CarryableComponent")
		if carry_component != null:
			carry_component.carry_distance_offset = BOOK_CARRY_DISTANCE_OFFSET
			carry_component.carrying_velocity_multiplier = BOOK_CARRYING_VELOCITY_MULTIPLIER
			carry_component.drop_distance = BOOK_DROP_DISTANCE
			carry_component.is_being_carried = false
			carry_component.is_disabled = false
			if carry_component not in _book_carry_components:
				_book_carry_components.append(carry_component)
			var callback := Callable(self, "_on_book_carry_state_changed").bind(
				active_book,
				carry_component,
			)
			if carry_component.has_signal("carry_state_changed") and not (
				carry_component.carry_state_changed.is_connected(callback)
			):
				carry_component.carry_state_changed.connect(callback)
	_update_book_pickup_gate()


func _place_box_candidates() -> void:
	var boxes := _box_candidates()
	for index: int in range(boxes.size()):
		var box := boxes[index]
		var position := GROUND_BOX_POSITIONS[index % GROUND_BOX_POSITIONS.size()]
		box.freeze = true
		box.linear_velocity = Vector3.ZERO
		box.angular_velocity = Vector3.ZERO
		box.position = position
		box.visible = false
		box.process_mode = Node.PROCESS_MODE_DISABLED
		_set_collision_enabled(box, false)
		var box_area := _ensure_drop_box_area(box)
		if box_area != null:
			box_area.monitoring = false


func _select_round_boxes(rng: RandomNumberGenerator) -> Array[Area3D]:
	_drop_box_areas.clear()
	var selected_boxes: Array = _draw_unique(_box_candidates(), ROUND_BOX_COUNT, rng)
	for selected_box: Variant in selected_boxes:
		var box := selected_box as RigidBody3D
		if box == null:
			continue
		box.visible = true
		box.process_mode = Node.PROCESS_MODE_INHERIT
		_set_collision_enabled(box, true)
		var box_area := _ensure_drop_box_area(box)
		if box_area != null:
			_register_box_area(box_area)
			_selected_box_names.append(box.name)
	return _drop_box_areas.duplicate()


func _select_round_books(rng: RandomNumberGenerator) -> Array[Node3D]:
	var selected_books: Array[Node3D] = []
	var high_books := _books_for_posture(POSTURE_JUMP)
	var low_books := _books_for_posture(POSTURE_CROUCH)
	var first_high: Array = _draw_unique(high_books, 1, rng)
	var first_low: Array = _draw_unique(low_books, 1, rng)
	for selected_book: Variant in first_high + first_low:
		var book := selected_book as Node3D
		if book != null:
			selected_books.append(book)
	var remaining_pool := _book_candidate_pool.duplicate()
	for selected_book: Node3D in selected_books:
		remaining_pool.erase(selected_book)
	for selected_book: Variant in _draw_unique(
		remaining_pool,
		ROUND_BOOK_COUNT - selected_books.size(),
		rng,
	):
		var book := selected_book as Node3D
		if book != null:
			selected_books.append(book)
	return selected_books


func _books_for_posture(posture: String) -> Array[Node3D]:
	var result: Array[Node3D] = []
	for book: Node3D in _book_candidate_pool:
		if _required_posture_for_book(book) == posture:
			result.append(book)
	return result


func _draw_unique(source: Array, count: int, rng: RandomNumberGenerator) -> Array:
	var pool := source.duplicate()
	var result: Array = []
	while not pool.is_empty() and result.size() < count:
		var index := rng.randi_range(0, pool.size() - 1)
		result.append(pool[index])
		pool.remove_at(index)
	return result


func _assign_correct_boxes(active_box_areas: Array[Area3D]) -> void:
	for book: RigidBody3D in _active_books:
		var source_book := _book_source_by_instance.get(book) as Node3D
		var correct_area: Area3D = _nearest_box_area_to_position(
			source_book.global_position,
			active_box_areas,
		)
		if correct_area != null:
			_correct_box_by_book[book] = correct_area
			correct_area.set_meta("put_book_correct_for_%s" % book.name, true)


func _place_player_and_task_card() -> void:
	player.global_transform = archive_spawn.global_transform
	_reparent_to_anchor(
		task_card.get_parent_node_3d(),
		archive_task_card_anchor,
	)


func _write_task_card() -> void:
	task_card.readable_title = TASK_TITLE
	task_card.readable_content = TASK_CONTENT
	task_card.interaction_text = "Read task card"
	task_card.is_disabled = false
	var card_object := task_card.get_parent() as CollisionObject3D
	if card_object != null:
		card_object.collision_layer = 2
	if task_card.is_node_ready():
		task_card.label_title.text = TASK_TITLE
		task_card.label_content.text = TASK_CONTENT


func _open_archive_door() -> void:
	archive_door.is_locked = false
	if not archive_door.is_open:
		archive_door.is_open = true
		archive_door.set_state()


func _physics_process(_delta: float) -> void:
	if _round_finished or target_box_area == null or carried_book == null:
		return
	_update_jump_pickup_window()
	_update_book_pickup_gate()
	_try_assisted_drop_into_nearby_box()
	_try_finish_book_in_box()


func _update_jump_pickup_window() -> void:
	if Input.is_action_just_pressed("jump") or (
		player != null and player.get("is_jumping") == true
	):
		_jump_pickup_window_until_ms = Time.get_ticks_msec() + JUMP_PICKUP_GRACE_MS


func _update_book_pickup_gate() -> void:
	for book: RigidBody3D in _active_books:
		var carry_component: Variant = book.get_node_or_null("CarryableComponent")
		if carry_component == null:
			continue
		if book in _completed_books:
			carry_component.is_disabled = true
			continue
		if carry_component.is_being_carried:
			carry_component.is_disabled = false
			continue
		carry_component.is_disabled = not _is_required_posture_satisfied(book)


func _is_required_posture_satisfied(book: RigidBody3D = null) -> bool:
	var posture: String = _book_posture_by_instance.get(book, _required_posture)
	match posture:
		POSTURE_CROUCH:
			return player != null and player.get("is_crouching") == true
		POSTURE_JUMP:
			if player == null:
				return false
			if player.get("is_jumping") == true:
				return true
			return (
				_jump_pickup_window_until_ms > 0
				and Time.get_ticks_msec() <= _jump_pickup_window_until_ms
			)
	return true


func _required_posture_for_book(book: Node3D) -> String:
	if book in [book_a, book_b, book_d]:
		return POSTURE_JUMP
	if book in [book_c, book_e, book_f]:
		return POSTURE_CROUCH
	return POSTURE_NONE


func _on_book_carry_state_changed(
	is_being_carried: bool,
	book: RigidBody3D,
	_carry_component: Variant,
) -> void:
	if is_being_carried:
		_book_has_been_carried = true
		_last_book_pickup_ms = Time.get_ticks_msec()
		_current_carried_book = book
		_book_posture_by_instance[book] = POSTURE_NONE
		_snap_book_to_carry_position(book)
		_update_book_pickup_gate()
	elif _current_carried_book == book:
		_current_carried_book = null


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
	if player == null:
		return null
	var interaction_component: Variant = player.get("player_interaction_component")
	if interaction_component != null:
		return interaction_component
	return player.get_node_or_null("PlayerInteractionComponent")


func _register_box_area(box_area: Area3D) -> void:
	if box_area == null:
		return
	box_area.monitoring = true
	_ensure_box_interaction(box_area)
	if box_area not in _drop_box_areas:
		_drop_box_areas.append(box_area)
	var callback := Callable(self, "_on_box_area_body_entered").bind(box_area)
	if not box_area.body_entered.is_connected(callback):
		box_area.body_entered.connect(callback)


func _ensure_drop_box_area(box: Node3D) -> Area3D:
	var existing_area := box.get_node_or_null("PutBookBoxArea") as Area3D
	if existing_area != null:
		return existing_area
	var template_shape := target_box_area.get_node_or_null("CollisionShape3D") as CollisionShape3D
	if template_shape == null or template_shape.shape == null:
		return null
	var box_area := Area3D.new()
	box_area.name = "PutBookBoxArea"
	box_area.collision_layer = 0
	box_area.collision_mask = target_box_area.collision_mask
	box_area.monitorable = false
	box.add_child(box_area)
	var shape := CollisionShape3D.new()
	shape.transform = template_shape.transform
	shape.shape = template_shape.shape.duplicate()
	box_area.add_child(shape)
	return box_area


func _ensure_box_interaction(box_area: Area3D) -> void:
	var box := box_area.get_parent() as RigidBody3D
	if box == null:
		return
	if box.get_script() == null:
		box.set_script(BoxInteractableScript)
	if box.get("interaction_nodes") == null:
		return
	box.set("display_name", "纸箱")
	box.add_to_group("interactable")
	var interaction := box.get_node_or_null("PutBookBoxDropInteraction")
	if interaction == null:
		interaction = Node3D.new()
		interaction.name = "PutBookBoxDropInteraction"
		interaction.set_script(BoxDropInteractionScript)
		box.add_child(interaction)
	interaction.set("monitor", self)
	interaction.set("box_area", box_area)
	interaction.set("input_map_action", "interact2")
	interaction.set("interaction_text", "放入箱子")
	interaction.set("prefer_while_carrying", true)
	var interaction_nodes: Array = box.get("interaction_nodes")
	if interaction not in interaction_nodes:
		interaction_nodes.append(interaction)
		box.set("interaction_nodes", interaction_nodes)


func _on_box_area_body_entered(body: Node, box_area: Area3D) -> void:
	var book := body as RigidBody3D
	if book != null and book in _active_books:
		_try_finish_book_in_box(book, box_area)


func _try_assisted_drop_into_nearby_box() -> void:
	if _round_finished or not _book_has_been_carried:
		return
	if not Input.is_action_just_pressed("interact2"):
		return
	if Time.get_ticks_msec() - _last_book_pickup_ms < ASSISTED_DROP_DEBOUNCE_MS:
		return
	var box_area := _nearest_box_area_to_player(ASSISTED_DROP_RANGE)
	if box_area == null:
		return
	assisted_drop_into_box_area(box_area)


func can_assisted_drop_to_box(box_area: Area3D) -> bool:
	return (
		not _round_finished
		and _book_has_been_carried
		and _current_carried_book != null
		and _current_carried_book not in _completed_books
		and _carry_component_for_book(_current_carried_book) != null
		and _carry_component_for_book(_current_carried_book).is_being_carried
		and _is_ground_box_area(box_area)
		and _is_box_area_near_player(box_area, ASSISTED_DROP_RANGE)
	)


func can_show_box_interaction(box_area: Area3D) -> bool:
	return (
		not _round_finished
		and _is_ground_box_area(box_area)
		and _is_box_area_near_player(box_area, ASSISTED_DROP_RANGE)
	)


func assisted_drop_into_box_area(box_area: Area3D) -> void:
	if not can_assisted_drop_to_box(box_area):
		return
	var book := _current_carried_book
	_place_book_inside_box(book, box_area)
	_finish_book_in_box(book, box_area)


func _nearest_box_area_to_player(max_distance: float) -> Area3D:
	if player == null:
		return null
	var nearest_area: Area3D = null
	var nearest_distance := max_distance
	for box_area: Area3D in _drop_box_areas:
		if not _is_ground_box_area(box_area):
			continue
		var distance := player.global_position.distance_to(box_area.global_position)
		if distance <= nearest_distance:
			nearest_area = box_area
			nearest_distance = distance
	return nearest_area


func _is_box_area_near_player(box_area: Area3D, max_distance: float) -> bool:
	return (
		player != null
		and box_area != null
		and player.global_position.distance_to(box_area.global_position) <= max_distance
	)


func _is_ground_box_area(box_area: Area3D) -> bool:
	return box_area != null and box_area.global_position.y <= GROUND_BOX_AREA_MAX_HEIGHT


func _nearest_box_area_to_position(position: Vector3, box_areas: Array[Area3D]) -> Area3D:
	var nearest_area: Area3D = null
	var nearest_distance := INF
	for box_area: Area3D in box_areas:
		var distance := position.distance_to(box_area.global_position)
		if distance < nearest_distance:
			nearest_area = box_area
			nearest_distance = distance
	return nearest_area


func _carry_component_for_book(book: RigidBody3D) -> Variant:
	if book == null:
		return null
	return book.get_node_or_null("CarryableComponent")


func _place_book_inside_box(book: RigidBody3D, box_area: Area3D) -> void:
	if book == null:
		return
	var carry_component: Variant = _carry_component_for_book(book)
	if (
		carry_component != null
		and carry_component.is_being_carried
		and carry_component.has_method("leave")
	):
		carry_component.leave()
	book.global_position = box_area.global_position
	book.linear_velocity = Vector3.ZERO
	book.angular_velocity = Vector3.ZERO
	_current_carried_book = null


func _try_finish_book_in_box(body: Node = null, entered_area: Area3D = null) -> void:
	if _round_finished:
		return
	var book := body as RigidBody3D
	if book != null:
		var carry_component: Variant = _carry_component_for_book(book)
		if carry_component != null and carry_component.is_being_carried:
			return
	if book in _active_books and entered_area != null:
		_finish_book_in_box(book, entered_area)
		return
	for active_book: RigidBody3D in _active_books:
		if active_book in _completed_books:
			continue
		var active_carry_component: Variant = _carry_component_for_book(active_book)
		if active_carry_component != null and active_carry_component.is_being_carried:
			continue
		for box_area: Area3D in _drop_box_areas:
			if active_book in box_area.get_overlapping_bodies():
				_finish_book_in_box(active_book, box_area)
				return


func _finish_book_in_box(book: RigidBody3D, box_area: Area3D) -> void:
	if _round_finished:
		return
	if book in _completed_books:
		return
	if _correct_box_by_book.get(book) != box_area:
		_round_finished = true
		game_finished.emit("failure", "book_in_wrong_box")
		return
	_completed_books.append(book)
	var carry_component: Variant = _carry_component_for_book(book)
	if carry_component != null:
		carry_component.is_disabled = true
	if _completed_books.size() >= _active_books.size():
		_round_finished = true
		game_finished.emit("success", "book_in_box")


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
	return {
		"book": _selected_book_names[0] if not _selected_book_names.is_empty() else "",
		"books": _selected_book_names.duplicate(),
		"boxes": _selected_box_names.duplicate(),
		"assignments": _round_assignments_snapshot(),
		"task_text": task_card.readable_content if task_card != null else "",
	}


func _round_assignments_snapshot() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for book: RigidBody3D in _active_books:
		var source_book := _book_source_by_instance.get(book) as Node3D
		var correct_area := _correct_box_by_book.get(book) as Area3D
		result.append({
			"book": source_book.name if source_book != null else book.name,
			"box": correct_area.get_parent().name if correct_area != null else "",
		})
	return result


func _has_required_nodes() -> bool:
	var required: Array[Node] = [
		game_over_screen,
		player,
		task_card,
		archive_door,
		carried_book,
		target_box,
		target_box_area,
		near_box_anchor,
		far_box_anchor,
		archive_spawn,
		archive_task_card_anchor,
		book_a,
		book_b,
		book_c,
		book_d,
		book_e,
		book_f,
	]
	for required_node: Node in required:
		if required_node == null:
			push_error("AIPlayPutBookMonitor is missing a required scene node")
			return false
	return true


func show_result(outcome: String, reason: String) -> void:
	game_over_screen.show_result(outcome, reason)
