extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	var economy: GDScript = load("res://conveyor_profit/scripts/market_economy.gd")
	_check(catalog != null, "recipe catalog loads")
	_check(economy != null, "market economy loads")
	if catalog == null or economy == null:
		quit(1)
		return

	var expected_categories := {
		"garden_salad": "salad",
		"avocado_salad": "salad",
		"carrot_sausage_soup": "soup",
		"pumpkin_sausage_soup": "soup",
		"classic_burger": "burger",
		"avocado_burger": "burger",
		"broccoli_bacon_omelet": "omelet",
		"corn_bacon_omelet": "omelet",
		"garden_fish_sandwich": "sandwich",
		"avocado_fish_sandwich": "sandwich",
	}
	for recipe_id: String in expected_categories:
		var recipe: Dictionary = catalog.recipe_by_id(recipe_id)
		_check(String(recipe.get("category", "")) == expected_categories[recipe_id], "%s category is stable" % recipe_id)
		_check(int(recipe.get("ingredient_cost", -1)) == int(recipe["sale_price"]) - int(recipe["profit"]), "%s stores exact ingredient cost" % recipe_id)

	_check(economy.adjusted_sale_price("avocado_burger", 0.75) == 23, "22.5 sale rounds up")
	_check(economy.adjusted_profit("avocado_burger", 0.75) == 11, "ingredient cost stays fixed")
	_check(economy.adjusted_profit("corn_bacon_omelet", 1.5) == 30, "40.5 sale rounds up")
	_check(economy.adjusted_profit("garden_salad", 1.25) == 6, "garden salad high-demand profit is exact")
	for multiplier: float in [0.75, 1.0, 1.25, 1.5]:
		_check(economy.is_valid_multiplier(multiplier), "%s multiplier is valid" % multiplier)
	_check(not economy.is_valid_multiplier(1.1), "arbitrary multiplier is rejected")
	_check(economy.adjusted_sale_price("missing_recipe", 1.0) == -1, "unknown recipe is rejected")
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
