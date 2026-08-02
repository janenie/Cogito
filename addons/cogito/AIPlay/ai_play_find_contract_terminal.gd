class_name AIPlayFindContractTerminal
extends Node

signal game_finished(outcome: String, reason: String)

@export var scenario_id: String = "find_contract"

const DATE_CANDIDATES: Array[String] = [
	"0115",
	"0228",
	"0412",
	"0526",
	"0714",
	"0830",
	"1019",
	"1221",
]
const VERSION_CANDIDATES: Array[String] = [
	"01",
	"03",
	"07",
	"12",
	"18",
	"24",
	"31",
	"42",
]
const ROUTES: Array[Array] = [
	["CUBICLE AREA", "MEETING ROOM", "CEO OFFICE"],
	["MEETING ROOM", "CEO OFFICE", "BREAK ROOM"],
	["LABORATORY", "CUBICLE AREA", "BREAK ROOM"],
]
const LOCKED_PASSCODE: String = "!!!!!!"

@export var keypad: CogitoKeypad
@export var game_over_screen: AIPlayGameOverScreen
@export var player: Node3D
@export var task_card: ReadableComponent
@export var clue_one: ReadableComponent
@export var clue_two: ReadableComponent
@export var ceo_file_clue: ReadableComponent
@export var break_room_file_clue: ReadableComponent
@export var cubicle_anchor: Node3D
@export var meeting_anchor: Node3D
@export var laboratory_anchor: Node3D
@export var entrance_spawn: Node3D
@export var entrance_task_card_anchor: Node3D
@export var lobby_spawn: Node3D
@export var lobby_task_card_anchor: Node3D
@export var archive_spawn: Node3D
@export var archive_task_card_anchor: Node3D
@export var round_seed: int = 0

var _selected_date: String
var _selected_version: String
var _version_first: bool
var _selected_route: Array
var _selected_spawn_name: String
var _progress: int = 0
var _round_ready: bool = false
var _round_finished: bool = false
var _active: bool = false
var _signals_connected: bool = false
var _active_clues: Array[ReadableComponent] = []


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
	configure_round(round_seed)


func configure_round(seed_value: int = 0) -> void:
	_connect_round_signals()
	_active = true
	var rng := RandomNumberGenerator.new()
	if seed_value == 0:
		rng.randomize()
	else:
		rng.seed = seed_value

	_selected_date = DATE_CANDIDATES[rng.randi_range(0, DATE_CANDIDATES.size() - 1)]
	_selected_version = VERSION_CANDIDATES[
		rng.randi_range(0, VERSION_CANDIDATES.size() - 1)
	]
	_version_first = rng.randi_range(0, 1) == 1
	_selected_route = ROUTES[rng.randi_range(0, ROUTES.size() - 1)].duplicate()
	var spawn_index: int = rng.randi_range(0, 2)
	_progress = 0
	_round_ready = false
	_round_finished = false
	keypad.passcode = LOCKED_PASSCODE
	_place_player_and_task_card(spawn_index)
	AIPlayReadablePresenter.configure(task_card, true)
	_place_clues()
	for active_clue: ReadableComponent in _active_clues:
		AIPlayReadablePresenter.configure(active_clue)
	_write_round_documents()
	_update_interaction_gates()


func _connect_round_signals() -> void:
	if _signals_connected:
		return
	keypad.code_checked.connect(_on_code_checked)
	task_card.has_been_read.connect(_on_task_card_read)
	clue_one.has_been_read.connect(_on_clue_readable.bind(clue_one))
	clue_two.has_been_read.connect(_on_clue_readable.bind(clue_two))
	ceo_file_clue.has_been_read.connect(
		_on_clue_readable.bind(ceo_file_clue)
	)
	break_room_file_clue.has_been_read.connect(
		_on_clue_readable.bind(break_room_file_clue)
	)
	_signals_connected = true


