class_name CampaignProfitPlanner
extends RefCounted

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")
const ECONOMY := preload("res://conveyor_profit/scripts/market_economy.gd")
const RECIPE_LIMIT: int = 2
const IMPOSSIBLE_PROFIT: int = -1_000_000


static func max_profit(
	windows: Array,
	start_index: int = 0,
	counts: Dictionary = {},
) -> int:
	if start_index < 0 or start_index > windows.size():
		return IMPOSSIBLE_PROFIT
	return _max_from(windows, start_index, _normalized_counts(counts), {})


static func is_optimal_choice(
	windows: Array,
	window_index: int,
	counts: Dictionary,
	recipe_id: String,
) -> bool:
	if window_index < 0 or window_index >= windows.size():
		return false
	var recipe_index := _recipe_index(recipe_id)
	if recipe_index < 0:
		return false
	var normalized := _normalized_counts(counts)
	if normalized[recipe_index] >= RECIPE_LIMIT:
		return false
	var window: Dictionary = windows[window_index]
	var feasible_ids: Array[String] = _feasible_recipe_ids(window.get("ingredients", []))
	if recipe_id not in feasible_ids:
		return false

	var next_counts: Array[int] = normalized.duplicate()
	next_counts[recipe_index] += 1
	var chosen_total := _recipe_profit(window, recipe_id) + _max_from(
		windows,
		window_index + 1,
		next_counts,
		{},
	)
	return chosen_total == _max_from(windows, window_index, normalized, {})


static func _max_from(
	windows: Array,
	window_index: int,
	counts: Array[int],
	memo: Dictionary,
) -> int:
	if window_index >= windows.size():
		return 0
	var key := "%d|%s" % [window_index, _count_signature(counts)]
	if memo.has(key):
		return int(memo[key])

	var window: Dictionary = windows[window_index]
	var best := IMPOSSIBLE_PROFIT
	for recipe_id: String in _feasible_recipe_ids(window.get("ingredients", [])):
		var recipe_index := _recipe_index(recipe_id)
		if counts[recipe_index] >= RECIPE_LIMIT:
			continue
		var next_counts: Array[int] = counts.duplicate()
		next_counts[recipe_index] += 1
		var continuation := _max_from(windows, window_index + 1, next_counts, memo)
		if continuation == IMPOSSIBLE_PROFIT:
			continue
		best = maxi(best, _recipe_profit(window, recipe_id) + continuation)
	memo[key] = best
	return best


static func _normalized_counts(counts: Dictionary) -> Array[int]:
	var normalized: Array[int] = []
	for recipe: Dictionary in CATALOG.RECIPES:
		normalized.append(clampi(int(counts.get(String(recipe["id"]), 0)), 0, RECIPE_LIMIT))
	return normalized


static func _feasible_recipe_ids(ingredients: Array) -> Array[String]:
	var result: Array[String] = []
	for recipe: Dictionary in CATALOG.attainable_single_dishes(ingredients):
		result.append(String(recipe["id"]))
	return result


static func _recipe_index(recipe_id: String) -> int:
	for index: int in CATALOG.RECIPES.size():
		if String(CATALOG.RECIPES[index]["id"]) == recipe_id:
			return index
	return -1


static func _recipe_profit(window: Dictionary, recipe_id: String) -> int:
	var recipe := CATALOG.recipe_by_id(recipe_id)
	if recipe.is_empty():
		return IMPOSSIBLE_PROFIT
	var multipliers: Dictionary = window.get("category_multipliers", {})
	var multiplier := float(multipliers.get(String(recipe["category"]), 1.0))
	return ECONOMY.adjusted_profit(recipe_id, multiplier)


static func _count_signature(counts: Array[int]) -> String:
	var parts: PackedStringArray = []
	for count: int in counts:
		parts.append(str(count))
	return ":".join(parts)
