class_name AIPlayArrangeMeetingBriefingsMonitor
extends Node

signal game_finished(outcome: String, reason: String)

const TASK_TITLE := "会议席位与资料分发 / ARRANGE MEETING BRIEFINGS"
const RECORD_TITLES := {
	"ceo": "CEO 办公室会议记录 / CEO OFFICE RECORD",
	"archive": "档案室会议记录 / ARCHIVE RECORD",
	"break_room": "休息室会议记录 / BREAK ROOM RECORD",
}
const RECORD_INTERACTION_TEXT := {
	"ceo": "Read CEO Office meeting record",
	"archive": "Read Archive meeting record",
	"break_room": "Read Break Room meeting record",
}

@export var scenario_id: String = "arrange_meeting_briefings"
@export var setup: Node3D
@export var player: Node3D
@export var task_card: ReadableComponent
@export var demo_hints: Node3D
@export var game_over_screen: AIPlayGameOverScreen
@export var record_readables: Array[ReadableComponent] = []
@export var folder_nodes: Array[RigidBody3D] = []
@export var seat_interactions: Array[AIPlayMeetingSeatInteraction] = []
@export var seat_snap_anchors: Array[Marker3D] = []
@export var verify_button: CogitoButton
@export var player_spawn: Marker3D
@export var task_card_anchor: Marker3D
@export var round_seed: int = 0

var _round := AIPlayMeetingBriefingRound.new()
var _round_finished: bool = false
var _task_active: bool = false
var _signals_connected: bool = false
var _folder_to_seat: Dictionary = {}
var _seat_to_folder: Dictionary = {}
var _submitted_map: Dictionary = {}
var _folder_home_transforms: Array[Transform3D] = []


func _ready() -> void:
	var controller: Node = get_parent()
	if (
		controller != null
		and controller.has_method("is_requested_scenario")
		and not controller.is_requested_scenario(scenario_id)
	):
		return
	_activate_task.call_deferred()


func _activate_task() -> void:
	if _task_active or not _has_required_nodes():
		return
	_task_active = true
	setup.visible = true
	setup.process_mode = Node.PROCESS_MODE_INHERIT
	_folder_home_transforms.clear()
	for folder: RigidBody3D in folder_nodes:
		_folder_home_transforms.append(folder.global_transform)
	for seat_index: int in range(seat_interactions.size()):
		seat_interactions[seat_index].monitor = self
		seat_interactions[seat_index].seat_id = (
			AIPlayMeetingBriefingRound.SEAT_IDS[seat_index]
		)
	_connect_signals()
	_set_records_enabled(true)
	_place_player_and_task_card()
	_disable_demo_hints()
	_configure_readable_ui(task_card, true)
	for readable: ReadableComponent in record_readables:
		_configure_readable_ui(readable)
	configure_round(round_seed)


func configure_round(seed_value: int = 0) -> void:
	if not _task_active or not _has_required_nodes():
		return
	_round_finished = false
	_submitted_map.clear()
	_folder_to_seat.clear()
	_seat_to_folder.clear()
	_reset_verify_button()
	_set_play_interactions_enabled(true)
	for index: int in range(folder_nodes.size()):
		var carry: CogitoCarryableComponent = _carry_component(folder_nodes[index])
		if carry != null and carry.is_being_carried:
			carry.leave()
		_reset_folder_to_home(index)
	if not _round.configure(seed_value):
		push_error("AIPlayArrangeMeetingBriefingsMonitor could not configure a round")
		_set_play_interactions_enabled(false)
		return
	_write_records()
	_write_task_card()


