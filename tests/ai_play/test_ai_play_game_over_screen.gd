extends SceneTree

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	var screen_scene: PackedScene = load(
		"res://addons/cogito/AIPlay/ai_play_game_over_screen.tscn"
	)
	_assert(screen_scene != null, "game-over screen scene exists")
	if screen_scene == null:
		_finish()
		return

	await _test_exit_controls(screen_scene)
	await _test_result(screen_scene, "success", "correct_password", "解谜成功", "密码正确")
	await _test_result(screen_scene, "failure", "wrong_password", "解谜失败", "密码错误")
	await _test_result(
		screen_scene,
		"failure",
		"max_requests",
		"解谜失败",
		"达到最大步长",
	)
	await _test_result(
		screen_scene,
		"success",
		"key_picked_up",
		"任务成功",
		"已找到办公室钥匙",
	)
	await _test_result(
		screen_scene,
		"success",
		"books_in_ceo_office",
		"任务成功",
		"三本任务书已按顺序送达 CEO OFFICE",
	)
	await _test_result(
		screen_scene,
		"success",
		"experiment_completed",
		"实验成功",
		"已组装出符合目标的实验回路",
	)
	await _test_result(
		screen_scene,
		"failure",
		"wrong_book_pickup",
		"任务失败",
		"拿取了错误的书或搬运顺序不正确",
	)
	await _test_result(
		screen_scene,
		"failure",
		"wrong_npc_limit",
		"任务失败",
		"两次问候了错误的同事",
	)
	await _test_result(
		screen_scene,
		"success",
		"circuit_repaired",
		"任务成功",
		"照明电路已修复",
	)
	await _test_result(
		screen_scene,
		"failure",
		"wrong_breaker",
		"任务失败",
		"断路器选择错误",
	)
	await _test_result(
		screen_scene,
		"failure",
		"incorrect_circuit_configuration",
		"任务失败",
		"照明配置不正确",
	)
	await _test_result(
		screen_scene,
		"success",
		"meeting_prepared",
		"任务成功",
		"会议资料已正确分发",
	)
	await _test_result(
		screen_scene,
		"failure",
		"incorrect_seating_assignment",
		"任务失败",
		"会议资料席位不正确",
	)
	await _test_result(
		screen_scene,
		"failure",
		"experiment_attempts_exhausted",
		"实验失败",
		"三次实验机会已用完",
	)
	await _test_result(
		screen_scene,
		"success",
		"efficiency_target_reached",
		"经营成功",
		"传送带经营效率达到目标",
	)
	await _test_result(
		screen_scene,
		"failure",
		"efficiency_below_target",
		"经营失败",
		"传送带经营效率未达到目标",
	)
	await _test_result(
		screen_scene,
		"success",
		"correct_floor_selected",
		"任务成功",
		"已找到真正的出口楼层",
	)
	await _test_result(
		screen_scene,
		"failure",
		"wrong_floor_selected",
		"任务失败",
		"选择了错误的出口楼层",
	)
	_finish()


func _test_exit_controls(screen_scene: PackedScene) -> void:
	paused = false
	var screen: CanvasLayer = screen_scene.instantiate()
	root.add_child(screen)
	await process_frame
	_assert(
		screen.process_mode == Node.PROCESS_MODE_ALWAYS,
		"game-over screen keeps processing while the SceneTree is paused",
	)
	var exit_button: Button = screen.get_node(
		"Screen/Center/Content/Margin/Labels/ExitButton"
	)
	_assert(exit_button.text == "退出游戏（Esc）", "exit control explains the Escape shortcut")

	var escape := InputEventKey.new()
	escape.keycode = KEY_ESCAPE
	escape.pressed = true
	_assert(
		not screen._should_exit_for_event(escape),
		"Escape does not exit before a terminal result",
	)
	screen.show_result("success", "correct_password")
	_assert(screen._should_exit_for_event(escape), "physical Escape exits a terminal result")

	var synthetic_escape := InputEventKey.new()
	synthetic_escape.keycode = KEY_ESCAPE
	synthetic_escape.pressed = true
	synthetic_escape.device = AIPlayExecutor.SYNTHETIC_DEVICE_ID
	_assert(
		not screen._should_exit_for_event(synthetic_escape),
		"synthetic Escape cannot exit a terminal result",
	)
	var released_escape := InputEventKey.new()
	released_escape.keycode = KEY_ESCAPE
	_assert(
		not screen._should_exit_for_event(released_escape),
		"released Escape does not exit a terminal result",
	)
	var other_key := InputEventKey.new()
	other_key.keycode = KEY_ENTER
	other_key.pressed = true
	_assert(
		not screen._should_exit_for_event(other_key),
		"non-Escape keys do not exit a terminal result",
	)
	paused = false
	screen.queue_free()
	await process_frame


func _test_result(
	screen_scene: PackedScene,
	outcome: String,
	reason: String,
	expected_outcome: String,
	expected_reason: String,
) -> void:
	paused = false
	var screen: CanvasLayer = screen_scene.instantiate()
	root.add_child(screen)
	await process_frame
	screen.show_result(outcome, reason)
	_assert(screen.visible, "%s result screen is visible" % reason)
	_assert(
		screen.get_node("Screen/Center/Content/Margin/Labels/Title").text == "游戏结束",
		"title describes terminal state",
	)
	_assert(
		screen.get_node("Screen/Center/Content/Margin/Labels/Outcome").text == expected_outcome,
		"%s result has expected outcome copy" % reason,
	)
	_assert(
		screen.get_node("Screen/Center/Content/Margin/Labels/Reason").text == expected_reason,
		"%s result has expected reason copy" % reason,
	)
	_assert(
		screen.get_node("Screen/Center/Content/Margin/Labels/ExitButton").visible,
		"%s result exposes an exit control" % reason,
	)
	_assert(paused, "%s pauses the SceneTree" % reason)
	paused = false
	screen.queue_free()
	await process_frame


func _finish() -> void:
	paused = false
	if _failures.is_empty():
		print("AIPlay game-over screen tests passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
