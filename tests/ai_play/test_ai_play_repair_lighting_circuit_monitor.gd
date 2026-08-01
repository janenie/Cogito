extends SceneTree

var _failures: Array[String] = []
var _terminal_results: Array[Dictionary] = []
var _test_scene_root: Node


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	_ensure_current_scene()
	var lobby_scene: PackedScene = load(
		"res://addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
	)
	_assert(lobby_scene != null, "Lobby scene loads")
	if lobby_scene == null:
		_finish()
		return

	var lobby: Node = lobby_scene.instantiate()
	root.add_child(lobby)
	await process_frame
	await process_frame

	var monitor: Node = lobby.get_node_or_null(
		"AIPlayController/RepairLightingCircuitMonitor"
	)
	_assert(monitor != null, "Lobby includes lighting circuit Monitor")
	var setup: Node = lobby.get_node_or_null("RepairLightingCircuitSetup")
	_assert(setup != null, "Lobby includes inert lighting circuit setup")
	if monitor == null or setup == null:
		await _cleanup(lobby)
		_finish()
		return

	if _is_selected_scenario():
		await _test_selected(lobby, monitor, setup)
	else:
		_test_isolation(lobby, monitor, setup)

	await _cleanup(lobby)
	_finish()


func _test_selected(lobby: Node, monitor: Node, setup: Node) -> void:
	var controller: Node = lobby.get_node("AIPlayController")
	var controller_terminal := Callable(controller, "_on_game_finished")
	if monitor.game_finished.is_connected(controller_terminal):
		monitor.game_finished.disconnect(controller_terminal)
	monitor.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			_terminal_results.append({"outcome": outcome, "reason": reason})
	)

	_assert(setup.visible, "selected setup is visible")
	_assert(
		setup.process_mode == Node.PROCESS_MODE_INHERIT,
		"selected setup processing is enabled",
	)
	_assert(
		monitor.control_switch_a == lobby.get_node("GenericSwitch"),
		"existing red switch is A",
	)
	var lobby_spawn: Marker3D = lobby.get_node("AIPlayRoundMarkers/LobbySpawn")
	_assert(
		monitor.panel_spawn.global_position.distance_to(lobby_spawn.global_position) < 0.01,
		"lighting task reuses the established main-Lobby position",
	)
	_assert(
		monitor.player.global_position.distance_to(lobby_spawn.global_position) < 0.25,
		"selected task places the player inside the main Lobby: actual=%s expected=%s"
		% [monitor.player.global_position, lobby_spawn.global_position],
	)
	var panel_direction: Vector3 = (
		monitor.control_switch_a.global_position - monitor.panel_spawn.global_position
	).normalized()
	var spawn_forward: Vector3 = -monitor.panel_spawn.global_basis.z.normalized()
	_assert(
		spawn_forward.dot(panel_direction) > 0.95,
		"indoor spawn faces the lighting control panel: forward=%s target=%s dot=%s"
		% [spawn_forward, panel_direction, spawn_forward.dot(panel_direction)],
	)
	_assert(
		monitor.panel_spawn.global_position.z > monitor.control_switch_a.global_position.z,
		"player starts on the control face of the panel wall",
	)
	_assert(
		monitor.task_card.get_parent_node_3d().global_position.z
		> monitor.control_switch_a.global_position.z,
		"task card stays on the same indoor side as the player",
	)
	var camera: Camera3D = monitor.player.get_node("Body/Neck/Head/Eyes/Camera")
	var sight_direction: Vector3 = (
		monitor.control_switch_a.global_position - camera.global_position
	).normalized()
	var sight_query := PhysicsRayQueryParameters3D.create(
		camera.global_position,
		monitor.control_switch_a.global_position + sight_direction * 0.25,
		3,
		[monitor.player.get_rid()],
	)
	var sight_hit: Dictionary = camera.get_world_3d().direct_space_state.intersect_ray(
		sight_query
	)
	_assert(
		sight_hit.get("collider") == monitor.control_switch_a,
		"no wall blocks the initial view of the control panel: hit=%s"
		% sight_hit.get("collider"),
	)
	for label_name: String in [
		"TitleLabel",
		"SwitchLabelA",
		"SwitchLabelB",
		"SwitchLabelC",
		"SwitchLabelD",
		"BreakerHeadingLabel",
		"BreakerEntranceLabel",
		"BreakerCEOLabel",
		"BreakerLobbyLabel",
		"BreakerBreakRoomLabel",
		"VerifyLabel",
	]:
		var panel_label: Label3D = setup.get_node(label_name)
		_assert(not panel_label.text.is_empty(), "%s has visible text" % label_name)
		_assert(
			panel_label.global_position.z > monitor.control_switch_a.global_position.z,
			"%s stays on the visible face of the panel wall" % label_name,
		)
	var title_label: Label3D = setup.get_node("TitleLabel")
	var verify_label: Label3D = setup.get_node("VerifyLabel")
	_assert(
		is_equal_approx(monitor.verify_button.global_position.x, title_label.global_position.x),
		"Verify button is centered instead of embedded in the side wall",
	)
	_assert(
		is_equal_approx(verify_label.global_position.x, title_label.global_position.x),
		"Verify label stays centered with its button",
	)
	_assert(monitor.lobby_lamps.size() == 6, "Lobby circuit contains six ceiling lamps")
	_assert(
		monitor.task_card.readable_content.contains("入口落地灯"),
		"task card lists entrance target",
	)
	_assert(
		monitor.task_card.readable_content.contains("CEO 办公室落地灯"),
		"task card lists CEO target",
	)
	_assert(
		monitor.task_card.readable_content.contains("大厅六盏顶灯"),
		"task card lists Lobby target",
	)
	_assert(
		monitor.task_card.readable_content.contains("休息室落地灯"),
		"task card lists break-room target",
	)
	for required_instruction: String in [
		"A～D 与四组灯是一对一未知对应",
		"必须判断 A、B、C、D 各自控制哪一组灯",
		"大厅六盏顶灯（右侧高处一排）",
		"操作步骤",
		"先观察并记住四组灯的当前状态",
		"每次只操作 A～D 中的一个开关",
		"指示状态会变化，但灯不会响应",
		"断路器只能选择一次，选错会立即失败",
		"确认四组灯均符合目标，再按 Verify 提交",
		"配置错误会立即失败",
	]:
		_assert(
			monitor.task_card.readable_content.contains(required_instruction),
			"task card clearly explains: %s" % required_instruction,
		)

	monitor.configure_round(7812)
	var first_snapshot: Dictionary = monitor.get_round_snapshot()
	monitor.configure_round(7812)
	_assert(
		monitor.get_round_snapshot() == first_snapshot,
		"same seed deterministically replays the integrated round",
	)
	for lamp: Node in _controlled_lamps(monitor):
		var interaction: Node = lamp.get_node_or_null("BasicInteraction")
		_assert(
			interaction == null or interaction.is_disabled,
			"controlled lamp direct interaction is disabled: %s" % lamp.name,
		)

	monitor.configure_round(9012)
	var state: Dictionary = monitor.get_round_snapshot()
	var fault_circuit: String = state.fault_circuit
	var fault_control: String = monitor._round.control_for_circuit(fault_circuit)
	var normal_circuit: String = _first_non_fault_circuit(fault_circuit)
	var normal_control: String = monitor._round.control_for_circuit(normal_circuit)
	var switches: Dictionary = _control_switches(monitor)
	var fault_before: Variant = _physical_circuit_state(monitor, fault_circuit)
	_toggle_switch(switches[fault_control])
	_assert(
		_physical_circuit_state(monitor, fault_circuit) == fault_before,
		"fault control changes indicator without changing physical lamps",
	)
	_toggle_switch(switches[normal_control])
	var normal_state: bool = monitor.get_round_snapshot().control_states[normal_control]
	_assert_circuit_state(
		monitor,
		normal_circuit,
		normal_state,
		"normal control changes its physical circuit",
	)

	monitor.configure_round(4512)
	state = monitor.get_round_snapshot()
	var wrong_circuit: String = _first_non_fault_circuit(state.fault_circuit)
	_terminal_results.clear()
	monitor._on_breaker_pressed(wrong_circuit)
	_assert(
		_terminal_results == [{"outcome": "failure", "reason": "wrong_breaker"}],
		"wrong breaker fails once",
	)
	monitor._on_breaker_pressed(state.fault_circuit)
	_assert(_terminal_results.size() == 1, "terminal is idempotent")

	monitor.configure_round(4513)
	_terminal_results.clear()
	monitor._on_verify_pressed()
	_assert(
		_terminal_results == [{
			"outcome": "failure",
			"reason": "incorrect_circuit_configuration",
		}],
		"early Verify fails",
	)

	monitor.configure_round(4514)
	_terminal_results.clear()
	_set_real_controls_to_targets(monitor)
	monitor._on_breaker_pressed(monitor.get_round_snapshot().fault_circuit)
	_set_real_controls_to_targets(monitor)
	monitor._on_verify_pressed()
	_assert(
		_terminal_results == [{"outcome": "success", "reason": "circuit_repaired"}],
		"repaired target succeeds",
	)

	monitor._exit_tree()
	_assert(not setup.visible, "exit hides the selected setup")
	_assert(
		setup.process_mode == Node.PROCESS_MODE_DISABLED,
		"exit disables setup processing",
	)
	_assert(
		monitor.control_switch_a.objects_call_interact.size() == 6,
		"exit restores A's six ordinary Lobby targets",
	)
	_assert(
		monitor.control_switch_a.collision_layer == 3
		and not monitor.control_switch_a.get_node("BasicInteraction").is_disabled,
		"exit restores A interaction",
	)
	for control: Node in [
		monitor.control_switch_b,
		monitor.control_switch_c,
		monitor.control_switch_d,
	]:
		_assert(control.collision_layer == 0, "exit disables %s collision" % control.name)
	for button: Node in _panel_buttons(monitor):
		_assert(button.collision_layer == 0, "exit disables %s collision" % button.name)


