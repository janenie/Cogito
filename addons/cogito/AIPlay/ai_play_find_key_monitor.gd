class_name AIPlayFindKeyMonitor
extends Node

signal game_finished(outcome: String, reason: String)

const ACT_REQUEST_LIMIT := 100
const KEY_SUBMISSION_INTERACTION_SCENE := preload(
	"res://addons/cogito/Components/Interactions/BasicInteraction.tscn"
)
const KEY_SUBMISSION_NODE_NAME := "KeySubmissionInteraction"
const KEY_SUBMISSION_TEXT := "提交此钥匙 / Submit this key"
const WRONG_PASSWORD_TEXT := "密码不对 / WRONG CODE"
const NPC_COLORS := {
	"李明": Color(0.18, 0.44, 0.62),
	"王芳": Color(0.58, 0.28, 0.62),
	"陈宇": Color(0.22, 0.56, 0.34),
}

@export var scenario_id: String = "find_key"
@export var game_over_screen: AIPlayGameOverScreen
@export var player: Node3D
@export var task_card: ReadableComponent
@export var setup: AIPlayFindKeySetup
@export var meeting_npc: FriendlyHumanNPC
@export var ceo_npc: FriendlyHumanNPC
@export var cubicle_npc: FriendlyHumanNPC
@export var keypad: CogitoKeypad
@export var archive_door: CogitoDoor
@export var entrance_spawn: Marker3D
@export var entrance_task_card_anchor: Marker3D
@export var lobby_spawn: Marker3D
@export var lobby_task_card_anchor: Marker3D
@export var archive_spawn: Marker3D
@export var archive_task_card_anchor: Marker3D
@export var round_seed: int = 0

var _round_data: Dictionary = {}
var _round_finished := false
var _registered_setup := false
var _keypad_connected := false


func _ready() -> void:
	var controller: Node = get_parent()
	if (
		controller != null
		and controller.has_method("is_requested_scenario")
		and not controller.is_requested_scenario(scenario_id)
	):
		return
	var selected_seed := round_seed
	if controller != null and controller.has_method("get_requested_round_seed"):
		var requested_seed: Dictionary = controller.get_requested_round_seed(
			OS.get_cmdline_user_args()
		)
		if not requested_seed["valid"]:
			return
		selected_seed = (
			requested_seed["value"]
			if requested_seed["provided"]
			else int(Time.get_ticks_usec() & 0x7fffffff)
		)
	configure_round.call_deferred(selected_seed)


func configure_round(seed_value: int = 0) -> void:
	if not _has_required_nodes():
		return
	_register_setup_objects()
	_round_data = AIPlayFindKeyRound.build(seed_value)
	_round_finished = false
	setup.set_scenario_active(true)
	setup.place_keys(seed_value)
	_configure_keys()
	_configure_documents()
	_configure_npcs()
	_configure_archive_lock()
	_place_player_and_task_card(seed_value)
	_write_task_card()
	_connect_terminals()


func get_act_request_limit() -> int:
	return ACT_REQUEST_LIMIT


func get_round_data() -> Dictionary:
	return _round_data.duplicate(true)


func get_decoy_keys() -> Array[RigidBody3D]:
	var result: Array[RigidBody3D] = []
	var archive_key: RigidBody3D = setup.key_by_region()["ARCHIVE"]
	for key: RigidBody3D in setup.keys():
		if key != archive_key:
			result.append(key)
	return result


func _register_setup_objects() -> void:
	if _registered_setup:
		return
	setup.register_external_npc(meeting_npc, "MEETING_ROOM")
	setup.register_external_npc(ceo_npc, "UPPER_OFFICE_CEO")
	setup.register_external_npc(cubicle_npc, "CUBICLE_AREA")
	_registered_setup = true


func _configure_keys() -> void:
	for key: RigidBody3D in setup.keys():
		key.freeze = true
		key.linear_velocity = Vector3.ZERO
		key.angular_velocity = Vector3.ZERO
		key.collision_layer = 3
		key.process_mode = Node.PROCESS_MODE_INHERIT
		var pickup := key.get_node_or_null("PickupComponent")
		if pickup != null:
			pickup.set("is_disabled", true)
		var submission := key.get_node_or_null(
			KEY_SUBMISSION_NODE_NAME
		) as InteractionComponent
		if submission == null:
			submission = (
				KEY_SUBMISSION_INTERACTION_SCENE.instantiate()
				as InteractionComponent
			)
			submission.name = KEY_SUBMISSION_NODE_NAME
			key.add_child(submission)
		submission.interaction_text = KEY_SUBMISSION_TEXT
		submission.is_disabled = false
		var submit_callback := _on_key_submitted.bind(key)
		if not submission.was_interacted_with.is_connected(submit_callback):
			submission.was_interacted_with.connect(submit_callback)
		var submission_nodes: Array[Node] = [submission]
		key.interaction_nodes = submission_nodes


