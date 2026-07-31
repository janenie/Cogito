class_name ProfitSession
extends RefCounted

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")

var target_profit: int
var selected_ingredients: Array[String] = []
var spent: int = 0
var revenue: int = 0
var terminal_status: String = ""
var terminal_reason: String = ""


func _init(goal: int = 100) -> void:
	target_profit = goal


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
		return {"accepted": false, "recipe_id": "", "profit": get_profit()}

	var recipe: Dictionary = CATALOG.find_recipe(selected_ingredients)
	for ingredient_id: String in selected_ingredients:
		spent += CATALOG.ingredient_cost(ingredient_id)
	if not recipe.is_empty():
		revenue += int(recipe.get("sale_price", 0))
	var recipe_id := String(recipe.get("id", ""))
	selected_ingredients.clear()

	if get_profit() >= target_profit:
		terminal_status = "success"
		terminal_reason = "profit_target_reached"
	return {
		"accepted": true,
		"recipe_id": recipe_id,
		"profit": get_profit(),
	}


func evaluate_reachability(available_ingredients: Array) -> String:
	if is_terminal():
		return terminal_status
	var unconsumed: Array = available_ingredients.duplicate()
	unconsumed.append_array(selected_ingredients)
	if get_profit() + CATALOG.max_attainable_profit(unconsumed) < target_profit:
		terminal_status = "failure"
		terminal_reason = "profit_target_unreachable"
	return terminal_status


func get_profit() -> int:
	return revenue - spent


func is_terminal() -> bool:
	return not terminal_status.is_empty()
