class_name AIPlayRepairLightingCircuitMonitor
extends Node

signal game_finished(outcome: String, reason: String)

const TASK_TITLE := "未知照明电路修复"
const CIRCUIT_LABELS := {
	"entrance": "入口落地灯",
	"ceo": "CEO 办公室落地灯",
	"lobby": "大厅六盏顶灯",
	"break_room": "休息室落地灯",
}

@export var scenario_id: String = "repair_lighting_circuit"
@export var setup: Node3D
@export var player: Node3D
@export var task_card: ReadableComponent
@export var game_over_screen: AIPlayGameOverScreen
@export var control_switch_a: CogitoSwitch
@export var control_switch_b: CogitoSwitch
@export var control_switch_c: CogitoSwitch
@export var control_switch_d: CogitoSwitch
@export var breaker_entrance: CogitoButton
@export var breaker_ceo: CogitoButton
@export var breaker_lobby: CogitoButton
@export var breaker_break_room: CogitoButton
@export var verify_button: CogitoButton
@export var panel_spawn: Marker3D
@export var task_card_anchor: Marker3D
@export var entrance_lamp: CogitoSwitch
@export var ceo_lamp: CogitoSwitch
@export var lobby_lamps: Array[CogitoSwitch] = []
@export var break_room_lamp: CogitoSwitch
@export var round_seed: int = 0

var _round := AIPlayLightingCircuitRound.new()
var _round_finished: bool = false
var _task_active: bool = false
var _configuring_round: bool = false
var _signals_connected: bool = false
var _original_a_targets: Array[NodePath] = []
var _original_lamp_interaction_states: Dictionary = {}
var _original_existing_lamp_states: Dictionary = {}


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
	_save_original_state()
	setup.visible = true
	setup.process_mode = Node.PROCESS_MODE_INHERIT
	_original_a_targets = control_switch_a.objects_call_interact.duplicate()
	control_switch_a.objects_call_interact.clear()
	_set_panel_interactions_enabled(true)
	for lamp: CogitoSwitch in _controlled_lamps():
		_set_basic_interaction_disabled(lamp, true)
	if break_room_lamp.collision_layer == 0:
		break_room_lamp.collision_layer = 3
	_connect_signals()
	_place_player_and_task_card()
	configure_round(round_seed)


func configure_round(seed_value: int = 0) -> void:
	if not _task_active or not _has_required_nodes():
		return
	_round_finished = false
	_set_panel_interactions_enabled(true)
	_reset_buttons()
	_round.configure(seed_value)
	var state: Dictionary = _round.snapshot()
	_configuring_round = true
	for control_id: String in AIPlayLightingCircuitRound.CONTROL_IDS:
		_set_switch_state(
			_control_switches()[control_id],
			state.control_states[control_id],
		)
	for circuit_id: String in AIPlayLightingCircuitRound.CIRCUIT_IDS:
		_apply_circuit_state(circuit_id, state.initial_states[circuit_id])
	_configuring_round = false
	_write_task_card(state.target_states)


func _on_control_switch_changed(is_on: bool, control_id: String) -> void:
	if _configuring_round or _round_finished or not _task_active:
		return
	var result: Dictionary = _round.set_control_state(control_id, is_on)
	if result.get("accepted", false) and result.get("applied", false):
		_apply_circuit_state(result.circuit, result.state)


func _on_breaker_pressed(circuit_id: String) -> void:
	if _round_finished or not _task_active:
		return
	var result: Dictionary = _round.reset_breaker(circuit_id)
	if not result.get("accepted", false):
		return
	_set_breaker_interactions_enabled(false)
	if not result.get("correct", false):
		_finish_round("failure", "wrong_breaker")
		return
	_apply_circuit_state(result.circuit, result.state)


func _on_verify_pressed() -> void:
	if _round_finished or not _task_active:
		return
	if _round.breaker_restored and _actual_configuration_matches_target():
		_finish_round("success", "circuit_repaired")
		return
	_finish_round("failure", "incorrect_circuit_configuration")


