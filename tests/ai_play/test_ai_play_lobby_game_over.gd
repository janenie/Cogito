extends SceneTree

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	paused = false
	var lobby_scene: PackedScene = load(
		"res://addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
	)
	_assert(lobby_scene != null, "Lobby scene loads")
	if lobby_scene == null:
		_finish()
		return

	var change_error: Error = change_scene_to_packed(lobby_scene)
	_assert(change_error == OK, "Lobby scene change starts")
	await scene_changed
	var lobby: Node = current_scene
	var terminal: Node = lobby.get_node("AIPlayController/TerminalMonitor")
	var screen: CanvasLayer = terminal.get_node("GameOverScreen")
	var keypad: Node = lobby.get_node("ARCHIVE/Keypad")
	_assert(
		keypad.passcode == terminal.LOCKED_PASSCODE,
		"normal Lobby launch generates a gated random puzzle",
	)
	_assert(
		terminal.get_round_snapshot()["route"] in terminal.ROUTES,
		"normal Lobby launch generates an approved random route",
	)
	terminal.configure_round(123456)
	var first_snapshot: Dictionary = terminal.get_round_snapshot()
	terminal.configure_round(123456)
	var second_snapshot: Dictionary = terminal.get_round_snapshot()
	_assert(first_snapshot == second_snapshot, "fixed round seed is deterministic")
	_assert(
		first_snapshot["date"] in terminal.DATE_CANDIDATES,
		"round date comes from the eight-date candidate pool",
	)
	_assert(
		first_snapshot["version"] in terminal.VERSION_CANDIDATES,
		"round version comes from the eight-version candidate pool",
	)
	_assert(
		first_snapshot["route"] in terminal.ROUTES,
		"round route comes from the three approved room combinations",
	)
	var seen_routes: Array = []
	var seen_spawns: Array = []
	var seen_orders: Array = []
	for seed_value: int in range(1, 65):
		terminal.configure_round(seed_value)
		var generated: Dictionary = terminal.get_round_snapshot()
		var generated_clues: Array = terminal.get_active_clues_for_test()
		var task_content: String = terminal.task_card.readable_content
		_assert(
			"6 位数字密码" in task_content,
			"task card explains that the archive password has six digits",
		)
		_assert(
			generated["route"][0] in task_content,
			"task card reveals the first investigation location",
		)
		_assert(
			generated["route"][1] not in task_content
				and generated["route"][2] not in task_content,
			"task card does not reveal the second or third location",
		)
		_assert(
			"圆形 COGITO Hint" in task_content
				and "实体文件" in task_content
				and "书本" in task_content,
			"task card explains the possible clue forms",
		)
		for required_instruction: String in [
			"任务目标",
			"调查流程",
			"记录 1/3 → 2/3 → 3/3",
			"提交规则",
			"提交错误密码会立即失败",
		]:
			_assert(
				task_content.contains(required_instruction),
				"task card clearly explains %s" % required_instruction,
			)
		var ceo_step: int = generated["route"].find("CEO OFFICE")
		if ceo_step >= 0:
			_assert(
				generated_clues[ceo_step] == terminal.ceo_file_clue,
				"CEO route step uses the fixed desk file",
			)
		var break_room_step: int = generated["route"].find("BREAK ROOM")
		if break_room_step >= 0:
			_assert(
				generated_clues[break_room_step] == terminal.break_room_file_clue,
				"Break Room route step uses the television cabinet file",
			)
		for clue: Variant in [
			terminal.clue_one,
			terminal.clue_two,
		]:
			_assert(
				not clue.get_parent_node_3d().visible
				or clue.get_parent_node_3d().get_parent().name != "UPPER_OFFICE_CEO",
				"no movable hint remains visible in the CEO office",
			)
		if generated["route"] not in seen_routes:
			seen_routes.append(generated["route"])
		if generated["spawn"] not in seen_spawns:
			seen_spawns.append(generated["spawn"])
		if generated["version_first"] not in seen_orders:
			seen_orders.append(generated["version_first"])
		var expected_passcode: String = (
			generated["version"] + generated["date"]
			if generated["version_first"]
			else generated["date"] + generated["version"]
		)
		_assert(
			generated["passcode"] == expected_passcode,
			"generated password follows the selected concatenation order",
		)
		var task_distance: float = terminal.player.global_position.distance_to(
			terminal.task_card.get_parent_node_3d().global_position
		)
		_assert(
			task_distance >= 1.0 and task_distance <= 2.0,
			"task card stays one to two meters from the selected spawn",
		)
	_assert(seen_routes.size() == 3, "seed sample reaches all approved routes")
	_assert(seen_spawns.size() == 3, "seed sample reaches all approved spawns")
	_assert(seen_orders.size() == 2, "seed sample reaches both password orders")
	var task_ui := terminal.task_card.get_node("ReadableUi") as Control
	var task_scroll := terminal.task_card.get_node(
		"ReadableUi/Bindings/ScrollContainer"
	) as ScrollContainer
	var task_content_container := terminal.task_card.get_node(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer"
	) as VBoxContainer
	task_ui.show()
	await process_frame
	await process_frame
	_assert(
		task_scroll.vertical_scroll_mode == ScrollContainer.SCROLL_MODE_DISABLED,
		"find-contract task card does not require scrolling",
	)
	_assert(
		task_content_container.get_combined_minimum_size().y <= task_scroll.size.y,
		"find-contract task card content fits without clipping",
	)
	task_ui.hide()

	terminal.configure_round(123456)
	_assert(keypad.passcode == terminal.LOCKED_PASSCODE, "keypad starts gated")
	var active_clues: Array = terminal.get_active_clues_for_test()
	_assert(
		not terminal.task_card.is_disabled
			and not active_clues[0].is_disabled
			and not active_clues[1].is_disabled
			and not active_clues[2].is_disabled,
		"the task card and all round documents are readable from the start",
	)
	active_clues[2].has_been_read.emit()
	_assert(
		terminal.get_round_snapshot()["progress"] == 0,
		"reading a later clue cannot skip the task card",
	)
	keypad.code_checked.emit(true)
	_assert(not screen.visible, "a guessed password cannot bypass the clue sequence")

	terminal.task_card.has_been_read.emit()
	_assert(
		not terminal.task_card.is_disabled,
		"the task card remains readable after it advances the puzzle",
	)
	_assert(
		not active_clues[0].is_disabled,
		"the first contract becomes readable after the task card",
	)
	active_clues[0].has_been_read.emit()
	_assert(
		not terminal.task_card.is_disabled
			and not active_clues[0].is_disabled
			and not active_clues[1].is_disabled,
		"the task card and earlier contracts remain readable as the puzzle advances",
	)
	active_clues[1].has_been_read.emit()
	_assert(
		keypad.passcode == terminal.LOCKED_PASSCODE,
		"keypad remains gated until the third contract is read",
	)
	active_clues[2].has_been_read.emit()
	_assert(
		not terminal.task_card.is_disabled
			and not active_clues[0].is_disabled
			and not active_clues[1].is_disabled
			and not active_clues[2].is_disabled,
		"all discovered documents remain available for rereading",
	)
	var ready_snapshot: Dictionary = terminal.get_round_snapshot()
	_assert(ready_snapshot["ready"], "ordered clue sequence activates the keypad")
	_assert(
		keypad.passcode == ready_snapshot["passcode"],
		"activated keypad uses this round's generated password",
	)
	_assert(keypad.passcode.length() == 6, "generated password contains six digits")
	keypad.code_checked.emit(true)
	_assert(screen.visible, "correct Lobby password displays the game-over screen")
	_assert(paused, "correct Lobby password pauses all player interaction")
	_assert(
		screen.get_node("Screen/Center/Content/Margin/Labels/Outcome").text == "解谜成功",
		"correct Lobby password displays success",
	)
	paused = false
	_finish()


func _finish() -> void:
	paused = false
	if _failures.is_empty():
		print("AIPlay Lobby game-over integration test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