func _test_isolation(lobby: Node, monitor: Node, setup: Node) -> void:
	_assert(not setup.visible, "unselected setup stays hidden")
	_assert(
		setup.process_mode == Node.PROCESS_MODE_DISABLED,
		"unselected setup processing stays disabled",
	)
	_assert(monitor.get_round_snapshot().is_empty(), "unselected Monitor has no round state")
	_assert(
		monitor.control_switch_a.objects_call_interact.size() == 6,
		"unselected existing A keeps six ordinary Lobby lamp targets",
	)
	for lamp: Node in [monitor.entrance_lamp, monitor.ceo_lamp]:
		var interaction: Node = lamp.get_node_or_null("BasicInteraction")
		_assert(
			interaction != null and not interaction.is_disabled,
			"unselected existing floor lamp remains directly interactable",
		)
	for control: Node in [
		monitor.control_switch_b,
		monitor.control_switch_c,
		monitor.control_switch_d,
	]:
		_assert(control.collision_layer == 0, "%s collision stays disabled" % control.name)
		_assert(
			control.get_node("BasicInteraction").is_disabled,
			"%s interaction stays disabled" % control.name,
		)
	for button: Node in _panel_buttons(monitor):
		_assert(button.collision_layer == 0, "%s collision stays disabled" % button.name)
		_assert(
			button.get_node("BasicInteraction").is_disabled,
			"%s interaction stays disabled" % button.name,
		)


