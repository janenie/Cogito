class_name ConveyorGameplay
extends Node

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")
const PROFIT_SESSION := preload("res://conveyor_profit/scripts/profit_session.gd")
const SUPPLY_GENERATOR := preload("res://conveyor_profit/scripts/supply_generator.gd")

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
@export var target_profit: int = 100

var session: RefCounted
var pending_supply: Array[String] = []
var _ingredient_path: Path3D
var _tray_visuals: Node3D
var _tray_label: Label3D
var _profit_label: Label
var _status_label: Label
var _make_button: StaticBody3D
var _undo_button: StaticBody3D
var _next_selection_id: int = 1


func initialize(
	ingredient_path: Path3D,
	tray_visuals: Node3D,
	tray_label: Label3D,
	profit_label: Label,
	status_label: Label,
	make_button: StaticBody3D,
	undo_button: StaticBody3D,
) -> void:
	_ingredient_path = ingredient_path
	_tray_visuals = tray_visuals
	_tray_label = tray_label
	_profit_label = profit_label
	_status_label = status_label
	_make_button = make_button
	_undo_button = undo_button
	session = PROFIT_SESSION.new(target_profit)
	pending_supply = SUPPLY_GENERATOR.generate(supply_seed, 120)
	_frontload_initial_variety()
	_make_button.activated.connect(_on_action_requested)
	_undo_button.activated.connect(_on_action_requested)
	for follower: Node in _ingredient_path.get_children():
		_fill_follower(follower as PathFollow3D)
	_update_public_display("Choose ingredients from the moving belt")


func _frontload_initial_variety() -> void:
	var first_of_each: Array[String] = []
	var seen: Dictionary = {}
	for ingredient_id: String in pending_supply:
		if seen.has(ingredient_id):
			continue
		seen[ingredient_id] = true
		first_of_each.append(ingredient_id)
		if first_of_each.size() == CATALOG.INGREDIENT_IDS.size():
			break
	var remainder := pending_supply.duplicate()
	for ingredient_id: String in first_of_each:
		remainder.erase(ingredient_id)
	first_of_each.append_array(remainder)
	pending_supply = first_of_each


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
	if session == null or session.is_terminal():
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
	var ingredient_id: String = session.undo()
	if ingredient_id.is_empty():
		_update_public_display("Nothing to undo")
		return
	pending_supply.push_front(ingredient_id)
	var child_count := _tray_visuals.get_child_count()
	if child_count > 0:
		_tray_visuals.get_child(child_count - 1).queue_free()
	_update_public_display("Returned %s" % ingredient_id.to_upper())


func _make_dish() -> void:
	var result: Dictionary = session.make()
	if not result.get("accepted", false):
		_update_public_display("Tray is empty")
		return
	for child: Node in _tray_visuals.get_children():
		child.queue_free()
	var recipe_id := String(result.get("recipe_id", ""))
	var message := "Invalid combo: ingredients consumed"
	if not recipe_id.is_empty():
		message = "Sold %s" % recipe_id.replace("_", " ").to_upper()
	session.evaluate_reachability(_available_ingredient_ids())
	if session.is_terminal():
		message = session.terminal_reason.replace("_", " ").to_upper()
		_set_input_enabled(false)
	_update_public_display(message)


func _available_ingredient_ids() -> Array[String]:
	var ingredient_ids := pending_supply.duplicate()
	for follower: Node in _ingredient_path.get_children():
		if follower.visible and follower.get_meta("available", false):
			ingredient_ids.append(String(follower.get_meta("ingredient_id", "")))
	return ingredient_ids


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
	_profit_label.text = "NET PROFIT  $%d / $%d" % [session.get_profit(), target_profit]
	_status_label.text = message


func _set_input_enabled(value: bool) -> void:
	_make_button.enabled = value
	_undo_button.enabled = value
	for follower: Node in _ingredient_path.get_children():
		var interactable := follower.get_node("IngredientPreview/Interactable") as Area3D
		interactable.enabled = value and follower.visible
