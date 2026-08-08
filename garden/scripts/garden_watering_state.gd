class_name GardenWateringState
extends Node

const GardenGame1Rules = preload("res://garden/scripts/garden_game1_rules.gd")
const ROUND_SEED_PARSER = preload(
	"res://addons/cogito/AIPlay/ai_play_round_seed.gd"
)
const WATERING_TASK_TEXT := (
	"浇水目标 / WATERING：用中央广场的 4 个满水壶，浇完向日葵房和绣球花房各 2 块草坪；"
	+ "兰花房草坪不要浇。每个水壶只能浇 1 块草坪。"
)
const RAIN_TASK_TEXT := "下雨警报 / RAIN ALERT：雨停前到兰花房按门铃报警。"
const TASK_RULE_SUMMARY := (
	"警报目标 / ALERT：等待 HUD 天气显示下雨，并在雨停前按兰花房门铃。"
	+ "浇错目标、按错门铃、未下雨时按铃或错过雨期都会失败。"
)

@export var player_path: NodePath
@export var refill_station_path: NodePath
@export var watering_cans_path: NodePath
@export var run_seed := 0
@export var real_day_seconds := 30.0 * 60.0
@export var pickup_distance := 2.0
@export var refill_distance := 10.0
@export var watering_distance := 3.2
@export var alarm_distance := 3.2
@export var rain_drop_count := 140
@export var rain_area_size := Vector2(28.0, 28.0)
@export var rain_spawn_height := 11.0
@export var rain_fall_distance := 13.0
@export var held_can_position := Vector3(0.62, -0.35, -0.78)
@export var held_can_rotation_degrees := Vector3(-8.0, -24.0, 10.0)
@export var held_can_scale := Vector3(0.72, 0.72, 0.72)
@export var watering_target_paths: Array[NodePath] = [
	NodePath("Houses/House1_Sunflowers/Garden/LeftRaisedLawn"),
	NodePath("Houses/House1_Sunflowers/Garden/RightFlowerBed"),
	NodePath("Houses/House2_Hydrangeas/HydrangeaGarden/LeftRaisedLawn"),
	NodePath("Houses/House2_Hydrangeas/HydrangeaGarden/RightFlowerBed"),
	NodePath("Houses/House3_Orchids/OutdoorOrchids/LeftRaisedLawn"),
	NodePath("Houses/House3_Orchids/OutdoorOrchids/RightFlowerBed"),
]
@export var alarm_button_paths: Array[NodePath] = [
	NodePath("Houses/House1_Sunflowers/Garden/CanopySwitch"),
	NodePath("Houses/House2_Hydrangeas/HydrangeaGarden/CanopySwitch"),
	NodePath("Houses/House3_Orchids/OutdoorOrchids/CanopySwitch"),
]

var has_can := false
var has_water := true
var watered_count := 0
var total_targets := 0
var last_message := "拿起一个装满水的水壶。"
var held_can: Node3D
var game1_rules := GardenGame1Rules.new()
var _watered_targets := {}
var _last_real_time_update_msec := 0
var _game1_time_float := float(GardenGame1Rules.START_MINUTE)
var _can_home: Dictionary = {}
var _rain_root: Node3D
var _rain_drops: Array[MeshInstance3D] = []
var _rain_speeds: Array[float] = []
var _rain_rng := RandomNumberGenerator.new()

var _garden_paths: Array[NodePath] = [
	NodePath("Houses/House1_Sunflowers/Garden"),
	NodePath("Houses/House2_Hydrangeas/HydrangeaGarden"),
	NodePath("Houses/House3_Orchids/OutdoorOrchids"),
]