func get_round_snapshot() -> Dictionary:
	return {
		"date": _selected_date,
		"version": _selected_version,
		"version_first": _version_first,
		"route": _selected_route.duplicate(),
		"spawn": _selected_spawn_name,
		"passcode": _build_passcode(),
		"progress": _progress,
		"ready": _round_ready,
	}


func get_active_clues_for_test() -> Array[ReadableComponent]:
	return _active_clues.duplicate()


func _has_required_nodes() -> bool:
	var required_nodes: Array[Node] = [
		keypad,
		game_over_screen,
		player,
		task_card,
		clue_one,
		clue_two,
		ceo_file_clue,
		break_room_file_clue,
		cubicle_anchor,
		meeting_anchor,
		laboratory_anchor,
		entrance_spawn,
		entrance_task_card_anchor,
		lobby_spawn,
		lobby_task_card_anchor,
		archive_spawn,
		archive_task_card_anchor,
	]
	for required_node: Node in required_nodes:
		if required_node == null:
			push_error("AIPlayFindContractTerminal is missing a required scene node")
			return false
	return true


func _place_player_and_task_card(spawn_index: int) -> void:
	var spawn: Node3D
	var card_anchor: Node3D
	match spawn_index:
		0:
			spawn = entrance_spawn
			card_anchor = entrance_task_card_anchor
			_selected_spawn_name = "ENTRANCE"
		1:
			spawn = lobby_spawn
			card_anchor = lobby_task_card_anchor
			_selected_spawn_name = "LOBBY"
		_:
			spawn = archive_spawn
			card_anchor = archive_task_card_anchor
			_selected_spawn_name = "ARCHIVE ENTRANCE"
	player.global_transform = spawn.global_transform
	_reparent_to_anchor(task_card.get_parent_node_3d(), card_anchor)


func _place_clues() -> void:
	var anchors := {
		"CUBICLE AREA": cubicle_anchor,
		"MEETING ROOM": meeting_anchor,
		"LABORATORY": laboratory_anchor,
	}
	var movable_clues: Array[ReadableComponent] = [clue_one, clue_two]
	_active_clues.clear()
	for clue: ReadableComponent in movable_clues:
		var clue_object: Node3D = clue.get_parent_node_3d()
		clue_object.visible = false
		var collision_object := clue_object as CollisionObject3D
		if collision_object != null:
			collision_object.collision_layer = 0
		clue.is_disabled = true
	var ceo_file: Node3D = ceo_file_clue.get_parent_node_3d()
	ceo_file.visible = false
	var ceo_file_collision := ceo_file as CollisionObject3D
	if ceo_file_collision != null:
		ceo_file_collision.collision_layer = 0
	ceo_file_clue.is_disabled = true
	var break_room_file: Node3D = break_room_file_clue.get_parent_node_3d()
	break_room_file.visible = false
	var break_room_file_collision := break_room_file as CollisionObject3D
	if break_room_file_collision != null:
		break_room_file_collision.collision_layer = 0
	break_room_file_clue.is_disabled = true

	var movable_index: int = 0
	for location: String in _selected_route:
		if location == "CEO OFFICE":
			ceo_file.visible = true
			_active_clues.append(ceo_file_clue)
			continue
		if location == "BREAK ROOM":
			break_room_file.visible = true
			_active_clues.append(break_room_file_clue)
			continue
		var clue: ReadableComponent = movable_clues[movable_index]
		movable_index += 1
		var clue_object: Node3D = clue.get_parent_node_3d()
		clue_object.visible = true
		_reparent_to_anchor(clue_object, anchors[location])
		_active_clues.append(clue)


func _reparent_to_anchor(object: Node3D, anchor: Node3D) -> void:
	object.reparent(anchor, false)
	object.transform = Transform3D.IDENTITY


