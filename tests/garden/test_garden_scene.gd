extends SceneTree

var failures := 0

func _init() -> void:
	_test_watering_state_accumulates_subminute_time()
	_test_vertical_slice_scene()
	if failures == 0:
		print("Garden scene tests passed")
		quit(0)
	else:
		push_error("%d Garden scene test(s) failed" % failures)
		quit(1)

func _test_watering_state_accumulates_subminute_time() -> void:
	var watering_state := GardenWateringState.new()
	watering_state.real_day_seconds = 30.0 * 60.0
	watering_state.game1_rules.start_run(1)
	watering_state.game1_rules.rain_scheduled = false
	watering_state._game1_time_float = float(watering_state.game1_rules.minutes_since_midnight)
	watering_state._last_real_time_update_msec = Time.get_ticks_msec() - 2500
	watering_state._advance_game1_time()
	var first_minute := watering_state.game1_rules.minutes_since_midnight
	watering_state._last_real_time_update_msec = Time.get_ticks_msec() - 2500
	watering_state._advance_game1_time()
	_assert(watering_state.game1_rules.minutes_since_midnight > first_minute, "small real-time ticks accumulate into game minutes")

func _test_vertical_slice_scene() -> void:
	var packed: PackedScene = load("res://garden/scenes/garden_vertical_slice.tscn")
	_assert(packed != null, "main scene loads")
	if packed == null:
		return
	var scene := packed.instantiate()
	root.add_child(scene)
	if scene is GardenWateringState:
		(scene as GardenWateringState)._setup_rain_visuals()
		(scene as GardenWateringState)._update_rain_visuals(0.0)
	_assert(scene.get_node_or_null("CogitoPlayer") != null, "scene has player")
	_assert((scene.get_node_or_null("WorldEnvironment") as WorldEnvironment).environment != null, "scene has sky environment")
	_assert(scene.get_node_or_null("GardenUI/Panel/Margin/Rows/TaskLabel") != null, "scene has task label")
	_assert(_task_label_hides_solution(scene), "task label does not reveal watering house numbers")
	_assert(scene.get_node_or_null("GardenUI/Panel/Margin/Rows/TimeLabel") != null, "scene has time label")
	_test_hud_time_updates_with_game_time(scene)
	_assert(scene.get_node_or_null("GardenUI/Panel/Margin/Rows/WeatherLabel") != null, "scene has weather label")
	_assert(scene.get_node_or_null("GardenUI/Panel/Margin/Rows/CanopyLabel") != null, "scene has orchid canopy label")
	_assert(scene.get_node_or_null("GardenUI/CenterCrosshair/Horizontal") != null, "scene has center crosshair")
	_assert(scene.get_node_or_null("GardenUI/ActionPrompt") != null, "scene has action prompt")
	_assert(scene.get_node_or_null("Roads/MainStreet") != null, "scene has main street")
	_assert(scene.get_node_or_null("NeighborhoodPlaza/SharedTap") != null, "scene has shared tap")
	_assert(scene.get_node_or_null("Houses/House1_Sunflowers/Garden") != null, "scene has sunflower house and garden")
	_assert(scene.get_node_or_null("Houses/House2_Hydrangeas/HydrangeaGarden") != null, "scene has hydrangea house and garden")
	_assert(scene.get_node_or_null("Houses/House3_Orchids/OutdoorOrchids") != null, "scene has orchid house and outdoor garden")
	_assert(scene.get_node_or_null("Houses/House3_Orchids/IndoorOrchidSpots/IndoorSpotA") != null, "scene has indoor orchid spots")
	_assert(_has_house_number_labels(scene), "scene has large generic house number labels")
	_assert(_has_unique_internal_flower_labels(scene), "scene has internal randomized flower labels")
	_assert(_has_doorbell_labels(scene), "all doorbells have labels")
	_assert(_has_white_ui_text(scene), "HUD and action prompt use white text")
	_assert(_has_translucent_black_hud_panel(scene), "HUD uses translucent black panel")
	_assert(_count_named_prefix(scene, "CanopySwitch") >= 3, "scene has canopy switches for randomized orchid house")
	_assert(_count_named_prefix(scene, "OrchidCanopy") >= 3, "scene has canopy roofs for randomized orchid house")
	_assert(_count_named_prefix(scene, "Sunflower") >= 4, "scene has sunflower props")
	_assert(_count_named_prefix(scene, "SunflowerBloom") >= 8, "scene has dense visible sunflower blooms")
	_test_rain_visuals_follow_weather(scene)
	_assert(_count_named_prefix(scene, "OrchidPot") == 3, "scene has three orchid pots")
	_assert(_count_named_prefix(scene, "FarmWateringCan") == 4, "scene has four farm watering cans")
	_assert(scene.get_node_or_null("NeighborhoodPlaza/WateringCans/FarmWateringCanA/Spout/Rose") != null, "watering cans have a spout rose")
	_assert(_watering_can_pickup_range_is_tight(scene), "watering can pickup range is tight")
	_assert(_player_starts_on_pool_street(scene), "player starts on street in front of pool")
	_assert(_count_static_body_collisions(scene.get_node_or_null("CollisionBounds")) >= 22, "scene has house, fence, and pool collisions")
	_assert(scene.get_node_or_null("Ground/CollisionShape3D") != null, "scene has walkable collision")
	_test_no_prompt_for_lawn_without_can(scene)
	_test_scene_watering_interaction(scene)
	_test_game1_watering_objective(scene)
	_test_wrong_watering_fails_after_four_used_lawns(scene)
	scene.queue_free()

