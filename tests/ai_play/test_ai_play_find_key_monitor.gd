extends SceneTree

const REGIONS: Array[String] = [
	"MAIN_LOBBY",
	"UPPER_OFFICE_CEO",
	"ARCHIVE",
	"MEETING_ROOM",
	"BREAK_ROOM",
	"CUBICLE_AREA",
]

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
	var static_lobby_npcs: Node3D = lobby.get_node_or_null("AIPlayNPCs")
	_assert(
		static_lobby_npcs != null and static_lobby_npcs.visible,
		"Lobby NPCs are visible in the editor before runtime scenario filtering",
	)
	root.add_child(lobby)
	await process_frame

	var monitor: Node = lobby.get_node_or_null("AIPlayController/FindKeyMonitor")
	var setup: Node = lobby.get_node_or_null("FindKeyContractSetup")
	var lobby_npcs: Node3D = lobby.get_node_or_null("AIPlayNPCs")
	_assert(monitor != null, "Lobby includes FindKeyMonitor")
	_assert(setup != null, "Lobby includes isolated find-key setup")
	_assert(lobby_npcs != null, "Lobby owns the permanent NPC group")
	if monitor == null or setup == null or lobby_npcs == null:
		lobby.queue_free()
		await process_frame
		_finish()
		return

	monitor.configure_round(0)
	_assert(
		monitor.task_card.readable_content.contains("最终签署合同")
		and monitor.task_card.readable_content.contains("钥匙"),
		"task card asks for the key related to the finally signed contract",
	)
	for investigation_location: String in [
		"CEO OFFICE",
		"MEETING ROOM",
		"CUBICLE AREA",
	]:
		_assert(
			monitor.task_card.readable_content.contains(investigation_location),
			"task card names investigation location: %s" % investigation_location,
		)
	for leaked_hint: String in [
		"Printed",
		"FINAL",
		"Submitted",
		"六个区域",
		"前五把",
		"一次确认提交机会",
	]:
		_assert(
			not monitor.task_card.readable_content.contains(leaked_hint),
			"task card does not reveal strategy or trap: %s" % leaked_hint,
		)
	_assert(
		setup.find_children("*", "FriendlyHumanNPC", true, false).is_empty(),
		"find-key setup no longer owns NPC instances",
	)
	_assert(
		lobby_npcs.find_children("*", "FriendlyHumanNPC", true, false).size() == 3,
		"Lobby permanently owns exactly three NPC instances",
	)
	_assert(monitor.get_act_request_limit() == 150, "find-key allows 150 requests")
	_assert(setup.keys().size() == 6, "active setup exposes six identical keys")
	for key: RigidBody3D in setup.keys():
		var pickup := key.get_node_or_null("PickupComponent")
		var submission := key.get_node_or_null("KeySubmissionInteraction") as InteractionComponent
		_assert(
			pickup != null and bool(pickup.get("is_disabled")),
			"key pickup is disabled",
		)
		_assert(submission != null, "key exposes a submission interaction")
		_assert(
			submission != null
			and submission.interaction_text == "提交此钥匙 / Submit this key",
			"key prompt describes final submission instead of pickup",
		)
		_assert(
			key.interaction_nodes == [submission],
			"key publicly exposes only its submission interaction",
		)
	_assert(setup.documents().size() == 3, "setup exposes three contract records")
	_assert(
		setup.get_node_or_null("MainLobbyStorage") == null,
		"find-key setup does not add furniture beside the Lobby stairs",
	)
	_assert(_unique_count(setup.key_by_region().keys()) == 6, "one key per region")
	for region_id: String in REGIONS:
		_assert(setup.key_by_region().has(region_id), "%s has one key" % region_id)
	var storage_count: int = setup.keys().filter(
		func(key: Node) -> bool: return key.get_meta("placement_kind") == "storage"
	).size()
	var surface_count: int = setup.keys().filter(
		func(key: Node) -> bool: return key.get_meta("placement_kind") == "surface"
	).size()
	_assert(storage_count == 3, "exactly three keys use storage placement")
	_assert(surface_count == 3, "exactly three keys use surface placement")
	_assert(setup.npc_by_region().size() == 3, "three clue NPCs are registered")
	_assert(monitor.archive_door.is_locked, "Archive starts locked")
	_assert(not monitor.cubicle_npc.is_sitting(), "cubicle NPC walks instead of sitting")
	_assert(
		monitor.meeting_npc.route_root == lobby.get_node_or_null("FriendlyHumanNPCPath"),
		"meeting NPC owns the fixed meeting route",
	)
	_assert(
		monitor.ceo_npc.route_root == lobby.get_node_or_null("CEONPCPath"),
		"CEO NPC owns an independent Lobby route",
	)
	_assert(
		monitor.cubicle_npc.route_root == lobby.get_node_or_null("CubicleNPCPath"),
		"cubicle NPC owns an independent Lobby route",
	)
	_assert(monitor.meeting_npc.route_point_count() >= 2, "meeting NPC has a walking route")
	for point_name: String in [
		"CEOOfficeDoorOutside",
		"CEOStairUpperLanding",
		"CEOStairMidpoint",
		"CEOStairLowerLanding",
	]:
		_assert(
			monitor.ceo_npc.route_point_by_name(point_name) != null,
			"CEO route includes %s" % point_name,
		)
	for point_name: String in [
		"CubiclePatrolStart",
		"CubicleExit",
		"CubicleLobbyCrossing",
		"CubicleBreakRoomVisit",
	]:
		_assert(
			monitor.cubicle_npc.route_point_by_name(point_name) != null,
			"cubicle route includes %s" % point_name,
		)
	_assert(
		monitor.cubicle_npc.route_point_by_name("CubicleBreakRoomEntrance") == null,
		"cubicle route omits the removed break-room entrance point",
	)
	var fixed_route_state := _npc_route_state(monitor)
	monitor.configure_round(3)
	_assert(
		_npc_route_state(monitor) == fixed_route_state,
		"all NPC route starts and directions stay fixed across rounds",
	)
	_assert(setup.get_node_or_null("Routes") == null, "permanent NPC routes live in Lobby")
	lobby_npcs.configure_for_scenario("find_contract")
	for npc: FriendlyHumanNPC in lobby_npcs.npcs():
		_assert(not npc.visible, "non-NPC scenario hides permanent NPCs")
	lobby_npcs.configure_for_scenario("find_key")
	for npc: FriendlyHumanNPC in lobby_npcs.npcs():
		_assert(npc.visible, "find-key shows all permanent NPCs")
	var layout: Dictionary = setup.layout_snapshot()
	_assert(
		layout["keys"]["ARCHIVE"]["position"].z > monitor.archive_door.global_position.z + 1.0,
		"current Archive key is physically behind the locked doorway",
	)
	_assert(
		layout["keys"]["ARCHIVE"]["position"].distance_to(
			lobby.get_node("ARCHIVE/cardboardBoxOpen2").global_position
		) < 0.5,
		"current Archive key sits inside the deep archive box",
	)
	_assert(
		setup.key_by_region()["UPPER_OFFICE_CEO"].get_parent() == monitor.ceo_drawer,
		"CEO key moves with the desk drawer",
	)
	_assert(
		setup.key_by_region()["MAIN_LOBBY"].get_parent()
		== lobby.get_node(
			"MAIN_LOBBY/LAB_CONNECTOR/LaboratoryClueDesk/AnimatableBody3D"
		),
		"Lobby key uses the existing laboratory desk drawer",
	)
	for placement_check: Dictionary in [
		{"region": "MEETING_ROOM", "path": "MEETING_ROOM/tableGlass", "radius": 1.3},
		{"region": "BREAK_ROOM", "path": "BREAK_ROOM/tableRound", "radius": 0.6},
		{"region": "CUBICLE_AREA", "path": "CUBICLE_AREA/desk", "radius": 1.2},
	]:
		_assert(
			layout["keys"][placement_check["region"]]["position"].distance_to(
				lobby.get_node(placement_check["path"]).global_position
			) < placement_check["radius"],
			"%s surface key stays on its intended furniture" % placement_check["region"],
		)

	setup.set_scenario_active(false)
	_assert(not setup.visible, "inactive setup is invisible")
	_assert(setup.process_mode == Node.PROCESS_MODE_DISABLED, "inactive setup does not process")
	for key: Node in setup.keys():
		_assert(key.collision_layer == 0, "inactive key does not collide")
	setup.set_scenario_active(true)

	for seed_value: int in range(4):
		monitor.configure_round(seed_value)
		var round_data: Dictionary = monitor.get_round_data()
		for stage: Dictionary in round_data["stages"]:
			var npc: Node = setup.npc_by_region()[stage["room_id"]]
			_assert(npc.display_name == stage["handler"], "NPC identity follows pack")
			_assert(
				npc.greeting_response_hint.contains(stage["password"]),
				"NPC gives the matching historical password",
			)
			var document: Node = setup.document_by_region()[stage["room_id"]]
			_assert(
				document.readable_content.contains(stage["version"]),
				"document version follows its room stage",
			)
			_assert(
				document.readable_content.contains(stage["contract_body"]),
				"readable document renders its substantive contract body",
			)

	monitor.configure_round(0)
	monitor.keypad.wrong_code_entered_sound = null
	monitor.keypad.correct_code_entered_sound = null
	var terminal_results: Array[Dictionary] = []
	monitor.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_results.append({"outcome": outcome, "reason": reason})
	)
	var submitted_decoy: RigidBody3D = monitor.get_decoy_keys()[0]
	if submitted_decoy.get_node_or_null("KeySubmissionInteraction") == null:
		lobby.queue_free()
		await process_frame
		_finish()
		return
	submitted_decoy.get_node("KeySubmissionInteraction").was_interacted_with.emit(
		"提交此钥匙 / Submit this key",
		"interact",
	)
	_assert(
		terminal_results == [{"outcome": "failure", "reason": "security_lockout"}],
		"submitting a decoy key ends the round",
	)
	monitor.configure_round(0)
	terminal_results.clear()
	var current_code: String = monitor.get_round_data()["current"]["password"]
	var wrong_code := ("0" if current_code[0] != "0" else "1") + current_code.substr(1)
	monitor.keypad.entered_code = wrong_code
	monitor.keypad.check_entered_code()
	monitor.keypad.cancel_submission()
	_assert(terminal_results.is_empty(), "cancel keeps the round alive")
	monitor.keypad.entered_code = wrong_code
	monitor.keypad.check_entered_code()
	monitor.keypad.confirm_submission()
	monitor.keypad.confirm_submission()
	_assert(
		terminal_results == [{"outcome": "failure", "reason": "security_lockout"}],
		"one wrong confirmed password ends the round exactly once",
	)

	monitor.configure_round(0)
	terminal_results.clear()
	monitor.keypad.unlock_wait_time = 0.0
	monitor.keypad.entered_code = monitor.get_round_data()["current"]["password"]
	monitor.keypad.check_entered_code()
	monitor.keypad.confirm_submission()
	await process_frame
	_assert(not monitor.archive_door.is_locked, "correct password unlocks Archive")
	_assert(terminal_results.is_empty(), "unlock alone is not success")
	var archive_key: RigidBody3D = setup.key_by_region()["ARCHIVE"]
	archive_key.get_node("KeySubmissionInteraction").was_interacted_with.emit(
		"提交此钥匙 / Submit this key",
		"interact",
	)
	_assert(
		terminal_results == [{"outcome": "success", "reason": "key_picked_up"}],
		"submitting the Archive key completes the task",
	)

	lobby.queue_free()
	await process_frame
	_finish()


func _unique_count(values: Array) -> int:
	var unique := {}
	for value: Variant in values:
		unique[value] = true
	return unique.size()


func _npc_route_state(monitor: Node) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for npc: FriendlyHumanNPC in [monitor.meeting_npc, monitor.ceo_npc, monitor.cubicle_npc]:
		result.append(
			{
				"position": npc.global_position,
				"route_index": npc._route_index,
				"route_direction": npc._route_direction,
				"loop_route": npc.loop_route,
			}
		)
	return result


func _ensure_current_scene() -> void:
	if current_scene != null:
		return
	_test_scene_root = Node.new()
	_test_scene_root.name = "AIPlayHeadlessTestScene"
	root.add_child(_test_scene_root)
	current_scene = _test_scene_root


func _finish() -> void:
	if _failures.is_empty():
		print("AIPlay find-key monitor test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
