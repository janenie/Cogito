class_name ConveyorGameplay
extends Node

signal game_finished(outcome: String, reason: String)

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")
const PROFIT_SESSION := preload("res://conveyor_profit/scripts/profit_session.gd")
const PROFIT_WINDOW_SESSION := preload("res://conveyor_profit/scripts/profit_window_session.gd")
const WINDOW_SUPPLY_GENERATOR := preload("res://conveyor_profit/scripts/window_supply_generator.gd")

const MODEL_PATHS := {
	"lettuce": "res://conveyor_profit/assets/kenney_food_kit/models/lettuce.glb",
	"tomato": "res://conveyor_profit/assets/kenney_food_kit/models/tomato.glb",
	"bread": "res://conveyor_profit/assets/kenney_food_kit/models/bread.glb",
	"egg": "res://conveyor_profit/assets/kenney_food_kit/models/egg.glb",
	"mushroom": "res://conveyor_profit/assets/kenney_food_kit/models/mushroom.glb",
	"cheese": "res://conveyor_profit/assets/kenney_food_kit/models/cheese.glb",
	"fish": "res://conveyor_profit/assets/kenney_food_kit/models/fish.glb",
	"meat": "res://conveyor_profit/assets/kenney_food_kit/models/meat.glb",
}

@export var supply_seed: int = 1337
@export_range(1, 100, 1) var window_count: int = 10
@export_range(0.01, 3600.0, 0.01) var window_seconds: float = 60.0

var session: RefCounted
var window_session: RefCounted
var window_supplies: Array[Dictionary] = []
var pending_supply: Array[String] = []
var _ingredient_path: Path3D
var _tray_visuals: Node3D
var _tray_label: Label3D
var _total_time_label: Label
var _window_label: Label
var _dish_label: Label
var _profit_label: Label
var _status_label: Label
var _make_button: StaticBody3D
var _undo_button: StaticBody3D
var _next_selection_id: int = 1


func initialize(
	ingredient_path: Path3D,
	tray_visuals: Node3D,
	tray_label: Label3D,
	total_time_label: Label,
	window_label: Label,
	dish_label: Label,
	profit_label: Label,
	status_label: Label,
	make_button: StaticBody3D,
	undo_button: StaticBody3D,
) -> void:
	_ingredient_path = ingredient_path
	_tray_visuals = tray_visuals
	_tray_label = tray_label
	_total_time_label = total_time_label
	_window_label = window_label
	_dish_label = dish_label
	_profit_label = profit_label
	_status_label = status_label
	_make_button = make_button
	_undo_button = undo_button
	session = PROFIT_SESSION.new()
	window_supplies = WINDOW_SUPPLY_GENERATOR.generate(supply_seed, window_count)
	var best_profits: Array[int] = []
	for window: Dictionary in window_supplies:
		best_profits.append(int(window["best_profit"]))
	window_session = PROFIT_WINDOW_SESSION.new(best_profits, window_seconds)
	_make_button.activated.connect(_on_action_requested)
	_undo_button.activated.connect(_on_action_requested)
	_load_window(0)
	_update_public_display("Choose ingredients from the moving belt")


func _process(delta: float) -> void:
	advance_time(delta)


func get_profit() -> int:
	return session.get_profit() if session != null else 0


func get_selected_count() -> int:
	return session.selected_ingredients.size() if session != null else 0


func get_remaining_count() -> int:
	if session == null:
		return 0
	var count: int = pending_supply.size() + session.selected_ingredients.size()
	for follower: Node in _ingredient_path.get_children():
		if follower.visible and follower.get_meta("available", false):
			count += 1
	return count


func get_public_state() -> Dictionary:
	if window_session == null or session == null:
		return {}
	return {
		"total_time": _format_seconds(window_session.get_total_remaining_seconds()),
		"window": "%d / %d" % [window_session.current_window_index + 1, window_count],
		"window_time": _format_seconds(window_session.get_window_remaining_seconds()),
		"dish": "1 / 1" if window_session.dish_made else "0 / 1",
		"net_profit": session.get_profit(),
		"tray": session.selected_ingredients.duplicate(),
		"finished": window_session.is_terminal(),
	}