func _test_hud_time_updates_with_game_time(scene: Node) -> void:
	var watering_state := scene as GardenWateringState
	var time_label := scene.get_node_or_null("GardenUI/Panel/Margin/Rows/TimeLabel") as Label
	if watering_state == null or time_label == null:
		return
	watering_state.reset_game_state_for_tests()
	_assert(time_label.text == "时间：08:29", "HUD time starts at the game start time")
	watering_state._last_real_time_update_msec = Time.get_ticks_msec() - 5000
	watering_state._advance_game1_time()
	_assert(time_label.text == "时间：08:30", "HUD time refreshes when game time advances")

func _test_no_prompt_for_lawn_without_can(scene: Node) -> void:
	var player := scene.get_node_or_null("CogitoPlayer") as Node3D
	var watering_state := scene as GardenWateringState
	var action_prompt := scene.get_node_or_null("GardenUI/ActionPrompt") as Label
	if player == null or watering_state == null or action_prompt == null:
		return
	watering_state.reset_game_state_for_tests()
	var watering_house: int = watering_state.game1_rules.watering_house_numbers[0]
	var lawn := scene.get_node_or_null(watering_state.target_path_for_house_lawn(watering_house, 1)) as Node3D
	_assert(lawn != null, "no-prompt test has target lawn")
	if lawn == null:
		return
	player.position = watering_state._resolved_position(lawn)
	watering_state._update_action_prompt()
	_assert(action_prompt.text == "", "no watering prompt appears near lawn without a can")
	var alarm := scene.get_node_or_null(watering_state._canopy_switch_path_for_house(watering_state.game1_rules.alarm_house_number)) as Node3D
	_assert(alarm != null, "no-prompt test has alarm button")
	if alarm == null:
		return
	player.position = watering_state._resolved_position(alarm)
	watering_state._update_action_prompt()
	_assert(action_prompt.text == "F  按门铃", "doorbell prompt appears before rain starts")
	_assert(watering_state.try_press_nearby_alarm(), "doorbell is interactable before rain")
	_assert(watering_state.game1_rules.day_failed, "orchid doorbell before rain fails immediately")
	watering_state.reset_game_state_for_tests()
	watering_state.game1_rules.start_rain()
	player.position = watering_state._resolved_position(alarm)
	watering_state._update_action_prompt()
	_assert(action_prompt.text == "F  按门铃", "doorbell prompt appears during rain")
	_assert(watering_state.try_press_nearby_alarm(), "alarm button is interactable during rain")

	var wrong_alarm := scene.get_node_or_null(watering_state._canopy_switch_path_for_house(1)) as Node3D
	if wrong_alarm != null and watering_state.game1_rules.alarm_house_number != 1:
		watering_state.reset_game_state_for_tests()
		watering_state.game1_rules.start_rain()
		player.position = watering_state._resolved_position(wrong_alarm)
		_assert(watering_state.try_press_nearby_alarm(), "wrong doorbell is still interactable during rain")
		_assert(watering_state.game1_rules.day_failed, "wrong doorbell fails immediately")
	watering_state.reset_game_state_for_tests()

