extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	var generator: GDScript = load("res://conveyor_profit/scripts/window_supply_generator.gd")
	_check(catalog != null, "recipe catalog loads")
	_check(generator != null, "window supply generator loads")
	_check(
		catalog != null and catalog.has_method("attainable_single_dishes"),
		"catalog exposes exact single-dish enumeration",
	)
	if catalog == null or generator == null or not catalog.has_method("attainable_single_dishes"):
		quit(1)
		return

	var dishes: Array[Dictionary] = catalog.attainable_single_dishes([
		"bread", "egg", "cheese",
	])
	_check(
		dishes.map(func(recipe: Dictionary) -> String: return String(recipe["id"]))
		== ["egg_toast", "cheese_toast"],
		"catalog enumerates every feasible single dish in recipe order",
	)

	var first: Array[Dictionary] = generator.generate(1337, 10)
	var second: Array[Dictionary] = generator.generate(1337, 10)
	_check(first == second, "same seed generates identical windows")
	_check(first.size() == 10, "generator returns ten windows")
	for window: Dictionary in first:
		_check(
			window.keys().size() == 2
			and window.has("ingredients")
			and window.has("best_profit"),
			"window exposes only ingredients and hidden best profit",
		)
		var ingredients: Array = window["ingredients"]
		_check(ingredients.size() == 16, "window contains sixteen real plates")
		var valid_ingredients := true
		for ingredient: Variant in ingredients:
			if not ingredient is String or ingredient not in catalog.INGREDIENT_IDS:
				valid_ingredients = false
		_check(valid_ingredients, "every plate contains a catalog ingredient")
		var candidates: Array[Dictionary] = catalog.attainable_single_dishes(ingredients)
		_check(candidates.size() == 2, "window has exactly two feasible recipes")
		if candidates.size() == 2:
			_check(
				int(candidates[0]["profit"]) != int(candidates[1]["profit"]),
				"candidate recipe profits differ",
			)
		var expected_best := 0
		for recipe: Dictionary in candidates:
			expected_best = maxi(expected_best, int(recipe["profit"]))
		_check(window["best_profit"] == expected_best, "hidden best profit is exact")

	var different: Array[Dictionary] = generator.generate(7331, 10)
	_check(first != different, "different seed changes window supply")
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
