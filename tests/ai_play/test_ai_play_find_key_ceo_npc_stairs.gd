extends Node

var _failures: Array[String] = []


func _ready() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	var lobby_scene: PackedScene = load(
		"res://addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
	)
	var lobby: Node = lobby_scene.instantiate()
	get_tree().root.add_child(lobby)
	await get_tree().process_frame

	lobby.get_node("AIPlayNPCs").configure_for_scenario("find_key")
	var monitor: AIPlayFindKeyMonitor = lobby.get_node("AIPlayController/FindKeyMonitor")
	monitor.configure_round(0)
	var npc: FriendlyHumanNPC = monitor.ceo_npc
	var office_door: Marker3D = lobby.get_node("CEONPCPath/CEOOfficeDoorOutside")
	npc.walk_speed = 2.0

	var reached_lower_end := false
	var returned_to_office := false
	var previous_visual_position := npc.visual_root.global_position
	var largest_upward_step := 0.0
	var smooth_forward_ascent_frames := 0
	for _frame: int in 900:
		await get_tree().physics_frame
		var visual_position := npc.visual_root.global_position
		var upward_motion := visual_position.y - previous_visual_position.y
		var horizontal_motion := Vector2(
			visual_position.x - previous_visual_position.x,
			visual_position.z - previous_visual_position.z,
		).length()
		largest_upward_step = maxf(
			largest_upward_step,
			upward_motion,
		)
		if upward_motion >= 0.005 and horizontal_motion >= 0.005:
			smooth_forward_ascent_frames += 1
		previous_visual_position = visual_position
		if npc._route_direction < 0:
			reached_lower_end = true
		if (
			reached_lower_end
			and npc.global_position.distance_to(office_door.global_position) <= 0.75
		):
			returned_to_office = true
			break

	_assert(reached_lower_end, "CEO NPC reaches the lower end of its route")
	_assert(returned_to_office, "CEO NPC climbs the stairs and returns to the office door")
	_assert(
		largest_upward_step <= 0.08,
		"CEO NPC climbs without visible vertical hops (largest step %.3f)" % largest_upward_step,
	)
	_assert(
		smooth_forward_ascent_frames >= 3,
		"CEO NPC visibly rises while continuing to move forward",
	)

	lobby.queue_free()
	await get_tree().process_frame
	if _failures.is_empty():
		print("AIPlay find-key CEO NPC stair route test passed")
		get_tree().quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	get_tree().quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