func _test_scene_watering_interaction(scene: Node) -> void:
	var player := scene.get_node_or_null("CogitoPlayer") as Node3D
	var pool := scene.get_node_or_null("NeighborhoodPlaza/RedrawnWaterPool/PoolWater") as Node3D
	var can := scene.get_node_or_null("NeighborhoodPlaza/WateringCans/FarmWateringCanA") as Node3D
	var watering_state := scene as GardenWateringState
	_assert(player != null, "interaction test has player")
	_assert(pool != null, "interaction test has pool water target")
	_assert(can != null, "interaction test has pickup can")
	_assert(watering_state != null, "scene root owns watering state")
	if player == null or pool == null or can == null or watering_state == null:
		return
	watering_state.has_water = false
	var watering_house: int = watering_state.game1_rules.watering_house_numbers[0]
	var lawn := scene.get_node_or_null(watering_state.target_path_for_house_lawn(watering_house, 1)) as Node3D
	_assert(lawn != null, "interaction test has target lawn")
	if lawn == null:
		return
	player.position = watering_state._resolved_position(lawn)
	_assert(not watering_state.try_water_nearby_garden(), "player cannot water before picking up can")
	player.position = watering_state._resolved_position(pool)
	_assert(not watering_state.try_refill(), "pool refill is not part of the simplified player flow before pickup")
	player.position = watering_state._resolved_position(can) + Vector3(0.0, 0.0, watering_state.pickup_distance + 0.25)
	_assert(not watering_state.try_pickup_can(), "player cannot pick up a watering can from outside the tight range")
	player.position = watering_state._resolved_position(can)
	_assert(watering_state.try_pickup_can(), "player can pick up a watering can")
	_assert(watering_state.has_can, "pickup marks player as carrying can")
	_assert(can.get_parent() == player, "picked up watering can follows player")
	player.position = watering_state._resolved_position(pool)
	var held_can := watering_state.held_can
	player.position = watering_state._resolved_position(lawn)
	_assert(watering_state.try_water_nearby_garden(), "player can water a target lawn")
	_assert(not watering_state.has_can, "watering consumes the held can")
	_assert(held_can == null or not held_can.visible, "used watering can is hidden after one lawn")

func _test_game1_watering_objective(scene: Node) -> void:
	var player := scene.get_node_or_null("CogitoPlayer") as Node3D
	var watering_state := scene as GardenWateringState
	var task_label := scene.get_node_or_null("GardenUI/Panel/Margin/Rows/TaskLabel") as Label
	if player == null or watering_state == null or task_label == null:
		return
	watering_state.reset_game_state_for_tests()
	for house_number in watering_state.game1_rules.watering_house_numbers:
		for lawn_number in range(1, 3):
			var target := scene.get_node_or_null(watering_state.target_path_for_house_lawn(house_number, lawn_number)) as Node3D
			_assert(target != null, "game1 has target lawn")
			if target == null:
				continue
			_assert(target.get_node_or_null("WaterStatusLabel") == null, "target lawn does not reveal drought status text")
			_pick_up_next_can(scene, player, watering_state)
			player.position = Vector3(40.0, 1.2, 30.0)
			var count_before_far_attempt := watering_state.watered_count
			_assert(not watering_state.try_water_nearby_garden(), "cannot water target from too far away")
			_assert(watering_state.watered_count == count_before_far_attempt, "failed watering does not advance progress")
			player.position = watering_state._resolved_position(target)
			_assert(watering_state.try_water_nearby_garden(), "can water game1 lawn")
			_assert(target.get_node_or_null("WateredMarker") != null, "watered lawn has visual marker")
			var status_label := target.get_node_or_null("WaterStatusLabel") as Label3D
			_assert(status_label != null and status_label.text == "水量充足", "watered lawn shows enough-water text")
	_assert(watering_state.game1_rules.is_watering_complete(), "game1 objective waters four lawns")
	watering_state.game1_rules.start_rain()
	var alarm := scene.get_node_or_null(watering_state._canopy_switch_path_for_house(watering_state.game1_rules.alarm_house_number)) as Node3D
	_assert(alarm != null, "game1 has rain alarm button")
	if alarm != null:
		player.position = watering_state._resolved_position(alarm)
		_assert(watering_state.try_press_nearby_alarm(), "player can press rain alarm during rain")
	_assert(watering_state.game1_rules.is_complete(), "game1 objective completes watering and rain alarm")
	_assert(task_label.text.contains("完成"), "task label shows game1 completion")