@onready var _status_label: Label = get_node_or_null("GardenUI/Panel/Margin/Rows/StatusLabel")
@onready var _time_label: Label = get_node_or_null("GardenUI/Panel/Margin/Rows/TimeLabel")
@onready var _weather_label: Label = get_node_or_null("GardenUI/Panel/Margin/Rows/WeatherLabel")
@onready var _canopy_label: Label = get_node_or_null("GardenUI/Panel/Margin/Rows/CanopyLabel")
@onready var _task_label: Label = get_node_or_null("GardenUI/Panel/Margin/Rows/TaskLabel")
@onready var _hint_label: Label = get_node_or_null("GardenUI/Panel/Margin/Rows/HintLabel")
@onready var _message_label: Label = get_node_or_null("GardenUI/Panel/Margin/Rows/MessageLabel")
@onready var _action_prompt_label: Label = get_node_or_null("GardenUI/ActionPrompt")

func _init() -> void:
	game1_rules.start_run(run_seed)
	_game1_time_float = float(game1_rules.minutes_since_midnight)

func _ready() -> void:
	run_seed = _resolve_run_seed()
	game1_rules.start_run(run_seed)
	total_targets = game1_rules.required_lawn_count()
	if game1_rules.get_parent() == null:
		add_child(game1_rules)
	_game1_time_float = float(game1_rules.minutes_since_midnight)
	_last_real_time_update_msec = Time.get_ticks_msec()
	_apply_readable_text_style()
	_apply_game1_assignments()
	_cache_can_homes()
	_setup_rain_visuals()
	_update_rain_visuals(0.0)
	_update_ui()


func ai_play_public_state() -> Dictionary:
	return {
		"objective": _current_objective_text(),
		"time": _formatted_game1_time(),
		"weather": game1_rules.current_weather(),
		"has_watering_can": has_can,
		"can_has_water": has_water,
		"watered_lawns": game1_rules.watered_lawn_count(),
		"required_lawns": game1_rules.required_lawn_count(),
		"rain_alarm_pressed": game1_rules.alarm_pressed,
		"completed": game1_rules.is_complete(),
		"failed": game1_rules.day_failed,
	}


func ai_play_interaction_prompt() -> String:
	if _nearest_alarm_button() != null:
		return "按门铃"
	if not has_can and _nearest_available_can() != null:
		return "拿水壶"
	if has_can and has_water and not _nearest_target_path().is_empty():
		return "浇草坪"
	return ""


func _resolve_run_seed() -> int:
	var parsed: Dictionary = ROUND_SEED_PARSER.parse(
		OS.get_cmdline_user_args(),
		true,
	)
	if not parsed["valid"]:
		push_error("Invalid AI Play round seed argument")
		return run_seed
	if parsed["provided"]:
		return ROUND_SEED_PARSER.runtime_seed(int(parsed["value"]))
	return run_seed

func _process(_delta: float) -> void:
	_advance_game1_time()
	_update_rain_visuals(_delta)
	_update_action_prompt()
	if Input.is_action_just_pressed("interact"):
		if try_press_nearby_alarm():
			return
		elif not has_can:
			try_pickup_can()
		else:
			try_water_nearby_garden()

func try_pickup_can() -> bool:
	var player := get_node_or_null(player_path) as Node3D
	var can := _nearest_available_can()
	if player == null or can == null:
		last_message = "靠近一个装满水的水壶。"
		_update_ui()
		return false
	_pickup_can(player, can)
	has_can = true
	has_water = true
	last_message = "已拿起装满水的水壶。"
	_update_ui()
	return true

func refill() -> void:
	has_water = true
	last_message = "水壶已装满。"
	_update_ui()

func water() -> bool:
	if not has_can:
		last_message = "先拿起一个水壶。"
		_update_ui()
		return false
	if not has_water:
		last_message = "水壶已经空了。"
		_update_ui()
		return false
	has_water = false
	has_can = false
	watered_count += 1
	last_message = "已浇一块草坪，这个水壶已经用完。"
	_update_ui()
	return true

func try_refill() -> bool:
	if not has_can:
		last_message = "先拿起一个水壶。"
		_update_ui()
		return false
	if not _is_player_near_node(refill_station_path, refill_distance):
		last_message = "水池只是装饰，不需要补水。"
		_update_ui()
		return false
	refill()
	return true

