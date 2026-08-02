class_name AIPlayRepairLightingCircuitMonitor
extends Node

signal game_finished(outcome: String, reason: String)

const TASK_TITLE := "未知照明电路修复"
const CIRCUIT_LABELS := {
	"entrance": "入口落地灯",
	"ceo": "CEO 办公室落地灯",
	"lobby": "大厅六盏顶灯（右侧高处一排）",
	"break_room": "休息室落地灯",
}
const BREAKER_PROMPT_LABELS := {
	"entrance": "Entrance lighting",
	"ceo": "CEO office lighting",
	"lobby": "Lobby ceiling lighting",
	"break_room": "Break room lighting",
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
var _original_control_prompts: Dictionary = {}
var _original_button_prompts: Dictionary = {}
var _original_control_states: Dictionary = {}
var _original_panel_collision_layers: Dictionary = {}
var _original_panel_interaction_states: Dictionary = {}
var _original_break_room_collision_layer: int = 0


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
	_configure_panel_prompts()
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
	AIPlayReadablePresenter.configure(task_card, true)
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
	_original_control_prompts.clear()
	for control: CogitoSwitch in _control_switches().values():
		_original_control_prompts[control] = {
			"on": control.interaction_text_when_on,
			"off": control.interaction_text_when_off,
		}
	_original_control_states.clear()
	for control: CogitoSwitch in _control_switches().values():
		_original_control_states[control] = control.is_on
	_original_button_prompts.clear()
	for button: CogitoButton in _panel_buttons():
		_original_button_prompts[button] = {
			"usable": button.usable_interaction_text,
			"unusable": button.unusable_interaction_text,
			"used_hint": button.has_been_used_hint,
			"has_been_used": button.has_been_used,
			"cooldown": button.cooldown,
		}
	_original_panel_collision_layers.clear()
	_original_panel_interaction_states.clear()
	for object: Node3D in _panel_objects():
		_original_panel_collision_layers[object] = object.collision_layer
		var interaction := object.get_node_or_null("BasicInteraction")
		if interaction != null:
			_original_panel_interaction_states[object] = interaction.is_disabled
	_original_break_room_collision_layer = break_room_lamp.collision_layer


func _configure_panel_prompts() -> void:
	for control_id: String in AIPlayLightingCircuitRound.CONTROL_IDS:
		var control: CogitoSwitch = _control_switches()[control_id]
		control.interaction_text_when_on = "Switch circuit %s off" % control_id
		control.interaction_text_when_off = "Switch circuit %s on" % control_id
		control.set_state()
	for circuit_id: String in AIPlayLightingCircuitRound.CIRCUIT_IDS:
		var breaker: CogitoButton = _breaker_buttons()[circuit_id]
		breaker.usable_interaction_text = "Reset %s breaker" % BREAKER_PROMPT_LABELS[circuit_id]
		breaker.unusable_interaction_text = "Breaker already selected"
		breaker.has_been_used_hint = "A breaker has already been selected"
		breaker.set_state()
	verify_button.usable_interaction_text = "Verify lighting configuration"
	verify_button.unusable_interaction_text = "Lighting configuration submitted"
	verify_button.has_been_used_hint = "Lighting configuration has already been submitted"
	verify_button.set_state()


func _restore_panel_prompts() -> void:
	for control: CogitoSwitch in _original_control_prompts:
		var prompts: Dictionary = _original_control_prompts[control]
		control.interaction_text_when_on = prompts.on
		control.interaction_text_when_off = prompts.off
		control.set_state()
	for button: CogitoButton in _original_button_prompts:
		var prompts: Dictionary = _original_button_prompts[button]
		button.usable_interaction_text = prompts.usable
		button.unusable_interaction_text = prompts.unusable
		button.has_been_used_hint = prompts.used_hint
		button.has_been_used = prompts.has_been_used
		button.cooldown = prompts.cooldown
		button.set_state()


func _restore_panel_state() -> void:
	for control: CogitoSwitch in _original_control_states:
		_set_switch_state(control, _original_control_states[control])
	for object: Node3D in _panel_objects():
		if object in _original_panel_collision_layers:
			object.collision_layer = _original_panel_collision_layers[object]
		if object in _original_panel_interaction_states:
			_set_basic_interaction_disabled(
				object,
				_original_panel_interaction_states[object],
			)


func _place_player_and_task_card() -> void:
	player.global_transform = panel_spawn.global_transform
	var card_object := task_card.get_parent_node_3d()
	card_object.reparent(task_card_anchor, false)
	card_object.transform = Transform3D.IDENTITY


func _write_task_card(target_states: Dictionary) -> void:
	var lines: Array[String] = [
		"任务目标：修复跳闸线路，并将四组照明调整为以下状态。",
		"",
		"接线规则：A～D 与四组灯是一对一未知对应。",
		"必须判断 A、B、C、D 各自控制哪一组灯。",
		"",
		"最终目标状态：",
	]
	for circuit_id: String in AIPlayLightingCircuitRound.CIRCUIT_IDS:
		lines.append(
			"%s：%s"
			% [CIRCUIT_LABELS[circuit_id], _state_text(target_states[circuit_id])]
		)
	lines.append_array([
		"",
		"操作步骤：",
		"1. 先观察并记住四组灯的当前状态。",
		"2. 每次只操作 A～D 中的一个开关，再巡视四组灯。",
		"   哪组灯发生变化，该字母就控制哪组灯。",
		"3. 一条线路已跳闸：它的开关指示状态会变化，但灯不会响应。",
		"4. 找出三个正常对应关系，用排除法确定故障灯组。",
		"   确定后按同名 RESET BREAKER。",
		"   断路器只能选择一次，选错会立即失败。",
		"5. 复位正确线路后，继续用 A～D 调整全部灯光。",
		"6. 确认四组灯均符合目标，再按 Verify 提交。",
		"   Verify 只能提交一次，配置错误会立即失败。",
	])
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


func _panel_objects() -> Array[Node3D]:
	var objects: Array[Node3D] = []
	for control: CogitoSwitch in _control_switches().values():
		objects.append(control)
	for button: CogitoButton in _panel_buttons():
		objects.append(button)
	return objects


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
	_restore_panel_prompts()
	control_switch_a.objects_call_interact = _original_a_targets.duplicate()
	_restore_panel_state()
	break_room_lamp.collision_layer = _original_break_room_collision_layer
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
