class_name LoopStaircaseManager
extends Node3D

signal game_finished(outcome: String, reason: String)

const SCENARIO_ID: String = "loop_staircase_anomaly"
const FLOOR_MIN: int = 2
const FLOOR_MAX: int = 9
const TOTAL_LOOPS: int = 5
const CLUE_CANDIDATE_COUNTS: Array[int] = [6, 4, 3, 2, 1]
const TWO_BOX_CANDIDATE_COUNT: int = 4
const STABLE_ROOM_NUMBER_COUNT: int = 3
const STABLE_FURNITURE_COUNT: int = 3
const LAMP_COLORS: Array[String] = ["red", "blue", "green", "yellow", "white", "purple"]
const SYMBOLS: Array[String] = ["circle", "triangle", "square", "star"]
const ANOMALY_TYPES: Array[String] = [
	"lamp_color",
	"symbol",
]
const DISTRACTOR_FIELDS: Array[String] = ["chair_count", "computer_count", "book_count"]
const LOBBY_FLOOR_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/floor_3x_3_00.tscn"
const LOBBY_STAIR_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/ksi_steps_single.tscn"
const LOBBY_BOX_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/cardboard_box_closed.tscn"
const LOBBY_OPEN_BOX_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/cardboard_box_open.tscn"
const LOBBY_PLANT_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/potted_plant.tscn"
const LOBBY_LAMP_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/lamp_round_floor.tscn"
const LOBBY_SOFA_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/lounge_sofa_corner.tscn"
const LOBBY_TABLE_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/table_coffee_glass.tscn"
const LOBBY_MUG_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/coffee_mug.tscn"
const LOBBY_BOOKS_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/books.tscn"
const LOBBY_CHAIR_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/chair_desk.tscn"
const LOBBY_CUSHION_CHAIR_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/chair_cushion.tscn"
const LOBBY_DESK_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/desk.tscn"
const LOBBY_LAPTOP_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/laptop_real.tscn"
const LOBBY_COMPUTER_SCREEN_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/computer_screen.tscn"
const LOBBY_COMPUTER_KEYBOARD_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/computer_keyboard.tscn"
const LOBBY_COMPUTER_MOUSE_SCENE: String = "res://addons/cogito/DemoScenes/DemoPrefabs/computer_mouse.tscn"
const NAVIGATION_SCRIPT: String = "res://addons/cogito/DemoScenes/LoopStaircase/loop_staircase_navigation.gd"
const BASIC_INTERACTION_SCENE: String = "res://addons/cogito/Components/Interactions/BasicInteraction.tscn"
const CASE_SCRIPT: Script = preload(
	"res://addons/cogito/DemoScenes/LoopStaircase/loop_staircase_case.gd"
)

@export var scenario_id: String = SCENARIO_ID
@export var round_seed: int = 0
@export var build_scene_on_ready: bool = false
@export var player: Node3D
@export var game_over_screen: Node

var current_loop: int = 0
var _rng := RandomNumberGenerator.new()
var _round_finished: bool = false
var _true_floor: int = FLOOR_MIN
var _current_floor: int = FLOOR_MIN
var _exit_symbol: String = SYMBOLS[0]
var _base_floors: Dictionary = {}
var _loop_states: Array[Dictionary] = []
var _clue_floors: Array[int] = []
var _round_clues: Array[Dictionary] = []
var _two_box_candidate_floors: Array[int] = []
var _stable_room_number_floors: Array[int] = []
var _stable_furniture_floors: Array[int] = []
var _scene_player_spawn_transform := Transform3D.IDENTITY
var _has_scene_player_spawn_transform: bool = false
var _case: RefCounted
var _observed_by_round: Array[Dictionary] = []
var _manual_candidates: Dictionary = {}


func _ready() -> void:
	_capture_scene_player_spawn_transform()
	if _base_floors.is_empty():
		configure_round(round_seed)
	if build_scene_on_ready:
		build_scene()


func configure_round(seed_value: int = 0) -> void:
	_case = CASE_SCRIPT.generate(seed_value)
	current_loop = 0
	_current_floor = FLOOR_MIN
	_round_finished = false
	_true_floor = int(_case.get("true_floor"))
	_observed_by_round.clear()
	for round_index: int in range(TOTAL_LOOPS):
		_observed_by_round.append({})
	_manual_candidates.clear()


func advance_loop() -> void:
	if current_loop < TOTAL_LOOPS - 1:
		current_loop += 1
	_update_floor_displays()
	_update_answer_visibility()


func advance_loop_and_reset_player(body: Node3D) -> void:
	advance_loop()
	reset_player_to_spawn(body)


func reset_player_to_spawn(body: Node3D = null) -> void:
	if body == null:
		body = player
	var spawn: Node3D = get_node_or_null("SpawnPoint")
	if spawn != null and body != null:
		body.global_transform = spawn.global_transform


func is_final_unlocked() -> bool:
	return current_loop >= TOTAL_LOOPS - 1


func get_current_floor() -> int:
	return _current_floor


func set_current_floor(floor_number: int) -> void:
	_current_floor = clamp(floor_number, FLOOR_MIN, FLOOR_MAX)
	_update_floor_displays()


func move_up() -> void:
	if _round_finished:
		return
	if _current_floor >= FLOOR_MAX:
		if not get_missing_floor_labels().is_empty():
			_update_floor_displays()
			return
		if current_loop < TOTAL_LOOPS - 1:
			_current_floor = FLOOR_MIN
			advance_loop()
	else:
		_current_floor += 1
		_update_floor_displays()


func move_down() -> void:
	if _round_finished:
		return
	if _current_floor <= FLOOR_MIN:
		_current_floor = FLOOR_MAX
	else:
		_current_floor -= 1
	_update_floor_displays()


func submit_current_floor() -> void:
	if is_final_unlocked():
		select_floor(_current_floor)


func select_floor(floor_number: int) -> void:
	if _round_finished or not is_final_unlocked():
		return
	_round_finished = true
	if floor_number == _true_floor:
		game_finished.emit("success", "correct_floor_selected")
	else:
		game_finished.emit("failure", "wrong_floor_selected")


func get_floor_state(floor_number: int, loop_index: int = current_loop) -> Dictionary:
	if _case == null or floor_number < FLOOR_MIN or floor_number > FLOOR_MAX:
		return {}
	return _case.visible_state(floor_number, loop_index)


func _apply_anomaly(state: Dictionary, anomaly_type: String) -> void:
	match anomaly_type:
		"lamp_color":
			state["lamp_color"] = _next_lamp_color(state["lamp_color"])
			state["lamp_changed"] = true
		"floor_sign":
			state["floor_sign"] = _shift_floor_sign(state["floor_sign"])
			state["sign_duplicated"] = true
		"symbol":
			state["symbol"] = _next_symbol(state["symbol"])
			state["symbol_changed"] = true
		"furniture":
			state["chair_count"] = _next_count(state["chair_count"], 1, 3)
			state["chair_count_changed"] = true
			state["computer_count"] = _next_count(state["computer_count"], 0, 2)
			state["computer_count_changed"] = true
			state["book_count"] = _next_count(state["book_count"], 1, 4)
			state["book_count_changed"] = true
			state["layout_variant"] = (int(state["layout_variant"]) + 1) % (FLOOR_MAX - FLOOR_MIN + 1)


func get_round_snapshot() -> Dictionary:
	var snapshot: Dictionary = _case.test_snapshot()
	snapshot["scenario_id"] = scenario_id
	snapshot["current_loop"] = current_loop
	snapshot["total_loops"] = TOTAL_LOOPS
	snapshot["observed_by_round"] = _observed_by_round.duplicate(true)
	snapshot["manual_candidates"] = _manual_candidates.duplicate(true)
	return snapshot


func ai_play_public_state() -> Dictionary:
	return {
		"objective": "寻找真正的出口楼层 / Find the true exit floor.",
		"current_floor": _current_floor,
		"current_floor_label": "%dF" % _current_floor,
		"current_loop": current_loop + 1,
		"total_loops": TOTAL_LOOPS,
		"final_unlocked": is_final_unlocked(),
		"completed": _round_finished,
		"failed": false,
	}


func get_current_clue_text() -> String:
	if _case == null:
		return ""
	var visible: Array[String] = _case.visible_clues(current_loop)
	return visible[-1] if not visible.is_empty() else ""


func get_visible_clue_lines() -> Array[String]:
	var result: Array[String] = []
	if _case == null:
		return result
	var visible: Array[String] = _case.visible_clues(current_loop)
	for index: int in range(visible.size()):
		var label: String = "本轮线索" if index == current_loop else _round_label(index)
		result.append("%s：%s" % [label, visible[index]])
	return result


