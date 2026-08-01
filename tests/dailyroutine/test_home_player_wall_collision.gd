extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var packed: PackedScene = load("res://dailyroutine/scenes/home_daily_routine.tscn")
	_assert(packed != null, "daily routine scene loads")
	if packed == null:
		_finish()
		return
	var scene := packed.instantiate()
	root.add_child(scene)
	await physics_frame

	var player := scene.get_node_or_null("CogitoPlayer") as CharacterBody3D
	_assert(player != null, "scene has player")
	if player == null:
		scene.queue_free()
		await physics_frame
		_finish()
		return

	player.global_position = Vector3(0.0, 1.05, -4.45)
	player.global_rotation = Vector3.ZERO
	Input.action_press("forward")
	for _i in range(40):
		await physics_frame
	Input.action_release("forward")
	_assert(
		player.global_position.z > -4.75,
		"player is blocked by north wall, z=%.3f" % player.global_position.z,
	)

	player.global_position = Vector3(-6.45, 1.05, 0.0)
	player.global_rotation = Vector3(0.0, PI / 2.0, 0.0)
	Input.action_press("forward")
	for _i in range(40):
		await physics_frame
	Input.action_release("forward")
	_assert(
		player.global_position.x > -6.75,
		"player is blocked by west wall, x=%.3f" % player.global_position.x,
	)

	player.global_position = Vector3(-1.6, 1.05, -0.45)
	player.global_rotation = Vector3(0.0, PI, 0.0)
	Input.action_press("forward")
	for _i in range(40):
		await physics_frame
	Input.action_release("forward")
	_assert(
		player.global_position.z < -0.25,
		"player is blocked by the visible left segment of CenterMiddleWall, z=%.3f" % player.global_position.z,
	)

	player.global_position = Vector3(2.6, 1.05, -0.45)
	player.global_rotation = Vector3(0.0, PI, 0.0)
	Input.action_press("forward")
	for _i in range(40):
		await physics_frame
	Input.action_release("forward")
	_assert(
		player.global_position.z < -0.25,
		"player is blocked by the visible left segment of RightMiddleWall, z=%.3f" % player.global_position.z,
	)

	scene.queue_free()
	await physics_frame
	_finish()


func _finish() -> void:
	if failures.is_empty():
		print("Home player wall collision test passed")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)
