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
	_finish()


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
