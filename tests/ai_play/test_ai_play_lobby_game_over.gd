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
