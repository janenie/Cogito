extends SceneTree

const GardenMonitor = preload(
	"res://addons/cogito/AIPlay/ai_play_garden_monitor.gd"
)

var failures := 0


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	var packed: PackedScene = load(
		"res://garden/scenes/garden_vertical_slice.tscn"
	)
	_assert(packed != null, "garden scene loads")
	if packed == null:
		_finish()
		return
	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame

	var controller: Node = scene.get_node_or_null("AIPlayController")
	var observer: Node = scene.get_node_or_null("AIPlayController/Observer")
	var monitor: Node = scene.get_node_or_null("AIPlayController/GardenMonitor")
	_assert(controller != null, "garden scene has an AI Play controller")
	_assert(observer != null, "garden scene has a garden observer")
	_assert(monitor != null, "garden scene has a terminal monitor")
	if controller != null:
		_assert(not controller.auto_start, "garden AI Play stays explicitly disabled")
		_assert(controller.host == "127.0.0.1", "garden bridge uses numeric loopback")
	if observer != null:
		_assert(observer.watering_state == scene, "observer reads the garden state")
	if monitor != null:
		_assert(monitor.scenario_id == "garden_watering", "monitor selects garden scenario")

	_test_public_observation(scene, observer)
	await _test_terminal_monitor(scene)
	scene.queue_free()
	await process_frame
	_finish()


func _test_public_observation(
	scene: Node,
	observer: Node,
) -> void:
	if observer == null:
		return
	var public_state: Dictionary = scene.ai_play_public_state()
	_assert(public_state.weather in ["sunny", "rain"], "weather is public and bounded")
	_assert(public_state.required_lawns == 4, "public progress requires four lawns")
	for forbidden: String in [
		"run_seed",
		"rain_start_minute",
		"rain_end_minute",
		"watering_target_paths",
	]:
		_assert(not public_state.has(forbidden), "public state hides %s" % forbidden)

	var player := scene.get_node("CogitoPlayer") as Node3D
	var watering_can := scene.get_node(
		"NeighborhoodPlaza/WateringCans/FarmWateringCanA"
	) as Node3D
	player.position = scene._resolved_position(watering_can)
	var interactions: Array = observer.get_available_interactions()
	_assert(interactions.size() == 1, "nearby watering can is exposed as interaction")
	if interactions.size() == 1:
		_assert(interactions[0].prompt == "拿水壶", "watering-can prompt is public")

	var observation: Dictionary = observer.capture_observation([])
	_assert(observation.has("garden"), "observation includes public garden state")
	_assert(observation.garden == public_state, "observation garden state is exact")
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


func _test_terminal_monitor(scene: Node) -> void:
	scene.reset_game_state_for_tests()
	var success_events: Array = []
	var success_monitor := GardenMonitor.new()
	success_monitor.watering_state = scene
	success_monitor.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			success_events.append([outcome, reason])
	)
	scene.add_child(success_monitor)
	for house_number: int in scene.game1_rules.watering_house_numbers:
		scene.game1_rules.try_water_lawn(house_number, 1)
		scene.game1_rules.try_water_lawn(house_number, 2)
	scene.game1_rules.advance_to_minutes(scene.game1_rules.rain_start_minute)
	scene.game1_rules.try_press_alarm(3)
	await process_frame
	await process_frame
	_assert(
		success_events == [["success", "garden_tasks_complete"]],
		"garden completion emits one allowlisted success",
	)
	success_monitor.queue_free()
	await process_frame

	scene.reset_game_state_for_tests()
	var failure_events: Array = []
	var failure_monitor := GardenMonitor.new()
	failure_monitor.watering_state = scene
	failure_monitor.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			failure_events.append([outcome, reason])
	)
	scene.add_child(failure_monitor)
	scene.game1_rules.fail_day("test failure")
	await process_frame
	await process_frame
	_assert(
		failure_events == [["failure", "garden_task_failed"]],
		"garden failure emits one allowlisted failure",
	)
	failure_monitor.queue_free()


func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)


func _finish() -> void:
	if failures == 0:
		print("Garden AI Play tests passed")
		quit(0)
	else:
		push_error("%d Garden AI Play test(s) failed" % failures)
		quit(1)