func get_missing_floor_labels() -> Array[String]:
	var result: Array[String] = []
	if _observed_by_round.is_empty():
		return result
	var observed: Dictionary = _observed_by_round[current_loop]
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		if not observed.has(floor_number):
			result.append("%dF" % floor_number)
	return result


func mark_floor_observed(floor_number: int) -> void:
	if floor_number < FLOOR_MIN or floor_number > FLOOR_MAX or _observed_by_round.is_empty():
		return
	_observed_by_round[current_loop][floor_number] = true


func toggle_candidate(floor_number: int) -> void:
	if floor_number < FLOOR_MIN or floor_number > FLOOR_MAX:
		return
	_manual_candidates[floor_number] = not _manual_candidates.get(floor_number, false)


func is_candidate_marked(floor_number: int) -> bool:
	return _manual_candidates.get(floor_number, false)


func _round_label(round_index: int) -> String:
	return ["第一轮线索", "第二轮线索", "第三轮线索", "第四轮线索", "第五轮线索"][round_index]


func build_scene() -> void:
	_capture_scene_player_spawn_transform()
	_clear_generated_scene()
	_create_spawn_point()
	_create_game_ui()
	_create_current_floor_room()
	_update_floor_displays()


func _capture_scene_player_spawn_transform() -> void:
	if _has_scene_player_spawn_transform or player == null:
		return
	_scene_player_spawn_transform = player.global_transform
	_has_scene_player_spawn_transform = true


func _unhandled_input(event: InputEvent) -> void:
	if _round_finished:
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_UP or event.physical_keycode == KEY_UP:
			move_up()
		elif event.keycode == KEY_DOWN or event.physical_keycode == KEY_DOWN:
			move_down()
		elif event.keycode == KEY_SPACE or event.physical_keycode == KEY_SPACE:
			submit_current_floor()


func show_result(outcome: String, reason: String) -> void:
	if game_over_screen != null and game_over_screen.has_method("show_result"):
		game_over_screen.show_result(outcome, reason)
		return
	var status := get_node_or_null("GameUI/StatusPanel/Status") as Label
	if status != null:
		status.text = "%s: %s" % [outcome, reason]
		var status_panel := get_node_or_null("GameUI/StatusPanel") as Control
		if status_panel != null:
			status_panel.visible = true
	var result_label := get_node_or_null("ResultLabel") as Label3D
	if result_label == null:
		result_label = get_node_or_null("CurrentFloorRoom/ResultLabel") as Label3D
	if result_label == null:
		return
	result_label.text = "%s: %s" % [outcome, reason]
	result_label.visible = true


func _generate_base_floors() -> void:
	_base_floors.clear()
	var layout_offset: int = _rng.randi_range(0, FLOOR_MAX - FLOOR_MIN)
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		var has_two_boxes: bool = floor_number in _two_box_candidate_floors
		_base_floors[floor_number] = {
			"floor": floor_number,
			"floor_sign": floor_number,
			"lamp_color": LAMP_COLORS[_rng.randi_range(0, LAMP_COLORS.size() - 1)],
			"box_count": 2 if has_two_boxes else _non_candidate_box_count(),
			"chair_count": _rng.randi_range(1, 3),
			"computer_count": _rng.randi_range(0, 2),
			"book_count": _rng.randi_range(1, 4),
			"layout_variant": (floor_number - FLOOR_MIN + layout_offset) % (FLOOR_MAX - FLOOR_MIN + 1),
			"symbol": SYMBOLS[_rng.randi_range(0, SYMBOLS.size() - 1)],
			"has_clue": floor_number in _clue_floors,
			"clue_text": _clue_text_for_floor(floor_number),
			"lamp_changed": false,
			"box_count_changed": false,
			"chair_count_changed": false,
			"computer_count_changed": false,
			"book_count_changed": false,
			"sign_duplicated": false,
			"symbol_changed": false,
		}
	_base_floors[_true_floor]["symbol"] = _exit_symbol
	_base_floors[_true_floor]["box_count"] = 2
	_base_floors[_true_floor]["chair_count"] = 2
	_base_floors[_true_floor]["computer_count"] = 1
	_base_floors[_true_floor]["book_count"] = 2


func _generate_loop_states() -> void:
	_loop_states = []
	var wall_changed_second_loop: Array[int] = _pick_wall_changed_floors()
	for loop_index: int in range(TOTAL_LOOPS):
		var anomalies: Dictionary = {}
		if loop_index > 0:
			for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
				if floor_number == _true_floor:
					continue
				if not floor_number in _stable_room_number_floors:
					_add_anomaly(anomalies, floor_number, "floor_sign")
				if not floor_number in _stable_furniture_floors:
					_add_anomaly(anomalies, floor_number, "furniture")
			for floor_number: int in wall_changed_second_loop:
				_add_anomaly(anomalies, floor_number, _random_wall_anomaly_type(floor_number))
			if loop_index == TOTAL_LOOPS - 1:
				for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
					if floor_number == _true_floor:
						continue
					if not floor_number in wall_changed_second_loop and _rng.randi_range(0, 1) == 0:
						_add_anomaly(anomalies, floor_number, _random_wall_anomaly_type(floor_number))
		_loop_states.append({
			"loop": loop_index,
			"anomalies": anomalies,
			"anomaly_floors": anomalies.keys(),
		})


func _clear_generated_scene() -> void:
	for child_name: String in [
		"SpawnPoint",
		"Floors",
		"AnswerChoices",
		"LoopTrigger",
		"ResultLabel",
		"StartHint",
		"Camera3D",
		"Tower",
		"CurrentFloorRoom",
		"GameUI",
	]:
		var child: Node = get_node_or_null(child_name)
		if child != null:
			remove_child(child)
			child.free()


func _create_static_camera() -> void:
	var camera := Camera3D.new()
	camera.name = "Camera3D"
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 7.2
	camera.current = true
	camera.position = Vector3(0, 4.2, 7.8)
	camera.rotation_degrees = Vector3(-26, 0, 0)
	add_child(camera)


