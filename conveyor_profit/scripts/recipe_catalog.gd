class_name RecipeCatalog
extends RefCounted

const INGREDIENT_IDS: Array[String] = [
	"lettuce",
	"tomato",
	"carrot",
	"avocado",
	"sausage",
	"bread",
	"egg",
	"mushroom",
	"onion",
	"pumpkin",
	"cheese",
	"bacon",
	"broccoli",
	"corn",
	"fish",
	"meat",
]

const INGREDIENT_COSTS := {
	"lettuce": 1,
	"tomato": 1,
	"carrot": 1,
	"onion": 1,
	"bread": 2,
	"egg": 2,
	"mushroom": 2,
	"pumpkin": 2,
	"broccoli": 2,
	"corn": 2,
	"cheese": 3,
	"avocado": 4,
	"sausage": 4,
	"bacon": 4,
	"fish": 4,
	"meat": 5,
}

const RECIPES: Array[Dictionary] = [
	{"id": "garden_salad", "category": "salad", "ingredients": ["lettuce", "tomato", "carrot"], "ingredient_cost": 3, "sale_price": 7, "profit": 4},
	{"id": "avocado_salad", "category": "salad", "ingredients": ["lettuce", "tomato", "avocado"], "ingredient_cost": 6, "sale_price": 19, "profit": 13},
	{"id": "carrot_sausage_soup", "category": "soup", "ingredients": ["sausage", "mushroom", "onion", "carrot"], "ingredient_cost": 8, "sale_price": 14, "profit": 6},
	{"id": "pumpkin_sausage_soup", "category": "soup", "ingredients": ["sausage", "mushroom", "onion", "pumpkin"], "ingredient_cost": 9, "sale_price": 24, "profit": 15},
	{"id": "classic_burger", "category": "burger", "ingredients": ["bread", "meat", "lettuce", "tomato"], "ingredient_cost": 9, "sale_price": 17, "profit": 8},
	{"id": "avocado_burger", "category": "burger", "ingredients": ["bread", "meat", "avocado", "tomato"], "ingredient_cost": 12, "sale_price": 30, "profit": 18},
	{"id": "broccoli_bacon_omelet", "category": "omelet", "ingredients": ["egg", "cheese", "bacon", "broccoli"], "ingredient_cost": 11, "sale_price": 18, "profit": 7},
	{"id": "corn_bacon_omelet", "category": "omelet", "ingredients": ["egg", "cheese", "bacon", "corn"], "ingredient_cost": 11, "sale_price": 27, "profit": 16},
	{"id": "garden_fish_sandwich", "category": "sandwich", "ingredients": ["bread", "fish", "lettuce", "onion"], "ingredient_cost": 8, "sale_price": 15, "profit": 7},
	{"id": "avocado_fish_sandwich", "category": "sandwich", "ingredients": ["bread", "fish", "avocado", "onion"], "ingredient_cost": 11, "sale_price": 28, "profit": 17},
]


static func ingredient_cost(ingredient_id: String) -> int:
	return int(INGREDIENT_COSTS.get(ingredient_id, -1))


static func recipe_by_id(recipe_id: String) -> Dictionary:
	for recipe: Dictionary in RECIPES:
		if String(recipe["id"]) == recipe_id:
			return recipe.duplicate(true)
	return {}


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
