class_name AIPlayFindKeyMonitor
extends Node

signal game_finished(outcome: String, reason: String)

const LOCATION_IDS: Array[String] = [
	"laptop_desk",
	"archive_sofa",
	"meeting_table",
	"tv_coffee_table",
]
const LOCATION_TASK_TEXT := {
	"laptop_desk": "钥匙在有笔记本电脑的办公桌上。",
	"archive_sofa": "钥匙在档案室旁边的沙发上。",
	"meeting_table": "钥匙在会议室的长桌上。",
	"tv_coffee_table": "钥匙在有大电视的茶几上。",
}
const ACT_REQUEST_LIMIT: int = 150

@export var scenario_id: String = "find_key"
@export var game_over_screen: AIPlayGameOverScreen
@export var player: Node3D
@export var task_card: ReadableComponent
@export var key: RigidBody3D
@export var laptop_desk_anchor: Marker3D
@export var archive_sofa_anchor: Marker3D
@export var meeting_table_anchor: Marker3D
@export var tv_coffee_table_anchor: Marker3D
@export var entrance_spawn: Marker3D
@export var entrance_task_card_anchor: Marker3D
@export var lobby_spawn: Marker3D
@export var lobby_task_card_anchor: Marker3D
@export var archive_spawn: Marker3D
@export var archive_task_card_anchor: Marker3D
@export var round_seed: int = 0

var _round_finished: bool = false
var _pickup_connected: bool = false
var _selected_location: String = ""
var _selected_spawn: String = ""
var _spawn_distances: Array[float] = []


func _ready() -> void:
	var controller: Node = get_parent()
	if (
		controller != null
		and controller.has_method("is_requested_scenario")
		and not controller.is_requested_scenario(scenario_id)
	):
		return
	configure_round(round_seed)


func configure_round(seed_value: int = 0) -> void:
	if not _has_required_nodes():
		return
	var rng := RandomNumberGenerator.new()
	if seed_value == 0:
		rng.randomize()
	else:
		rng.seed = seed_value
	_round_finished = false
	var location_index: int = rng.randi_range(0, LOCATION_IDS.size() - 1)
	_selected_location = LOCATION_IDS[location_index]
	var key_anchors := _key_anchors()
	_place_key(key_anchors[_selected_location])
	var selected_spawn: Dictionary = _select_farthest_spawn(rng)
	_selected_spawn = selected_spawn["id"]
	player.global_transform = selected_spawn["spawn"].global_transform
	_reparent_to_anchor(
		task_card.get_parent_node_3d(),
		selected_spawn["card"],
	)
	AIPlayReadablePresenter.configure(task_card, true)
	_write_task_card()
	_connect_pickup()


func _key_anchors() -> Dictionary:
	return {
		"laptop_desk": laptop_desk_anchor,
		"archive_sofa": archive_sofa_anchor,
		"meeting_table": meeting_table_anchor,
		"tv_coffee_table": tv_coffee_table_anchor,
	}


func get_act_request_limit() -> int:
	return ACT_REQUEST_LIMIT


func _spawn_options() -> Array[Dictionary]:
	return [
		{
			"id": "ENTRANCE",
			"spawn": entrance_spawn,
			"card": entrance_task_card_anchor,
		},
		{
			"id": "LOBBY",
			"spawn": lobby_spawn,
			"card": lobby_task_card_anchor,
		},
		{
			"id": "ARCHIVE ENTRANCE",
			"spawn": archive_spawn,
			"card": archive_task_card_anchor,
		},
	]


func _place_key(anchor: Marker3D) -> void:
	key.freeze = true
	key.linear_velocity = Vector3.ZERO
	key.angular_velocity = Vector3.ZERO
	_reparent_to_anchor(key, anchor)


func _select_farthest_spawn(rng: RandomNumberGenerator) -> Dictionary:
	var options: Array[Dictionary] = _spawn_options()
	var farthest: Array[Dictionary] = []
	var max_distance: float = -1.0
	_spawn_distances.clear()
	for option: Dictionary in options:
		var distance: float = option["spawn"].global_position.distance_to(
			key.global_position
		)
		_spawn_distances.append(distance)
		if distance > max_distance and not is_equal_approx(
			distance,
			max_distance,
		):
			max_distance = distance
			farthest = [option]
		elif is_equal_approx(distance, max_distance):
			farthest.append(option)
	return farthest[rng.randi_range(0, farthest.size() - 1)]


func _write_task_card() -> void:
	var content: String = (
		"任务目标 / OBJECTIVE：根据本局位置线索，找到并拾取办公室里唯一的金色钥匙。\n\n"
		+ "位置线索 / LOCATION CLUE："
		+ LOCATION_TASK_TEXT[_selected_location]
		+ "\n\n操作 / ACTION：观察房间文字标识和家具特征；靠近并对准钥匙，"
		+ "出现拾取提示后执行交互。\n\n"
		+ "完成条件 / SUCCESS：必须实际拾取钥匙；只看到钥匙不算完成。"
		+ "搜索错误区域不会立即失败。"
	)
	task_card.readable_title = "寻找办公室钥匙 / FIND OFFICE KEY"
	task_card.readable_content = content
	task_card.interaction_text = "读取任务说明 / Read task brief"
	task_card.is_disabled = false
	var card_object := task_card.get_parent() as CollisionObject3D
	if card_object != null:
		card_object.collision_layer = 2
	if task_card.is_node_ready():
		task_card.label_title.text = task_card.readable_title
		task_card.label_content.text = content


func _connect_pickup() -> void:
	if _pickup_connected:
		return
	var pickup: Node = key.get_node("PickupComponent")
	pickup.was_interacted_with.connect(_on_key_picked_up)
	_pickup_connected = true


func _on_key_picked_up(
	_interaction_text: String,
	_input_map_action: String,
) -> void:
	if _round_finished:
		return
	_round_finished = true
	game_finished.emit("success", "key_picked_up")


func _reparent_to_anchor(object: Node3D, anchor: Node3D) -> void:
	object.reparent(anchor, false)
	object.transform = Transform3D.IDENTITY


func get_round_snapshot() -> Dictionary:
	var selected_distance: float = 0.0
	var options: Array[Dictionary] = _spawn_options()
	for index: int in options.size():
		if options[index]["id"] == _selected_spawn:
			selected_distance = _spawn_distances[index]
			break
	return {
		"location": _selected_location,
		"spawn": _selected_spawn,
		"spawn_distances": _spawn_distances.duplicate(),
		"selected_spawn_distance": selected_distance,
		"task_text": LOCATION_TASK_TEXT.get(_selected_location, ""),
	}


func _has_required_nodes() -> bool:
	var required: Array[Node] = [
		game_over_screen,
		player,
		task_card,
		key,
		laptop_desk_anchor,
		archive_sofa_anchor,
		meeting_table_anchor,
		tv_coffee_table_anchor,
		entrance_spawn,
		entrance_task_card_anchor,
		lobby_spawn,
		lobby_task_card_anchor,
		archive_spawn,
		archive_task_card_anchor,
	]
	for required_node: Node in required:
		if required_node == null:
			push_error("AIPlayFindKeyMonitor is missing a required scene node")
			return false
	return true


func show_result(outcome: String, reason: String) -> void:
	game_over_screen.show_result(outcome, reason)
