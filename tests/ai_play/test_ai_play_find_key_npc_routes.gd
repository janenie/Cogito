extends SceneTree

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	var lobby_scene: PackedScene = load(
		"res://addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
	)
	var lobby: Node = lobby_scene.instantiate()
	root.add_child(lobby)
	await process_frame
	var expected_routes := {
		"CEONPCPath": {
			"CEOOfficeDoorOutside": Vector3(-1.5017378, 2.68, -11.8),
			"CEOStairUpperLanding": Vector3(-0.9196604, 2.48, -7.74386),
			"CEOStairMidpoint": Vector3(-1.164998, 1.3688686, -6.14386),
			"CEOStairLowerLanding": Vector3(-1.164998, -0.016200514, -4.127927),
		},
		"CubicleNPCPath": {
			"CubiclePatrolStart": Vector3(3.8033056, 0.05, -1.05),
			"CubicleExit": Vector3(4.0734672, 0.05, -2.9590578),
			"CubicleLobbyCrossing": Vector3(3.039483, 0.05, -8.395132),
			"CubicleBreakRoomVisit": Vector3(1.2537853, 0.05, -10.1),
		},
		"FriendlyHumanNPCPath": {
			"HumanMeetingRoomStart": Vector3(6.503384, 0.05, 13.398232),
			"HumanMeetingRoomDoorInside": Vector3(5.7690372, 0.05, 12.671461),
			"HumanMeetingRoomDoorOutside": Vector3(5.6, 0.05, 10.45),
			"HumanLobbyExitLane": Vector3(3.1950548, 0.05, 8.4),
			"HumanLobbyStairBypass": Vector3(1.150378, 0.090000004, 4.4),
			"HumanLobbyCenterApproach": Vector3(0.67847425, 0.05, 1.4),
			"HumanMainLobbyCrossing": Vector3(-1.3306849, 0.05, -1.6),
			"HumanBreakRoomEntrance": Vector3(-3.728009, 0.05, -6.7445846),
			"HumanBreakRoomVisit": Vector3(-4.0919952, 0.033618916, -8.747376),
			"HumanSofaApproach": Vector3(-4.6626005, 0.05, -9.68025),
			"HumanSofaStop": Vector3(-6.9691844, 0.05, -10.0),
		},
	}
	for route_name: String in expected_routes:
		var expected_points: Dictionary = expected_routes[route_name]
		for point_name: String in expected_points:
			var marker: Marker3D = lobby.get_node("%s/%s" % [route_name, point_name])
			_assert(
				marker.position.is_equal_approx(expected_points[point_name]),
				"%s marker %s uses the yellow sphere position" % [route_name, point_name],
			)
			var debug_sphere: Node3D = marker.get_node("DebugSphere")
			_assert(
				debug_sphere.transform == Transform3D.IDENTITY,
				"%s marker %s keeps its yellow sphere centered" % [route_name, point_name],
			)
	_assert(
		lobby.get_node_or_null("CubicleNPCPath/CubicleBreakRoomEntrance") == null,
		"cubicle route omits the removed break-room entrance point",
	)

	var monitor: AIPlayFindKeyMonitor = lobby.get_node("AIPlayController/FindKeyMonitor")
	monitor.configure_round(0)
	var meeting_start := monitor.meeting_npc.global_position
	var ceo_start := monitor.ceo_npc.global_position
	var cubicle_start := monitor.cubicle_npc.global_position
	for _frame: int in 240:
		await physics_frame

	_assert(
		monitor.meeting_npc.global_position.distance_to(meeting_start) > 0.75,
		"meeting NPC keeps moving along its permanent Lobby route",
	)
	_assert(
		monitor.ceo_npc.global_position.distance_to(ceo_start) > 0.75,
		"CEO NPC keeps moving from the office door toward the stairs",
	)
	_assert(
		monitor.cubicle_npc.global_position.distance_to(cubicle_start) > 0.75,
		"cubicle NPC keeps moving toward the break room",
	)

	lobby.queue_free()
	await process_frame
	if _failures.is_empty():
		print("AIPlay find-key NPC route test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