func _create_current_floor_room() -> void:
	var existing: Node = get_node_or_null("CurrentFloorRoom")
	if existing != null:
		remove_child(existing)
		existing.free()
	var state: Dictionary = get_floor_state(_current_floor)
	var layout_variant: int = int(state.get("layout_variant", 0))
	var room := Node3D.new()
	room.name = "CurrentFloorRoom"
	add_child(room)

	_add_box_body(room, "LobbyFloor", Vector3(7.0, 0.16, 5.0), Vector3(0, -0.08, 0), Color(0.42, 0.34, 0.25))
	_add_wall_body(room, "BackWall", Vector3(7.0, 3.1, 0.18), Vector3(0, 1.45, -2.55))
	_add_wall_body(room, "LeftWall", Vector3(0.18, 3.1, 5.0), Vector3(-3.55, 1.45, 0))
	_add_wall_body(room, "RightWall", Vector3(0.18, 3.1, 5.0), Vector3(3.55, 1.45, 0))
	_add_box_body(room, "RightDoorFrame", Vector3(1.1, 2.1, 0.16), Vector3(2.35, 1.0, -2.45), Color(0.46, 0.31, 0.2))
	_add_wall_wash_light(room)

	_instance_optional_scene(room, LOBBY_SOFA_SCENE, "LobbySofa", _layout_position(layout_variant, "sofa"), Vector3(0, _layout_rotation_y(layout_variant, "sofa"), 0), Vector3(1.0, 1.0, 1.0))
	_instance_optional_scene(room, LOBBY_TABLE_SCENE, "CoffeeTable", _layout_position(layout_variant, "table"), Vector3(0, _layout_rotation_y(layout_variant, "table"), 0), Vector3(1.1, 1.1, 1.1))
	_instance_optional_scene(room, LOBBY_MUG_SCENE, "CoffeeMug", _mug_position(state), Vector3(0, 15, 0), Vector3(1.35, 1.35, 1.35))
	_freeze_rigid_body(room.get_node_or_null("CoffeeMug"))
	_instance_optional_scene(room, LOBBY_BOOKS_SCENE, "LobbyBooks", _layout_position(layout_variant, "display_books"), Vector3(0, _layout_rotation_y(layout_variant, "display_books"), 0), Vector3(0.75, 0.75, 0.75))
	_instance_optional_scene(room, LOBBY_PLANT_SCENE, "LobbyPlant", _layout_position(layout_variant, "plant"), Vector3(0, _layout_rotation_y(layout_variant, "plant"), 0), Vector3(0.85, 0.85, 0.85))
	_instance_optional_scene(room, LOBBY_LAMP_SCENE, "LobbyLamp", _layout_position(layout_variant, "floor_lamp"), Vector3.ZERO, Vector3(0.75, 0.75, 0.75))

	var lamp_indicator := MeshInstance3D.new()
	lamp_indicator.name = "LampIndicator"
	var sphere := SphereMesh.new()
	sphere.radius = 0.18
	sphere.height = 0.36
	lamp_indicator.mesh = sphere
	lamp_indicator.position = Vector3(-2.15, 1.45, -2.18)
	lamp_indicator.material_override = _material(_lamp_color(state.get("lamp_color", "white")))
	room.add_child(lamp_indicator)

	var boxes := Node3D.new()
	boxes.name = "Boxes"
	boxes.position = _layout_position(layout_variant, "boxes")
	room.add_child(boxes)

	var chairs := Node3D.new()
	chairs.name = "Chairs"
	room.add_child(chairs)

	var books := Node3D.new()
	books.name = "Books"
	room.add_child(books)

	var computer_set := Node3D.new()
	computer_set.name = "ComputerSet"
	computer_set.position = _layout_position(layout_variant, "computer")
	computer_set.rotation_degrees = Vector3(0, _layout_rotation_y(layout_variant, "computer"), 0)
	room.add_child(computer_set)

	var floor_sign := Label3D.new()
	floor_sign.name = "FloorSign"
	floor_sign.position = Vector3(1.8, 2.1, -2.34)
	floor_sign.pixel_size = 0.01
	floor_sign.font_size = 46
	floor_sign.modulate = Color.WHITE
	room.add_child(floor_sign)

	var symbol := Node3D.new()
	symbol.name = "WallSymbol"
	symbol.position = Vector3(-1.6, 2.05, -2.36)
	room.add_child(symbol)

	var clue := Label3D.new()
	clue.name = "Clue"
	clue.position = Vector3(0, 1.45, -2.34)
	clue.pixel_size = 0.006
	clue.font_size = 34
	clue.modulate = Color(0.95, 0.9, 0.72)
	clue.visible = false
	room.add_child(clue)

	var observation := Label3D.new()
	observation.name = "ObservationLabel"
	observation.position = Vector3(0, 1.05, -2.34)
	observation.pixel_size = 0.0055
	observation.font_size = 28
	observation.modulate = Color(0.78, 0.92, 1.0)
	room.add_child(observation)

	var result_label := Label3D.new()
	result_label.name = "ResultLabel"
	result_label.position = Vector3(0, 0.7, -2.34)
	result_label.pixel_size = 0.007
	result_label.font_size = 30
	result_label.modulate = Color(1.0, 0.9, 0.55)
	result_label.visible = false
	room.add_child(result_label)

	var stairs := Node3D.new()
	stairs.name = "StairButtonsPreview"
	stairs.position = Vector3(3.15, 0.02, -0.55)
	room.add_child(stairs)
	_add_room_stair_preview(stairs)

	_add_navigation_marker(
		room,
		"UpStairsTrigger",
		"up",
		Vector3(2.85, 0.55, -0.9),
		"Go Up",
		"UP",
		Color(0.18, 0.48, 0.85),
	)
	_add_navigation_marker(
		room,
		"DownStairsTrigger",
		"down",
		Vector3(2.85, 0.55, 1.1),
		"Go Down",
		"DOWN",
		Color(0.26, 0.55, 0.32),
	)
	_add_navigation_marker(
		room,
		"AnswerCurrentFloor",
		"answer",
		Vector3(0, 0.75, 1.95),
		"Choose Current Floor",
		"CHOOSE",
		Color(0.7, 0.46, 0.16),
	)
	var answer := room.get_node("AnswerCurrentFloor") as Area3D
	answer.visible = is_final_unlocked()
	answer.monitoring = is_final_unlocked()
	answer.collision_layer = 2 if is_final_unlocked() else 0


func _create_game_ui() -> void:
	var ui := CanvasLayer.new()
	ui.name = "GameUI"
	add_child(ui)

	var panel := PanelContainer.new()
	panel.name = "RulesPanel"
	panel.offset_left = 18.0
	panel.offset_top = 18.0
	panel.custom_minimum_size = Vector2(390, 0)
	ui.add_child(panel)

	var margin := MarginContainer.new()
	margin.name = "RulesMargin"
	margin.add_theme_constant_override("margin_left", 12)
	margin.add_theme_constant_override("margin_top", 10)
	margin.add_theme_constant_override("margin_right", 12)
	margin.add_theme_constant_override("margin_bottom", 10)
	panel.add_child(margin)

	var rules := Label.new()
	rules.name = "Rules"
	rules.text = "循环楼梯任务 / LOOPING STAIRCASE\n寻找真正的出口楼层 / FIND THE TRUE EXIT FLOOR\n\n每一轮只有一条新线索。\n每次开局的线索顺序都会变化。\n线索只说明一种观察依据，不直接给楼层号。\n自己记录每层变化，不能反悔。\n\n观察五轮后，按空格选择。\n上/下：切换楼层"
	rules.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	rules.add_theme_font_size_override("font_size", 19)
	margin.add_child(rules)

	var status_panel := PanelContainer.new()
	status_panel.name = "StatusPanel"
	status_panel.offset_left = 18.0
	status_panel.offset_top = 300.0
	status_panel.custom_minimum_size = Vector2(390, 0)
	status_panel.visible = false
	ui.add_child(status_panel)

	var status_margin := MarginContainer.new()
	status_margin.name = "StatusMargin"
	status_margin.add_theme_constant_override("margin_left", 12)
	status_margin.add_theme_constant_override("margin_top", 8)
	status_margin.add_theme_constant_override("margin_right", 12)
	status_margin.add_theme_constant_override("margin_bottom", 8)
	status_panel.add_child(status_margin)

	var status := Label.new()
	status.name = "Status"
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status.add_theme_font_size_override("font_size", 15)
	status_margin.add_child(status)


func _mug_position(state: Dictionary) -> Vector3:
	var symbol: String = state.get("symbol", "circle")
	match symbol:
		"circle":
			return Vector3(-0.25, 0.62, 0.35)
		"triangle":
			return Vector3(0.2, 0.62, 0.2)
		"square":
			return Vector3(0.48, 0.62, 0.58)
		"star":
			return Vector3(-0.52, 0.62, 0.72)
	return Vector3(0.0, 0.62, 0.45)


func _freeze_rigid_body(node: Node) -> void:
	if node is RigidBody3D:
		var rigid := node as RigidBody3D
		rigid.freeze = true
		rigid.collision_layer = 0


func _add_room_stair_preview(parent: Node3D) -> void:
	var stair_scene: PackedScene = load(LOBBY_STAIR_SCENE)
	for step: int in range(5):
		var stair: Node3D
		if stair_scene != null:
			stair = stair_scene.instantiate()
			stair.name = "VisibleStep_%d" % (step + 1)
			stair.scale = Vector3(0.9, 0.28, 0.55)
		else:
			stair = MeshInstance3D.new()
			var mesh := BoxMesh.new()
			mesh.size = Vector3(1.1, 0.14, 0.42)
			stair.mesh = mesh
		stair.position = Vector3(0, step * 0.18, step * -0.48)
		stair.rotation_degrees = Vector3(0, -18, 0)
		parent.add_child(stair)


func _add_navigation_marker(
	parent: Node3D,
	node_name: String,
	action: String,
	position: Vector3,
	prompt: String,
	label_text: String,
	color: Color,
) -> void:
	var area := Area3D.new()
	area.name = node_name
	area.script = load(NAVIGATION_SCRIPT)
	area.set("action", action)
	area.position = position
	parent.add_child(area)
	area.set("manager_path", area.get_path_to(self))

	var shape := BoxShape3D.new()
	shape.size = Vector3(1.0, 1.1, 0.6)
	var collision := CollisionShape3D.new()
	collision.shape = shape
	area.add_child(collision)

	var mesh := MeshInstance3D.new()
	mesh.name = "MarkerMesh"
	var box := BoxMesh.new()
	box.size = Vector3(1.0, 0.75, 0.1)
	mesh.mesh = box
	mesh.position = Vector3(0, 0.12, 0)
	mesh.material_override = _material(color)
	mesh.visible = action == "answer"
	area.add_child(mesh)

	var label := Label3D.new()
	label.name = "Label"
	label.text = label_text
	label.position = Vector3(0, 0.16, 0.08)
	label.rotation_degrees = Vector3(0, 180, 0)
	label.pixel_size = 0.01
	label.font_size = 46
	label.modulate = Color.WHITE
	label.visible = action == "answer"
	area.add_child(label)

	var interaction: Node = load(BASIC_INTERACTION_SCENE).instantiate()
	interaction.name = "BasicInteraction"
	interaction.set("interaction_text", prompt)
	interaction.set("input_map_action", "interact")
	area.add_child(interaction)