func try_water_nearby_garden() -> bool:
	if not has_can:
		last_message = "先拿起一个水壶。"
		_update_ui()
		return false
	var target_path := _nearest_target_path()
	if target_path.is_empty():
		last_message = "靠近草坪再浇水。"
		_update_ui()
		return false
	var target := get_node_or_null(target_path) as Node3D
	if target == null:
		last_message = "靠近草坪再浇水。"
		_update_ui()
		return false
	if not has_water:
		last_message = "这个水壶已经空了，去拿另一个满水壶。"
		_update_ui()
		return false
	var house_number := _house_number_for_target_path(target_path)
	var lawn_number := _lawn_number_for_target_path(target_path)
	if not game1_rules.try_water_lawn(house_number, lawn_number):
		last_message = _invalid_watering_message(house_number)
		_update_ui()
		return false
	has_water = false
	has_can = false
	_watered_targets[str(target_path)] = true
	watered_count = game1_rules.watered_lawn_count()
	_mark_target_watered(target)
	if game1_rules.is_complete():
		last_message = "任务成功：浇水和下雨警报都完成了。"
	elif game1_rules.day_failed:
		last_message = game1_rules.failure_reason
	else:
		last_message = "已浇%s的一块草坪，去拿另一个满水壶。" % _house_display_name(house_number)
	if held_can != null and is_instance_valid(held_can):
		held_can.visible = false
		held_can = null
	_update_ui()
	return true

func reset_game_state_for_tests() -> void:
	_reset_watering_cans()
	_watered_targets.clear()
	for path in watering_target_paths:
		var target := get_node_or_null(path) as Node3D
		if target != null:
			var marker := target.get_node_or_null("WateredMarker")
			if marker != null:
				target.remove_child(marker)
				marker.free()
			var label := target.get_node_or_null("WaterStatusLabel")
			if label != null:
				target.remove_child(label)
				label.free()
	has_can = false
	has_water = true
	watered_count = 0
	last_message = "拿起一个装满水的水壶。"
	game1_rules.start_run(run_seed)
	_game1_time_float = float(game1_rules.minutes_since_midnight)
	_apply_game1_assignments()
	_update_ui()

func target_path_for_flower(flower: String) -> NodePath:
	match flower:
		"water_a":
			return _primary_target_path_for_house(game1_rules.watering_house_numbers[0])
		"water_b":
			return _primary_target_path_for_house(game1_rules.watering_house_numbers[1])
		"alarm":
			return _primary_target_path_for_house(game1_rules.alarm_house_number)
	return NodePath("")

func target_path_for_house_lawn(house_number: int, lawn_number: int) -> NodePath:
	for path in watering_target_paths:
		if _house_number_for_target_path(path) == house_number and _lawn_number_for_target_path(path) == lawn_number:
			return path
	return NodePath("")

func try_press_nearby_alarm() -> bool:
	var switch := _nearest_alarm_button()
	if switch == null:
		return false
	var house_number := _house_number_for_canopy_switch(switch)
	if game1_rules.alarm_pressed:
		last_message = "门铃已经按过了。"
	elif game1_rules.try_press_alarm(house_number):
		last_message = "已按下%s的下雨警报。" % _house_display_name(house_number)
	else:
		last_message = game1_rules.failure_reason
	_update_ui()
	return true

func _nearest_available_can() -> Node3D:
	var player := get_node_or_null(player_path) as Node3D
	var cans_root := get_node_or_null(watering_cans_path)
	if player == null or cans_root == null:
		return null
	var nearest_can: Node3D
	var nearest_distance := INF
	var player_position := _resolved_position(player)
	for child in cans_root.get_children():
		var can := child as Node3D
		if can == null or not can.visible:
			continue
		var distance := player_position.distance_to(_resolved_position(can))
		if distance <= pickup_distance and distance < nearest_distance:
			nearest_can = can
			nearest_distance = distance
	return nearest_can

