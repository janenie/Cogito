class_name AIPlayGreetNPCMeetingMonitor
extends Node

signal game_finished(outcome: String, reason: String)

const FRIENDLY_HUMAN_NPC_SCENE := preload(
	"res://addons/cogito/DemoScenes/friendly_human_npc.tscn"
)
const TASK_TITLE := "先打招呼再去会议室 / GREET, THEN MEET"
const GREETING_PHRASES: Array[String] = ["你好", "要去开会了么？", "hi"]
const GREETING_DISTANCE := 1.8
const MAX_WRONG_GREETINGS := 2
const PATROL_ROUTE_FIRST_POINT := "HumanLobbyExitLane"
const MEETING_APPROACH_POINTS: Array[String] = [
	"HumanMeetingRoomDoorOutside",
	"HumanMeetingRoomDoorInside",
]
const PLAYER_DESTINATION_DISTANCE := 2.4
const NPC_DESTINATION_DISTANCE := 1.25
const NPC_IDENTITIES := [
	{
		"display_name": "H. Voss",
		"shirt_label": "蓝色上衣 / BLUE SHIRT",
		"shirt_color": Color(0.18, 0.44, 0.62, 1.0),
	},
	{
		"display_name": "M. Chen",
		"shirt_label": "绿色上衣 / GREEN SHIRT",
		"shirt_color": Color(0.22, 0.56, 0.34, 1.0),
	},
	{
		"display_name": "R. Diaz",
		"shirt_label": "橙色上衣 / ORANGE SHIRT",
		"shirt_color": Color(0.78, 0.36, 0.12, 1.0),
	},
]
const MEETING_DESTINATIONS := [
	{
		"label": "靠窗区 / WINDOW SIDE",
		"local_position": Vector3(-5.45, 0.05, -22.15),
	},
	{
		"label": "屏幕区 / SCREEN SIDE",
		"local_position": Vector3(-1.15, 0.05, -22.05),
	},
]

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
var _wrong_greeting_count: int = 0
var _selected_greeting: String = ""
var _selected_route_start_index: int = -1
var _selected_route_direction: int = 1
var _target_npc_index: int = -1
var _target_identity: Dictionary = {}
var _selected_destination: Dictionary = {}
var _target_npc: FriendlyHumanNPC
var _destination_marker: Marker3D
var _candidate_npcs: Array[FriendlyHumanNPC] = []


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
	call_deferred("_initialize_round")


func _initialize_round() -> void:
	if not is_inside_tree() or not _has_required_nodes():
		return
	_ensure_candidate_npcs()
	_ensure_destination_marker()
	configure_round(round_seed)


func configure_round(seed_value: int = 0) -> void:
	if not _has_required_nodes():
		return
	var rng := RandomNumberGenerator.new()
	if seed_value == 0:
		rng.randomize()
	else:
		rng.seed = seed_value
	_ensure_candidate_npcs()
	_ensure_destination_marker()
	if _candidate_npcs.size() != NPC_IDENTITIES.size():
		return
	_round_finished = false
	_has_greeted_npc = false
	_wrong_greeting_count = 0
	_selected_greeting = GREETING_PHRASES[
		rng.randi_range(0, GREETING_PHRASES.size() - 1)
	]
	var route_count := max(npc.route_point_count(), 1)
	_selected_route_start_index = rng.randi_range(0, route_count - 1)
	_selected_route_direction = -1 if rng.randi_range(0, 1) == 0 else 1
	_target_npc_index = rng.randi_range(0, _candidate_npcs.size() - 1)
	_target_npc = _candidate_npcs[_target_npc_index]
	_target_identity = NPC_IDENTITIES[_target_npc_index]
	_selected_destination = MEETING_DESTINATIONS[
		rng.randi_range(0, MEETING_DESTINATIONS.size() - 1)
	]
	_destination_marker.position = _selected_destination["local_position"]
	_configure_npcs(route_count)
	_place_player_and_task_card()
	AIPlayReadablePresenter.configure(task_card, true)
	_write_task_card()
	_open_meeting_door()


func _configure_npcs(route_count: int) -> void:
	for index: int in range(_candidate_npcs.size()):
		var candidate := _candidate_npcs[index]
		var identity: Dictionary = NPC_IDENTITIES[index]
		candidate.configure_public_identity(
			identity["display_name"],
			identity["shirt_color"],
		)
		candidate.greeting_enabled = true
		candidate.greeting_phrases = GREETING_PHRASES.duplicate()
		candidate.selected_greeting_phrase = _selected_greeting
		candidate.max_greeting_distance = GREETING_DISTANCE
		candidate.auto_open_doors = true
		candidate.auto_close_doors = true
		candidate.greeting_response_hint = (
			"%s：在 %s 开会，请跟我走。 / Meet at %s. Follow me."
			% [
				identity["display_name"],
				_selected_destination["label"],
				_selected_destination["label"],
			]
			if index == _target_npc_index
			else "%s：不是我，请核对任务卡上的上衣颜色。 / Not me; check the shirt colour."
			% identity["display_name"]
		)
		candidate.default_dialogue_hint = candidate.greeting_response_hint
		var route_start := (_selected_route_start_index + index * 2) % route_count
		candidate.configure_route_loop_from(
			PATROL_ROUTE_FIRST_POINT,
			route_start,
			_selected_route_direction,
		)
		var interaction := candidate.get_node_or_null("BasicInteraction")
		if interaction != null and "interaction_text" in interaction:
			interaction.interaction_text = _selected_greeting