func _test_wrong_watering_fails_after_four_used_lawns(scene: Node) -> void:
	var player := scene.get_node_or_null("CogitoPlayer") as Node3D
	var watering_state := scene as GardenWateringState
	var task_label := scene.get_node_or_null("GardenUI/Panel/Margin/Rows/TaskLabel") as Label
	if player == null or watering_state == null or task_label == null:
		return
	watering_state.reset_game_state_for_tests()
	for target_path in [
		watering_state.target_path_for_house_lawn(1, 1),
		watering_state.target_path_for_house_lawn(1, 2),
		watering_state.target_path_for_house_lawn(2, 1),
		watering_state.target_path_for_house_lawn(3, 1),
	]:
		var target := scene.get_node_or_null(target_path) as Node3D
		_assert(target != null, "wrong watering test has target lawn")
		if target == null:
			continue
		_pick_up_next_can(scene, player, watering_state)
		player.position = watering_state._resolved_position(target)
		_assert(watering_state.try_water_nearby_garden(), "can spend one watering can on chosen lawn")
	_assert(watering_state.game1_rules.day_failed, "wrong set of four watered lawns fails")
	_assert(task_label.text.contains("任务失败"), "task label shows failure after wrong watering")

func _pick_up_next_can(scene: Node, player: Node3D, watering_state: GardenWateringState) -> void:
	for child in scene.get_node("NeighborhoodPlaza/WateringCans").get_children():
		var can := child as Node3D
		if can != null and can.visible:
			player.position = watering_state._resolved_position(can)
			_assert(watering_state.try_pickup_can(), "can pick up a full watering can")
			return
	_assert(false, "a full watering can is available")

func _test_rain_visuals_follow_weather(scene: Node) -> void:
	var watering_state := scene as GardenWateringState
	if watering_state == null:
		return
	watering_state.game1_rules.rain_active = false
	watering_state._update_rain_visuals(0.0)
	_assert(not _has_active_rain_visuals(scene), "rain visuals are hidden before rain starts")
	watering_state.game1_rules.start_rain()
	watering_state._update_rain_visuals(0.0)
	_assert(_has_rainy_light(scene), "scene dims lighting during rain")
	_assert(_has_active_rain_visuals(scene), "scene shows visible rain drops during rain")

func _has_house_number_labels(scene: Node) -> bool:
	var labels: Array[Label3D] = [
		scene.get_node_or_null("Houses/House1_Sunflowers/Label") as Label3D,
		scene.get_node_or_null("Houses/House2_Hydrangeas/Label") as Label3D,
		scene.get_node_or_null("Houses/House3_Orchids/Label") as Label3D,
	]
	var expected: Array[String] = ["房屋一", "房屋二", "房屋三"]
	for index in range(labels.size()):
		var label: Label3D = labels[index]
		if label == null or label.text != expected[index] or label.font_size < 90 or not _has_white_text_with_black_outline(label):
			return false
	return true

func _has_unique_internal_flower_labels(scene: Node) -> bool:
	var labels: Array[Label3D] = [
		scene.get_node_or_null("Houses/House1_Sunflowers/Garden/FlowerLabel") as Label3D,
		scene.get_node_or_null("Houses/House2_Hydrangeas/HydrangeaGarden/FlowerLabel") as Label3D,
		scene.get_node_or_null("Houses/House3_Orchids/OutdoorOrchids/FlowerLabel") as Label3D,
	]
	var values: Array[String] = []
	for label in labels:
		if label == null:
			return false
		if label.font_size < 60 or not _has_white_text_with_black_outline(label):
			return false
		values.append(label.text)
	return values.has("向日葵") and values.has("绣球花") and values.has("兰花")

func _has_doorbell_labels(scene: Node) -> bool:
	var watering_state := scene as GardenWateringState
	if watering_state == null:
		return false
	for house_number in range(1, 4):
		var alarm := scene.get_node_or_null(watering_state._canopy_switch_path_for_house(house_number)) as Node3D
		if alarm == null or not alarm.visible:
			return false
		var label := alarm.get_node_or_null("DoorbellLabel") as Label3D
		if label == null or label.text != "门铃" or label.font_size < 40 or not _has_white_text_with_black_outline(label):
			return false
	return true

