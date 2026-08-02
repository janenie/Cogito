extends SceneTree

var _failures: Array[String] = []
var _test_scene_root: Node


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	_ensure_current_scene()
	var scene: PackedScene = load(
		"res://addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn"
	)
	_assert(scene != null, "Loop staircase scene loads")
	if scene == null:
		_finish()
		return

	var root_node: Node = scene.instantiate()
	var configured_player: Node3D = root_node.get_node_or_null("Player")
	var configured_player_transform := Transform3D.IDENTITY
	if configured_player != null:
		configured_player_transform = configured_player.transform
	_assert(
		root_node.get_node_or_null(
			"AIPlayController/LoopStaircaseManager/CurrentFloorRoom"
		) != null,
		"scene file includes an editor-visible room preview",
	)
	_assert(
		root_node.get_node_or_null(
			"AIPlayController/LoopStaircaseManager/CurrentFloorRoom/WallWashLight"
		) != null,
		"editor-visible room preview includes a wall-facing light",
	)
	root.add_child(root_node)
	await process_frame

	var controller: Node = root_node.get_node_or_null("AIPlayController")
	_assert(controller != null, "scene includes AIPlayController")
	var manager: Node = root_node.get_node_or_null(
		"AIPlayController/LoopStaircaseManager"
	)
	_assert(manager != null, "AIPlayController includes loop staircase monitor")
	_assert(
		manager != null
		and manager.game_over_screen == manager.get_node_or_null("GameOverScreen"),
		"loop staircase uses the shared terminal exit screen",
	)
	var observer: Node = root_node.get_node_or_null("AIPlayController/Observer")
	_assert(
		observer != null
		and observer.get_script() != null
		and observer.get_script().resource_path.ends_with("ai_play_loop_staircase_observer.gd"),
		"loop staircase scene uses the dedicated public-state observer",
	)
	if manager == null:
		root_node.queue_free()
		await process_frame
		_finish()
		return

	manager.configure_round(98765)
	manager.build_scene()
	await process_frame
	var observation: Dictionary = observer.capture_observation([])
	_assert(observation.has("staircase"), "loop observer includes public staircase state")
	if observation.has("staircase"):
		var staircase: Dictionary = observation["staircase"]
		_assert(
			staircase["current_floor"] == manager.get_current_floor()
			and staircase["current_loop"] == manager.current_loop + 1,
			"public staircase state matches the navigational manager state",
		)
		_assert(
			not staircase.has("lamp_color")
			and not staircase.has("wall_marker")
			and not staircase.has("box_count"),
			"public staircase state does not expose visual clue memory fields",
		)

	var ui: CanvasLayer = manager.get_node_or_null("GameUI")
	_assert(ui != null, "manager builds a compact HUD layer for rules")
	var rules: Label = manager.get_node_or_null("GameUI/RulesPanel/RulesMargin/Rules")
	_assert(
		rules != null
		and "寻找真正的出口楼层" in rules.text
		and "LOOPING STAIRCASE" in rules.text
		and "上/下" in rules.text
		and "空格" in rules.text
		and "五轮" in rules.text,
		"HUD explains the loop staircase rules and controls",
	)
	_assert(
		rules != null and rules.get_theme_font_size("font_size") >= 19,
		"task description uses a larger font",
	)
	var clue_label := manager.get_node_or_null("CurrentFloorRoom/Clue") as Label3D
	_assert(
		clue_label != null and clue_label.font_size >= 34,
		"in-world clue text uses a larger font",
	)
	_assert(
		rules != null and not "2 boxes" in rules.text and not "two boxes" in rules.text,
		"HUD does not reveal the old two-box answer rule",
	)
	var status: Label = manager.get_node_or_null("GameUI/StatusPanel/StatusMargin/Status")
	_assert(
		status != null
		and not "Lamp:" in status.text
		and not "Boxes:" in status.text
		and not "Symbol:" in status.text,
		"HUD status does not expose visual clue values",
	)
	var view: Control = manager.get_node_or_null("GameUI/StairView")
	_assert(view == null, "UI does not draw a full-screen staircase over the room")
	_assert(
		manager.get_node_or_null("GameUI/UpButton") == null,
		"UI does not use a 2D Up button",
	)
	_assert(
		manager.get_node_or_null("GameUI/DownButton") == null,
		"UI does not use a 2D Down button",
	)
	var player_gui: Control = root_node.get_node_or_null("Player/GUI")
	_assert(
		player_gui == null or not player_gui.visible,
		"loop staircase scene hides the default Cogito player HUD",
	)
	var room: Node = manager.get_node_or_null("CurrentFloorRoom")
	_assert(room != null, "manager builds a close lobby-style floor room")
	if room != null:
		_assert(
			room.get_node_or_null("LobbySofa") != null,
			"room reuses the lobby sofa prefab",
		)
		_assert(
			room.get_node_or_null("CoffeeTable") != null,
			"room includes a lobby coffee table",
		)
		_assert(
			room.get_node_or_null("CoffeeMug") != null,
			"room includes the existing coffee mug prop",
		)
		_assert(
			room.get_node_or_null("Boxes/LobbyBox_1") != null,
			"room includes variable lobby boxes",
		)
		_assert(
			room.get_node_or_null("Chairs") != null,
			"room includes a variable chair container",
		)
		_assert(
			room.get_node_or_null("Books") != null,
			"room includes a variable book container",
		)
		_assert(
			room.get_node_or_null("ComputerSet") != null,
			"room includes a variable computer set using lobby prefabs",
		)
		_assert(
			room.get_node_or_null("FloorSign") != null,
			"room includes a visible floor sign",
		)
		var floor_sign: Label3D = room.get_node_or_null("FloorSign")
		_assert(
			floor_sign != null and is_zero_approx(floor_sign.rotation_degrees.y),
			"floor sign faces the player instead of rendering mirrored",
		)
		var observation_label: Label3D = room.get_node_or_null("ObservationLabel")
		_assert(
			observation_label != null
			and not "Lamp:" in observation_label.text
			and not "Boxes:" in observation_label.text
			and not "Chairs:" in observation_label.text
			and not "Computers:" in observation_label.text
			and not "Books:" in observation_label.text,
			"wall observation text does not expose a variable table",
		)
		var wall_clue: Label3D = room.get_node_or_null("Clue")
		_assert(
			wall_clue == null or not wall_clue.visible,
			"room does not show the old yellow wall clue text",
		)
		_assert(
			room.get_node_or_null("Symbol") == null,
			"symbol is not a flat Label3D",
		)
		_assert(
			room.get_node_or_null("WallSymbol") is Node3D,
			"room renders the key symbol as a 3D wall marker",
		)
		_assert(
			room.get_node_or_null("UpStairsTrigger") != null,
			"room includes a 3D up-stairs trigger",
		)
		_assert(
			room.get_node_or_null("DownStairsTrigger") != null,
			"room includes a 3D down-stairs trigger",
		)
		var down_label: Label3D = room.get_node_or_null("DownStairsTrigger/Label")
		_assert(
			down_label == null or not down_label.visible,
			"3D navigation labels do not block the camera view",
		)
		_assert(
			room.get_node_or_null("WallWashLight") != null,
			"runtime room includes a direct light aimed at the walls",
		)
		_assert(
			room.get_node_or_null("BackWall") != null
			and room.get_node_or_null("LeftWall") != null
			and room.get_node_or_null("RightWall") != null,
			"runtime room keeps the three-wall composition from the scene preview",
		)
		var initial_state: Dictionary = manager.get_floor_state(manager.get_current_floor())
		var chair_nodes: Node = room.get_node_or_null("Chairs")
		var book_nodes: Node = room.get_node_or_null("Books")
		var computer_nodes: Node = room.get_node_or_null("ComputerSet")
		var symbol_node: Node3D = room.get_node_or_null("WallSymbol")
		_assert(
			chair_nodes != null and chair_nodes.get_child_count() == initial_state["chair_count"],
			"room chair count matches the current floor state",
		)
		_assert(
			book_nodes != null and book_nodes.get_child_count() == initial_state["book_count"],
			"room book count matches the current floor state",
		)
		_assert(
			computer_nodes != null and computer_nodes.visible == (initial_state["computer_count"] > 0),
			"room computer visibility matches the current floor state",
		)
		_assert(
			symbol_node != null and not is_zero_approx(symbol_node.rotation_degrees.z),
			"wall symbol has a subtle per-floor tilt instead of a flat repeated decal",
		)

	var spawn: Node3D = manager.get_node_or_null("SpawnPoint")
	_assert(spawn != null, "room has a playable spawn point")
	_assert(
		spawn != null and spawn.global_transform.is_equal_approx(configured_player_transform),
		"runtime spawn preserves the Player transform configured in the scene",
	)
	_assert(
		spawn != null and absf(spawn.position.x) <= 3.2 and spawn.position.z <= 2.35,
		"runtime spawn starts on the playable lobby floor instead of outside the room",
	)
	_assert(
		manager.get_node_or_null("StartHint") == null,
		"room does not spawn a large mirrored start hint label",
	)
	var floor_sign_position: Vector3 = Vector3.ZERO
	var floor_sign_node: Label3D = manager.get_node_or_null("CurrentFloorRoom/FloorSign")
	if floor_sign_node != null:
		floor_sign_position = floor_sign_node.position
	_assert(
		floor_sign_position.z < -2.0,
		"floor labels stay on the far wall instead of blocking the entry view",
	)

	_assert(manager.get_current_floor() == 2, "round starts at 2F")
	var up_event := InputEventKey.new()
	up_event.keycode = KEY_UP
	up_event.pressed = true
	manager._unhandled_input(up_event)
	_assert(manager.get_current_floor() == 3, "keyboard Up moves to the next floor")
	if room != null:
		var updated_floor_sign: Label3D = manager.get_node_or_null("CurrentFloorRoom/FloorSign")
		_assert(
			updated_floor_sign != null and "3F" in updated_floor_sign.text,
			"current room refreshes after moving floors",
		)
	var down_event := InputEventKey.new()
	down_event.keycode = KEY_DOWN
	down_event.pressed = true
	manager._unhandled_input(down_event)
	_assert(manager.get_current_floor() == 2, "keyboard Down moves to the previous floor")

	_assert(not manager.is_final_unlocked(), "final starts locked")
	for step: int in range(32):
		manager.move_up()
	_assert(manager.is_final_unlocked(), "final unlocks after five observation loops")
	var answer: Node = manager.get_node_or_null("CurrentFloorRoom/AnswerCurrentFloor")
	_assert(answer != null and answer.visible, "final loop exposes a 3D answer interaction")
	manager.move_down()
	_assert(manager.get_current_floor() == 9, "Down remains available on the final loop")

	var terminal_results: Array[Dictionary] = []
	manager.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_results.append({
				"outcome": outcome,
				"reason": reason,
			})
	)
	var snapshot: Dictionary = manager.get_round_snapshot()
	manager.set_current_floor(snapshot["true_floor"])
	manager.submit_current_floor()
	_assert(
		terminal_results == [{
			"outcome": "success",
			"reason": "correct_floor_selected",
		}],
		"space-style submit chooses the current floor",
	)
	if _is_selected_scenario():
		_assert(
			manager.game_over_screen != null
			and manager.game_over_screen.visible,
			"selected loop terminal shows the shared exit screen",
		)

	var expected_scenario := (
		"loop_staircase_anomaly" if _is_selected_scenario() else "find_contract"
	)
	_assert(
		controller.get_active_scenario_id() == expected_scenario,
		"controller uses the requested scenario or the documented default",
	)
	_assert(
		manager.scenario_id == "loop_staircase_anomaly",
		"manager exposes AI Play scenario id",
	)

	root_node.queue_free()
	paused = false
	if _test_scene_root != null:
		_test_scene_root.queue_free()
	await process_frame
	_finish()


func _is_selected_scenario() -> bool:
	return "--ai-play-scenario=loop_staircase_anomaly" in OS.get_cmdline_user_args()


func _ensure_current_scene() -> void:
	if current_scene != null:
		return
	_test_scene_root = Node.new()
	_test_scene_root.name = "AIPlayHeadlessTestScene"
	root.add_child(_test_scene_root)
	current_scene = _test_scene_root


func _finish() -> void:
	paused = false
	if _failures.is_empty():
		print("Loop staircase scene test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