func _first_non_fault_circuit(fault_circuit: String) -> String:
	for circuit_id: String in AIPlayLightingCircuitRound.CIRCUIT_IDS:
		if circuit_id != fault_circuit:
			return circuit_id
	return ""


func _set_real_controls_to_targets(monitor: Node) -> void:
	var snapshot: Dictionary = monitor.get_round_snapshot()
	var switches: Dictionary = _control_switches(monitor)
	for control_id: String in AIPlayLightingCircuitRound.CONTROL_IDS:
		var circuit_id: String = snapshot.mapping[control_id]
		var desired: bool = snapshot.target_states[circuit_id]
		var control: Node = switches[control_id]
		if control.get("is_on") != desired:
			if desired:
				control.call("switch_on")
			else:
				control.call("switch_off")


func _control_switches(monitor: Node) -> Dictionary:
	return {
		"A": monitor.control_switch_a,
		"B": monitor.control_switch_b,
		"C": monitor.control_switch_c,
		"D": monitor.control_switch_d,
	}


func _panel_buttons(monitor: Node) -> Array[Node]:
	return [
		monitor.breaker_entrance,
		monitor.breaker_ceo,
		monitor.breaker_lobby,
		monitor.breaker_break_room,
		monitor.verify_button,
	]


func _controlled_lamps(monitor: Node) -> Array[Node]:
	var lamps: Array[Node] = [
		monitor.entrance_lamp,
		monitor.ceo_lamp,
		monitor.break_room_lamp,
	]
	for lamp: Node in monitor.lobby_lamps:
		lamps.append(lamp)
	return lamps


func _physical_circuit_state(monitor: Node, circuit_id: String) -> Variant:
	match circuit_id:
		"entrance":
			return monitor.entrance_lamp.get("is_on")
		"ceo":
			return monitor.ceo_lamp.get("is_on")
		"break_room":
			return monitor.break_room_lamp.get("is_on")
		"lobby":
			var states: Array[bool] = []
			for lamp: Node in monitor.lobby_lamps:
				states.append(lamp.get("is_on"))
			return states
	return null


func _assert_circuit_state(
	monitor: Node,
	circuit_id: String,
	expected: bool,
	label: String,
) -> void:
	var state: Variant = _physical_circuit_state(monitor, circuit_id)
	if state is Array:
		_assert((state as Array).all(func(value: bool) -> bool: return value == expected), label)
		return
	_assert(state == expected, label)


func _toggle_switch(control: Node) -> void:
	if control.get("is_on"):
		control.call("switch_off")
	else:
		control.call("switch_on")


func _is_selected_scenario() -> bool:
	return "--ai-play-scenario=repair_lighting_circuit" in OS.get_cmdline_user_args()


func _ensure_current_scene() -> void:
	if current_scene != null:
		return
	_test_scene_root = Node.new()
	_test_scene_root.name = "AIPlayHeadlessTestScene"
	root.add_child(_test_scene_root)
	current_scene = _test_scene_root


func _cleanup(lobby: Node) -> void:
	lobby.queue_free()
	if _test_scene_root != null:
		_test_scene_root.queue_free()
	await process_frame


func _finish() -> void:
	if _failures.is_empty():
		if _is_selected_scenario():
			print("AIPlay lighting-circuit selected test passed")
		else:
			print("AIPlay lighting-circuit isolation test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