func _add_wall_wash_light(parent: Node3D) -> void:
	var light := SpotLight3D.new()
	light.name = "WallWashLight"
	light.position = Vector3(0.0, 2.25, 1.65)
	light.rotation_degrees = Vector3(0, 0, 0)
	light.light_energy = 7.0
	light.spot_range = 7.0
	light.spot_angle = 52.0
	light.shadow_enabled = false
	parent.add_child(light)


func _create_tower_scene() -> void:
	var tower := Node3D.new()
	tower.name = "Tower"
	add_child(tower)
	var pillar := MeshInstance3D.new()
	pillar.name = "CenterPillar"
	var pillar_mesh := CylinderMesh.new()
	pillar_mesh.top_radius = 0.58
	pillar_mesh.bottom_radius = 0.58
	pillar_mesh.height = 18.0
	pillar.mesh = pillar_mesh
	pillar.position = Vector3(0, 7.2, 0)
	pillar.material_override = _material(Color(0.78, 0.47, 0.2))
	tower.add_child(pillar)
	for index: int in range(FLOOR_MAX - FLOOR_MIN + 1):
		var floor_number: int = FLOOR_MIN + index
		var floor_node := Node3D.new()
		floor_node.name = "Platform_%d" % floor_number
		floor_node.position = Vector3(0, index * 1.7, 0)
		tower.add_child(floor_node)
		_build_visual_platform(floor_node, floor_number)


func _build_visual_platform(parent: Node3D, floor_number: int) -> void:
	var deck := MeshInstance3D.new()
	deck.name = "RoundFloor"
	var deck_mesh := CylinderMesh.new()
	deck_mesh.top_radius = 4.5
	deck_mesh.bottom_radius = 4.5
	deck_mesh.height = 0.16
	deck.mesh = deck_mesh
	deck.position = Vector3(0, 0, 0)
	deck.material_override = _material(Color(0.95, 0.91, 0.84))
	parent.add_child(deck)

	var wood := MeshInstance3D.new()
	wood.name = "WoodFloor"
	var wood_mesh := CylinderMesh.new()
	wood_mesh.top_radius = 4.25
	wood_mesh.bottom_radius = 4.25
	wood_mesh.height = 0.18
	wood.mesh = wood_mesh
	wood.position = Vector3(0, 0.08, 0)
	wood.material_override = _material(Color(0.64, 0.34, 0.13))
	parent.add_child(wood)

	var highlight := MeshInstance3D.new()
	highlight.name = "CurrentHighlight"
	var highlight_mesh := CylinderMesh.new()
	highlight_mesh.top_radius = 4.35
	highlight_mesh.bottom_radius = 4.35
	highlight_mesh.height = 0.04
	highlight.mesh = highlight_mesh
	highlight.position = Vector3(0, 0.2, 0)
	highlight.material_override = _material(Color(0.2, 0.85, 1.0))
	highlight.visible = false
	parent.add_child(highlight)

	_add_lobby_room(parent, floor_number)
	_add_spiral_stair(parent)
	_add_floor_props(parent)

	var sign := Label3D.new()
	sign.name = "FloorSign"
	sign.position = Vector3(-2.9, 1.25, 0.45)
	sign.pixel_size = 0.014
	sign.font_size = 78
	sign.modulate = Color.WHITE
	parent.add_child(sign)

	var symbol := Label3D.new()
	symbol.name = "Symbol"
	symbol.position = Vector3(-1.9, 1.25, 0.45)
	symbol.pixel_size = 0.014
	symbol.font_size = 64
	symbol.modulate = Color(1.0, 0.92, 0.58)
	parent.add_child(symbol)

	var label := Label3D.new()
	label.name = "ObservationLabel"
	label.position = Vector3(1.4, 1.25, 0.55)
	label.pixel_size = 0.009
	label.font_size = 42
	label.modulate = Color(0.8, 0.96, 1.0)
	parent.add_child(label)

	var clue := Label3D.new()
	clue.name = "Clue"
	clue.position = Vector3(-2.8, 0.82, -0.7)
	clue.pixel_size = 0.007
	clue.font_size = 44
	clue.modulate = Color(0.95, 0.9, 0.72)
	clue.visible = false
	parent.add_child(clue)

	var lamp := MeshInstance3D.new()
	lamp.name = "Lamp"
	var sphere := SphereMesh.new()
	sphere.radius = 0.18
	sphere.height = 0.36
	lamp.mesh = sphere
	lamp.position = Vector3(-1.65, 0.95, -1.2)
	parent.add_child(lamp)

	var boxes := Node3D.new()
	boxes.name = "Boxes"
	boxes.position = Vector3(2.0, 0.32, 1.1)
	parent.add_child(boxes)


func _add_lobby_room(parent: Node3D, floor_number: int) -> void:
	var room := Node3D.new()
	room.name = "LobbyRoom_%d" % floor_number
	room.position = Vector3(-3.0, 0.14, 0)
	parent.add_child(room)
	_add_box_body(room, "RoomWall", Vector3(1.6, 1.4, 1.5), Vector3(0, 0.7, 0), Color(0.92, 0.92, 0.9))
	_add_box_body(room, "Door", Vector3(0.55, 1.1, 0.08), Vector3(0.35, 0.58, 0.78), Color(0.5, 0.32, 0.2))
	var handle := MeshInstance3D.new()
	handle.name = "DoorHandle"
	var handle_mesh := SphereMesh.new()
	handle_mesh.radius = 0.06
	handle_mesh.height = 0.12
	handle.mesh = handle_mesh
	handle.position = Vector3(0.55, 0.55, 0.84)
	handle.material_override = _material(Color(0.95, 0.78, 0.35))
	room.add_child(handle)


func _add_spiral_stair(parent: Node3D) -> void:
	var stair_scene: PackedScene = load(LOBBY_STAIR_SCENE)
	for step: int in range(11):
		var angle: float = step * 0.38
		var stair: Node3D
		if stair_scene != null:
			stair = stair_scene.instantiate()
			stair.name = "LobbyStairPrefab_%02d" % step
			stair.scale = Vector3(1.15, 0.45, 0.62)
		else:
			stair = MeshInstance3D.new()
			var mesh := BoxMesh.new()
			mesh.size = Vector3(1.4, 0.12, 0.36)
			stair.mesh = mesh
		stair.position = Vector3(cos(angle) * 1.55, 0.14 + step * 0.12, sin(angle) * 1.55)
		stair.rotation_degrees = Vector3(0, rad_to_deg(-angle) + 90.0, 0)
		parent.add_child(stair)


func _add_floor_props(parent: Node3D) -> void:
	_instance_optional_scene(parent, LOBBY_PLANT_SCENE, "LobbyPlant", Vector3(2.9, 0.18, -0.9), Vector3(0, -35, 0), Vector3(0.75, 0.75, 0.75))
	_instance_optional_scene(parent, LOBBY_BOX_SCENE, "LobbyBox", Vector3(2.4, 0.18, 1.0), Vector3.ZERO, Vector3(0.8, 0.8, 0.8))
	_instance_optional_scene(parent, LOBBY_LAMP_SCENE, "LobbyLamp", Vector3(-1.6, 0.18, -1.2), Vector3.ZERO, Vector3(0.7, 0.7, 0.7))


func _instance_optional_scene(
	parent: Node3D,
	scene_path: String,
	node_name: String,
	position: Vector3,
	rotation_degrees: Vector3,
	scale: Vector3,
) -> Node3D:
	var packed: PackedScene = load(scene_path)
	if packed == null:
		return null
	var instance := packed.instantiate() as Node3D
	if instance == null:
		return null
	instance.name = node_name
	instance.position = position
	instance.rotation_degrees = rotation_degrees
	instance.scale = scale
	parent.add_child(instance)
	return instance


func _create_spawn_point() -> void:
	var spawn := Marker3D.new()
	spawn.name = "SpawnPoint"
	add_child(spawn)
	if _has_scene_player_spawn_transform:
		spawn.global_transform = _scene_player_spawn_transform
		if player != null:
			player.global_transform = spawn.global_transform
	elif player != null:
		spawn.global_transform = player.global_transform
		player.global_transform = spawn.global_transform
	else:
		spawn.position = Vector3(0, 1.4, 8.0)