func _task_label_hides_solution(scene: Node) -> bool:
	var task_label := scene.get_node_or_null("GardenUI/Panel/Margin/Rows/TaskLabel") as Label
	if task_label == null:
		return false
	return not task_label.text.contains("房屋一") and not task_label.text.contains("房屋二") and not task_label.text.contains("房屋三")

func _has_white_ui_text(scene: Node) -> bool:
	for path in [
		"GardenUI/ActionPrompt",
		"GardenUI/Panel/Margin/Rows/TimeLabel",
		"GardenUI/Panel/Margin/Rows/WeatherLabel",
		"GardenUI/Panel/Margin/Rows/CanopyLabel",
		"GardenUI/Panel/Margin/Rows/StatusLabel",
		"GardenUI/Panel/Margin/Rows/TaskLabel",
		"GardenUI/Panel/Margin/Rows/HintLabel",
		"GardenUI/Panel/Margin/Rows/MessageLabel",
	]:
		var label := scene.get_node_or_null(path) as Label
		if label == null or not _is_white(label.modulate):
			return false
	return true

func _has_translucent_black_hud_panel(scene: Node) -> bool:
	var panel := scene.get_node_or_null("GardenUI/Panel") as PanelContainer
	if panel == null:
		return false
	var style := panel.get_theme_stylebox("panel")
	if not style is StyleBoxFlat:
		return false
	var flat := style as StyleBoxFlat
	return _is_black(flat.bg_color) and flat.bg_color.a >= 0.45 and flat.bg_color.a <= 0.75

func _has_white_text_with_black_outline(label: Label3D) -> bool:
	return _is_white(label.modulate) and _is_black(label.outline_modulate) and label.outline_size >= 8

func _is_white(color: Color) -> bool:
	return color.r >= 0.98 and color.g >= 0.98 and color.b >= 0.98

func _is_black(color: Color) -> bool:
	return color.r <= 0.02 and color.g <= 0.02 and color.b <= 0.02

func _count_named_prefix(node: Node, prefix: String) -> int:
	var count := 0
	var node_name := str(node.name)
	if node_name.begins_with(prefix):
		count += 1
	for child in node.get_children():
		count += _count_named_prefix(child, prefix)
	return count

func _count_static_body_collisions(node: Node) -> int:
	if node == null:
		return 0
	var count := 0
	if node is StaticBody3D and node.get_node_or_null("CollisionShape3D") != null:
		count += 1
	for child in node.get_children():
		count += _count_static_body_collisions(child)
	return count

func _has_rainy_light(scene: Node) -> bool:
	var world_environment := scene.get_node_or_null("WorldEnvironment") as WorldEnvironment
	var sun := scene.get_node_or_null("Sun") as DirectionalLight3D
	if world_environment == null or world_environment.environment == null or sun == null:
		return false
	return world_environment.environment.background_energy_multiplier <= 0.55 \
		and world_environment.environment.ambient_light_energy <= 0.45 \
		and world_environment.environment.ambient_light_sky_contribution <= 0.2 \
		and sun.light_energy <= 0.9

func _has_active_rain_visuals(scene: Node) -> bool:
	var rain_root := scene.get_node_or_null("RainVisuals") as Node3D
	if rain_root == null or not rain_root.visible:
		return false
	return _count_named_prefix(rain_root, "RainDrop") >= 80

func _watering_can_pickup_range_is_tight(scene: Node) -> bool:
	var player := scene.get_node_or_null("CogitoPlayer") as Node3D
	var can := scene.get_node_or_null("NeighborhoodPlaza/WateringCans/FarmWateringCanA") as Node3D
	var watering_state := scene as GardenWateringState
	if player == null or can == null or watering_state == null:
		return false
	return watering_state.pickup_distance <= 2.1 \
		and watering_state._resolved_position(player).distance_to(watering_state._resolved_position(can)) > watering_state.pickup_distance

func _player_starts_on_pool_street(scene: Node) -> bool:
	var player := scene.get_node_or_null("CogitoPlayer") as Node3D
	if player == null:
		return false
	return player.position.z <= -9.0 and absf(player.position.x) <= 4.0

func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