func _configure_documents() -> void:
	var documents: Dictionary = setup.document_by_region()
	for room_id: String in _round_data["document_by_room"]:
		var stage: Dictionary = _round_data["document_by_room"][room_id]
		var document: ReadableComponent = documents[room_id]
		document.readable_title = "%s / %s" % [
			_round_data["contract_name"],
			stage["version_label"],
		]
		document.readable_content = (
			"合同 / CONTRACT：%s\n版本 / VERSION：%s\n状态 / STATUS：%s\n"
			+ "经手人 / HANDLER：%s\n记录时间 / RECORDED：%s %s\n\n%s"
		) % [
			_round_data["contract_name"],
			stage["version"],
			stage["status"],
			stage["handler"],
			stage["date_text"],
			stage["time_text"],
			stage["contract_body"],
		]
		document.interaction_text = "阅读合同记录 / Read contract record"
		document.is_disabled = false
		AIPlayReadablePresenter.configure(document)
		_update_readable_labels(document)


func _configure_npcs() -> void:
	var npcs: Dictionary = setup.npc_by_region()
	for room_id: String in _round_data["npc_by_room"]:
		var npc_data: Dictionary = _round_data["npc_by_room"][room_id]
		var npc: FriendlyHumanNPC = npcs[room_id]
		var display_name: String = npc_data["display_name"]
		npc.configure_public_identity(display_name, NPC_COLORS[display_name])
		npc.greeting_enabled = true
		npc.greeting_phrases = ["请说明这份合同的审查记录"]
		npc.selected_greeting_phrase = npc.greeting_phrases[0]
		npc.max_greeting_distance = 1.5
		npc.greeting_response_hint = npc_data["dialogue"]
		npc.default_dialogue_hint = npc_data["dialogue"]
		var interaction := npc.get_node_or_null("BasicInteraction")
		if interaction != null and "interaction_text" in interaction:
			interaction.interaction_text = "询问合同记录 / Ask about contract"
	ceo_npc.configure_route_loop(0, 1)
	cubicle_npc.configure_route_loop(0, 1)
	meeting_npc.configure_route_loop_from(
		"HumanMeetingRoomStart",
		0,
		1,
	)


func _configure_archive_lock() -> void:
	if archive_door.is_open:
		archive_door.close_door(player)
	archive_door.lock_door()
	keypad.is_locked = true
	keypad.passcode = _round_data["current"]["password"]
	keypad.require_submit_confirmation = false
	keypad.open_when_unlocked = true
	keypad.reset_submission()
	keypad.set_state()


func _place_player_and_task_card(seed_value: int) -> void:
	var options: Array[Dictionary] = [
		{"spawn": entrance_spawn, "card": entrance_task_card_anchor},
		{"spawn": lobby_spawn, "card": lobby_task_card_anchor},
		{"spawn": archive_spawn, "card": archive_task_card_anchor},
	]
	var selected: Dictionary = options[seed_value % options.size()]
	player.global_transform = selected["spawn"].global_transform
	var card_root := task_card.get_parent_node_3d()
	card_root.reparent(selected["card"], false)
	card_root.transform = Transform3D.IDENTITY
	AIPlayReadablePresenter.configure(task_card, true)


func _write_task_card() -> void:
	var content := (
		"老板不在办公室 / THE BOSS IS AWAY。\n\n"
		+ "任务 / OBJECTIVE：董事会会议开始前，调查 CEO OFFICE、MEETING ROOM "
		+ "和 CUBICLE AREA 内的合同记录，"
		+ "并向相关同事核实，找到与 %s 最终签署合同相关的那把钥匙。"
	) % _round_data["contract_name"]
	task_card.readable_title = "寻找合同钥匙 / FIND THE CONTRACT KEY"
	task_card.readable_content = content
	task_card.interaction_text = "读取任务说明 / Read task brief"
	task_card.is_disabled = false
	var card_object := task_card.get_parent() as CollisionObject3D
	if card_object != null:
		card_object.collision_layer = 2
	_update_readable_labels(task_card)


func _update_readable_labels(readable: ReadableComponent) -> void:
	if not readable.is_node_ready():
		return
	if readable.label_title != null:
		readable.label_title.text = readable.readable_title
	if readable.label_content != null:
		readable.label_content.text = readable.readable_content


func _connect_terminals() -> void:
	if not _keypad_connected:
		keypad.code_checked.connect(_on_code_checked)
		_keypad_connected = true


func _on_code_checked(is_correct: bool) -> void:
	if _round_finished:
		return
	if not is_correct:
		keypad.code_display.text = WRONG_PASSWORD_TEXT


func _on_key_submitted(
	_interaction_text: String,
	_input_map_action: String,
	key: RigidBody3D,
) -> void:
	if key == setup.key_by_region()["ARCHIVE"]:
		_finish_round("success", "key_picked_up")
	else:
		_finish_round("failure", "security_lockout")


func _finish_round(outcome: String, reason: String) -> void:
	if _round_finished:
		return
	_round_finished = true
	game_finished.emit(outcome, reason)


func _has_required_nodes() -> bool:
	for required: Node in [
		player,
		task_card,
		setup,
		meeting_npc,
		ceo_npc,
		cubicle_npc,
		keypad,
		archive_door,
		entrance_spawn,
		entrance_task_card_anchor,
		lobby_spawn,
		lobby_task_card_anchor,
		archive_spawn,
		archive_task_card_anchor,
	]:
		if required == null:
			push_error("find_key monitor missing a required node")
			return false
	return true
