class_name MarketEconomy
extends RefCounted

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")
const CATEGORIES: Array[String] = ["salad", "soup", "burger", "omelet", "sandwich"]
const MULTIPLIERS: Array[float] = [0.75, 1.0, 1.25, 1.5]


static func adjusted_sale_price(recipe_id: String, multiplier: float) -> int:
	var recipe: Dictionary = CATALOG.recipe_by_id(recipe_id)
	if recipe.is_empty() or not is_valid_multiplier(multiplier):
		return -1
	return floori(float(recipe["sale_price"]) * multiplier + 0.5)


static func adjusted_profit(recipe_id: String, multiplier: float) -> int:
	var recipe: Dictionary = CATALOG.recipe_by_id(recipe_id)
	if recipe.is_empty():
		return -1
	var sale_price := adjusted_sale_price(recipe_id, multiplier)
	if sale_price < 0:
		return -1
	return sale_price - int(recipe["ingredient_cost"])


static func is_valid_multiplier(value: float) -> bool:
	return value in MULTIPLIERS
