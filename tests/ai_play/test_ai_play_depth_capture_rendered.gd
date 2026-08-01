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
	camera.position = Vector3(0.0, 0.0, 1000.5)
	var gameplay_environment := Environment.new()
	gameplay_environment.tonemap_mode = Environment.TONE_MAPPER_ACES
	gameplay_environment.tonemap_exposure = 4.0
	camera.environment = gameplay_environment
	scene_root.add_child(camera)
	camera.look_at(Vector3.ZERO)
	camera.make_current()

	var foreground := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(500.0, 500.0, 1.0)
	foreground.mesh = box
	var foreground_material := StandardMaterial3D.new()
	foreground_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	foreground_material.albedo_color = Color.RED
	foreground.material_override = foreground_material
	scene_root.add_child(foreground)

	var spectator_viewport := SubViewport.new()
	spectator_viewport.size = Vector2i(96, 54)
	spectator_viewport.own_world_3d = false
	spectator_viewport.world_3d = camera.get_world_3d()
	spectator_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	scene_root.add_child(spectator_viewport)
	var spectator_camera := Camera3D.new()
	spectator_camera.near = camera.near
	spectator_camera.far = camera.far
	spectator_camera.position = camera.position
	var spectator_environment := Environment.new()
	spectator_environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	spectator_environment.tonemap_exposure = 1.0
	spectator_camera.environment = spectator_environment
	spectator_viewport.add_child(spectator_camera)
	spectator_camera.look_at(Vector3.ZERO)
	spectator_camera.make_current()

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

	spectator_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	RenderingServer.force_draw(false)
	var spectator_before := spectator_viewport.get_texture().get_image().get_pixel(48, 27)
	var spectator_mask_before: int = spectator_camera.cull_mask
	spectator_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	var payload: Dictionary = capture.capture(camera, 96, 54)
	spectator_viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	var spectator_after := spectator_viewport.get_texture().get_image().get_pixel(48, 27)
	print(
		"AI_PLAY_DEPTH_SPECTATOR before=%s after=%s"
		% [spectator_before, spectator_after]
	)
	_assert(
		spectator_before.r > 0.8 and spectator_before.g < 0.1,
		"spectator test begins with red foreground",
	)
	_assert(
		absf(spectator_after.r - spectator_before.r) <= 1.0 / 255.0
		and absf(spectator_after.g - spectator_before.g) <= 1.0 / 255.0
		and absf(spectator_after.b - spectator_before.b) <= 1.0 / 255.0,
		"depth overlay stays hidden from other cameras",
	)
	_assert(
		spectator_camera.cull_mask == spectator_mask_before,
		"spectator cull mask is restored",
	)
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
			absf(center_depth - 0.25) <= 2.0 / 255.0,
			"depth bytes are linear and independent of gameplay exposure",
		)
		_assert(corner_depth > 0.9, "background reaches the far depth value")

	camera.position = Vector3(0.0, 0.0, 2000.5)
	camera.look_at(Vector3.ZERO)
	var second_payload: Dictionary = capture.capture(camera, 96, 54)
	var second_image := Image.new()
	var second_decode_error := second_image.load_png_from_buffer(
		Marshalls.base64_to_raw(second_payload.get("base64", ""))
	)
	_assert(second_decode_error == OK, "second rendered depth is a decodable PNG")
	if second_decode_error == OK:
		var second_center_depth: float = second_image.get_pixel(48, 27).r
		print("AI_PLAY_DEPTH second_center=%f" % second_center_depth)
		_assert(
			absf(second_center_depth - 0.5) <= 2.0 / 255.0,
			"capture reflects a second finite depth from the current frame",
		)

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