func _write_round_documents() -> void:
	_set_readable(
		task_card,
		"档案室合同任务 / ARCHIVE CONTRACT TASK",
		(
			"任务目标 / OBJECTIVE：按顺序读取三份合同记录，组合本局 6 位数字密码并解锁 ARCHIVE。\n\n"
			+ "调查流程 / INVESTIGATION：\n"
			+ "1. 从下方第一处地点开始；当前记录会公开下一处地点。\n"
			+ "2. 必须按记录 1/3 → 2/3 → 3/3 的顺序阅读，不能提前跳步。\n"
			+ "3. 记录可能是圆形 COGITO Hint、实体文件或书本，均可重复读取。\n\n"
			+ "第一处地点：%s\n\n"
			+ "提交规则 / SUBMISSION：三份记录分别给出日期代码、版本代码和拼接顺序。"
			+ "读完记录 3/3 后再使用 ARCHIVE 密码盘；提交错误密码会立即失败。"
		) % _selected_route[0],
		"读取任务说明 / Read task brief",
	)
	_set_readable(
		_active_clues[0],
		"合同线索 1/3：签署日期 / SIGNING DATE",
		(
			"签署日期代码：%s（MMDD）\n\n"
			+ "下一份合同记录位于：%s"
		) % [_selected_date, _selected_route[1]],
		"读取合同线索 1/3 / Read clue 1/3",
	)
	_set_readable(
		_active_clues[1],
		"合同线索 2/3：版本号 / VERSION",
		(
			"合同版本代码：%s（VV）\n\n"
			+ "最终授权记录位于：%s"
		) % [_selected_version, _selected_route[2]],
		"读取合同线索 2/3 / Read clue 2/3",
	)
	var order_text := (
		"版本号在前、签署日期在后（VV + MMDD）"
		if _version_first
		else "签署日期在前、版本号在后（MMDD + VV）"
	)
	_set_readable(
		_active_clues[2],
		"合同线索 3/3：门禁拼接顺序 / CODE ORDER",
		"最终授权：%s\n\n读完本记录后，ARCHIVE 密码盘才会接受本局密码。" % order_text,
		"读取合同线索 3/3 / Read clue 3/3",
	)


func _set_readable(
	readable: ReadableComponent,
	title: String,
	content: String,
	interaction_text: String,
) -> void:
	readable.readable_title = title
	readable.readable_content = content
	readable.interaction_text = interaction_text
	if readable.is_node_ready():
		readable.label_title.text = title
		if readable.rich_text:
			readable.label_content.bbcode_text = content
		else:
			readable.label_content.text = content


func _on_task_card_read() -> void:
	if _progress != 0:
		return
	_progress = 1
	_update_interaction_gates()


func _on_clue_readable(readable: ReadableComponent) -> void:
	var clue_index: int = _active_clues.find(readable)
	if clue_index < 0:
		return
	if _progress != clue_index + 1:
		return
	_progress += 1
	if _progress == 4:
		_round_ready = true
		keypad.passcode = _build_passcode()
	_update_interaction_gates()


func _update_interaction_gates() -> void:
	_set_readable_enabled(task_card, true)
	for clue: ReadableComponent in _active_clues:
		_set_readable_enabled(clue, true)


func _set_readable_enabled(readable: ReadableComponent, enabled: bool) -> void:
	var object: CollisionObject3D = readable.get_parent() as CollisionObject3D
	if object != null:
		object.collision_layer = 2 if enabled else 0
	readable.is_disabled = not enabled


func _build_passcode() -> String:
	if _version_first:
		return _selected_version + _selected_date
	return _selected_date + _selected_version


func _on_code_checked(is_correct: bool) -> void:
	if not _active or _round_finished or not _round_ready:
		return
	_round_finished = true
	if is_correct:
		game_finished.emit("success", "correct_password")
	else:
		game_finished.emit("failure", "wrong_password")


func show_result(outcome: String, reason: String) -> void:
	if game_over_screen == null:
		push_error("AIPlayFindContractTerminal cannot display the game result")
		return
	game_over_screen.show_result(outcome, reason)