func _pickup_can(player: Node3D, can: Node3D) -> void:
	if not _can_home.has(can):
		_can_home[can] = {
			"parent": can.get_parent(),
			"transform": can.transform,
		}
	var old_parent := can.get_parent()
	if old_parent != null:
		old_parent.remove_child(can)
	can.owner = null
	player.add_child(can)
	can.position = held_can_position
	can.rotation_degrees = held_can_rotation_degrees
	can.scale = held_can_scale
	can.visible = true
	held_can = can

func _cache_can_homes() -> void:
	var cans_root := get_node_or_null(watering_cans_path)
	if cans_root == null:
		return
	for child in cans_root.get_children():
		var can := child as Node3D
		if can != null and not _can_home.has(can):
			_can_home[can] = {
				"parent": cans_root,
				"transform": can.transform,
			}

func _reset_watering_cans() -> void:
	_cache_can_homes()
	for can in _can_home.keys():
		if not is_instance_valid(can):
			continue
		var home: Dictionary = _can_home[can]
		var parent := home.get("parent") as Node
		if parent == null:
			continue
		var current_parent := (can as Node).get_parent()
		if current_parent != parent:
			if current_parent != null:
				current_parent.remove_child(can)
			parent.add_child(can)
		(can as Node3D).transform = home.get("transform")
		(can as Node3D).visible = true
	held_can = null

func _nearest_target_path() -> NodePath:
	var player := get_node_or_null(player_path) as Node3D
	if player == null:
		return NodePath("")
	var nearest_path := NodePath("")
	var nearest_distance := INF
	var player_position := _resolved_position(player)
	for path in watering_target_paths:
		var target := get_node_or_null(path) as Node3D
		if target == null:
			continue
		var house_number := _house_number_for_target_path(path)
		var lawn_number := _lawn_number_for_target_path(path)
		if _watered_targets.has(str(path)) or not _lawn_can_be_watered(house_number, lawn_number):
			continue
		var distance := player_position.distance_to(_resolved_position(target))
		if distance <= watering_distance and distance < nearest_distance:
			nearest_path = path
			nearest_distance = distance
	return nearest_path

func _mark_target_watered(target: Node3D) -> void:
	if target.get_node_or_null("WateredMarker") != null:
		return
	var marker := MeshInstance3D.new()
	marker.name = "WateredMarker"
	var mesh := SphereMesh.new()
	mesh.radius = 0.18
	mesh.height = 0.3
	mesh.radial_segments = 10
	mesh.rings = 5
	marker.mesh = mesh
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.18, 0.58, 0.94, 1.0)
	material.emission_enabled = true
	material.emission = Color(0.08, 0.28, 0.5, 1.0)
	marker.set_surface_override_material(0, material)
	marker.position = Vector3(0.0, 1.25, 0.0)
	target.add_child(marker)
	var label := Label3D.new()
	label.name = "WaterStatusLabel"
	label.text = "水量充足"
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = Vector3(0.0, 1.75, 0.0)
	target.add_child(label)
	_style_label3d(label, 42)

func _is_player_near_node(path: NodePath, distance: float) -> bool:
	var player := get_node_or_null(player_path) as Node3D
	var target := get_node_or_null(path) as Node3D
	if player == null or target == null:
		return false
	return _resolved_position(player).distance_to(_resolved_position(target)) <= distance

func _resolved_position(node: Node3D) -> Vector3:
	if node.is_inside_tree():
		return node.global_position
	var resolved_transform := node.transform
	var parent := node.get_parent()
	while parent is Node3D:
		resolved_transform = (parent as Node3D).transform * resolved_transform
		parent = parent.get_parent()
	return resolved_transform.origin

