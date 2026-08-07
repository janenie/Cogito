extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	var campaigns_script: GDScript = load("res://conveyor_profit/scripts/market_campaigns.gd")
	var generator: GDScript = load("res://conveyor_profit/scripts/window_supply_generator.gd")
	_check(catalog != null, "recipe catalog loads")
	_check(campaigns_script != null, "market campaigns load")
	_check(generator != null, "window supply generator loads")
	if catalog == null or campaigns_script == null or generator == null:
		quit(1)
		return

	for campaign: Dictionary in campaigns_script.CAMPAIGNS:
		for seed_value: int in [7, 1337, 7331]:
			var first: Array[Dictionary] = generator.generate(campaign, seed_value)
			var second: Array[Dictionary] = generator.generate(campaign, seed_value)
			_check(first == second, "campaign %s seed %d is deterministic" % [campaign["id"], seed_value])
			_check(first.size() == 10, "campaign %s has ten generated windows" % campaign["id"])
			for window_index: int in first.size():
				var window: Dictionary = first[window_index]
				_check(window.keys() == ["ingredients", "category_multipliers", "signals"], "generated window exposes only current public data")
				var ingredients: Array = window.get("ingredients", [])
				_check(ingredients.size() == 16, "generated window has sixteen plates")
				for ingredient_id: Variant in ingredients:
					_check(ingredient_id is String and ingredient_id in catalog.INGREDIENT_IDS, "generated plate uses public ingredient")
				var actual_ids: Array[String] = []
				for recipe: Dictionary in catalog.attainable_single_dishes(ingredients):
					actual_ids.append(String(recipe["id"]))
				actual_ids.sort()
				var expected_ids: Array = campaign["rounds"][window_index]["candidate_recipe_ids"].duplicate()
				expected_ids.sort()
				_check(actual_ids == expected_ids, "campaign %s round %d preserves exactly three candidates" % [campaign["id"], window_index + 1])
				_check(window["category_multipliers"] == campaign["rounds"][window_index]["category_multipliers"], "current market is copied exactly")
				_check(window["signals"] == campaign["rounds"][window_index]["signals"], "current signals are copied exactly")

		var seed_seven: Array[Dictionary] = generator.generate(campaign, 7)
		var seed_other: Array[Dictionary] = generator.generate(campaign, 7331)
		_check(seed_seven != seed_other, "campaign %s changes plate composition or order across seeds" % campaign["id"])
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
