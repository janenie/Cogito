extends SceneTree

const AIPlayExecutor = preload("res://addons/cogito/AIPlay/ai_play_executor.gd")

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	var packed: PackedScene = load("res://addons/cogito/PackedScenes/cogito_player.tscn")
	_assert(packed != null, "Cogito player scene loads")
	if packed == null:
		_finish()
		return
	var player: Node = packed.instantiate()
	player.body = player.get_node("Body")
	player.neck = player.get_node("Body/Neck")
	player.head = player.get_node("Body/Neck/Head")
	var starting_body: Vector3 = player.body.rotation
	var starting_head: Vector3 = player.head.rotation

	player.set_ai_play_mouse_motion_device(AIPlayExecutor.SYNTHETIC_DEVICE_ID)
	var physical := InputEventMouseMotion.new()
	physical.device = 0
	physical.relative = Vector2(40.0, 20.0)
	player._input(physical)
	_assert(player.body.rotation == starting_body, "guard blocks physical yaw")
	_assert(player.head.rotation == starting_head, "guard blocks physical pitch")

	var synthetic := InputEventMouseMotion.new()
	synthetic.device = AIPlayExecutor.SYNTHETIC_DEVICE_ID
	synthetic.relative = Vector2(40.0, 20.0)
	player._input(synthetic)
	_assert(
		not player.body.rotation.is_equal_approx(starting_body),
		"guard accepts AI yaw",
	)

	player.set_ai_play_mouse_motion_device(-1)
	var restored_body: Vector3 = player.body.rotation
	player._input(physical)
	_assert(
		not player.body.rotation.is_equal_approx(restored_body),
		"disable restores human yaw",
	)

	player.free()
	_finish()


func _finish() -> void:
	if _failures.is_empty():
		print("Cogito player AI mouse guard tests passed")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