func _create_floor_container() -> void:
	var floors := Node3D.new()
	floors.name = "Floors"
	add_child(floors)
	for index: int in range(FLOOR_MAX - FLOOR_MIN + 1):
		var floor_number: int = FLOOR_MIN + index
		var floor_node := Node3D.new()
		floor_node.name = "Floor_%d" % floor_number
		floor_node.position = Vector3(0, index * 3.0, index * 7.0)
		floors.add_child(floor_node)
		_build_floor_landing(floor_node, floor_number)
		if floor_number < FLOOR_MAX:
			_build_ramp(floor_node)
	_update_floor_displays()


func _build_floor_landing(parent: Node3D, floor_number: int) -> void:
	_add_lobby_floor_prefab(parent)
	_add_box_body(parent, "LandingCollision", Vector3(7.0, 0.25, 5.0), Vector3(0, -0.08, 0), Color(0.28, 0.3, 0.31), false)
	_add_box_body(parent, "BackWall", Vector3(7.0, 3.2, 0.25), Vector3(0, 1.45, 2.6), Color(0.18, 0.2, 0.21))
	_add_box_body(parent, "LeftRail", Vector3(0.2, 1.1, 5.0), Vector3(-3.5, 0.8, 0), Color(0.1, 0.1, 0.1))
	_add_box_body(parent, "RightRail", Vector3(0.2, 1.1, 5.0), Vector3(3.5, 0.8, 0), Color(0.1, 0.1, 0.1))

	var sign := Label3D.new()
	sign.name = "FloorSign"
	sign.position = Vector3(-2.2, 2.2, 2.45)
	sign.pixel_size = 0.015
	sign.font_size = 96
	sign.modulate = Color.WHITE
	parent.add_child(sign)

	var symbol := Label3D.new()
	symbol.name = "Symbol"
	symbol.position = Vector3(2.2, 2.1, 2.45)
	symbol.pixel_size = 0.018
	symbol.font_size = 72
	symbol.modulate = Color(0.95, 0.95, 0.75)
	parent.add_child(symbol)

	var clue := Label3D.new()
	clue.name = "Clue"
	clue.position = Vector3(0, 1.35, 2.45)
	clue.pixel_size = 0.012
	clue.font_size = 54
	clue.modulate = Color(0.95, 0.9, 0.7)
	clue.visible = false
	parent.add_child(clue)

	var lamp := MeshInstance3D.new()
	lamp.name = "Lamp"
	var sphere := SphereMesh.new()
	sphere.radius = 0.28
	sphere.height = 0.56
	lamp.mesh = sphere
	lamp.position = Vector3(-2.8, 2.5, 1.4)
	parent.add_child(lamp)

	var boxes := Node3D.new()
	boxes.name = "Boxes"
	boxes.position = Vector3(2.25, 0.45, 1.2)
	parent.add_child(boxes)

	var floor_label := Label3D.new()
	floor_label.name = "ObservationLabel"
	floor_label.position = Vector3(0, 0.2, -1.8)
	floor_label.rotation_degrees = Vector3(-70, 0, 0)
	floor_label.pixel_size = 0.012
	floor_label.font_size = 34
	floor_label.modulate = Color(0.78, 0.9, 1.0)
	parent.add_child(floor_label)


func _build_ramp(parent: Node3D) -> void:
	var stair_scene: PackedScene = load(LOBBY_STAIR_SCENE)
	if stair_scene != null:
		var stair: Node3D = stair_scene.instantiate()
		stair.name = "LobbyStairPrefab"
		stair.position = Vector3(-1.55, 0.05, 3.6)
		stair.rotation_degrees = Vector3(0, 180, 0)
		stair.scale = Vector3(2.2, 1.8, 2.0)
		parent.add_child(stair)

	var ramp := StaticBody3D.new()
	ramp.name = "RampCollision"
	ramp.position = Vector3(0, 1.45, 5.6)
	ramp.rotation_degrees = Vector3(-23.2, 0, 0)
	parent.add_child(ramp)

	var shape := BoxShape3D.new()
	shape.size = Vector3(4.0, 0.35, 7.7)
	var collision := CollisionShape3D.new()
	collision.shape = shape
	ramp.add_child(collision)

	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = shape.size
	mesh.mesh = box
	mesh.material_override = _material(Color(0.24, 0.25, 0.27))
	mesh.visible = false
	ramp.add_child(mesh)


func _add_lobby_floor_prefab(parent: Node3D) -> void:
	var floor_scene: PackedScene = load(LOBBY_FLOOR_SCENE)
	if floor_scene == null:
		return
	var floor: Node3D = floor_scene.instantiate()
	floor.name = "LobbyFloorPrefab"
	floor.position = Vector3(-1.5, 0, -1.5)
	floor.scale = Vector3(2.4, 1.0, 1.8)
	parent.add_child(floor)


func _create_answer_choices() -> void:
	var answers := Node3D.new()
	answers.name = "AnswerChoices"
	answers.position = Vector3(0, (FLOOR_MAX - FLOOR_MIN) * 3.0 + 0.6, (FLOOR_MAX - FLOOR_MIN) * 7.0 + 1.0)
	add_child(answers)
	var answer_script: Script = load("res://addons/cogito/DemoScenes/LoopStaircase/loop_staircase_answer.gd")
	for index: int in range(FLOOR_MAX - FLOOR_MIN + 1):
		var floor_number: int = FLOOR_MIN + index
		var answer := StaticBody3D.new()
		answer.name = "Answer_%dF" % floor_number
		answer.script = answer_script
		answer.set("answer_floor", floor_number)
		answer.position = Vector3((index % 3 - 1) * 1.9, 0.8, int(index / 3) * 1.2)
		answers.add_child(answer)
		answer.set("manager_path", answer.get_path_to(self))
		_add_answer_visual(answer, floor_number)

	var result_label := Label3D.new()
	result_label.name = "ResultLabel"
	result_label.position = answers.position + Vector3(0, 2.4, 1.0)
	result_label.pixel_size = 0.014
	result_label.font_size = 56
	result_label.visible = false
	add_child(result_label)


func _add_answer_visual(answer: StaticBody3D, floor_number: int) -> void:
	var shape := BoxShape3D.new()
	shape.size = Vector3(1.4, 0.8, 0.25)
	var collision := CollisionShape3D.new()
	collision.shape = shape
	answer.add_child(collision)

	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = shape.size
	mesh.mesh = box
	mesh.material_override = _material(Color(0.18, 0.28, 0.38))
	answer.add_child(mesh)

	var label := Label3D.new()
	label.name = "Label"
	label.text = "%dF" % floor_number
	label.position = Vector3(0, 0, -0.15)
	label.pixel_size = 0.01
	label.font_size = 58
	label.modulate = Color.WHITE
	answer.add_child(label)

	var basic: Node = load("res://addons/cogito/Components/Interactions/BasicInteraction.tscn").instantiate()
	basic.name = "BasicInteraction"
	basic.set("interaction_text", "Choose %dF" % floor_number)
	basic.set("input_map_action", "interact")
	answer.add_child(basic)


func _create_loop_trigger() -> void:
	var trigger := Area3D.new()
	trigger.name = "LoopTrigger"
	trigger.script = load("res://addons/cogito/DemoScenes/LoopStaircase/loop_staircase_loop_trigger.gd")
	trigger.position = Vector3(0, (FLOOR_MAX - FLOOR_MIN) * 3.0 + 0.8, (FLOOR_MAX - FLOOR_MIN) * 7.0 + 3.8)
	add_child(trigger)
	trigger.set("manager_path", trigger.get_path_to(self))
	var shape := BoxShape3D.new()
	shape.size = Vector3(6.0, 3.0, 1.5)
	var collision := CollisionShape3D.new()
	collision.shape = shape
	trigger.add_child(collision)


func _add_box_body(
	parent: Node3D,
	node_name: String,
	size: Vector3,
	position: Vector3,
	color: Color,
	visible: bool = true,
) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = node_name
	body.position = position
	parent.add_child(body)
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	collision.shape = shape
	body.add_child(collision)
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = size
	mesh.mesh = box
	mesh.material_override = _material(color)
	mesh.visible = visible
	body.add_child(mesh)
	return body


func _add_wall_body(
	parent: Node3D,
	node_name: String,
	size: Vector3,
	position: Vector3,
) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = node_name
	body.position = position
	parent.add_child(body)
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	collision.shape = shape
	body.add_child(collision)
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = size
	mesh.mesh = box
	mesh.material_override = _room_wall_material()
	body.add_child(mesh)
	return body