func _update_ui() -> void:
	_refresh_ui_refs()
	_apply_readable_text_style()
	if total_targets == 0:
		total_targets = game1_rules.required_lawn_count()
	if _time_label != null:
		_time_label.text = "时间：%s" % _formatted_game1_time()
	if _weather_label != null:
		_weather_label.text = "天气：%s" % _display_weather(game1_rules.current_weather())
	if _canopy_label != null:
		_canopy_label.text = "警报：%s" % ("已按下" if game1_rules.alarm_pressed else "等待中")
	if _status_label != null:
		if has_can:
			_status_label.text = "水壶：%s" % ("满水" if has_water else "空")
		else:
			_status_label.text = "水壶：未拿起"
	if _task_label != null:
		if game1_rules.day_failed:
			_task_label.text = "任务失败：%s" % game1_rules.failure_reason
		elif game1_rules.is_complete():
			_task_label.text = "任务成功：浇水和下雨警报都完成了。"
		elif game1_rules.rain_active and not game1_rules.alarm_pressed:
			_task_label.text = RAIN_TASK_TEXT
		else:
			_task_label.text = WATERING_TASK_TEXT
	if _hint_label != null:
		_hint_label.text = "F：拿水壶 / 浇草坪 / 按下雨警报"
	if _message_label != null:
		_message_label.text = _rule_summary_text() if not game1_rules.day_failed and not game1_rules.is_complete() else last_message
	_update_action_prompt()

func _update_action_prompt() -> void:
	_refresh_ui_refs()
	if _action_prompt_label == null:
		return
	if _nearest_alarm_button() != null:
		_action_prompt_label.text = "F  按门铃"
	elif not has_can:
		_action_prompt_label.text = "F  拿水壶" if _nearest_available_can() != null else ""
	elif game1_rules.is_complete():
		_action_prompt_label.text = "任务成功"
	elif _nearest_target_path().is_empty():
		_action_prompt_label.text = ""
	elif has_water:
		_action_prompt_label.text = "F  浇草坪"
	else:
		_action_prompt_label.text = "去拿另一个满水壶"

func _refresh_ui_refs() -> void:
	if _status_label == null:
		_status_label = get_node_or_null("GardenUI/Panel/Margin/Rows/StatusLabel")
	if _time_label == null:
		_time_label = get_node_or_null("GardenUI/Panel/Margin/Rows/TimeLabel")
	if _weather_label == null:
		_weather_label = get_node_or_null("GardenUI/Panel/Margin/Rows/WeatherLabel")
	if _canopy_label == null:
		_canopy_label = get_node_or_null("GardenUI/Panel/Margin/Rows/CanopyLabel")
	if _task_label == null:
		_task_label = get_node_or_null("GardenUI/Panel/Margin/Rows/TaskLabel")
	if _hint_label == null:
		_hint_label = get_node_or_null("GardenUI/Panel/Margin/Rows/HintLabel")
	if _message_label == null:
		_message_label = get_node_or_null("GardenUI/Panel/Margin/Rows/MessageLabel")
	if _action_prompt_label == null:
		_action_prompt_label = get_node_or_null("GardenUI/ActionPrompt")

func _advance_game1_time() -> void:
	if game1_rules.day_failed or game1_rules.is_complete():
		return
	var now := Time.get_ticks_msec()
	if _last_real_time_update_msec == 0:
		_last_real_time_update_msec = now
		return
	var delta_seconds := float(now - _last_real_time_update_msec) / 1000.0
	_last_real_time_update_msec = now
	if delta_seconds <= 0.0:
		return
	var previous_minute := game1_rules.minutes_since_midnight
	var was_raining := game1_rules.rain_active
	var had_failed := game1_rules.day_failed
	var scale := float(GardenGame1Rules.END_MINUTE - GardenGame1Rules.START_MINUTE) / real_day_seconds
	_game1_time_float = minf(float(GardenGame1Rules.END_MINUTE), _game1_time_float + delta_seconds * scale)
	game1_rules.advance_to_minutes(floori(_game1_time_float))
	if game1_rules.day_failed:
		last_message = game1_rules.failure_reason
	if game1_rules.minutes_since_midnight != previous_minute or game1_rules.rain_active != was_raining or game1_rules.day_failed != had_failed:
		_update_ui()

