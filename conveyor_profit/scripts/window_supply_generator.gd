class_name WindowSupplyGenerator
extends RefCounted

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")
const PLATE_COUNT: int = 16


static func generate(seed_value: int, window_count: int = 10) -> Array[Dictionary]:
	var random := RandomNumberGenerator.new()
	random.seed = seed_value
	var recipe_pairs: Array[Dictionary] = _viable_recipe_pairs()
	var windows: Array[Dictionary] = []
	for _window_index: int in window_count:
		var pair: Dictionary = recipe_pairs[random.randi_range(0, recipe_pairs.size() - 1)]
		var ingredients: Array[String] = []
		ingredients.assign(pair["ingredients"])
		var support: Array[String] = []
		support.assign(pair["support"])
		while ingredients.size() < PLATE_COUNT:
			ingredients.append(support[random.randi_range(0, support.size() - 1)])
		_shuffle(ingredients, random)
		windows.append({
			"ingredients": ingredients,
			"best_profit": int(pair["best_profit"]),
		})
	return windows


static func _viable_recipe_pairs() -> Array[Dictionary]:
	var pairs: Array[Dictionary] = []
	for first_index: int in CATALOG.RECIPES.size():
		for second_index: int in range(first_index + 1, CATALOG.RECIPES.size()):
			var first: Dictionary = CATALOG.RECIPES[first_index]
			var second: Dictionary = CATALOG.RECIPES[second_index]
			if int(first["profit"]) == int(second["profit"]):
				continue
			var ingredients: Array[String] = []
			for ingredient_id: Variant in first["ingredients"]:
				ingredients.append(String(ingredient_id))
			for ingredient_id: Variant in second["ingredients"]:
				ingredients.append(String(ingredient_id))
			var feasible: Array[Dictionary] = CATALOG.attainable_single_dishes(ingredients)
			if feasible.size() != 2:
				continue
			var feasible_ids: Array[String] = []
			for recipe: Dictionary in feasible:
				feasible_ids.append(String(recipe["id"]))
			if String(first["id"]) not in feasible_ids or String(second["id"]) not in feasible_ids:
				continue
			var support: Array[String] = []
			for ingredient_id: String in ingredients:
				if ingredient_id not in support:
					support.append(ingredient_id)
			pairs.append({
				"ingredients": ingredients,
				"support": support,
				"best_profit": maxi(int(first["profit"]), int(second["profit"])),
			})
	return pairs


static func _shuffle(values: Array[String], random: RandomNumberGenerator) -> void:
	for index: int in range(values.size() - 1, 0, -1):
		var swap_index := random.randi_range(0, index)
		var temporary := values[index]
		values[index] = values[swap_index]
		values[swap_index] = temporary
