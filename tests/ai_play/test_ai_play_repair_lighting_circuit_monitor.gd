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
	var demo_hints := lobby.get_node("DEMO_HINTS") as Node3D
	_assert(not demo_hints.visible, "unrelated Demo Hints are hidden")
	_assert(
		demo_hints.process_mode == Node.PROCESS_MODE_DISABLED,
		"unrelated Demo Hints stop processing",
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
	var panel_interactables: Array[Node] = [
		monitor.control_switch_a,
		monitor.control_switch_b,
		monitor.control_switch_c,
		monitor.control_switch_d,
	]
	panel_interactables.append_array(_panel_buttons(monitor))
	var leftmost_panel_x: float = INF
	for panel_object: Node3D in panel_interactables:
		leftmost_panel_x = minf(leftmost_panel_x, panel_object.global_position.x)
		var interaction_hitbox := panel_object.get_node_or_null(
			"AIPlayInteractionHitbox"
		) as CollisionShape3D
		_assert(
			interaction_hitbox != null,
			"%s receives a scenario-local interaction hitbox" % panel_object.name,
		)
		if interaction_hitbox != null:
			var hitbox_shape := interaction_hitbox.shape as BoxShape3D
			_assert(
				hitbox_shape != null and hitbox_shape.size == Vector3(0.32, 0.08, 0.32),
				"%s interaction hitbox has the bounded panel size" % panel_object.name,
			)
	_assert(
		monitor.task_card.get_parent_node_3d().global_position.x < leftmost_panel_x - 0.5,
		"task card is positioned clear of the panel interaction fan",
	)
	var camera: Camera3D = monitor.player.get_node("Body/Neck/Head/Eyes/Camera")
	for control: Node3D in [
		monitor.control_switch_a,
		monitor.control_switch_b,
		monitor.control_switch_c,
		monitor.control_switch_d,
	]:
		var sight_direction: Vector3 = (
			control.global_position - camera.global_position
		).normalized()
		var sight_query := PhysicsRayQueryParameters3D.create(
			camera.global_position,
			control.global_position + sight_direction * 0.25,
			3,
			[monitor.player.get_rid()],
		)
		var sight_hit: Dictionary = camera.get_world_3d().direct_space_state.intersect_ray(
			sight_query
		)
		_assert(
			sight_hit.get("collider") == control,
			"no wall or task card blocks the initial view of %s: hit=%s"
			% [control.name, sight_hit.get("collider")],
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
	for control_id: String in ["A", "B", "C", "D"]:
		var control: Node = monitor._control_switches()[control_id]
		_assert(
			control.interaction_text_when_on == "Switch circuit %s off" % control_id
			and control.interaction_text_when_off == "Switch circuit %s on" % control_id,
			"%s switch publishes a distinct semantic prompt" % control_id,
		)
	_assert(
		monitor.breaker_entrance.usable_interaction_text == "Reset Entrance lighting breaker",
		"entrance breaker prompt is distinct",
	)
	_assert(
		monitor.breaker_ceo.usable_interaction_text == "Reset CEO office lighting breaker",
		"CEO breaker prompt is distinct",
	)
	_assert(
		monitor.breaker_lobby.usable_interaction_text == "Reset Lobby ceiling lighting breaker",
		"Lobby breaker prompt is distinct",
	)
	_assert(
		monitor.breaker_break_room.usable_interaction_text == "Reset Break room lighting breaker",
		"break-room breaker prompt is distinct",
	)
	_assert(
		monitor.verify_button.usable_interaction_text == "Verify lighting configuration",
		"Verify publishes a semantic prompt",
	)
	await _assert_controls_are_probe_discoverable(lobby, monitor)
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
	var task_readable_ui := monitor.task_card.get_node("ReadableUi") as Control
	task_readable_ui.show()
	await process_frame
	await process_frame
	_assert_task_readable_without_scroll(monitor.task_card)
	task_readable_ui.hide()

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
	for control: Node in monitor._original_control_states:
		_assert(
			control.is_on == monitor._original_control_states[control],
			"exit restores %s switch state" % control.name,
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
	for panel_object: Node in panel_interactables:
		_assert(
			panel_object.get_node_or_null("AIPlayInteractionHitbox") == null,
			"exit removes %s scenario-local interaction hitbox" % panel_object.name,
		)
	for object: Node in monitor._original_panel_collision_layers:
		_assert(
			object.collision_layer == monitor._original_panel_collision_layers[object],
			"exit restores %s collision layer exactly" % object.name,
		)
		if object in monitor._original_panel_interaction_states:
			_assert(
				object.get_node("BasicInteraction").is_disabled
				== monitor._original_panel_interaction_states[object],
				"exit restores %s interaction state exactly" % object.name,
			)


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
	for panel_object: Node in [
		monitor.control_switch_a,
		monitor.control_switch_b,
		monitor.control_switch_c,
		monitor.control_switch_d,
	] + _panel_buttons(monitor):
		_assert(
			panel_object.get_node_or_null("AIPlayInteractionHitbox") == null,
			"unselected scenario does not add a hitbox to %s" % panel_object.name,
		)


func _assert_task_readable_without_scroll(readable: Node) -> void:
	var readable_ui := readable.get_node("ReadableUi") as Control
	var scroll := readable.get_node(
		"ReadableUi/Bindings/ScrollContainer"
	) as ScrollContainer
	var content_container := readable.get_node(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer"
	) as VBoxContainer
	var title := readable.get_node(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer/ReadableTitle"
	) as Label
	var content := readable.get_node(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer/ReadableContent"
	) as RichTextLabel
	_assert(readable_ui.size.x >= 1000.0, "task card popup is wider")
	_assert(readable_ui.size.y >= 860.0, "task card popup is taller")
	_assert(scroll.custom_minimum_size.x >= 900.0, "task card text area is wider")
	_assert(title.get_theme_font_size("font_size") >= 42, "task title is larger")
	_assert(
		content.get_theme_font_size("normal_font_size") >= 24,
		"task content is larger",
	)
	_assert(
		scroll.vertical_scroll_mode == ScrollContainer.SCROLL_MODE_DISABLED,
		"task card vertical scrolling is disabled",
	)
	_assert(not scroll.get_v_scroll_bar().visible, "task card has no visible scrollbar")
	_assert(
		content_container.get_combined_minimum_size().y <= scroll.size.y,
		"task card content fits without clipping (content=%s viewport=%s)" % [
			content_container.get_combined_minimum_size(),
			scroll.size,
		],
	)


func _assert_controls_are_probe_discoverable(lobby: Node, monitor: Node) -> void:
	var player := monitor.player as Node3D
	var body := player.get_node("Body") as Node3D
	var neck := player.get_node("Body/Neck") as Node3D
	var head := player.get_node("Body/Neck/Head") as Node3D
	var eyes := player.get_node("Body/Neck/Head/Eyes") as Node3D
	var camera := player.get_node("Body/Neck/Head/Eyes/Camera") as Camera3D
	body.rotation = Vector3.ZERO
	neck.rotation = Vector3.ZERO
	head.rotation = Vector3.ZERO
	eyes.rotation = Vector3.ZERO
	camera.rotation = Vector3.ZERO
	player.global_position = Vector3(6.31, monitor.panel_spawn.global_position.y, -14.45)
	var panel_center := Vector3(6.31, 1.1, -15.8447)
	var flat_direction := panel_center - player.global_position
	flat_direction.y = 0.0
	var player_transform := player.global_transform
	player_transform.basis = Basis.looking_at(flat_direction.normalized(), Vector3.UP)
	player.global_transform = player_transform
	var camera_direction := panel_center - camera.global_position
	head.rotation.x = atan2(
		camera_direction.y,
		Vector2(camera_direction.x, camera_direction.z).length(),
	)
	await physics_frame
	await create_timer(0.0).timeout

	var probe: Node = lobby.get_node("AIPlayController/InteractionProbe")
	var viewport_size: Vector2 = camera.get_viewport().get_visible_rect().size
	for control_id: String in ["A", "B", "C", "D"]:
		var control := monitor._control_switches()[control_id] as Node3D
		_assert(
			not camera.is_position_behind(control.global_position),
			"%s is in front of the panel test camera" % control.name,
		)
		var screen_position: Vector2 = camera.unproject_position(control.global_position)
		var result: Dictionary = await probe.probe(
			screen_position.x / viewport_size.x,
			screen_position.y / viewport_size.y,
		)
		var interactions: Variant = result.get("available_interactions", [])
		_assert(
			result.get("outcome") == "aligned"
			and interactions is Array
			and not interactions.is_empty(),
			"probe discovers %s from the marked panel operating area: %s"
			% [control.name, result],
		)
		if interactions is Array and not interactions.is_empty():
			_assert(
				String(interactions[0].get("prompt", "")).begins_with(
					"Switch circuit %s " % control_id
				),
				"probe returns %s's public semantic prompt: %s"
				% [control_id, interactions],
			)
			await physics_frame
			await create_timer(0.0).timeout
			var current_interactions: Array = lobby.get_node(
				"AIPlayController/Observer"
			).get_available_interactions()
			_assert(
				current_interactions == interactions,
				"%s prompt remains stable for the following observation" % control_id,
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