func _setup_rain_visuals() -> void:
	if _rain_root != null:
		return
	_rain_rng.seed = 829
	_rain_root = Node3D.new()
	_rain_root.name = "RainVisuals"
	add_child(_rain_root)

	var drop_mesh := BoxMesh.new()
	drop_mesh.size = Vector3(0.025, 0.95, 0.025)

	var drop_material := StandardMaterial3D.new()
	drop_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	drop_material.albedo_color = Color(0.58, 0.78, 1.0, 0.58)
	drop_material.emission_enabled = true
	drop_material.emission = Color(0.12, 0.28, 0.48, 1.0)
	drop_material.emission_energy_multiplier = 0.35

	for index in range(rain_drop_count):
		var drop := MeshInstance3D.new()
		drop.name = "RainDrop%d" % index
		drop.mesh = drop_mesh
		drop.set_surface_override_material(0, drop_material)
		drop.position = _random_rain_position()
		_rain_root.add_child(drop)
		_rain_drops.append(drop)
		_rain_speeds.append(_rain_rng.randf_range(11.0, 17.0))

func _update_rain_visuals(delta: float) -> void:
	_apply_weather_lighting()
	if _rain_root == null:
		return
	var raining := game1_rules.rain_active
	_rain_root.visible = raining
	if not raining:
		return
	var player := get_node_or_null(player_path) as Node3D
	if player != null:
		var player_position := _resolved_position(player)
		var rain_position := Vector3(player_position.x, player_position.y + rain_spawn_height, player_position.z)
		if _rain_root.is_inside_tree():
			_rain_root.global_position = rain_position
		else:
			_rain_root.position = rain_position
	for index in range(_rain_drops.size()):
		var drop := _rain_drops[index]
		if drop == null:
			continue
		drop.position.y -= _rain_speeds[index] * delta
		if drop.position.y < -rain_fall_distance:
			drop.position = _random_rain_position()

func _apply_weather_lighting() -> void:
	var sun := get_node_or_null("Sun") as DirectionalLight3D
	var world_environment := get_node_or_null("WorldEnvironment") as WorldEnvironment
	if game1_rules.rain_active:
		if sun != null:
			sun.light_energy = 0.65
			sun.light_color = Color(0.68, 0.78, 0.9, 1.0)
		if world_environment != null and world_environment.environment != null:
			world_environment.environment.background_energy_multiplier = 0.42
			world_environment.environment.ambient_light_energy = 0.36
			world_environment.environment.ambient_light_sky_contribution = 0.12
	else:
		if sun != null:
			sun.light_energy = 2.25
			sun.light_color = Color(1.0, 0.92, 0.78, 1.0)
		if world_environment != null and world_environment.environment != null:
			world_environment.environment.background_energy_multiplier = 0.95
			world_environment.environment.ambient_light_energy = 0.72
			world_environment.environment.ambient_light_sky_contribution = 0.35

func _random_rain_position() -> Vector3:
	return Vector3(
		_rain_rng.randf_range(-rain_area_size.x * 0.5, rain_area_size.x * 0.5),
		_rain_rng.randf_range(-rain_fall_distance, 0.0),
		_rain_rng.randf_range(-rain_area_size.y * 0.5, rain_area_size.y * 0.5)
	)

func _apply_game1_assignments() -> void:
	_set_house_label(1, "房屋一")
	_set_house_label(2, "房屋二")
	_set_house_label(3, "房屋三")
	for house_number in range(1, 4):
		var label := get_node_or_null(_flower_label_path_for_house(house_number)) as Label3D
		if label != null:
			label.text = _flower_name_for_house(house_number)
			_style_label3d(label, 64)
	_update_alarm_visuals()

