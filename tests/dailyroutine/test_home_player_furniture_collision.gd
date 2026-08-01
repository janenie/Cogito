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

	_assert_hits(player, Vector3(1.15, 1.05, 1.65), Vector3(0.0, 0.0, 2.0), "SofaCollision")
	_assert_hits(player, Vector3(-0.862, 1.05, 0.95), Vector3(0.0, 0.0, 1.6), "LowTableCollision")
	_assert_hits(player, Vector3(2.2, 1.05, -2.4), Vector3(0.0, 0.0, -1.6), "CabinetACollision")
	_assert_hits(player, Vector3(3.4, 1.05, -2.4), Vector3(0.0, 0.0, -1.6), "SinkCollision")
	_assert_hits(player, Vector3(5.5, 1.05, -2.4), Vector3(0.0, 0.0, -1.8), "FridgeCollision")
	_assert_hits(player, Vector3(-4.8, 1.05, -1.4), Vector3(-1.8, 0.0, 0.0), "BedCollision")
	_assert_hits(player, Vector3(-3.4, 1.05, -3.0), Vector3(0.0, 0.0, -1.4), "BedCabinetCollision")

	scene.queue_free()
	await physics_frame
	_finish()


func _assert_hits(player: CharacterBody3D, start: Vector3, motion: Vector3, expected_collider_name: String) -> void:
	player.global_position = start
	player.velocity = Vector3.ZERO
	var collision := player.move_and_collide(motion, true)
	_assert(collision != null, "player hits %s" % expected_collider_name)
	if collision == null:
		return
	var collider := collision.get_collider() as Node
	_assert(collider != null, "collision with %s has node collider" % expected_collider_name)
	if collider == null:
		return
	_assert(
		str(collider.name) == expected_collider_name,
		"player hits %s, got %s" % [expected_collider_name, collider.name],
	)


func _finish() -> void:
	if failures.is_empty():
		print("Home player furniture collision test passed")
		quit(0)
		return
	for failure: String in failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)
