extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	if DisplayServer.get_name() == "headless":
		print("AIPlay rendered depth capture test skipped in headless mode")
		quit(0)
		return

	var scene_root := Node3D.new()
	root.add_child(scene_root)

	var camera := Camera3D.new()
	camera.near = 0.05
	camera.far = 4000.0
	camera.position = Vector3(0.0, 0.0, 5.0)
	scene_root.add_child(camera)
	camera.look_at(Vector3.ZERO)
	camera.make_current()

	var foreground := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(2.0, 2.0, 2.0)
	foreground.mesh = box
	scene_root.add_child(foreground)

	var capture_script: GDScript = load(
		"res://addons/cogito/AIPlay/ai_play_depth_capture.gd"
	)
	_assert(capture_script != null, "depth capture component exists")
	if capture_script == null:
		scene_root.free()
		_finish()
		return

	var capture: Node = capture_script.new()
	scene_root.add_child(capture)
	for unused_index: int in 3:
		await process_frame
	await RenderingServer.frame_post_draw

	var payload: Dictionary = capture.capture(camera, 96, 54)
	var image := Image.new()
	var decode_error := image.load_png_from_buffer(
		Marshalls.base64_to_raw(payload.get("base64", ""))
	)
	_assert(decode_error == OK, "rendered depth is a decodable PNG")
	if decode_error == OK:
		_assert(image.get_size() == Vector2i(96, 54), "rendered depth has requested size")
		var center_depth: float = image.get_pixel(48, 27).r
		var corner_depth: float = image.get_pixel(2, 2).r
		print("AI_PLAY_DEPTH center=%f corner=%f" % [center_depth, corner_depth])
		_assert(
			center_depth < corner_depth,
			"foreground geometry is nearer than background",
		)
		_assert(corner_depth > 0.9, "background reaches the far depth value")

	var depth_viewport: SubViewport = capture.get_node_or_null("AIPlayDepthViewport")
	_assert(depth_viewport != null, "capture creates a depth viewport")
	if depth_viewport != null:
		_assert(
			depth_viewport.size == Vector2i(96, 54),
			"capture renders at requested size",
		)

	scene_root.free()
	_finish()


func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)


func _finish() -> void:
	if failures.is_empty():
		print("AIPlay rendered depth capture tests passed")
		quit(0)
	else:
		for failure: String in failures:
			push_error(failure)
		quit(1)