func _set_house_label(house_number: int, text: String) -> void:
	var label := get_node_or_null(_house_label_path(house_number)) as Label3D
	if label != null:
		label.text = text
		_style_label3d(label, 96)

func _update_alarm_visuals() -> void:
	for house_number in range(1, 4):
		var switch := get_node_or_null(_canopy_switch_path_for_house(house_number)) as Node3D
		if switch != null:
			switch.visible = true
			_set_doorbell_label(switch)
		var canopy := get_node_or_null(_canopy_roof_path_for_house(house_number)) as Node3D
		if canopy != null:
			canopy.visible = false

func _set_doorbell_label(switch: Node3D) -> void:
	var label := switch.get_node_or_null("DoorbellLabel") as Label3D
	if label == null:
		label = Label3D.new()
		label.name = "DoorbellLabel"
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.position = Vector3(0.0, 1.05, 0.0)
		switch.add_child(label)
	label.text = "门铃"
	_style_label3d(label, 44)

func _apply_readable_text_style() -> void:
	for path in [
		NodePath("NeighborhoodPlaza/TapLabel"),
		NodePath("Houses/House1_Sunflowers/Garden/EntranceLabel"),
		NodePath("Houses/House2_Hydrangeas/HydrangeaGarden/EntranceLabel"),
		NodePath("Houses/House3_Orchids/OutdoorOrchids/EntranceLabel"),
	]:
		var label := get_node_or_null(path) as Label3D
		if label != null:
			_style_label3d(label, 48)
	_style_ui_label(_action_prompt_label)
	_style_ui_label(_time_label)
	_style_ui_label(_weather_label)
	_style_ui_label(_canopy_label)
	_style_ui_label(_status_label)
	_style_ui_label(_task_label)
	_style_ui_label(_hint_label)
	_style_ui_label(_message_label)

func _style_label3d(label: Label3D, font_size: int) -> void:
	label.font_size = font_size
	label.modulate = Color.WHITE
	label.outline_modulate = Color(0.0, 0.0, 0.0, 0.86)
	label.outline_size = max(8, roundi(float(font_size) * 0.2))

func _style_ui_label(label: Label) -> void:
	if label != null:
		label.modulate = Color.WHITE
		label.add_theme_color_override("font_color", Color.WHITE)
		label.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 0.92))
		label.add_theme_constant_override("outline_size", 4)
		if label == _task_label or label == _message_label:
			label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		if label == _task_label:
			label.add_theme_font_size_override("font_size", 18)

func _nearest_alarm_button() -> Node3D:
	var player := get_node_or_null(player_path) as Node3D
	if player == null:
		return null
	var nearest: Node3D
	var nearest_distance := INF
	for house_number in range(1, 4):
		var switch := get_node_or_null(_canopy_switch_path_for_house(house_number)) as Node3D
		if switch == null or not switch.visible:
			continue
		var distance := _resolved_position(player).distance_to(_resolved_position(switch))
		if distance <= alarm_distance and distance < nearest_distance:
			nearest = switch
			nearest_distance = distance
	return nearest

func _house_number_for_target_path(path: NodePath) -> int:
	var value := str(path)
	if value.begins_with("Houses/House1_"):
		return 1
	if value.begins_with("Houses/House2_"):
		return 2
	if value.begins_with("Houses/House3_"):
		return 3
	return 0

func _lawn_number_for_target_path(path: NodePath) -> int:
	var value := str(path)
	if value.ends_with("/LeftRaisedLawn"):
		return 1
	if value.ends_with("/RightFlowerBed"):
		return 2
	return 0

func _lawn_can_be_watered(house_number: int, lawn_number: int) -> bool:
	return house_number >= 1 \
		and house_number <= 3 \
		and lawn_number >= 1 \
		and lawn_number <= GardenGame1Rules.LAWN_COUNT_PER_GARDEN

