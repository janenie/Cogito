extends SceneTree

func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	if DisplayServer.get_name() == "headless":
		print("AIPlay rendered look test skipped in headless mode")
		quit(0)
		return
	var change_error: Error = change_scene_to_file(
		"res://addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
	)
	if change_error != OK:
		push_error("failed to load Lobby: %s" % error_string(change_error))
		quit(1)
		return
	for unused_index: int in 10:
		await process_frame
	await RenderingServer.frame_post_draw

	var lobby: Node = current_scene
	var player: Node3D = lobby.get_node("Player")
	var viewport: Viewport = player.get_viewport()
	var player_camera: Camera3D = player.get_node("Body/Neck/Head/Eyes/Camera")
	var current_camera: Camera3D = viewport.get_camera_3d()
	var before_transform: Transform3D = player_camera.global_transform
	var before_pixels: PackedByteArray = viewport.get_texture().get_image().get_data()

	var controller: Node = lobby.get_node("AIPlayController")
	var executor: Node = controller.get_node("Executor")
	controller._set_ai_mouse_guard(true)
	var action_results: Array = []
	executor.batch_finished.connect(
		func(results: Array) -> void: action_results.append(results.duplicate(true)),
		CONNECT_ONE_SHOT,
	)
	executor.execute_batch([{
		"type": "look",
		"yaw": -45.0,
		"pitch": 0.0,
	}], {})
	while action_results.is_empty():
		await process_frame
	await RenderingServer.frame_post_draw
	var after_transform: Transform3D = player_camera.global_transform
	var after_pixels: PackedByteArray = viewport.get_texture().get_image().get_data()
	var before_pitch: float = player.get_node("Body/Neck/Head").rotation_degrees.x
	action_results.clear()
	executor.batch_finished.connect(
		func(results: Array) -> void: action_results.append(results.duplicate(true)),
		CONNECT_ONE_SHOT,
	)
	executor.execute_batch([{
		"type": "look",
		"yaw": 0.0,
		"pitch": 20.0,
	}], {})
	while action_results.is_empty():
		await process_frame
	await RenderingServer.frame_post_draw
	var after_pitch: float = player.get_node("Body/Neck/Head").rotation_degrees.x
	var after_pitch_pixels: PackedByteArray = viewport.get_texture().get_image().get_data()

	var before_forced_yaw: float = player.get_node("Body").global_rotation_degrees.y
	var before_forced_pixels: PackedByteArray = viewport.get_texture().get_image().get_data()
	RenderingServer.render_loop_enabled = false
	action_results.clear()
	executor.batch_finished.connect(
		func(results: Array) -> void: action_results.append(results.duplicate(true)),
		CONNECT_ONE_SHOT,
	)
	executor.execute_batch([{
		"type": "look",
		"yaw": 30.0,
		"pitch": 0.0,
	}], {})
	while action_results.is_empty():
		await process_frame
	await process_frame
	RenderingServer.force_draw(false)
	var after_forced_yaw: float = player.get_node("Body").global_rotation_degrees.y
	var after_forced_pixels: PackedByteArray = viewport.get_texture().get_image().get_data()
	RenderingServer.render_loop_enabled = true

	print("AI_PLAY_RENDER current_is_player=%s" % (current_camera == player_camera))
	print("AI_PLAY_RENDER action_results=%s" % action_results)
	print("AI_PLAY_RENDER camera_transform_changed=%s" % (before_transform != after_transform))
	print("AI_PLAY_RENDER pixels_changed=%s" % (before_pixels != after_pixels))
	print("AI_PLAY_RENDER semantic_up_changed_pitch=%s" % (after_pitch > before_pitch))
	print("AI_PLAY_RENDER semantic_up_changed_pixels=%s" % (after_pitch_pixels != after_pixels))
	print("AI_PLAY_RENDER forced_yaw_changed=%s" % (
		before_forced_yaw != after_forced_yaw
	))
	print("AI_PLAY_RENDER forced_pixels_changed=%s" % (
		before_forced_pixels != after_forced_pixels
	))
	quit(0 if (
		current_camera == player_camera
		and before_transform != after_transform
		and before_pixels != after_pixels
		and after_pitch > before_pitch
		and after_pitch_pixels != after_pixels
		and before_forced_yaw != after_forced_yaw
		and before_forced_pixels != after_forced_pixels
	) else 1)
