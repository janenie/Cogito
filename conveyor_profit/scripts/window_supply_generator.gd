class_name WindowSupplyGenerator
extends RefCounted

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")
const PLATE_COUNT: int = 16
const MAX_FILL_ATTEMPTS: int = 500


static func generate(campaign: Dictionary, seed_value: int) -> Array[Dictionary]:
	var composition_random := RandomNumberGenerator.new()
	composition_random.seed = seed_value ^ String(campaign.get("id", "")).hash()
	var order_random := RandomNumberGenerator.new()
	order_random.seed = seed_value ^ 0x5A17C0DE
	var windows: Array[Dictionary] = []
	for round_data: Dictionary in campaign.get("rounds", []):
		var candidates: Array = round_data.get("candidate_recipe_ids", [])
		var ingredients := _required_ingredients(candidates)
		var attempts := 0
		while ingredients.size() < PLATE_COUNT and attempts < MAX_FILL_ATTEMPTS:
			attempts += 1
			var ingredient_id: String = CATALOG.INGREDIENT_IDS[
				composition_random.randi_range(0, CATALOG.INGREDIENT_IDS.size() - 1)
			]
			ingredients.append(ingredient_id)
			if not _matches_candidates(ingredients, candidates):
				ingredients.pop_back()
		if ingredients.size() < PLATE_COUNT:
			_fill_with_safe_duplicates(ingredients, candidates)
		if ingredients.size() != PLATE_COUNT or not _matches_candidates(ingredients, candidates):
			push_error("Unable to materialize a safe conveyor window")
			return []
		_shuffle(ingredients, order_random)
		windows.append({
			"ingredients": ingredients,
			"category_multipliers": round_data.get("category_multipliers", {}).duplicate(true),
			"signals": round_data.get("signals", []).duplicate(true),
		})
	return windows


static func _required_ingredients(candidate_ids: Array) -> Array[String]:
	var maximum_counts: Dictionary = {}
	for recipe_id: Variant in candidate_ids:
		var recipe: Dictionary = CATALOG.recipe_by_id(String(recipe_id))
		var recipe_counts: Dictionary = {}
		for ingredient_id: String in recipe.get("ingredients", []):
			recipe_counts[ingredient_id] = int(recipe_counts.get(ingredient_id, 0)) + 1
		for ingredient_id: String in recipe_counts:
			maximum_counts[ingredient_id] = maxi(
				int(maximum_counts.get(ingredient_id, 0)),
				int(recipe_counts[ingredient_id]),
			)
	var result: Array[String] = []
	for ingredient_id: String in CATALOG.INGREDIENT_IDS:
		for _copy_index: int in int(maximum_counts.get(ingredient_id, 0)):
			result.append(ingredient_id)
	return result


static func _fill_with_safe_duplicates(ingredients: Array[String], candidates: Array) -> void:
	var safe_source: Array[String] = ingredients.duplicate()
	var source_index := 0
	while ingredients.size() < PLATE_COUNT and not safe_source.is_empty():
		ingredients.append(safe_source[source_index % safe_source.size()])
		source_index += 1
	if not _matches_candidates(ingredients, candidates):
		ingredients.clear()


static func _matches_candidates(ingredients: Array, candidate_ids: Array) -> bool:
	var actual: Array[String] = []
	for recipe: Dictionary in CATALOG.attainable_single_dishes(ingredients):
		actual.append(String(recipe["id"]))
	actual.sort()
	var expected: Array = candidate_ids.duplicate()
	expected.sort()
	return actual == expected


static func _shuffle(values: Array[String], random: RandomNumberGenerator) -> void:
	for index: int in range(values.size() - 1, 0, -1):
		var swap_index := random.randi_range(0, index)
		var temporary := values[index]
		values[index] = values[swap_index]
		values[swap_index] = temporary
