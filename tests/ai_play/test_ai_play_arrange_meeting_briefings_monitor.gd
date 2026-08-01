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
		"AIPlayController/ArrangeMeetingBriefingsMonitor"
	)
	var setup: Node = lobby.get_node_or_null("ArrangeMeetingBriefingsSetup")
	_assert(monitor != null, "Lobby includes meeting briefing Monitor")
	_assert(setup != null, "Lobby includes inert meeting briefing setup")
	if monitor == null or setup == null:
		await _cleanup(lobby)
		_finish()
		return

	if _is_selected_scenario():
		await _test_selected(lobby, monitor, setup)
	else:
		_test_isolation(monitor, setup)

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

	_assert(monitor.scenario_id == "arrange_meeting_briefings", "scenario ID matches")
	_assert(setup.visible, "selected setup is visible")
	_assert(
		setup.process_mode == Node.PROCESS_MODE_INHERIT,
		"selected setup processing is enabled",
	)
	_assert(monitor.folder_nodes.size() == 4, "four folders are active")
	for folder: RigidBody3D in monitor.folder_nodes:
		_assert(
			folder.process_mode == Node.PROCESS_MODE_INHERIT,
			"%s processing is active" % folder.name,
		)
	_assert(monitor.seat_interactions.size() == 4, "four seats are active")
	_assert(monitor.record_readables.size() == 3, "three records are active")
	_assert(
		monitor.task_card.get_parent().name == "TaskCard",
		"task card uses its dedicated paper object",
	)
	_assert(
		monitor.task_card.get_parent().find_children("*", "Sprite3D", true, false).is_empty(),
		"task card does not reuse the rotating Demo Hint model",
	)
	_assert(not monitor.demo_hints.visible, "unrelated Demo Hints are hidden")
	_assert(
		monitor.demo_hints.process_mode == Node.PROCESS_MODE_DISABLED,
		"unrelated Demo Hints stop processing",
	)
	for child: Node in monitor.demo_hints.find_children(
		"*",
		"CollisionObject3D",
		true,
		false,
	):
		var hint_object := child as CollisionObject3D
		_assert(hint_object.collision_layer == 0, "%s hint collision is removed" % child.name)
		_assert(hint_object.collision_mask == 0, "%s hint mask is removed" % child.name)
	for child: Node in monitor.demo_hints.find_children("*", "", true, false):
		if child.name == "ReadableComponent":
			_assert(child.get("is_disabled") == true, "Demo Hint readable is disabled")
	for child: Node in lobby.find_children("*", "", true, false):
		if (
			child.name != "ReadableComponent"
			or str(child.get("interaction_text")).strip_edges().to_lower() != "read hint"
		):
			continue
		_assert(child.get("is_disabled") == true, "map Read hint interaction is disabled")
		var hint_object: Node3D = child.get_parent_node_3d()
		_assert(hint_object != null and not hint_object.visible, "map Read hint is hidden")
		var collision_object := hint_object as CollisionObject3D
		_assert(
			collision_object == null or collision_object.collision_layer == 0,
			"map Read hint collision is removed",
		)
	for required_text: String in [
		"CEO 办公室",
		"CEO OFFICE",
		"档案室",
		"ARCHIVE",
		"休息室",
		"BREAK ROOM",
		"李明",
		"王芳",
		"陈宇",
		"赵宁",
		"电视侧",
		"会议室门侧",
		"电视对面侧",
		"内墙侧",
		"Verify 只有一次机会",
	]:
		_assert(
			monitor.task_card.readable_content.contains(required_text),
			"task card explains %s" % required_text,
		)
	var task_readable_ui := monitor.task_card.get_node("ReadableUi") as Control
	task_readable_ui.show()
	await process_frame
	await process_frame
	_assert_task_readable_without_scroll(monitor.task_card)
	task_readable_ui.hide()
	for readable: Node in monitor.record_readables:
		_assert_large_readable(readable, readable.get_parent().name)
	_assert(
		monitor.player.global_position.distance_to(monitor.player_spawn.global_position)
		< 0.25,
		"player starts at the indoor task spawn",
	)

	monitor.configure_round(7812)
	var first_snapshot: Dictionary = monitor.get_round_snapshot()
	monitor.configure_round(7812)
	_assert(
		monitor.get_round_snapshot() == first_snapshot,
		"same seed deterministically replays integrated round",
	)
	var task_text: String = monitor.task_card.readable_content
	for clue: Dictionary in first_snapshot.clues:
		_assert(
			not task_text.contains(monitor._round.clue_text(clue)),
			"task card does not reveal generated clue text",
		)
	for record_index: int in range(AIPlayMeetingBriefingRound.RECORD_IDS.size()):
		var record_id: String = AIPlayMeetingBriefingRound.RECORD_IDS[record_index]
		var clue_index: int = first_snapshot.record_clues[record_id]
		var interaction_text: String = monitor.record_readables[record_index].interaction_text
		_assert(
			monitor.record_readables[record_index].readable_content
			== monitor._round.clue_text(first_snapshot.clues[clue_index]),
			"%s record contains its assigned clue" % record_id,
		)
		_assert(
			interaction_text.begins_with("Read "),
			"%s record interaction is English" % record_id,
		)
		_assert(
			not interaction_text.contains("break_room"),
			"%s record interaction uses a readable place name" % record_id,
		)

	var player_interaction: Node = monitor.player.get_node("PlayerInteractionComponent")
	monitor.configure_round(8011)
	var placed: Dictionary = _hold_and_place(
		monitor,
		player_interaction,
		"atlas",
		"tv_side",
	)
	_assert(placed.get("accepted", false), "task folder places into empty seat")
	_assert(
		monitor.get_folder_seat_map() == {"atlas": "tv_side"},
		"trusted map records placement",
	)
	var atlas: RigidBody3D = _folder_for_id(monitor, "atlas")
	var tv_anchor: Marker3D = _anchor_for_seat(monitor, "tv_side")
	_assert(atlas.freeze, "placed folder is frozen")
	_assert(atlas.linear_velocity.is_zero_approx(), "placed folder linear speed is cleared")
	_assert(atlas.angular_velocity.is_zero_approx(), "placed folder angular speed is cleared")
	_assert(
		atlas.global_transform.is_equal_approx(tv_anchor.global_transform),
		"placed folder aligns to exact seat anchor",
	)

	_hold_folder(monitor, player_interaction, "birch")
	var occupied: Dictionary = monitor.place_carried_folder(
		"tv_side",
		player_interaction,
	)
	_assert(
		not occupied.get("accepted", false) and occupied.get("reason") == "occupied",
		"occupied seat rejects second folder",
	)
	_assert(player_interaction.carried_object != null, "occupied rejection keeps folder held")
	player_interaction.carried_object.leave()

	player_interaction.carried_object = monitor.get_node(
		"../../ARCHIVE/PutBook_CarryableBook/CarryableComponent"
	)
	var invalid: Dictionary = monitor.place_carried_folder(
		"door_side",
		player_interaction,
	)
	_assert(
		not invalid.get("accepted", false)
		and invalid.get("reason") == "invalid_folder",
		"non-task carried object is rejected",
	)
	player_interaction.carried_object = null

	_hold_folder(monitor, player_interaction, "atlas")
	_assert(monitor.get_folder_seat_map().is_empty(), "taking folder clears trusted map")
	var moved: Dictionary = monitor.place_carried_folder(
		"door_side",
		player_interaction,
	)
	_assert(moved.get("accepted", false), "taken folder can move to another seat")
	_assert(
		monitor.get_folder_seat_map() == {"atlas": "door_side"},
		"moved folder has only its new seat",
	)

	monitor.configure_round(4514)
	_terminal_results.clear()
	var solution: Dictionary = monitor.get_round_snapshot().solution
	_place_assignment(monitor, player_interaction, solution)
	monitor._on_verify_pressed()
	_assert(
		_terminal_results == [{"outcome": "success", "reason": "meeting_prepared"}],
		"correct complete assignment succeeds once",
	)
	var frozen_map: Dictionary = monitor.get_folder_seat_map()
	monitor._on_verify_pressed()
	monitor.folder_nodes[0].get_node("CarryableComponent").carry_state_changed.emit(true)
	_assert(_terminal_results.size() == 1, "terminal remains idempotent")
	_assert(monitor.get_folder_seat_map() == frozen_map, "terminal map remains frozen")

	monitor.configure_round(4515)
	_terminal_results.clear()
	var wrong_solution: Dictionary = monitor.get_round_snapshot().solution
	var atlas_seat: String = wrong_solution.atlas
	wrong_solution.atlas = wrong_solution.birch
	wrong_solution.birch = atlas_seat
	_place_assignment(monitor, player_interaction, wrong_solution)
	monitor._on_verify_pressed()
	_assert(
		_terminal_results == [{
			"outcome": "failure",
			"reason": "incorrect_seating_assignment",
		}],
		"wrong assignment fails once",
	)

	monitor.configure_round(4516)
	_terminal_results.clear()
	var partial: Dictionary = monitor.get_round_snapshot().solution
	_hold_and_place(monitor, player_interaction, "atlas", partial.atlas)
	monitor._on_verify_pressed()
	_assert(
		_terminal_results == [{
			"outcome": "failure",
			"reason": "incorrect_seating_assignment",
		}],
		"incomplete assignment fails once",
	)


