extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	_check(catalog != null, "recipe catalog loads")
	if catalog == null:
		quit(1)
		return

	var salad: Dictionary = catalog.find_recipe(["tomato", "mushroom", "lettuce"])
	_check(salad.get("id", "") == "salad", "recipe matching ignores order")
	_check(catalog.find_recipe(["lettuce", "tomato", "tomato"]).is_empty(), "duplicates do not match")
	_check(catalog.find_recipe(["bread", "unknown"]).is_empty(), "unknown ingredients do not match")
	_check(catalog.ingredient_cost("lettuce") == 1, "lettuce cost")
	_check(catalog.ingredient_cost("cheese") == 3, "cheese cost")
	_check(catalog.ingredient_cost("meat") == 5, "meat cost")
	_check(catalog.ingredient_cost("unknown") == -1, "unknown cost rejected")
	_check(catalog.max_attainable_profit(["bread", "fish", "lettuce"]) == 7, "one fish sandwich profit")
	_check(
		catalog.max_attainable_profit(["bread", "fish", "lettuce", "bread", "fish", "lettuce"]) == 14,
		"two fish sandwich profit",
	)
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
