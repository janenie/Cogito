class_name AIPlayGreetNPCMeetingMonitor
extends Node

signal game_finished(outcome: String, reason: String)

const TASK_TITLE := "先打招呼再去会议室"
const GREETING_PHRASES: Array[String] = ["你好", "要去开会了么？", "hi"]
const GREETING_DISTANCE := 1.8
const TASK_CONTENT := (
	"先找到正在办公室里走动的 NPC，在近距离和他打招呼。\n\n"
	+ "打过招呼以后，进入会议室，并把会议室门关上。"
)

@export var scenario_id: String = "greet_npc_meeting"
@export var game_over_screen: AIPlayGameOverScreen
@export var player: Node3D
@export var task_card: ReadableComponent
@export var npc: FriendlyHumanNPC
@export var conference_door: CogitoDoor
@export var meeting_room: Node3D
@export var entrance_spawn: Marker3D
@export var entrance_task_card_anchor: Marker3D
@export var meeting_room_local_min: Vector2 = Vector2(-6.6, -25.2)
@export var meeting_room_local_max: Vector2 = Vector2(0.8, -20.6)
@export var round_seed: int = 0

var _round_finished: bool = false
var _has_greeted_npc: bool = false
var _selected_greeting: String = ""
var _selected_route_start_index: int = -1
var _selected_route_direction: int = 1


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
	if not npc.greeted.is_connected(_on_npc_greeted):
		npc.greeted.connect(_on_npc_greeted)
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
	_has_greeted_npc = false
	_selected_greeting = GREETING_PHRASES[
		rng.randi_range(0, GREETING_PHRASES.size() - 1)
	]
	var route_count := max(npc.route_point_count(), 1)
	_selected_route_start_index = rng.randi_range(0, route_count - 1)
	_selected_route_direction = -1 if rng.randi_range(0, 1) == 0 else 1
	_configure_npc()
	_place_player_and_task_card()
	_write_task_card()
	_open_meeting_door()


func _configure_npc() -> void:
	npc.greeting_enabled = true
	npc.greeting_phrases = GREETING_PHRASES.duplicate()
	npc.selected_greeting_phrase = _selected_greeting
	npc.max_greeting_distance = GREETING_DISTANCE
	npc.configure_route_loop(
		_selected_route_start_index,
		_selected_route_direction,
	)
	var interaction := npc.get_node_or_null("BasicInteraction")
	if interaction != null and "interaction_text" in interaction:
		interaction.interaction_text = _selected_greeting


func _place_player_and_task_card() -> void:
	player.global_transform = entrance_spawn.global_transform
	_reparent_to_anchor(
		task_card.get_parent_node_3d(),
		entrance_task_card_anchor,
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


func _open_meeting_door() -> void:
	conference_door.is_locked = false
	if not conference_door.is_open:
		conference_door.is_open = true
		conference_door.set_state()


func _physics_process(_delta: float) -> void:
	_try_finish_meeting_goal()


func _on_npc_greeted(_phrase: String) -> void:
	if _round_finished:
		return
	_has_greeted_npc = true
	_try_finish_meeting_goal()


func _try_finish_meeting_goal() -> void:
	if _round_finished or not _has_greeted_npc:
		return
	if conference_door.is_open:
		return
	if not _is_player_inside_meeting_room():
		return
	_round_finished = true
	game_finished.emit("success", "meeting_door_closed")


func _is_player_inside_meeting_room() -> bool:
	var local_position := meeting_room.to_local(player.global_position)
	return (
		local_position.x >= meeting_room_local_min.x
		and local_position.x <= meeting_room_local_max.x
		and local_position.z >= meeting_room_local_min.y
		and local_position.z <= meeting_room_local_max.y
	)


func _reparent_to_anchor(object: Node3D, anchor: Node3D) -> void:
	object.reparent(anchor, false)
	object.transform = Transform3D.IDENTITY


func get_round_snapshot() -> Dictionary:
	return {
		"greeting": _selected_greeting,
		"route_start_index": _selected_route_start_index,
		"route_direction": _selected_route_direction,
		"has_greeted_npc": _has_greeted_npc,
		"task_text": task_card.readable_content if task_card != null else "",
	}


func _has_required_nodes() -> bool:
	var required: Array[Node] = [
		game_over_screen,
		player,
		task_card,
		npc,
		conference_door,
		meeting_room,
		entrance_spawn,
		entrance_task_card_anchor,
	]
	for required_node: Node in required:
		if required_node == null:
			push_error("AIPlayGreetNPCMeetingMonitor is missing a required scene node")
			return false
	return true


func show_result(outcome: String, reason: String) -> void:
	game_over_screen.show_result(outcome, reason)
