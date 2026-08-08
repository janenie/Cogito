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


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
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

	var monitor: Node = lobby.get_node_or_null("AIPlayController/FindKeyMonitor")
	var setup: Node = lobby.get_node_or_null("FindKeyContractSetup")
	_assert(monitor != null, "Lobby includes FindKeyMonitor")
	_assert(setup != null, "Lobby includes isolated find-key setup")
	if monitor == null or setup == null:
		lobby.queue_free()
		await process_frame
		_finish()
		return

	monitor.configure_round(0)
	_assert(monitor.get_act_request_limit() == 150, "find-key allows 150 requests")
	_assert(setup.keys().size() == 6, "active setup exposes six identical keys")
	_assert(setup.documents().size() == 3, "setup exposes three contract records")
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
	_assert(setup.cubicle_npc.is_sitting(), "cubicle NPC remains seated")
	_assert(setup.ceo_npc.route_point_count() == 2, "CEO NPC paces between two office points")
	var layout: Dictionary = setup.layout_snapshot()
	_assert(
		layout["keys"]["ARCHIVE"]["position"].z < monitor.archive_door.global_position.z,
		"current Archive key is physically behind the locked doorway",
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

	monitor.configure_round(0)
	var terminal_results: Array[Dictionary] = []
	monitor.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_results.append({"outcome": outcome, "reason": reason})
	)
	for decoy: RigidBody3D in monitor.get_decoy_keys():
		decoy.get_node("PickupComponent").was_interacted_with.emit("Pick up", "interact")
	_assert(terminal_results.is_empty(), "decoy pickups are nonterminal")
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
	archive_key.get_node("PickupComponent").was_interacted_with.emit("Pick up", "interact")
	_assert(
		terminal_results == [{"outcome": "success", "reason": "key_picked_up"}],
		"Archive key pickup completes the task",
	)

	lobby.queue_free()
	await process_frame
	_finish()


func _unique_count(values: Array) -> int:
	var unique := {}
	for value: Variant in values:
		unique[value] = true
	return unique.size()


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