func place_carried_folder(
	seat_id: String,
	player_interaction: Variant,
) -> Dictionary:
	if not _task_active or _round_finished:
		return {"accepted": false, "reason": "locked"}
	if seat_id not in AIPlayMeetingBriefingRound.SEAT_IDS:
		return {"accepted": false, "reason": "invalid_seat"}
	if _seat_to_folder.has(seat_id):
		return {"accepted": false, "reason": "occupied"}
	if player_interaction == null:
		return {"accepted": false, "reason": "not_carrying"}
	var carried: Variant = player_interaction.get("carried_object")
	if carried == null:
		return {"accepted": false, "reason": "not_carrying"}
	var folder_index: int = _folder_index_for_carry(carried)
	if folder_index < 0:
		return {"accepted": false, "reason": "invalid_folder"}
	var carry: CogitoCarryableComponent = carried as CogitoCarryableComponent
	if carry == null or not carry.is_being_carried:
		return {"accepted": false, "reason": "not_carrying"}

	var folder_id: String = AIPlayMeetingBriefingRound.FOLDER_IDS[folder_index]
	_clear_folder_placement(folder_id)
	carry.leave()
	var folder: RigidBody3D = folder_nodes[folder_index]
	var seat_index: int = AIPlayMeetingBriefingRound.SEAT_IDS.find(seat_id)
	var anchor: Marker3D = seat_snap_anchors[seat_index]
	folder.linear_velocity = Vector3.ZERO
	folder.angular_velocity = Vector3.ZERO
	folder.freeze = true
	folder.global_transform = anchor.global_transform
	_folder_to_seat[folder_id] = seat_id
	_seat_to_folder[seat_id] = folder_id
	return {"accepted": true, "folder_id": folder_id, "seat_id": seat_id}


func get_round_snapshot() -> Dictionary:
	if not _task_active:
		return {}
	return _round.snapshot()


func get_folder_seat_map() -> Dictionary:
	return _folder_to_seat.duplicate(true)


func show_result(outcome: String, reason: String) -> void:
	game_over_screen.show_result(outcome, reason)


func _on_verify_pressed() -> void:
	if not _task_active or _round_finished:
		return
	_round_finished = true
	_submitted_map = _folder_to_seat.duplicate(true)
	_set_play_interactions_enabled(false)
	_freeze_all_folders()
	if _is_submitted_map_correct(_submitted_map):
		game_finished.emit("success", "meeting_prepared")
		return
	game_finished.emit("failure", "incorrect_seating_assignment")


func _is_submitted_map_correct(submitted: Dictionary) -> bool:
	if (
		submitted.size() != AIPlayMeetingBriefingRound.FOLDER_IDS.size()
		or _seat_to_folder.size() != AIPlayMeetingBriefingRound.SEAT_IDS.size()
	):
		return false
	var solution: Dictionary = _round.snapshot().get("solution", {})
	for folder_id: String in AIPlayMeetingBriefingRound.FOLDER_IDS:
		if submitted.get(folder_id, "") != solution.get(folder_id, ""):
			return false
	return true


func _write_records() -> void:
	var state: Dictionary = _round.snapshot()
	for record_index: int in range(AIPlayMeetingBriefingRound.RECORD_IDS.size()):
		var record_id: String = AIPlayMeetingBriefingRound.RECORD_IDS[record_index]
		var clue_index: int = state.record_clues[record_id]
		var content: String = _round.clue_text(state.clues[clue_index])
		var readable: ReadableComponent = record_readables[record_index]
		readable.readable_title = RECORD_TITLES[record_id]
		readable.readable_content = content
		readable.interaction_text = RECORD_INTERACTION_TEXT[record_id]
		readable.is_disabled = false
		if readable.is_node_ready():
			readable.label_title.text = readable.readable_title
			readable.label_content.text = content


func _write_task_card() -> void:
	var lines: Array[String] = [
		"任务目标：读取三份会议记录，推断四位参会者资料对应的会议席位。",
		"",
		"调查地点：CEO 办公室 (CEO OFFICE)、档案室 (ARCHIVE)、",
		"休息室 (BREAK ROOM)。每处记录只有一条线索，必须合并使用。",
		"",
		"参会者资料：李明、王芳、陈宇、赵宁。",
		"会议席位：电视侧 (TV SIDE)、会议室门侧 (DOOR SIDE)、",
		"电视对面侧 (OPPOSITE TV)、内墙侧 (INNER WALL)。",
		"桌面的 ↻ CLOCKWISE 标记定义“顺时针下一席”的方向。",
		"",
		"操作：从电视附近侧桌拿起资料；手持资料对准空席位，",
		"使用放置交互自动对齐。每席最多一份，提交前可重新调整。",
		"系统不会提前提示正误。确认四份资料后，按出口旁的 Verify。",
		"Verify 只有一次机会；资料缺失或摆错都会立即失败。",
	]
	var content: String = "\n".join(lines)
	task_card.readable_title = TASK_TITLE
	task_card.readable_content = content
	task_card.interaction_text = "Read task card"
	task_card.is_disabled = false
	var card_object := task_card.get_parent() as CollisionObject3D
	if card_object != null:
		card_object.collision_layer = 2
	if task_card.is_node_ready():
		task_card.label_title.text = TASK_TITLE
		task_card.label_content.text = content