func advance_time(delta_seconds: float) -> void:
	if window_session == null or window_session.is_terminal():
		return
	var was_expired: bool = window_session.is_time_expired()
	for entered_index: int in window_session.advance_time(delta_seconds):
		_expire_current_window()
		_load_window(entered_index)
	if not was_expired and window_session.is_time_expired():
		_expire_current_window()
		_finish_game()
	else:
		_update_public_display(_status_label.text)


func request_undo() -> Dictionary:
	if window_session.is_terminal() or window_session.is_time_expired():
		return {"outcome": "game_finished"}
	if window_session.dish_made:
		return {"outcome": "window_locked"}
	var ingredient_id: String = session.undo()
	if ingredient_id.is_empty():
		return {"outcome": "tray_empty"}
	pending_supply.push_front(ingredient_id)
	_remove_last_tray_visual()
	_fill_empty_slots()
	return {"outcome": "undone", "ingredient": ingredient_id}


func request_make() -> Dictionary:
	if window_session.is_terminal() or window_session.is_time_expired():
		return {"outcome": "game_finished"}
	if window_session.dish_made:
		return {"outcome": "window_locked"}
	var result: Dictionary = session.make()
	if not result.get("accepted", false):
		return {"outcome": "tray_empty"}
	_clear_tray_visuals()
	var recipe_id := String(result.get("recipe_id", ""))
	var outcome: String = window_session.record_make(recipe_id)
	if outcome == "accepted":
		_set_input_enabled(false)
	return {"outcome": outcome, "recipe_id": recipe_id, "profit": session.get_profit()}


func _fill_follower(follower: PathFollow3D) -> void:
	var preview := follower.get_node("IngredientPreview") as Node3D
	var previous_model := preview.get_node_or_null("FoodModel")
	if previous_model != null:
		preview.remove_child(previous_model)
		previous_model.free()
	var interactable := preview.get_node("Interactable") as Area3D
	if pending_supply.is_empty():
		follower.visible = false
		follower.set_meta("available", false)
		interactable.enabled = false
		interactable.selection_id = -1
		return

	var ingredient_id: String = pending_supply.pop_front()
	var selection_id := _next_selection_id
	_next_selection_id += 1
	follower.visible = true
	follower.set_meta("available", true)
	follower.set_meta("ingredient_id", ingredient_id)
	follower.set_meta("selection_id", selection_id)
	var label := preview.get_node("CostLabel") as Label3D
	label.text = "$%d  %s" % [CATALOG.ingredient_cost(ingredient_id), ingredient_id.to_upper()]
	interactable.enabled = true
	interactable.selection_id = selection_id
	if not interactable.select_requested.is_connected(_on_select_requested):
		interactable.select_requested.connect(_on_select_requested)
	var food_scene := load(String(MODEL_PATHS[ingredient_id])) as PackedScene
	var food := food_scene.instantiate() as Node3D
	food.name = "FoodModel"
	food.position.y = 0.16
	food.scale = Vector3.ONE * 1.35
	preview.add_child(food)


func _on_select_requested(selection_id: int) -> void:
	if session == null or session.is_terminal() or window_session.dish_made:
		return
	for follower: Node in _ingredient_path.get_children():
		if follower.get_meta("selection_id", -1) != selection_id:
			continue
		var ingredient_id := String(follower.get_meta("ingredient_id", ""))
		if not session.select_ingredient(ingredient_id):
			return
		_add_tray_visual(ingredient_id)
		_fill_follower(follower as PathFollow3D)
		_update_public_display("Selected %s" % ingredient_id.to_upper())
		return


func _on_action_requested(action: String) -> void:
	match action:
		"undo":
			_undo_last()
		"make":
			_make_dish()


func _undo_last() -> void:
	var result := request_undo()
	if result["outcome"] == "tray_empty":
		_update_public_display("Nothing to undo")
		return
	if result["outcome"] == "undone":
		_update_public_display("Returned %s" % String(result["ingredient"]).to_upper())