func _update_floor_displays() -> void:
	if get_node_or_null("CurrentFloorRoom") == null:
		return
	_create_current_floor_room()
	var room: Node = get_node_or_null("CurrentFloorRoom")
	if room == null:
		return
	var current_state: Dictionary = get_floor_state(_current_floor)
	(room.get_node("FloorSign") as Label3D).text = "%dF" % current_state["floor_sign"]
	_rebuild_wall_symbol(room.get_node("WallSymbol") as Node3D, current_state["symbol"], current_state)
	(room.get_node("Clue") as Label3D).text = current_state["clue_text"]
	(room.get_node("ObservationLabel") as Label3D).text = (
		"第 %d/%d 轮\n当前线索：%s\n上/下切换楼层  空格选择"
		% [current_loop + 1, TOTAL_LOOPS, get_current_clue_text()]
	)
	var lamp := room.get_node("LampIndicator") as MeshInstance3D
	lamp.material_override = _material(_lamp_color(current_state["lamp_color"]))
	_rebuild_boxes(room.get_node("Boxes") as Node3D, current_state["box_count"])
	var layout_variant: int = int(current_state.get("layout_variant", 0))
	_rebuild_chairs(room.get_node("Chairs") as Node3D, current_state["chair_count"], layout_variant)
	_rebuild_books(room.get_node("Books") as Node3D, current_state["book_count"], layout_variant)
	_rebuild_computer_set(room.get_node("ComputerSet") as Node3D, current_state["computer_count"], layout_variant)
	var status := get_node_or_null("GameUI/StatusPanel/Status") as Label
	if status != null:
		status.text = (
			"当前楼层 / CURRENT：%dF\n轮次 / LOOP：%d/%d\n线索 / CLUE：%s\n%s"
			% [
				_current_floor,
				current_loop + 1,
				TOTAL_LOOPS,
				get_current_clue_text(),
				(
					"按空格选择本层 / Press Space to choose."
					if is_final_unlocked()
					else "收集五条线索后按空格 / Collect five clues, then press Space."
				),
			]
		)


func _rebuild_boxes(boxes: Node3D, box_count: int) -> void:
	for child: Node in boxes.get_children():
		boxes.remove_child(child)
		child.free()
	for index: int in range(box_count):
		var path: String = LOBBY_OPEN_BOX_SCENE if index == 0 and box_count == 1 else LOBBY_BOX_SCENE
		var packed: PackedScene = load(path)
		if packed != null:
			var instance := packed.instantiate() as Node3D
			if instance != null:
				instance.name = "LobbyBox_%d" % (index + 1)
				instance.position = Vector3(
					index * 0.62 + _visual_noise(index, 1, 0.08),
					0,
					_visual_noise(index, 2, 0.08),
				)
				instance.rotation_degrees = Vector3(0, index * 18 + _visual_noise(index, 3, 10.0), 0)
				instance.scale = Vector3(0.72, 0.72, 0.72)
				boxes.add_child(instance)
				continue
		var mesh := MeshInstance3D.new()
		mesh.name = "LobbyBox_%d" % (index + 1)
		var box := BoxMesh.new()
		box.size = Vector3(0.65, 0.65, 0.65)
		mesh.mesh = box
		mesh.position = Vector3(index * 0.75 + _visual_noise(index, 1, 0.08), 0, _visual_noise(index, 2, 0.08))
		mesh.material_override = _material(Color(0.45, 0.34, 0.22))
		boxes.add_child(mesh)


func _rebuild_chairs(chairs: Node3D, chair_count: int, layout_variant: int) -> void:
	for child: Node in chairs.get_children():
		chairs.remove_child(child)
		child.free()
	var positions: Array[Vector3] = [
		_layout_position(layout_variant, "chair_a"),
		_layout_position(layout_variant, "chair_b"),
		_layout_position(layout_variant, "chair_c"),
	]
	for index: int in range(chair_count):
		var path: String = LOBBY_CHAIR_SCENE if index < 2 else LOBBY_CUSHION_CHAIR_SCENE
		var instance := _instance_optional_scene(
			chairs,
			path,
			"LobbyChair_%d" % (index + 1),
			positions[index] + Vector3(_visual_noise(index, 4, 0.08), 0, _visual_noise(index, 5, 0.08)),
			Vector3(0, 180 + _visual_noise(index, 6, 8.0), 0),
			Vector3(0.72, 0.72, 0.72),
		)
		_freeze_rigid_body(instance)


func _rebuild_books(books: Node3D, book_count: int, layout_variant: int) -> void:
	for child: Node in books.get_children():
		books.remove_child(child)
		child.free()
	var positions: Array[Vector3] = [
		_layout_position(layout_variant, "book_a"),
		_layout_position(layout_variant, "book_b"),
		_layout_position(layout_variant, "book_c"),
		_layout_position(layout_variant, "book_d"),
	]
	for index: int in range(book_count):
		var instance := _instance_optional_scene(
			books,
			LOBBY_BOOKS_SCENE,
			"LobbyBooks_%d" % (index + 1),
			positions[index] + Vector3(_visual_noise(index, 7, 0.06), 0, _visual_noise(index, 8, 0.06)),
			Vector3(0, -15 + index * 20 + _visual_noise(index, 9, 8.0), 0),
			Vector3(0.68, 0.68, 0.68),
		)
		_freeze_rigid_body(instance)


func _rebuild_computer_set(computer_set: Node3D, computer_count: int, layout_variant: int) -> void:
	for child: Node in computer_set.get_children():
		computer_set.remove_child(child)
		child.free()
	computer_set.visible = computer_count > 0
	if computer_count <= 0:
		return
	var desk := _instance_optional_scene(
		computer_set,
		LOBBY_DESK_SCENE,
		"ComputerDesk",
		Vector3(0, 0, 0),
		Vector3(0, 90 + _layout_rotation_y(layout_variant, "desk"), 0),
		Vector3(0.85, 0.85, 0.85),
	)
	_freeze_rigid_body(desk)
	var laptop := _instance_optional_scene(
		computer_set,
		LOBBY_LAPTOP_SCENE,
		"LobbyLaptop",
		Vector3(0.05 + _visual_noise(0, 10, 0.05), 0.78, -0.1 + _visual_noise(0, 11, 0.05)),
		Vector3(0, 180 + _visual_noise(0, 12, 4.0), 0),
		Vector3(0.72, 0.72, 0.72),
	)
	_freeze_rigid_body(laptop)
	if computer_count < 2:
		return
	_instance_optional_scene(computer_set, LOBBY_COMPUTER_SCREEN_SCENE, "ComputerScreen", Vector3(-0.35, 0.78, 0.15), Vector3(0, 180, 0), Vector3(0.72, 0.72, 0.72))
	_instance_optional_scene(computer_set, LOBBY_COMPUTER_KEYBOARD_SCENE, "ComputerKeyboard", Vector3(-0.35, 0.78, -0.2), Vector3(0, 180, 0), Vector3(0.72, 0.72, 0.72))
	_instance_optional_scene(computer_set, LOBBY_COMPUTER_MOUSE_SCENE, "ComputerMouse", Vector3(0.18, 0.78, -0.16), Vector3(0, 180, 0), Vector3(0.72, 0.72, 0.72))


func _rebuild_wall_symbol(symbol_root: Node3D, symbol_name: String, state: Dictionary) -> void:
	for child: Node in symbol_root.get_children():
		symbol_root.remove_child(child)
		child.free()
	symbol_root.rotation_degrees = Vector3(
		_visual_noise(state.get("floor", _current_floor), 13, 3.0),
		0,
		_visual_noise(state.get("floor_sign", _current_floor), 14, 12.0),
	)
	var material := _symbol_material()
	match symbol_name:
		"circle":
			var torus := MeshInstance3D.new()
			torus.name = "CircleRing"
			var mesh := TorusMesh.new()
			mesh.inner_radius = 0.18
			mesh.outer_radius = 0.32
			torus.mesh = mesh
			torus.rotation_degrees = Vector3(90, 0, 0)
			torus.material_override = material
			symbol_root.add_child(torus)
		"triangle":
			_add_symbol_bar(symbol_root, "TriangleLeft", Vector3(-0.17, -0.02, 0), Vector3(0, 0, -31), 0.48, material)
			_add_symbol_bar(symbol_root, "TriangleRight", Vector3(0.17, -0.02, 0), Vector3(0, 0, 31), 0.48, material)
			_add_symbol_bar(symbol_root, "TriangleBase", Vector3(0, -0.23, 0), Vector3(0, 0, 90), 0.46, material)
		"square":
			_add_symbol_bar(symbol_root, "SquareTop", Vector3(0, 0.23, 0), Vector3(0, 0, 90), 0.48, material)
			_add_symbol_bar(symbol_root, "SquareBottom", Vector3(0, -0.23, 0), Vector3(0, 0, 90), 0.48, material)
			_add_symbol_bar(symbol_root, "SquareLeft", Vector3(-0.23, 0, 0), Vector3.ZERO, 0.48, material)
			_add_symbol_bar(symbol_root, "SquareRight", Vector3(0.23, 0, 0), Vector3.ZERO, 0.48, material)
		"star":
			for index: int in range(5):
				_add_symbol_bar(
					symbol_root,
					"StarArm_%d" % index,
					Vector3.ZERO,
					Vector3(0, 0, index * 36),
					0.62,
					material,
				)