func _place_player_and_task_card() -> void:
	player.global_transform = player_spawn.global_transform


func _disable_demo_hints() -> void:
	demo_hints.visible = false
	demo_hints.process_mode = Node.PROCESS_MODE_DISABLED
	var scene_root: Node = self
	while scene_root.get_parent() != null and scene_root.get_parent() != get_tree().root:
		scene_root = scene_root.get_parent()
	for child: Node in scene_root.find_children("*", "", true, false):
		var readable := child as ReadableComponent
		if (
			readable == null
			or readable == task_card
			or readable.interaction_text.strip_edges().to_lower() != "read hint"
		):
			continue
		readable.is_disabled = true
		var hint_object := readable.get_parent_node_3d()
		if hint_object != null:
			hint_object.visible = false
		var collision_object := hint_object as CollisionObject3D
		if collision_object != null:
			collision_object.collision_layer = 0
			collision_object.collision_mask = 0
	for child: Node in demo_hints.find_children("*", "CollisionObject3D", true, false):
		var collision_object := child as CollisionObject3D
		collision_object.collision_layer = 0
		collision_object.collision_mask = 0


func _configure_readable_ui(
	readable: ReadableComponent,
	disable_scrolling: bool = false,
) -> void:
	var readable_ui := readable.get_node_or_null("ReadableUi") as Control
	var scroll := readable.get_node_or_null(
		"ReadableUi/Bindings/ScrollContainer"
	) as ScrollContainer
	var title := readable.get_node_or_null(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer/ReadableTitle"
	) as Label
	var content := readable.get_node_or_null(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer/ReadableContent"
	) as RichTextLabel
	var popup_half_width: float = 500.0 if disable_scrolling else 440.0
	var popup_half_height: float = 430.0 if disable_scrolling else 360.0
	var text_width: float = 900.0 if disable_scrolling else 760.0
	if readable_ui != null:
		readable_ui.offset_left = -popup_half_width
		readable_ui.offset_top = -popup_half_height
		readable_ui.offset_right = popup_half_width
		readable_ui.offset_bottom = popup_half_height
	if scroll != null:
		scroll.custom_minimum_size = Vector2(text_width, 0.0)
		if disable_scrolling:
			scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
			scroll.follow_focus = false
	if title != null:
		title.custom_minimum_size = Vector2(text_width, 0.0)
		title.add_theme_font_size_override("font_size", 42)
	if content != null:
		content.custom_minimum_size = Vector2(text_width, 0.0)
		content.add_theme_font_size_override("normal_font_size", 24)


func _set_records_enabled(enabled: bool) -> void:
	for readable: ReadableComponent in record_readables:
		readable.is_disabled = not enabled
		var record_object := readable.get_parent() as CollisionObject3D
		if record_object != null:
			record_object.collision_layer = 3 if enabled else 0


func _set_play_interactions_enabled(enabled: bool) -> void:
	for folder: RigidBody3D in folder_nodes:
		folder.process_mode = (
			Node.PROCESS_MODE_INHERIT if enabled else Node.PROCESS_MODE_DISABLED
		)
		folder.collision_layer = 3 if enabled else 0
		folder.collision_mask = 3 if enabled else 0
		var carry: CogitoCarryableComponent = _carry_component(folder)
		if carry != null:
			carry.is_disabled = not enabled
	for interaction: AIPlayMeetingSeatInteraction in seat_interactions:
		interaction.is_disabled = not enabled
		var seat := interaction.get_parent() as CollisionObject3D
		if seat != null:
			seat.collision_layer = 3 if enabled else 0
			seat.collision_mask = 3 if enabled else 0
	verify_button.collision_layer = 3 if enabled else 0
	var verify_interaction := verify_button.get_node_or_null("BasicInteraction")
	if verify_interaction != null:
		verify_interaction.is_disabled = not enabled


