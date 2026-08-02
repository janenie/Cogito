class_name SupplyGenerator
extends RefCounted

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")


static func generate(seed_value: int, minimum_profit: int = 120) -> Array[String]:
	var random := RandomNumberGenerator.new()
	random.seed = seed_value
	var ingredient_ids: Array[String] = []
	var witness_profit := 0
	while witness_profit < minimum_profit:
		var recipe: Dictionary = CATALOG.RECIPES[random.randi_range(0, CATALOG.RECIPES.size() - 1)]
		for ingredient_id: Variant in recipe.get("ingredients", []):
			ingredient_ids.append(String(ingredient_id))
		witness_profit += int(recipe.get("profit", 0))

	for index: int in range(ingredient_ids.size() - 1, 0, -1):
		var swap_index := random.randi_range(0, index)
		var temporary := ingredient_ids[index]
		ingredient_ids[index] = ingredient_ids[swap_index]
		ingredient_ids[swap_index] = temporary
	return ingredient_ids