func _place_player_and_task_card() -> void:
	player.global_transform = entrance_spawn.global_transform
	_reparent_to_anchor(
		task_card.get_parent_node_3d(),
		entrance_task_card_anchor,
	)


func _write_task_card() -> void:
	var task_content := (
		"任务目标 / OBJECTIVE：找到穿%s的联系人 %s，先打招呼，再一起进入会议室指定区域并关门。\n\n"
		+ "操作步骤 / STEPS：\n"
		+ "1. 办公室有三名走动的同事；按上衣颜色识别联系人。\n"
		+ "2. 正确联系人会告知本局会面区域并带路；跟随对方进入 MEETING ROOM。\n"
		+ "3. 你和联系人都到达指定区域后，从室内关上会议室门。\n\n"
		+ "错误限制 / LIMIT：第二次问候错误同事会立即失败；同一错误同事只计一次。\n"
		+ "完成条件 / SUCCESS：已问候正确联系人、双方到达指定区域、会议室门关闭。"
	) % [_target_identity["shirt_label"], _target_identity["display_name"]]
	task_card.readable_title = TASK_TITLE
	task_card.readable_content = task_content
	task_card.interaction_text = "读取任务说明 / Read task brief"
	task_card.is_disabled = false
	var card_object := task_card.get_parent() as CollisionObject3D
	if card_object != null:
		card_object.collision_layer = 2
	if task_card.is_node_ready():
		task_card.label_title.text = TASK_TITLE
		task_card.label_content.text = task_content


func _open_meeting_door() -> void:
	conference_door.is_locked = false
	if not conference_door.is_open:
		conference_door.is_open = true
		conference_door.set_state()


func _physics_process(_delta: float) -> void:
	_try_finish_meeting_goal()


func _on_candidate_greeted(_phrase: String, greeted_npc: FriendlyHumanNPC) -> void:
	if _round_finished:
		return
	if greeted_npc != _target_npc:
		greeted_npc.greeting_enabled = false
		_wrong_greeting_count += 1
		if _wrong_greeting_count >= MAX_WRONG_GREETINGS:
			_round_finished = true
			game_finished.emit("failure", "wrong_npc_limit")
		return
	_has_greeted_npc = true
	for candidate: FriendlyHumanNPC in _candidate_npcs:
		candidate.greeting_enabled = candidate == _target_npc
	var meeting_route: Array[Node3D] = []
	for point_name: String in MEETING_APPROACH_POINTS:
		var route_point := _target_npc.route_point_by_name(point_name)
		if route_point != null:
			meeting_route.append(route_point)
	meeting_route.append(_destination_marker)
	_target_npc.configure_route_to_points(meeting_route)
	_try_finish_meeting_goal()


func _try_finish_meeting_goal() -> void:
	if _round_finished or not _has_greeted_npc:
		return
	if conference_door.is_open:
		return
	if not _is_player_inside_meeting_room() or not _is_player_at_destination():
		return
	if not _is_target_npc_at_destination():
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


func _is_player_at_destination() -> bool:
	return _flat_distance(player, _destination_marker) <= PLAYER_DESTINATION_DISTANCE


func _is_target_npc_at_destination() -> bool:
	return _flat_distance(_target_npc, _destination_marker) <= NPC_DESTINATION_DISTANCE


func _flat_distance(first: Node3D, second: Node3D) -> float:
	if first == null or second == null:
		return INF
	var offset := first.global_position - second.global_position
	offset.y = 0.0
	return offset.length()


func _ensure_candidate_npcs() -> void:
	if not _candidate_npcs.is_empty():
		return
	_candidate_npcs.append(npc)
	for index: int in range(1, NPC_IDENTITIES.size()):
		var candidate := FRIENDLY_HUMAN_NPC_SCENE.instantiate() as FriendlyHumanNPC
		candidate.name = "GreetMeetingCandidate%d" % (index + 1)
		candidate.route_root = npc.route_root
		candidate.final_facing_target = npc.final_facing_target
		candidate.walk_speed = npc.walk_speed
		candidate.scale = npc.scale
		npc.get_parent().add_child(candidate)
		_candidate_npcs.append(candidate)
	for candidate: FriendlyHumanNPC in _candidate_npcs:
		var callback := _on_candidate_greeted.bind(candidate)
		if not candidate.greeted.is_connected(callback):
			candidate.greeted.connect(callback)


func _ensure_destination_marker() -> void:
	if _destination_marker != null:
		return
	_destination_marker = Marker3D.new()
	_destination_marker.name = "GreetMeetingDestination"
	meeting_room.add_child(_destination_marker)


func _reparent_to_anchor(object: Node3D, anchor: Node3D) -> void:
	object.reparent(anchor, false)
	object.transform = Transform3D.IDENTITY


func get_round_snapshot() -> Dictionary:
	return {
		"greeting": _selected_greeting,
		"route_start_index": _selected_route_start_index,
		"route_direction": _selected_route_direction,
		"has_greeted_npc": _has_greeted_npc,
		"wrong_greeting_count": _wrong_greeting_count,
		"candidate_count": _candidate_npcs.size(),
		"target_npc_index": _target_npc_index,
		"target_display_name": _target_identity.get("display_name", ""),
		"target_shirt_label": _target_identity.get("shirt_label", ""),
		"destination_label": _selected_destination.get("label", ""),
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