func _add_symbol_bar(
	parent: Node3D,
	node_name: String,
	position: Vector3,
	rotation_degrees: Vector3,
	height: float,
	material: Material,
) -> void:
	var bar := MeshInstance3D.new()
	bar.name = node_name
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.085, height, 0.08)
	bar.mesh = mesh
	bar.position = position
	bar.rotation_degrees = rotation_degrees
	bar.material_override = material
	parent.add_child(bar)


func _layout_position(layout_variant: int, role: String) -> Vector3:
	var index: int = abs(layout_variant) % 9
	match role:
		"sofa":
			return [
				Vector3(-2.45, 0.04, -0.95),
				Vector3(-2.75, 0.04, 0.75),
				Vector3(-1.35, 0.04, -1.55),
				Vector3(1.25, 0.04, -1.65),
				Vector3(-2.85, 0.04, -1.65),
				Vector3(1.55, 0.04, 0.85),
				Vector3(-1.25, 0.04, 1.15),
				Vector3(2.0, 0.04, -0.85),
				Vector3(-2.05, 0.04, 1.45),
			][index]
		"table":
			return [
				Vector3(0.25, 0.02, 0.55),
				Vector3(-0.55, 0.02, 0.05),
				Vector3(1.05, 0.02, 0.35),
				Vector3(-1.0, 0.02, 0.9),
				Vector3(0.85, 0.02, -0.45),
				Vector3(-0.2, 0.02, 1.25),
				Vector3(1.35, 0.02, -0.15),
				Vector3(-0.95, 0.02, -0.35),
				Vector3(0.15, 0.02, -0.95),
			][index]
		"display_books":
			return [
				Vector3(1.85, 0.2, 0.15),
				Vector3(1.65, 0.2, -0.75),
				Vector3(-0.2, 0.2, 1.45),
				Vector3(-1.95, 0.2, 0.25),
				Vector3(2.45, 0.2, 0.55),
				Vector3(-2.05, 0.2, -0.55),
				Vector3(0.65, 0.2, -1.35),
				Vector3(-1.55, 0.2, 1.15),
				Vector3(2.15, 0.2, -0.25),
			][index]
		"plant":
			return [
				Vector3(-3.0, 0.02, 1.65),
				Vector3(2.8, 0.02, 1.55),
				Vector3(-3.0, 0.02, -1.75),
				Vector3(2.55, 0.02, -1.65),
				Vector3(-1.85, 0.02, 1.7),
				Vector3(3.0, 0.02, 0.3),
				Vector3(-2.75, 0.02, 0.65),
				Vector3(2.75, 0.02, -0.05),
				Vector3(-0.65, 0.02, 1.75),
			][index]
		"floor_lamp":
			return [
				Vector3(-2.9, 0.02, -2.0),
				Vector3(2.6, 0.02, -1.85),
				Vector3(-2.45, 0.02, 1.25),
				Vector3(1.95, 0.02, 1.55),
				Vector3(-0.85, 0.02, -1.9),
				Vector3(2.85, 0.02, 1.15),
				Vector3(-3.05, 0.02, -0.55),
				Vector3(0.65, 0.02, 1.65),
				Vector3(-2.9, 0.02, 0.95),
			][index]
		"boxes":
			return [
				Vector3(2.05, 0.02, 1.35),
				Vector3(-2.35, 0.02, 1.35),
				Vector3(2.25, 0.02, -1.2),
				Vector3(-2.15, 0.02, -1.25),
				Vector3(0.25, 0.02, 1.55),
				Vector3(2.4, 0.02, 0.15),
				Vector3(-2.55, 0.02, 0.15),
				Vector3(0.8, 0.02, -1.45),
				Vector3(-0.85, 0.02, -1.45),
			][index]
		"computer":
			return [
				Vector3(-1.15, 0.02, -1.55),
				Vector3(1.45, 0.02, -1.45),
				Vector3(-2.05, 0.02, 0.65),
				Vector3(2.15, 0.02, 0.45),
				Vector3(-0.2, 0.02, -1.55),
				Vector3(-2.35, 0.02, -0.95),
				Vector3(1.85, 0.02, 1.05),
				Vector3(-1.35, 0.02, 1.1),
				Vector3(1.15, 0.02, -0.95),
			][index]
		"chair_a":
			return [
				Vector3(-1.65, 0.08, 1.42),
				Vector3(1.55, 0.08, 1.25),
				Vector3(-2.8, 0.08, -0.35),
				Vector3(2.55, 0.08, -0.15),
				Vector3(-0.85, 0.08, 1.45),
				Vector3(0.95, 0.08, -1.15),
				Vector3(-2.35, 0.08, 0.95),
				Vector3(2.35, 0.08, 0.95),
				Vector3(-0.25, 0.08, -1.35),
			][index]
		"chair_b":
			return [
				Vector3(-2.45, 0.08, 1.42),
				Vector3(2.35, 0.08, 1.05),
				Vector3(-1.85, 0.08, -0.95),
				Vector3(1.65, 0.08, -0.85),
				Vector3(0.15, 0.08, 1.45),
				Vector3(1.75, 0.08, -0.45),
				Vector3(-1.55, 0.08, 1.35),
				Vector3(1.65, 0.08, 1.45),
				Vector3(0.75, 0.08, -1.25),
			][index]
		"chair_c":
			return [
				Vector3(-3.05, 0.08, 0.7),
				Vector3(2.8, 0.08, 0.25),
				Vector3(-2.95, 0.08, 0.85),
				Vector3(2.9, 0.08, 1.15),
				Vector3(-1.75, 0.08, -1.25),
				Vector3(-0.35, 0.08, 1.55),
				Vector3(-2.8, 0.08, -1.15),
				Vector3(2.95, 0.08, -1.25),
				Vector3(1.75, 0.08, 0.65),
			][index]
		"book_a":
			return _layout_position(layout_variant, "display_books") + Vector3(0, 0, 0)
		"book_b":
			return _layout_position(layout_variant, "display_books") + Vector3(-0.42, 0, -0.35)
		"book_c":
			return _layout_position(layout_variant, "display_books") + Vector3(0.46, 0, -0.22)
		"book_d":
			return _layout_position(layout_variant, "display_books") + Vector3(0.32, 0, 0.42)
	return Vector3.ZERO


func _layout_rotation_y(layout_variant: int, role: String) -> float:
	var index: int = abs(layout_variant) % 9
	match role:
		"sofa":
			return [90.0, -90.0, 45.0, -45.0, 135.0, -135.0, 0.0, 180.0, 25.0][index]
		"table":
			return [0.0, 25.0, -20.0, 45.0, -35.0, 15.0, 70.0, -65.0, 90.0][index]
		"display_books":
			return [-15.0, 35.0, 70.0, -45.0, 10.0, -75.0, 95.0, 120.0, -25.0][index]
		"plant":
			return [-35.0, 35.0, -80.0, 80.0, 15.0, -15.0, 120.0, -120.0, 45.0][index]
		"computer":
			return [0.0, 180.0, 90.0, -90.0, 45.0, 135.0, -45.0, -135.0, 25.0][index]
		"desk":
			return [0.0, 20.0, -20.0, 35.0, -35.0, 55.0, -55.0, 80.0, -80.0][index]
	return 0.0


func _symbol_material() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(1.0, 0.88, 0.25)
	material.emission_enabled = true
	material.emission = Color(0.9, 0.65, 0.08)
	material.emission_energy_multiplier = 0.35
	material.roughness = 0.42
	return material


func _visual_noise(index: int, salt: int, amplitude: float) -> float:
	var raw: int = abs(index * 37 + _current_floor * 19 + current_loop * 29 + salt * 53) % 101
	return ((float(raw) / 100.0) - 0.5) * amplitude


