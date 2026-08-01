class_name WindowSupplyGenerator
extends RefCounted

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")


static func generate(seed_value: int, window_count: int = 10) -> Array[Dictionary]:
	var random := RandomNumberGenerator.new()
	random.seed = seed_value
	var windows: Array[Dictionary] = []
	while windows.size() < window_count:
		var ingredients := _candidate_ingredients(random)
		var recipes: Array[Dictionary] = CATALOG.attainable_single_dishes(ingredients)
		if recipes.size() not in [1, 2]:
			continue
		_shuffle(ingredients, random)
		var best_profit := 0
		for recipe: Dictionary in recipes:
			best_profit = maxi(best_profit, int(recipe.get("profit", 0)))
		windows.append({
			"ingredients": ingredients,
			"best_profit": best_profit,
		})
	return windows


static func _candidate_ingredients(random: RandomNumberGenerator) -> Array[String]:
	var first_index := random.randi_range(0, CATALOG.RECIPES.size() - 1)
	var recipe_indices: Array[int] = [first_index]
	if random.randi_range(0, 1) == 1:
		var second_index := random.randi_range(0, CATALOG.RECIPES.size() - 2)
		if second_index >= first_index:
			second_index += 1
		recipe_indices.append(second_index)

	var ingredients: Array[String] = []
	for recipe_index: int in recipe_indices:
		for ingredient_id: Variant in CATALOG.RECIPES[recipe_index].get("ingredients", []):
			ingredients.append(String(ingredient_id))
	return ingredients


static func _shuffle(values: Array[String], random: RandomNumberGenerator) -> void:
	for index: int in range(values.size() - 1, 0, -1):
		var swap_index := random.randi_range(0, index)
		var temporary := values[index]
		values[index] = values[swap_index]
		values[swap_index] = temporary
