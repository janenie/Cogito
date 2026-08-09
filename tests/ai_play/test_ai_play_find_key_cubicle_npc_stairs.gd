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
	var npc: FriendlyHumanNPC = monitor.cubicle_npc
	var patrol_start: Marker3D = lobby.get_node("CubicleNPCPath/CubiclePatrolStart")
	npc.configure_route_loop(2, -1)

	var returned_to_cubicle := false
	for _frame: int in 1500:
		await get_tree().physics_frame
		if npc.global_position.distance_to(patrol_start.global_position) <= 0.75:
			returned_to_cubicle = true
			break

	_assert(
		returned_to_cubicle,
		"cubicle NPC climbs from CubicleExit back into the cubicle area",
	)

	lobby.queue_free()
	await get_tree().process_frame
	if _failures.is_empty():
		print("AIPlay find-key cubicle NPC stair route test passed")
		get_tree().quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	get_tree().quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
