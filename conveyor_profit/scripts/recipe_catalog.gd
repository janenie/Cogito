class_name RecipeCatalog
extends RefCounted

const INGREDIENT_IDS: Array[String] = [
	"lettuce",
	"tomato",
	"bread",
	"egg",
	"mushroom",
	"cheese",
	"fish",
	"meat",
]

const INGREDIENT_COSTS := {
	"lettuce": 1,
	"tomato": 1,
	"bread": 2,
	"egg": 2,
	"mushroom": 2,
	"cheese": 3,
	"fish": 4,
	"meat": 5,
}

const RECIPES: Array[Dictionary] = [
	{"id": "salad", "ingredients": ["lettuce", "tomato", "mushroom"], "sale_price": 7, "profit": 3},
	{"id": "egg_toast", "ingredients": ["bread", "egg"], "sale_price": 8, "profit": 4},
	{"id": "cheese_toast", "ingredients": ["bread", "cheese"], "sale_price": 10, "profit": 5},
	{"id": "burger", "ingredients": ["bread", "meat", "lettuce", "tomato"], "sale_price": 15, "profit": 6},
	{"id": "fish_sandwich", "ingredients": ["bread", "fish", "lettuce"], "sale_price": 14, "profit": 7},
	{"id": "mushroom_omelet", "ingredients": ["egg", "cheese", "mushroom"], "sale_price": 14, "profit": 7},
]


static func ingredient_cost(ingredient_id: String) -> int:
	return int(INGREDIENT_COSTS.get(ingredient_id, -1))


static func find_recipe(ingredient_ids: Array) -> Dictionary:
	var wanted_signature := _ingredient_signature(ingredient_ids)
	for recipe: Dictionary in RECIPES:
		if _ingredient_signature(recipe.get("ingredients", [])) == wanted_signature:
			return recipe.duplicate(true)
	return {}


static func max_attainable_profit(ingredient_ids: Array) -> int:
	return _max_profit_for_counts(_ingredient_counts(ingredient_ids), {})


static func attainable_single_dishes(ingredient_ids: Array) -> Array[Dictionary]:
	var available_counts := _ingredient_counts(ingredient_ids)
	var result: Array[Dictionary] = []
	for recipe: Dictionary in RECIPES:
		if _can_consume(available_counts, _ingredient_counts(recipe.get("ingredients", []))):
			result.append(recipe.duplicate(true))
	return result


static func _ingredient_signature(ingredient_ids: Array) -> String:
	var sorted_ids: Array[String] = []
	for ingredient_id: Variant in ingredient_ids:
		sorted_ids.append(String(ingredient_id))
	sorted_ids.sort()
	return ",".join(sorted_ids)


static func _ingredient_counts(ingredient_ids: Array) -> Array[int]:
	var counts: Array[int] = []
	counts.resize(INGREDIENT_IDS.size())
	counts.fill(0)
	for ingredient_id: Variant in ingredient_ids:
		var index := INGREDIENT_IDS.find(String(ingredient_id))
		if index >= 0:
			counts[index] += 1
	return counts


static func _max_profit_for_counts(counts: Array[int], memo: Dictionary) -> int:
	var key := _count_signature(counts)
	if memo.has(key):
		return int(memo[key])

	var best := 0
	for recipe: Dictionary in RECIPES:
		var recipe_counts: Array[int] = []
		recipe_counts.resize(INGREDIENT_IDS.size())
		recipe_counts.fill(0)
		for ingredient_id: Variant in recipe.get("ingredients", []):
			recipe_counts[INGREDIENT_IDS.find(String(ingredient_id))] += 1
		if not _can_consume(counts, recipe_counts):
			continue
		var remaining := counts.duplicate()
		for index: int in range(remaining.size()):
			remaining[index] -= recipe_counts[index]
		best = maxi(
			best,
			int(recipe.get("profit", 0)) + _max_profit_for_counts(remaining, memo),
		)
	memo[key] = best
	return best


static func _can_consume(available: Array[int], required: Array[int]) -> bool:
	for index: int in range(available.size()):
		if available[index] < required[index]:
			return false
	return true


static func _count_signature(counts: Array[int]) -> String:
	var parts: PackedStringArray = []
	for count: int in counts:
		parts.append(str(count))
	return ":".join(parts)