func _finish_round(outcome: String, reason: String) -> void:
	if _round_finished:
		return
	_round_finished = true
	_set_panel_interactions_enabled(false)
	game_finished.emit(outcome, reason)


func show_result(outcome: String, reason: String) -> void:
	game_over_screen.show_result(outcome, reason)


func get_round_snapshot() -> Dictionary:
	if not _task_active:
		return {}
	var state: Dictionary = _round.snapshot()
	state["task_text"] = task_card.readable_content
	return state


func _save_original_state() -> void:
	_original_lamp_interaction_states.clear()
	_original_existing_lamp_states.clear()
	for lamp: CogitoSwitch in _controlled_lamps():
		var interaction := lamp.get_node_or_null("BasicInteraction")
		if interaction != null:
			_original_lamp_interaction_states[lamp] = interaction.is_disabled
	for lamp: CogitoSwitch in _existing_lamps():
		_original_existing_lamp_states[lamp] = lamp.is_on


func _place_player_and_task_card() -> void:
	player.global_transform = panel_spawn.global_transform
	var card_object := task_card.get_parent_node_3d()
	card_object.reparent(task_card_anchor, false)
	card_object.transform = Transform3D.IDENTITY


func _write_task_card(target_states: Dictionary) -> void:
	var lines: Array[String] = [
		"将四组照明调整为以下目标状态：",
		"",
	]
	for circuit_id: String in AIPlayLightingCircuitRound.CIRCUIT_IDS:
		lines.append(
			"%s：%s"
			% [CIRCUIT_LABELS[circuit_id], _state_text(target_states[circuit_id])]
		)
	lines.append("")
	lines.append("找出跳闸线路，只选择一次断路器，完成后按 Verify。")
	var content := "\n".join(lines)
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


func _state_text(is_on: bool) -> String:
	return "ON" if is_on else "OFF"


func _set_switch_state(control: CogitoSwitch, is_on: bool) -> void:
	if control.is_on == is_on:
		control.set_state()
		return
	if is_on:
		control.switch_on()
	else:
		control.switch_off()


func _apply_circuit_state(circuit_id: String, is_on: bool) -> void:
	match circuit_id:
		"entrance":
			_set_switch_state(entrance_lamp, is_on)
		"ceo":
			_set_switch_state(ceo_lamp, is_on)
		"lobby":
			for lamp: CogitoSwitch in lobby_lamps:
				_set_switch_state(lamp, is_on)
		"break_room":
			_set_switch_state(break_room_lamp, is_on)


func _actual_configuration_matches_target() -> bool:
	var targets: Dictionary = _round.target_states
	if entrance_lamp.is_on != targets.entrance:
		return false
	if ceo_lamp.is_on != targets.ceo:
		return false
	for lamp: CogitoSwitch in lobby_lamps:
		if lamp.is_on != targets.lobby:
			return false
	return break_room_lamp.is_on == targets.break_room


func _control_switches() -> Dictionary:
	return {
		"A": control_switch_a,
		"B": control_switch_b,
		"C": control_switch_c,
		"D": control_switch_d,
	}


func _breaker_buttons() -> Dictionary:
	return {
		"entrance": breaker_entrance,
		"ceo": breaker_ceo,
		"lobby": breaker_lobby,
		"break_room": breaker_break_room,
	}


func _panel_buttons() -> Array[CogitoButton]:
	return [
		breaker_entrance,
		breaker_ceo,
		breaker_lobby,
		breaker_break_room,
		verify_button,
	]


func _controlled_lamps() -> Array[CogitoSwitch]:
	var lamps: Array[CogitoSwitch] = _existing_lamps()
	lamps.append(break_room_lamp)
	return lamps


func _existing_lamps() -> Array[CogitoSwitch]:
	var lamps: Array[CogitoSwitch] = [entrance_lamp, ceo_lamp]
	lamps.append_array(lobby_lamps)
	return lamps


func _set_panel_interactions_enabled(enabled: bool) -> void:
	for control: CogitoSwitch in _control_switches().values():
		control.collision_layer = 3 if enabled else 0
		_set_basic_interaction_disabled(control, not enabled)
	for button: CogitoButton in _panel_buttons():
		button.collision_layer = 3 if enabled else 0
		_set_basic_interaction_disabled(button, not enabled)