func _test_isolation(monitor: Node, setup: Node) -> void:
	_assert(not setup.visible, "unselected setup stays hidden")
	_assert(
		setup.process_mode == Node.PROCESS_MODE_DISABLED,
		"unselected setup processing stays disabled",
	)
	_assert(monitor.get_round_snapshot().is_empty(), "unselected Monitor has no state")
	_assert(monitor.get_folder_seat_map().is_empty(), "unselected placement map is empty")
	_assert(monitor.task_card.is_disabled, "unselected task card stays unreadable")
	_assert(
		monitor.task_card.get_parent().collision_layer == 0,
		"unselected task card collision stays disabled",
	)
	_assert(monitor.demo_hints.visible, "unselected Demo Hints stay visible")
	_assert(
		monitor.demo_hints.process_mode != Node.PROCESS_MODE_DISABLED,
		"unselected Demo Hints keep normal processing",
	)
	for folder: RigidBody3D in monitor.folder_nodes:
		_assert(
			folder.process_mode == Node.PROCESS_MODE_DISABLED,
			"%s processing stays disabled" % folder.name,
		)
		_assert(folder.collision_layer == 0, "%s collision stays disabled" % folder.name)
		_assert(folder.collision_mask == 0, "%s mask stays disabled" % folder.name)
		_assert(
			folder.get_node("CarryableComponent").is_disabled,
			"%s carry interaction stays disabled" % folder.name,
		)
	for interaction: Node in monitor.seat_interactions:
		_assert(interaction.is_disabled, "%s interaction stays disabled" % interaction.name)
		_assert(
			interaction.get_parent().collision_layer == 0,
			"%s collision stays disabled" % interaction.get_parent().name,
		)
	for readable: Node in monitor.record_readables:
		_assert(readable.is_disabled, "%s stays unreadable" % readable.get_parent().name)
		_assert(
			readable.get_parent().collision_layer == 0,
			"%s collision stays disabled" % readable.get_parent().name,
		)
	_assert(monitor.verify_button.collision_layer == 0, "Verify collision stays disabled")
	_assert(
		monitor.verify_button.get_node("BasicInteraction").is_disabled,
		"Verify interaction stays disabled",
	)


