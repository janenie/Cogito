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
	await process_frame

	var player := scene.get_node_or_null("CogitoPlayer")
	var manager := scene.get_node_or_null("DailyRoutineManager")
	var observer := scene.get_node_or_null("AIPlayController/Observer")
	_assert(player != null, "scene has HomeRobotPlayer")
	_assert(manager != null, "scene has manager")
	_assert(observer != null, "scene has home observer")
	if player == null or manager == null or observer == null:
		scene.queue_free()
		await process_frame
		_finish()
		return

	observer.player = player
	observer.manager = manager
	var observation: Dictionary = observer.capture_observation([])

	_assert(observation["observation_id"] == 1, "observation id starts at one")
	_assert(observation["image"]["mime_type"] == "image/jpeg", "observation includes jpeg image")
	_assert(observation["depth_image"]["mime_type"] == "image/png", "observation includes png depth")
	_assert(
		observation["depth_image"]["encoding"] == "linear_depth_normalized_8bit",
		"depth encoding is public",
	)
	var depth_image := Image.new()
	_assert(
		depth_image.load_png_from_buffer(
			Marshalls.base64_to_raw(observation["depth_image"]["base64"])
		) == OK,
		"depth base64 decodes as PNG",
	)
	_assert(depth_image.get_size() == Vector2i(768, 432), "depth image has public dimensions")
	_assert(observation["player"]["position"].size() == 3, "player position is public")
	_assert(observation["player"].has("yaw_degrees"), "player yaw is public")
	_assert(observation["player"].has("pitch_degrees"), "player pitch is public")
	_assert(observation["interface"].has("available_interactions"), "interactions are public")
	_assert(observation["interface"]["visible_object_text"] == "", "no hidden text is leaked")
	_assert(observation["routine"]["objective"] == manager.current_objective, "routine objective is exposed")
	_assert(observation["routine"]["trash_collected"] == manager.collected_trash_count, "trash count current is exposed")
	_assert(observation["routine"]["trash_required"] == manager.required_trash_count, "trash count required is exposed")
	_assert(observation["routine"]["held_item"] == manager.held_item_label(), "held item is exposed")
	var observation_text := JSON.stringify(observation)
	_assert(not observation_text.contains("DailyRoutineManager"), "observation does not leak class names")
	_assert(not observation_text.contains("dailyroutine/scripts"), "observation does not leak script paths")

	scene.queue_free()
	await process_frame
	_finish()


func _finish() -> void:
	if failures.is_empty():
		print("Home AI Play observer test passed")
		quit(0)
	for failure: String in failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)
