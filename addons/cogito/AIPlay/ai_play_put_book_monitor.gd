class_name AIPlayPutBookMonitor
extends Node

signal game_finished(outcome: String, reason: String)

const TASK_TITLE := "整理档案室书籍"
const TASK_CONTENT := (
	"档案室里只有一本需要整理的书。\n\n"
	+ "进入档案室，找到唯一可见的书，把它放进地上的纸箱里。\n\n"
	+ "书可能在高处或低处，必要时跳起或蹲下。"
)

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
var _selected_box: String = ""
var _initial_visible_books: Array[Node3D] = []
var _book_carry_component: CogitoCarryableComponent


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
	if not target_box_area.body_entered.is_connected(_on_target_box_body_entered):
		target_box_area.body_entered.connect(_on_target_box_body_entered)
	_capture_initial_visible_books()
	configure_round(round_seed)


func configure_round(seed_value: int = 0) -> void:
	if not _has_required_nodes():
		return
	if _initial_visible_books.is_empty():
		_capture_initial_visible_books()
	if _initial_visible_books.is_empty():
		push_error("AIPlayPutBookMonitor needs at least one visible book candidate")
		return
	var rng := RandomNumberGenerator.new()
	if seed_value == 0:
		rng.randomize()
	else:
		rng.seed = seed_value
	_round_finished = false
	var selected_book: Node3D = _initial_visible_books[
		rng.randi_range(0, _initial_visible_books.size() - 1)
	]
	_selected_book_name = selected_book.name
	_hide_book_candidates()
	_place_carried_book(selected_book)
	_place_target_box(rng)
	_place_player_and_task_card()
	_write_task_card()
	_open_archive_door()


func _capture_initial_visible_books() -> void:
	_initial_visible_books.clear()
	for book: Node3D in _book_candidates():
		if book != null and book.visible:
			_initial_visible_books.append(book)


func _book_candidates() -> Array[Node3D]:
	return [book_a, book_b, book_c, book_d, book_e, book_f]


func _hide_book_candidates() -> void:
	for book: Node3D in _book_candidates():
		if book != null:
			book.visible = false
			book.process_mode = Node.PROCESS_MODE_DISABLED
			_set_collision_enabled(book, false)


func _place_carried_book(selected_book: Node3D) -> void:
	carried_book.visible = true
	carried_book.process_mode = Node.PROCESS_MODE_INHERIT
	carried_book.freeze = true
	carried_book.linear_velocity = Vector3.ZERO
	carried_book.angular_velocity = Vector3.ZERO
	carried_book.global_transform = selected_book.global_transform
	_set_collision_enabled(carried_book, true)
	_book_carry_component = carried_book.get_node_or_null(
		"CarryableComponent"
	) as CogitoCarryableComponent
	if _book_carry_component != null:
		_book_carry_component.is_disabled = false


func _place_target_box(rng: RandomNumberGenerator) -> void:
	var use_near_box: bool = rng.randi_range(0, 1) == 0
	var anchor: Marker3D = near_box_anchor if use_near_box else far_box_anchor
	_selected_box = "near" if use_near_box else "far"
	target_box.freeze = true
	target_box.linear_velocity = Vector3.ZERO
	target_box.angular_velocity = Vector3.ZERO
	target_box.global_transform = anchor.global_transform
	target_box.visible = true
	target_box.process_mode = Node.PROCESS_MODE_INHERIT
	target_box_area.monitoring = true


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
	_try_finish_book_in_box()


func _on_target_box_body_entered(body: Node) -> void:
	if body == carried_book:
		_try_finish_book_in_box(body)


func _try_finish_book_in_box(body: Node = null) -> void:
	if _round_finished:
		return
	if _book_carry_component != null and _book_carry_component.is_being_carried:
		return
	if body == carried_book or carried_book in target_box_area.get_overlapping_bodies():
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
		"book": _selected_book_name,
		"box": _selected_box,
		"task_text": task_card.readable_content if task_card != null else "",
	}


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
