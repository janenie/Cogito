extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	var generator: GDScript = load("res://conveyor_profit/scripts/supply_generator.gd")
	_check(generator != null, "supply generator loads")
	if generator == null:
		quit(1)
		return

	for seed: int in [0, 1, 2, 7, 42, 999]:
		var first: Array[String] = generator.generate(seed, 120)
		var second: Array[String] = generator.generate(seed, 120)
		_check(first == second, "seed %d is deterministic" % seed)
		_check(not first.is_empty(), "seed %d is non-empty" % seed)
		_check(first.size() < 128, "seed %d is finite" % seed)
		for ingredient_id: String in first:
			_check(catalog.ingredient_cost(ingredient_id) >= 0, "seed %d has valid IDs" % seed)
		_check(
			catalog.max_attainable_profit(first) >= 120,
			"seed %d has at least 120 attainable profit" % seed,
		)
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