func _reset_verify_button() -> void:
	verify_button.has_been_used = false
	verify_button.cooldown = 0.0
	verify_button.set_state()


func _reset_folder_to_home(index: int) -> void:
	var folder: RigidBody3D = folder_nodes[index]
	folder.linear_velocity = Vector3.ZERO
	folder.angular_velocity = Vector3.ZERO
	folder.freeze = true
	folder.global_transform = _folder_home_transforms[index]


func _freeze_all_folders() -> void:
	for folder: RigidBody3D in folder_nodes:
		folder.linear_velocity = Vector3.ZERO
		folder.angular_velocity = Vector3.ZERO
		folder.freeze = true


func _on_folder_carry_state_changed(
	is_being_carried: bool,
	folder_id: String,
) -> void:
	if not _task_active or _round_finished or not is_being_carried:
		return
	_clear_folder_placement(folder_id)


func _clear_folder_placement(folder_id: String) -> void:
	if not _folder_to_seat.has(folder_id):
		return
	var seat_id: String = _folder_to_seat[folder_id]
	_folder_to_seat.erase(folder_id)
	if _seat_to_folder.get(seat_id, "") == folder_id:
		_seat_to_folder.erase(seat_id)


func _carry_component(folder: RigidBody3D) -> CogitoCarryableComponent:
	return folder.get_node_or_null("CarryableComponent") as CogitoCarryableComponent


func _folder_index_for_carry(carry: Variant) -> int:
	for index: int in range(folder_nodes.size()):
		if _carry_component(folder_nodes[index]) == carry:
			return index
	return -1


func _connect_signals() -> void:
	if _signals_connected:
		return
	for index: int in range(folder_nodes.size()):
		var carry: CogitoCarryableComponent = _carry_component(folder_nodes[index])
		var folder_id: String = AIPlayMeetingBriefingRound.FOLDER_IDS[index]
		carry.carry_state_changed.connect(
			_on_folder_carry_state_changed.bind(folder_id)
		)
	verify_button.pressed.connect(_on_verify_pressed)
	_signals_connected = true


func _disconnect_signals() -> void:
	if not _signals_connected:
		return
	for index: int in range(folder_nodes.size()):
		var carry: CogitoCarryableComponent = _carry_component(folder_nodes[index])
		var folder_id: String = AIPlayMeetingBriefingRound.FOLDER_IDS[index]
		var callback := _on_folder_carry_state_changed.bind(folder_id)
		if carry.carry_state_changed.is_connected(callback):
			carry.carry_state_changed.disconnect(callback)
	if verify_button.pressed.is_connected(_on_verify_pressed):
		verify_button.pressed.disconnect(_on_verify_pressed)
	_signals_connected = false


func _has_required_nodes() -> bool:
	var required: Array[Node] = [
		setup,
		player,
		task_card,
		demo_hints,
		game_over_screen,
		verify_button,
		player_spawn,
		task_card_anchor,
	]
	if (
		record_readables.size() != AIPlayMeetingBriefingRound.RECORD_IDS.size()
		or folder_nodes.size() != AIPlayMeetingBriefingRound.FOLDER_IDS.size()
		or seat_interactions.size() != AIPlayMeetingBriefingRound.SEAT_IDS.size()
		or seat_snap_anchors.size() != AIPlayMeetingBriefingRound.SEAT_IDS.size()
	):
		push_error("AIPlayArrangeMeetingBriefingsMonitor has invalid task arrays")
		return false
	for node: Node in record_readables:
		required.append(node)
	for node: Node in folder_nodes:
		required.append(node)
	for node: Node in seat_interactions:
		required.append(node)
	for node: Node in seat_snap_anchors:
		required.append(node)
	for required_node: Node in required:
		if required_node == null:
			push_error("AIPlayArrangeMeetingBriefingsMonitor is missing a required node")
			return false
	for folder: RigidBody3D in folder_nodes:
		if _carry_component(folder) == null:
			push_error("Meeting briefing folder has no CarryableComponent")
			return false
	return true


func _exit_tree() -> void:
	if not _task_active:
		return
	_disconnect_signals()
	_set_play_interactions_enabled(false)
	_set_records_enabled(false)
	setup.visible = false
	setup.process_mode = Node.PROCESS_MODE_DISABLED
	_task_active = false