func _update_answer_visibility() -> void:
	var unlocked: bool = is_final_unlocked()
	var answer := get_node_or_null("CurrentFloorRoom/AnswerCurrentFloor") as Area3D
	if answer != null:
		answer.visible = unlocked
		answer.monitoring = unlocked
		answer.monitorable = unlocked
		answer.collision_layer = 2 if unlocked else 0
	var answers: Node3D = get_node_or_null("AnswerChoices")
	if answers != null:
		answers.visible = unlocked
		for answer_choice: Node in answers.get_children():
			if answer_choice is CollisionObject3D:
				(answer_choice as CollisionObject3D).collision_layer = 2 if unlocked else 0
	var trigger := get_node_or_null("LoopTrigger") as Area3D
	if trigger != null:
		trigger.monitoring = not unlocked
		trigger.monitorable = not unlocked


func _material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.emission_enabled = true
	material.emission = color * 0.25
	return material


func _room_wall_material() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.92, 0.92, 0.86)
	material.roughness = 0.82
	material.emission_enabled = true
	material.emission = Color(0.72, 0.72, 0.64)
	material.emission_energy_multiplier = 0.45
	return material


func _lamp_color(color_name: String) -> Color:
	match color_name:
		"red":
			return Color(1, 0.1, 0.08)
		"blue":
			return Color(0.15, 0.35, 1)
		"green":
			return Color(0.1, 0.9, 0.25)
		"yellow":
			return Color(1, 0.86, 0.15)
		"purple":
			return Color(0.72, 0.25, 1)
	return Color(0.95, 0.95, 0.95)


func _symbol_label(symbol: String) -> String:
	match symbol:
		"circle":
			return "O"
		"triangle":
			return "^"
		"square":
			return "[]"
		"star":
			return "*"
	return "?"


func _is_solution_floor(state: Dictionary) -> bool:
	return (
		state["floor"] == _true_floor
		and not state["sign_duplicated"]
		and not state["chair_count_changed"]
		and not state["computer_count_changed"]
		and not state["book_count_changed"]
	)


func _pick_distinct_floors(count: int) -> Array[int]:
	var candidates: Array[int] = []
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		candidates.append(floor_number)
	var result: Array[int] = []
	while result.size() < count and not candidates.is_empty():
		var index: int = _rng.randi_range(0, candidates.size() - 1)
		result.append(candidates.pop_at(index))
	return result


func _pick_two_box_candidate_floors() -> Array[int]:
	var candidates: Array[int] = []
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		if floor_number != _true_floor:
			candidates.append(floor_number)
	var result: Array[int] = [_true_floor]
	while result.size() < TWO_BOX_CANDIDATE_COUNT and not candidates.is_empty():
		var index: int = _rng.randi_range(0, candidates.size() - 1)
		result.append(candidates.pop_at(index))
	result.sort()
	return result


func _pick_stability_floors() -> void:
	_stable_room_number_floors = [_true_floor]
	var sign_candidates: Array[int] = []
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		if floor_number != _true_floor:
			sign_candidates.append(floor_number)
	while _stable_room_number_floors.size() < STABLE_ROOM_NUMBER_COUNT and not sign_candidates.is_empty():
		var index: int = _rng.randi_range(0, sign_candidates.size() - 1)
		_stable_room_number_floors.append(sign_candidates.pop_at(index))
	_stable_room_number_floors.sort()

	_stable_furniture_floors = [_true_floor]
	var furniture_candidates: Array[int] = []
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		if floor_number != _true_floor and not floor_number in _stable_room_number_floors:
			furniture_candidates.append(floor_number)
	while _stable_furniture_floors.size() < STABLE_FURNITURE_COUNT and not furniture_candidates.is_empty():
		var index: int = _rng.randi_range(0, furniture_candidates.size() - 1)
		_stable_furniture_floors.append(furniture_candidates.pop_at(index))
	_stable_furniture_floors.sort()


func _generate_round_clues() -> void:
	_round_clues = []
	var remaining: Array[int] = []
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		remaining.append(floor_number)
	var false_floors: Array[int] = []
	for floor_number: int in remaining:
		if floor_number != _true_floor:
			false_floors.append(floor_number)
	_shuffle_ints(false_floors)
	var hint_indices: Array[int] = []
	for hint_index: int in range(_observation_hint_count()):
		hint_indices.append(hint_index)
	_shuffle_ints(hint_indices)
	var eliminated_count: int = 0
	for clue_index: int in range(TOTAL_LOOPS):
		var target_count: int = CLUE_CANDIDATE_COUNTS[clue_index]
		var eliminated_this_clue: int = 0
		while remaining.size() > target_count and eliminated_count < false_floors.size():
			eliminated_this_clue = false_floors[eliminated_count]
			remaining.erase(eliminated_this_clue)
			eliminated_count += 1
		remaining.sort()
		_round_clues.append({
			"loop": clue_index,
			"text": _clue_text_for_observation(clue_index, hint_indices[clue_index], remaining.size()),
			"eliminated_floor": eliminated_this_clue,
			"remaining_floors": remaining.duplicate(),
		})


func _clue_text_for_observation(clue_index: int, hint_index: int, remaining_count: int) -> String:
	var clue_number: int = clue_index + 1
	var hint: String = _observation_hint(hint_index)
	if remaining_count == 1:
		return "线索 %d：%s。用全部记录做最终判断。" % [clue_number, hint]
	return "线索 %d：%s。" % [clue_number, hint]


func _observation_hint_count() -> int:
	return _observation_hints().size()


func _observation_hint(clue_index: int) -> String:
	var hints: Array[String] = _observation_hints()
	return hints[clue_index % hints.size()]


func _observation_hints() -> Array[String]:
	var hints: Array[String] = [
		"真正房间的门牌不会随循环随机改写",
		"真正房间的墙灯颜色会保持一致",
		"真正房间的墙上符号会保持一致",
		"真正房间会稳定保留两只纸箱",
		"真正房间的桌面物品类型不会跳变",
		"真正房间的电脑会一直存在",
		"真正房间的书本数量会保持一致",
		"真正房间的家具布局不会整体错位",
		"最后只选择同时满足全部线索的房间",
	]
	return hints


func _shuffle_ints(values: Array[int]) -> void:
	for index: int in range(values.size() - 1, 0, -1):
		var swap_index: int = _rng.randi_range(0, index)
		var current: int = values[index]
		values[index] = values[swap_index]
		values[swap_index] = current


func _pick_wall_changed_floors() -> Array[int]:
	var candidates: Array[int] = []
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		if floor_number != _true_floor:
			candidates.append(floor_number)
	var change_count: int = 4 if _rng.randi_range(0, 1) == 0 else 5
	var result: Array[int] = []
	while result.size() < change_count and not candidates.is_empty():
		var index: int = _rng.randi_range(0, candidates.size() - 1)
		result.append(candidates.pop_at(index))
	return result


func _add_anomaly(anomalies: Dictionary, floor_number: int, anomaly_type: String) -> void:
	if not anomalies.has(floor_number):
		anomalies[floor_number] = []
	(anomalies[floor_number] as Array).append(anomaly_type)


func _non_candidate_box_count() -> int:
	return 1 if _rng.randi_range(0, 1) == 0 else 3


func _random_wall_anomaly_type(floor_number: int) -> String:
	var index: int = abs(floor_number + _rng.randi()) % ANOMALY_TYPES.size()
	return ANOMALY_TYPES[index]


func _shift_floor_sign(current: int) -> int:
	var shifted: int = current + 1
	if shifted > FLOOR_MAX:
		shifted = FLOOR_MIN
	return shifted


func _next_lamp_color(current: String) -> String:
	var index: int = LAMP_COLORS.find(current)
	return LAMP_COLORS[(index + 1) % LAMP_COLORS.size()]


func _next_count(current: int, minimum: int, maximum: int) -> int:
	if current >= maximum:
		return minimum
	return current + 1


func _next_symbol(current: String) -> String:
	var index: int = SYMBOLS.find(current)
	return SYMBOLS[(index + 1) % SYMBOLS.size()]


func _clue_text_for_floor(floor_number: int) -> String:
	var clue_index: int = _clue_floors.find(floor_number)
	match clue_index:
		0:
			return "真正的房间会保留自己的房间号。"
		1:
			return "真正的房间会保留关键家具。"
		2:
			return "墙上的线索可能变化，也可能骗人。"
		3:
			return "有些假房间最后一轮才露出破绽。"
	return ""
