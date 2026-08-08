extends SceneTree

var _failures: Array[String] = []
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

	var monitor: Node = lobby.get_node_or_null(
		"AIPlayController/GreetNPCMeetingMonitor"
	)
	var find_key_setup: Node3D = lobby.get_node_or_null("FindKeyContractSetup")
	_assert(monitor != null, "Lobby includes GreetNPCMeetingMonitor")
	_assert(
		find_key_setup != null
		and not find_key_setup.visible
		and find_key_setup.process_mode == Node.PROCESS_MODE_DISABLED,
		"find-key setup stays inactive for the greeting scenario",
	)
	if monitor == null:
		lobby.queue_free()
		await process_frame
		_finish()
		return

	monitor.configure_round(777)
	var movement_starts: Array[Vector3] = []
	for candidate: Node3D in monitor._candidate_npcs:
		movement_starts.append(candidate.global_position)
		for route_point: Node3D in candidate._route_points:
			_assert(
				route_point.name not in monitor.MEETING_APPROACH_POINTS,
				"pre-greeting patrol keeps candidates out of the narrow meeting door",
			)
	for _frame: int in 120:
		await physics_frame
	for candidate_index: int in range(monitor._candidate_npcs.size()):
		_assert(
			monitor._candidate_npcs[candidate_index].global_position.distance_to(
				movement_starts[candidate_index],
			) > 0.05,
			"candidate %d has real movement instead of walking in place"
			% (candidate_index + 1),
		)

	var seen_greetings: Array[String] = []
	var seen_route_starts: Array[int] = []
	var seen_targets: Array[String] = []
	var seen_destinations: Array[String] = []
	for seed_value: int in range(1, 96):
		monitor.configure_round(seed_value)
		var snapshot: Dictionary = monitor.get_round_snapshot()
		_assert(
			snapshot["greeting"] in monitor.GREETING_PHRASES,
			"greeting phrase is from the approved set",
		)
		_assert(
			int(snapshot["route_start_index"]) >= 0,
			"route start index is selected",
		)
		_assert(
			not monitor.conference_door.is_locked and monitor.conference_door.is_open,
			"meeting door starts open and unlocked",
		)
		_assert(
			int(snapshot["candidate_count"]) == 3,
			"round has three moving NPC candidates",
		)
		for candidate: Node in monitor._candidate_npcs:
			_assert(
				is_equal_approx(candidate.max_greeting_distance, 1.8),
				"every candidate uses a forgiving greeting distance",
			)
		_assert(
			String(snapshot["task_text"]).contains(snapshot["target_shirt_label"]),
			"task card identifies the target by visible shirt colour",
		)
		for required_instruction: String in [
			"任务目标",
			"操作步骤",
			"MEETING ROOM",
			"三名走动的同事",
			"第二次问候错误",
			"完成条件",
			"双方到达指定区域",
			"从室内关上会议室门",
		]:
			_assert(
				String(snapshot["task_text"]).contains(required_instruction),
				"task card clearly explains %s" % required_instruction,
			)
		_assert(
			monitor.player.global_position.distance_to(
				monitor.task_card.get_parent_node_3d().global_position
			) >= 1.0,
			"task card is not spawned on top of the player",
		)
		if snapshot["greeting"] not in seen_greetings:
			seen_greetings.append(snapshot["greeting"])
		if int(snapshot["route_start_index"]) not in seen_route_starts:
			seen_route_starts.append(int(snapshot["route_start_index"]))
		if snapshot["target_display_name"] not in seen_targets:
			seen_targets.append(snapshot["target_display_name"])
		if snapshot["destination_label"] not in seen_destinations:
			seen_destinations.append(snapshot["destination_label"])

	_assert(seen_greetings.size() == 3, "fixed seed sample reaches all greetings")
	_assert(seen_route_starts.size() >= 3, "fixed seed sample varies NPC start")
	_assert(seen_targets.size() == 3, "fixed seed sample reaches all target NPCs")
	_assert(
		seen_destinations.size() == 2,
		"fixed seed sample reaches both meeting areas",
	)
	var task_ui := monitor.task_card.get_node("ReadableUi") as Control
	var task_scroll := monitor.task_card.get_node(
		"ReadableUi/Bindings/ScrollContainer"
	) as ScrollContainer
	var task_content_container := monitor.task_card.get_node(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer"
	) as VBoxContainer
	task_ui.show()
	await process_frame
	await process_frame
	_assert(
		task_scroll.vertical_scroll_mode == ScrollContainer.SCROLL_MODE_DISABLED,
		"greet-NPC task card does not require scrolling",
	)
	_assert(
		task_content_container.get_combined_minimum_size().y <= task_scroll.size.y,
		"greet-NPC task card content fits without clipping",
	)
	task_ui.hide()

	var terminal_results: Array[Dictionary] = []
	monitor.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_results.append({
				"outcome": outcome,
				"reason": reason,
			})
	)
	monitor.configure_round(123456)
	var wrong_snapshot: Dictionary = monitor.get_round_snapshot()
	var wrong_target_index := int(wrong_snapshot["target_npc_index"])
	var wrong_candidates: Array[Node] = []
	for candidate_index: int in range(monitor._candidate_npcs.size()):
		if candidate_index != wrong_target_index:
			wrong_candidates.append(monitor._candidate_npcs[candidate_index])
	for wrong_index: int in range(wrong_candidates.size()):
		wrong_candidates[wrong_index].global_position = monitor.player.global_position
		wrong_candidates[wrong_index].interact(
			monitor.player.player_interaction_component
		)
		if wrong_index == 0:
			_assert(
				terminal_results.is_empty(),
				"the first wrong colleague greeting remains recoverable",
			)
	_assert(
		terminal_results == [{
			"outcome": "failure",
			"reason": "wrong_npc_limit",
		}],
		"the second distinct wrong greeting fails exactly once",
	)

	terminal_results.clear()
	monitor.configure_round(654321)
	monitor.player.global_position = monitor.meeting_room.to_global(
		monitor._destination_marker.position + Vector3(0.0, 1.0, 0.0)
	)
	monitor.conference_door.is_open = false
	monitor._try_finish_meeting_goal()
	_assert(
		terminal_results.is_empty(),
		"closing the meeting door before greeting is not success",
	)

	monitor.player.global_transform = monitor.entrance_spawn.global_transform
	monitor._target_npc.global_position = monitor.player.global_position
	monitor._target_npc.interact(monitor.player.player_interaction_component)
	_assert(
		monitor._target_npc.greeting_enabled,
		"correct contact can repeat the destination hint",
	)
	_assert(
		monitor._target_npc._route_points[0].name == "HumanMeetingRoomDoorOutside"
		and monitor._target_npc._route_points[1].name == "HumanMeetingRoomDoorInside"
		and monitor._target_npc._route_points[-1] == monitor._destination_marker,
		"correct contact reuses the blue NPC door approach before the destination",
	)
	monitor.player.global_position = monitor.meeting_room.to_global(
		monitor._destination_marker.position + Vector3(0.0, 1.0, 0.0)
	)
	monitor._try_finish_meeting_goal()
	_assert(
		terminal_results.is_empty(),
		"correct greeting and player arrival wait for the contact to arrive",
	)
	monitor._target_npc.global_position = (
		monitor._destination_marker.global_position
	)
	monitor._try_finish_meeting_goal()
	monitor._try_finish_meeting_goal()
	_assert(
		terminal_results == [{
			"outcome": "success",
			"reason": "meeting_door_closed",
		}],
		"greeting then closing the meeting door ends the round exactly once",
	)

	lobby.queue_free()
	if _test_scene_root != null:
		_test_scene_root.queue_free()
	await process_frame
	_finish()


func _ensure_current_scene() -> void:
	if current_scene != null:
		return
	_test_scene_root = Node.new()
	_test_scene_root.name = "AIPlayHeadlessTestScene"
	root.add_child(_test_scene_root)
	current_scene = _test_scene_root


func _finish() -> void:
	if _failures.is_empty():
		print("AIPlay greet-npc-meeting monitor test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
