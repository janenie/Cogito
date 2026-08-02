class_name ProfitSession
extends RefCounted

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")
const RECIPE_LIMIT: int = 2

var selected_ingredients: Array[String] = []
var spent: int = 0
var revenue: int = 0
var _recipe_counts: Dictionary = {}
var terminal_status: String = ""
var terminal_reason: String = ""


func _init(_legacy_goal: int = 0) -> void:
	pass


func select_ingredient(ingredient_id: String) -> bool:
	if is_terminal() or CATALOG.ingredient_cost(ingredient_id) < 0:
		return false
	selected_ingredients.append(ingredient_id)
	return true


func undo() -> String:
	if is_terminal() or selected_ingredients.is_empty():
		return ""
	return selected_ingredients.pop_back()


func make() -> Dictionary:
	if is_terminal() or selected_ingredients.is_empty():
		return {
			"accepted": false,
			"outcome": "game_finished" if is_terminal() else "empty_tray",
			"recipe_id": "",
			"dish_profit": 0,
			"profit": get_profit(),
		}

	var recipe: Dictionary = CATALOG.find_recipe(selected_ingredients)
	for ingredient_id: String in selected_ingredients:
		spent += CATALOG.ingredient_cost(ingredient_id)
	var recipe_id := String(recipe.get("id", ""))
	var outcome := "invalid_combo"
	var dish_profit := 0
	if not recipe.is_empty() and int(_recipe_counts.get(recipe_id, 0)) >= RECIPE_LIMIT:
		outcome = "recipe_limit_exceeded"
	elif not recipe.is_empty():
		outcome = "accepted"
		dish_profit = int(recipe.get("profit", 0))
		revenue += int(recipe.get("sale_price", 0))
		_recipe_counts[recipe_id] = int(_recipe_counts.get(recipe_id, 0)) + 1
	selected_ingredients.clear()

	return {
		"accepted": true,
		"outcome": outcome,
		"recipe_id": recipe_id,
		"dish_profit": dish_profit,
		"profit": get_profit(),
	}


func get_recipe_counts() -> Dictionary:
	return _recipe_counts.duplicate(true)


func get_profit() -> int:
	return revenue - spent


func freeze(status: String, reason: String) -> void:
	if is_terminal():
		return
	terminal_status = status
	terminal_reason = reason


func is_terminal() -> bool:
	return not terminal_status.is_empty()