func _assert_large_readable(readable: Node, label: String) -> void:
	var readable_ui := readable.get_node("ReadableUi") as Control
	var scroll := readable.get_node(
		"ReadableUi/Bindings/ScrollContainer"
	) as ScrollContainer
	var title := readable.get_node(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer/ReadableTitle"
	) as Label
	var content := readable.get_node(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer/ReadableContent"
	) as RichTextLabel
	_assert(readable_ui.size.x >= 880.0, "%s popup is wider" % label)
	_assert(readable_ui.size.y >= 720.0, "%s popup is taller" % label)
	_assert(scroll.custom_minimum_size.x >= 760.0, "%s text area is wider" % label)
	_assert(title.get_theme_font_size("font_size") >= 42, "%s title is larger" % label)
	_assert(
		content.get_theme_font_size("normal_font_size") >= 24,
		"%s content is larger" % label,
	)


func _assert_task_readable_without_scroll(readable: Node) -> void:
	_assert_large_readable(readable, "task card")
	var scroll := readable.get_node(
		"ReadableUi/Bindings/ScrollContainer"
	) as ScrollContainer
	var content_container := readable.get_node(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer"
	) as VBoxContainer
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


func _place_assignment(
	monitor: Node,
	player_interaction: Node,
	assignment: Dictionary,
) -> void:
	for folder_id: String in AIPlayMeetingBriefingRound.FOLDER_IDS:
		var result: Dictionary = _hold_and_place(
			monitor,
			player_interaction,
			folder_id,
			assignment[folder_id],
		)
		_assert(result.get("accepted", false), "%s assignment places" % folder_id)


func _hold_and_place(
	monitor: Node,
	player_interaction: Node,
	folder_id: String,
	seat_id: String,
) -> Dictionary:
	_hold_folder(monitor, player_interaction, folder_id)
	return monitor.place_carried_folder(seat_id, player_interaction)


func _hold_folder(
	monitor: Node,
	player_interaction: Node,
	folder_id: String,
) -> void:
	if player_interaction.carried_object != null:
		player_interaction.carried_object.leave()
	var folder: RigidBody3D = _folder_for_id(monitor, folder_id)
	var carry: Node = folder.get_node("CarryableComponent")
	carry.carry(player_interaction)


func _folder_for_id(monitor: Node, folder_id: String) -> RigidBody3D:
	var index: int = AIPlayMeetingBriefingRound.FOLDER_IDS.find(folder_id)
	return monitor.folder_nodes[index]


func _anchor_for_seat(monitor: Node, seat_id: String) -> Marker3D:
	var index: int = AIPlayMeetingBriefingRound.SEAT_IDS.find(seat_id)
	return monitor.seat_snap_anchors[index]


func _is_selected_scenario() -> bool:
	return (
		"--ai-play-scenario=arrange_meeting_briefings"
		in OS.get_cmdline_user_args()
	)


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
			print("AIPlay meeting-briefing selected test passed")
		else:
			print("AIPlay meeting-briefing isolation test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