func _house_number_for_canopy_switch(node: Node) -> int:
	for house_number in range(1, 4):
		if get_node_or_null(_canopy_switch_path_for_house(house_number)) == node:
			return house_number
	return 0

func _primary_target_path_for_house(house_number: int) -> NodePath:
	match house_number:
		1:
			return NodePath("Houses/House1_Sunflowers/Garden/SunflowerA")
		2:
			return NodePath("Houses/House2_Hydrangeas/HydrangeaGarden/HydrangeaAssets/PlantModelA")
		3:
			return NodePath("Houses/House3_Orchids/OutdoorOrchids/OrchidPotA")
	return NodePath("")

func _flower_label_path_for_house(house_number: int) -> NodePath:
	match house_number:
		1:
			return NodePath("Houses/House1_Sunflowers/Garden/FlowerLabel")
		2:
			return NodePath("Houses/House2_Hydrangeas/HydrangeaGarden/FlowerLabel")
		3:
			return NodePath("Houses/House3_Orchids/OutdoorOrchids/FlowerLabel")
	return NodePath("")

func _house_label_path(house_number: int) -> NodePath:
	match house_number:
		1:
			return NodePath("Houses/House1_Sunflowers/Label")
		2:
			return NodePath("Houses/House2_Hydrangeas/Label")
		3:
			return NodePath("Houses/House3_Orchids/Label")
	return NodePath("")

func _canopy_switch_path_for_house(house_number: int) -> NodePath:
	match house_number:
		1:
			return NodePath("Houses/House1_Sunflowers/Garden/CanopySwitch")
		2:
			return NodePath("Houses/House2_Hydrangeas/HydrangeaGarden/CanopySwitch")
		3:
			return NodePath("Houses/House3_Orchids/OutdoorOrchids/CanopySwitch")
	return NodePath("")

func _canopy_roof_path_for_house(house_number: int) -> NodePath:
	match house_number:
		1:
			return NodePath("Houses/House1_Sunflowers/Garden/OrchidCanopy")
		2:
			return NodePath("Houses/House2_Hydrangeas/HydrangeaGarden/OrchidCanopy")
		3:
			return NodePath("Houses/House3_Orchids/OutdoorOrchids/OrchidCanopy")
	return NodePath("")

func _formatted_game1_time() -> String:
	var total := clampi(game1_rules.minutes_since_midnight, GardenGame1Rules.START_MINUTE, GardenGame1Rules.END_MINUTE)
	return "%02d:%02d" % [total / 60, total % 60]

func _display_weather(value: String) -> String:
	match value:
		"rain":
			return "下雨"
		"cloudy":
			return "阴天"
	return "晴天"

func _display_next_weather() -> String:
	return ""

func _display_flower(flower: String) -> String:
	match flower:
		"sunflower":
			return "向日葵"
		"hydrangea":
			return "绣球花"
		"orchid":
			return "兰花"
	return "未知"

func _display_flower_for_house(house_number: int) -> String:
	return "浇水花园" if game1_rules.watering_house_numbers.has(house_number) else "下雨警报花园"

func _invalid_watering_message(house_number: int) -> String:
	if game1_rules.watering_house_numbers.has(house_number):
		return "这块草坪已经浇过水。"
	return "这块草坪已经浇过水。"

func _current_objective_text() -> String:
	if game1_rules.rain_active and not game1_rules.alarm_pressed:
		return RAIN_TASK_TEXT
	return WATERING_TASK_TEXT

func _rule_summary_text() -> String:
	return TASK_RULE_SUMMARY

func _house_display_name(house_number: int) -> String:
	match house_number:
		1:
			return "房屋一"
		2:
			return "房屋二"
		3:
			return "房屋三"
	return "未知房屋"

func _flower_name_for_house(house_number: int) -> String:
	match house_number:
		1:
			return "向日葵"
		2:
			return "绣球花"
		3:
			return "兰花"
	return "未知花卉"
