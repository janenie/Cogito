extends SceneTree


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	if DisplayServer.get_name() == "headless":
		print("AIPlay rendered recovery test skipped in headless mode")
		quit(0)
		return
	var change_error: Error = change_scene_to_file(
		"res://addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
	)
	if change_error != OK:
		_fail("failed to load Lobby: %s" % error_string(change_error))
		return
	for unused_index: int in 10:
		await process_frame
	await RenderingServer.frame_post_draw

	var lobby: Node = current_scene
	var player: Node3D = lobby.get_node("Player")
	var controller: Node = lobby.get_node("AIPlayController")
	var observer: Node = controller.get_node("Observer")
	var executor: Node = controller.get_node("Executor")
	controller._set_ai_mouse_guard(true)
	var initial_observation: Dictionary = observer.capture_observation([])
	var initial_id: int = initial_observation["observation_id"]
	var initial_image: String = initial_observation["image"]["base64"]
	var spawn_position: Vector3 = player.global_position

	var action_results: Array = []
	executor.batch_finished.connect(
		func(results: Array) -> void: action_results.append(results.duplicate(true)),
		CONNECT_ONE_SHOT,
	)
	executor.execute_batch([{
		"type": "sprint",
		"forward": 1.0,
		"right": 0.0,
		"duration_ms": 250,
	}], {})
	await create_timer(0.12).timeout
	var partial_position: Vector3 = player.global_position
	executor.cancel_all("action_timeout")
	while action_results.is_empty():
		await process_frame
	await RenderingServer.frame_post_draw
	var recovered_observation: Dictionary = observer.capture_observation(action_results[0])
	var recovered_position: Vector3 = player.global_position

	var moved_before_recovery: bool = spawn_position.distance_to(partial_position) > 0.01
	var stayed_in_world: bool = spawn_position.distance_to(recovered_position) > 0.01
	var fresh_id: bool = recovered_observation["observation_id"] > initial_id
	var fresh_pixels: bool = recovered_observation["image"]["base64"] != initial_image
	var inputs_released: bool = (
		not Input.is_action_pressed("forward")
		and not Input.is_action_pressed("sprint")
	)
	var action_cancelled: bool = (
		action_results[0].size() == 1
		and action_results[0][0].get("status") == "cancelled"
		and action_results[0][0].get("reason") == "action_timeout"
	)

	print("AI_PLAY_RECOVERY moved_before_recovery=%s" % moved_before_recovery)
	print("AI_PLAY_RECOVERY stayed_in_world=%s" % stayed_in_world)
	print("AI_PLAY_RECOVERY fresh_id=%s" % fresh_id)
	print("AI_PLAY_RECOVERY fresh_pixels=%s" % fresh_pixels)
	print("AI_PLAY_RECOVERY inputs_released=%s" % inputs_released)
	print("AI_PLAY_RECOVERY action_cancelled=%s" % action_cancelled)
	quit(0 if (
		moved_before_recovery
		and stayed_in_world
		and fresh_id
		and fresh_pixels
		and inputs_released
		and action_cancelled
	) else 1)


func _fail(message: String) -> void:
	push_error(message)
	quit(1)
