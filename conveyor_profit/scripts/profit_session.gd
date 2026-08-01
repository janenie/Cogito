class_name ProfitSession
extends RefCounted

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")

var selected_ingredients: Array[String] = []
var spent: int = 0
var revenue: int = 0
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
		return {"accepted": false, "recipe_id": "", "profit": get_profit()}

	var recipe: Dictionary = CATALOG.find_recipe(selected_ingredients)
	for ingredient_id: String in selected_ingredients:
		spent += CATALOG.ingredient_cost(ingredient_id)
	if not recipe.is_empty():
		revenue += int(recipe.get("sale_price", 0))
	var recipe_id := String(recipe.get("id", ""))
	var dish_profit := int(recipe.get("profit", 0))
	selected_ingredients.clear()

	return {
		"accepted": true,
		"recipe_id": recipe_id,
		"dish_profit": dish_profit,
		"profit": get_profit(),
	}


func get_profit() -> int:
	return revenue - spent


func freeze(status: String, reason: String) -> void:
	if is_terminal():
		return
	terminal_status = status
	terminal_reason = reason


func is_terminal() -> bool:
	return not terminal_status.is_empty()
