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
	_assert(monitor != null, "Lobby includes GreetNPCMeetingMonitor")
	if monitor == null:
		lobby.queue_free()
		await process_frame
		_finish()
		return

	var seen_greetings: Array[String] = []
	var seen_route_starts: Array[int] = []
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
			is_equal_approx(monitor.npc.max_greeting_distance, 1.8),
			"greet-npc meeting uses a forgiving NPC greeting distance",
		)
		_assert(
			String(snapshot["task_text"]).contains("NPC"),
			"task card mentions NPC greeting",
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

	_assert(seen_greetings.size() == 3, "fixed seed sample reaches all greetings")
	_assert(seen_route_starts.size() >= 3, "fixed seed sample varies NPC start")

	monitor.configure_round(123456)
	var terminal_results: Array[Dictionary] = []
	monitor.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_results.append({
				"outcome": outcome,
				"reason": reason,
			})
	)
	monitor.player.global_position = monitor.meeting_room.to_global(
		Vector3(-3.2, 1.0, -23.0)
	)
	monitor.conference_door.is_open = false
	monitor._try_finish_meeting_goal()
	_assert(
		terminal_results.is_empty(),
		"closing the meeting door before greeting is not success",
	)

	monitor.npc.global_position = monitor.player.global_position
	monitor.npc.interact(monitor.player.player_interaction_component)
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