func _set_breaker_interactions_enabled(enabled: bool) -> void:
	for button: CogitoButton in _breaker_buttons().values():
		button.collision_layer = 3 if enabled else 0
		_set_basic_interaction_disabled(button, not enabled)


func _set_basic_interaction_disabled(object: Node, disabled: bool) -> void:
	var interaction := object.get_node_or_null("BasicInteraction")
	if interaction != null:
		interaction.is_disabled = disabled


func _reset_buttons() -> void:
	for button: CogitoButton in _panel_buttons():
		button.has_been_used = false
		button.cooldown = 0.0
		button.set_state()


func _connect_signals() -> void:
	if _signals_connected:
		return
	for control_id: String in AIPlayLightingCircuitRound.CONTROL_IDS:
		var control: CogitoSwitch = _control_switches()[control_id]
		control.switched.connect(_on_control_switch_changed.bind(control_id))
	for circuit_id: String in AIPlayLightingCircuitRound.CIRCUIT_IDS:
		var button: CogitoButton = _breaker_buttons()[circuit_id]
		button.pressed.connect(_on_breaker_pressed.bind(circuit_id))
	verify_button.pressed.connect(_on_verify_pressed)
	_signals_connected = true


func _disconnect_signals() -> void:
	if not _signals_connected:
		return
	for control_id: String in AIPlayLightingCircuitRound.CONTROL_IDS:
		var control: CogitoSwitch = _control_switches()[control_id]
		var control_callable := _on_control_switch_changed.bind(control_id)
		if control.switched.is_connected(control_callable):
			control.switched.disconnect(control_callable)
	for circuit_id: String in AIPlayLightingCircuitRound.CIRCUIT_IDS:
		var button: CogitoButton = _breaker_buttons()[circuit_id]
		var breaker_callable := _on_breaker_pressed.bind(circuit_id)
		if button.pressed.is_connected(breaker_callable):
			button.pressed.disconnect(breaker_callable)
	if verify_button.pressed.is_connected(_on_verify_pressed):
		verify_button.pressed.disconnect(_on_verify_pressed)
	_signals_connected = false


func _has_required_nodes() -> bool:
	var required: Array[Node] = [
		setup,
		player,
		task_card,
		game_over_screen,
		control_switch_a,
		control_switch_b,
		control_switch_c,
		control_switch_d,
		breaker_entrance,
		breaker_ceo,
		breaker_lobby,
		breaker_break_room,
		verify_button,
		panel_spawn,
		task_card_anchor,
		entrance_lamp,
		ceo_lamp,
		break_room_lamp,
	]
	if lobby_lamps.size() != 6:
		push_error("AIPlayRepairLightingCircuitMonitor requires exactly six Lobby lamps")
		return false
	for lamp: CogitoSwitch in lobby_lamps:
		required.append(lamp)
	for required_node: Node in required:
		if required_node == null:
			push_error("AIPlayRepairLightingCircuitMonitor is missing a required scene node")
			return false
	return true


func _exit_tree() -> void:
	if not _task_active:
		return
	_disconnect_signals()
	_set_panel_interactions_enabled(false)
	control_switch_a.objects_call_interact = _original_a_targets.duplicate()
	control_switch_a.collision_layer = 3
	_set_basic_interaction_disabled(control_switch_a, false)
	break_room_lamp.collision_layer = 0
	for lamp: CogitoSwitch in _controlled_lamps():
		if lamp in _original_lamp_interaction_states:
			_set_basic_interaction_disabled(
				lamp,
				_original_lamp_interaction_states[lamp],
			)
	_configuring_round = true
	for lamp: CogitoSwitch in _existing_lamps():
		if lamp in _original_existing_lamp_states:
			_set_switch_state(lamp, _original_existing_lamp_states[lamp])
	_configuring_round = false
	setup.visible = false
	setup.process_mode = Node.PROCESS_MODE_DISABLED
	_task_active = false
