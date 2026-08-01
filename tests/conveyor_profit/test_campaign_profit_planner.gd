extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	var decks_script: GDScript = load("res://conveyor_profit/scripts/fixed_window_decks.gd")
	var planner: GDScript = load("res://conveyor_profit/scripts/campaign_profit_planner.gd")
	_check(planner != null, "campaign profit planner loads")
	if planner == null:
		quit(1)
		return

	var fixture: Array[Dictionary] = [
		{"ingredients": ["egg", "cheese", "bacon", "corn", "lettuce", "tomato", "carrot"]},
		{"ingredients": ["egg", "cheese", "bacon", "corn", "sausage", "mushroom", "onion", "carrot"]},
		{"ingredients": ["egg", "cheese", "bacon", "corn", "sausage", "mushroom", "onion", "pumpkin"]},
	]
	_check(planner.max_profit(fixture) == 47, "global optimum saves the third local alternative")
	_check(
		planner.is_optimal_choice(fixture, 2, {"corn_bacon_omelet": 2}, "pumpkin_sausage_soup"),
		"an available lower-profit recipe is optimal after the local best reaches quota",
	)
	_check(
		not planner.is_optimal_choice(fixture, 2, {"corn_bacon_omelet": 2}, "corn_bacon_omelet"),
		"a recipe at quota cannot be an optimal choice",
	)

	for deck: Dictionary in decks_script.DECKS:
		var windows: Array[Dictionary] = []
		for authored: Dictionary in deck["windows"]:
			windows.append({"ingredients": authored["ingredients"]})
		var deck_id := String(deck["id"])
		_check(planner.max_profit(windows) == 136, "deck %s has the hand-checked optimum" % deck_id)
		_check(
			_count_canonical_quota_pressure(catalog, planner, windows) >= 2,
			"deck %s has at least two quota-pressure windows" % deck_id,
		)
	quit(1 if not failures.is_empty() else 0)


func _count_canonical_quota_pressure(
	catalog: GDScript,
	planner: GDScript,
	windows: Array[Dictionary],
) -> int:
	var counts: Dictionary = {}
	var pressure_count := 0
	for window_index: int in windows.size():
		var feasible: Array[Dictionary] = catalog.attainable_single_dishes(
			windows[window_index]["ingredients"],
		)
		feasible.sort_custom(func(left: Dictionary, right: Dictionary) -> bool:
			return int(left["profit"]) > int(right["profit"])
		)
		var local_best_id := String(feasible[0]["id"])
		var selected_id := ""
		for recipe: Dictionary in feasible:
			var recipe_id := String(recipe["id"])
			if planner.is_optimal_choice(windows, window_index, counts, recipe_id):
				selected_id = recipe_id
				break
		_check(not selected_id.is_empty(), "canonical optimal route remains complete")
		if selected_id.is_empty():
			return pressure_count
		if selected_id != local_best_id and int(counts.get(local_best_id, 0)) == 2:
			pressure_count += 1
		counts[selected_id] = int(counts.get(selected_id, 0)) + 1
	return pressure_count


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