func _make_dish() -> void:
	var result := request_make()
	if result["outcome"] == "tray_empty":
		_update_public_display("Tray is empty")
		return
	if result["outcome"] == "window_locked":
		_update_public_display("Dish already made; wait for next window")
		return
	var recipe_id := String(result.get("recipe_id", ""))
	var message := "Invalid combo: ingredients consumed"
	if result["outcome"] == "accepted":
		message = "Sold %s; wait for next window" % recipe_id.replace("_", " ").to_upper()
	_update_public_display(message)


func _add_tray_visual(ingredient_id: String) -> void:
	var food_scene := load(String(MODEL_PATHS[ingredient_id])) as PackedScene
	var food := food_scene.instantiate() as Node3D
	food.name = "Selected%02d_%s" % [_tray_visuals.get_child_count() + 1, ingredient_id]
	food.position = Vector3((_tray_visuals.get_child_count() - 1.5) * 0.45, 0.1, 0)
	food.scale = Vector3.ONE * 0.8
	_tray_visuals.add_child(food)


func _update_public_display(message: String) -> void:
	var selected_text := " + ".join(session.selected_ingredients).to_upper()
	_tray_label.text = "TRAY  EMPTY" if selected_text.is_empty() else "TRAY  %s" % selected_text
	_total_time_label.text = "TOTAL TIME  %s" % _format_seconds(
		window_session.get_total_remaining_seconds(),
	)
	_window_label.text = "WINDOW  %d / %d  ·  %s" % [
		window_session.current_window_index + 1,
		window_count,
		_format_seconds(window_session.get_window_remaining_seconds()),
	]
	_dish_label.text = "DISH  %s" % ("1 / 1" if window_session.dish_made else "0 / 1")
	_profit_label.text = "NET PROFIT  $%d" % session.get_profit()
	_status_label.text = message


func _set_input_enabled(value: bool) -> void:
	_make_button.enabled = value
	_undo_button.enabled = value
	for follower: Node in _ingredient_path.get_children():
		var interactable := follower.get_node("IngredientPreview/Interactable") as Area3D
		interactable.enabled = value and follower.visible


func _load_window(index: int) -> void:
	pending_supply.assign(window_supplies[index]["ingredients"])
	for follower: Node in _ingredient_path.get_children():
		_fill_follower(follower as PathFollow3D)
	_set_input_enabled(true)


func _expire_current_window() -> void:
	pending_supply.clear()
	session.selected_ingredients.clear()
	_clear_tray_visuals()
	for follower: Node in _ingredient_path.get_children():
		_clear_follower(follower as PathFollow3D)


func _clear_follower(follower: PathFollow3D) -> void:
	var interactable := follower.get_node("IngredientPreview/Interactable") as Area3D
	follower.visible = false
	follower.set_meta("available", false)
	follower.set_meta("ingredient_id", "")
	follower.set_meta("selection_id", -1)
	interactable.enabled = false
	interactable.selection_id = -1


func _fill_empty_slots() -> void:
	for follower: Node in _ingredient_path.get_children():
		if pending_supply.is_empty():
			return
		if not follower.visible:
			_fill_follower(follower as PathFollow3D)


func _remove_last_tray_visual() -> void:
	var child_count := _tray_visuals.get_child_count()
	if child_count > 0:
		_tray_visuals.get_child(child_count - 1).queue_free()


func _clear_tray_visuals() -> void:
	for child: Node in _tray_visuals.get_children():
		child.queue_free()


func _finish_game() -> void:
	window_session.finish(session.get_profit())
	session.freeze(window_session.terminal_status, window_session.terminal_reason)
	_set_input_enabled(false)
	_update_public_display(
		"EFFICIENCY  %d%%  ·  %s" % [
			window_session.get_efficiency_percent(session.get_profit()),
			window_session.terminal_status.to_upper(),
		],
	)
	game_finished.emit(window_session.terminal_status, window_session.terminal_reason)


static func _format_seconds(seconds: float) -> String:
	var whole_seconds := maxi(ceili(seconds), 0)
	return "%02d:%02d" % [whole_seconds / 60, whole_seconds % 60]
