extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	_check(catalog != null, "recipe catalog loads")
	if catalog == null:
		quit(1)
		return

	var expected_costs := {
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
	_check(catalog.INGREDIENT_IDS.size() == 16, "catalog exposes sixteen ingredients")
	for ingredient_id: String in expected_costs:
		_check(
			catalog.ingredient_cost(ingredient_id) == expected_costs[ingredient_id],
			"%s has the approved cost" % ingredient_id,
		)

	var expected_recipes := {
		"garden_salad": [["lettuce", "tomato", "carrot"], 7, 4],
		"avocado_salad": [["lettuce", "tomato", "avocado"], 19, 13],
		"carrot_sausage_soup": [["sausage", "mushroom", "onion", "carrot"], 14, 6],
		"pumpkin_sausage_soup": [["sausage", "mushroom", "onion", "pumpkin"], 24, 15],
		"classic_burger": [["bread", "meat", "lettuce", "tomato"], 17, 8],
		"avocado_burger": [["bread", "meat", "avocado", "tomato"], 30, 18],
		"broccoli_bacon_omelet": [["egg", "cheese", "bacon", "broccoli"], 18, 7],
		"corn_bacon_omelet": [["egg", "cheese", "bacon", "corn"], 27, 16],
		"garden_fish_sandwich": [["bread", "fish", "lettuce", "onion"], 15, 7],
		"avocado_fish_sandwich": [["bread", "fish", "avocado", "onion"], 28, 17],
	}
	_check(catalog.RECIPES.size() == 10, "catalog exposes ten recipes")
	for recipe_id: String in expected_recipes:
		var expected: Array = expected_recipes[recipe_id]
		var recipe: Dictionary = catalog.find_recipe(expected[0])
		_check(recipe.get("id", "") == recipe_id, "%s matches regardless of order" % recipe_id)
		_check(recipe.get("sale_price", -1) == expected[1], "%s has the approved sale price" % recipe_id)
		_check(recipe.get("profit", -1) == expected[2], "%s has the approved profit" % recipe_id)

	_check(catalog.find_recipe(["lettuce", "tomato", "tomato"]).is_empty(), "duplicates do not match")
	_check(catalog.find_recipe(["bread", "unknown"]).is_empty(), "unknown ingredients do not match")
	_check(catalog.ingredient_cost("unknown") == -1, "unknown cost rejected")
	_check(catalog.max_attainable_profit(["lettuce", "tomato", "carrot"]) == 4, "one garden salad profit")
	_check(
		catalog.max_attainable_profit([
			"lettuce", "tomato", "carrot", "lettuce", "tomato", "avocado",
		]) == 17,
		"multiple dishes use the best attainable combination",
	)
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
