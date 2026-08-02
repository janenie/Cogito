extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	var decks_script: GDScript = load("res://conveyor_profit/scripts/fixed_window_decks.gd")
	_check(decks_script != null, "fixed window decks load")
	if decks_script == null:
		quit(1)
		return

	var decks: Array = decks_script.DECKS
	_check(decks.size() == 5, "five authored decks are available")
	var seen_ids: Dictionary = {}
	for deck: Dictionary in decks:
		var deck_id := String(deck.get("id", ""))
		_check(not deck_id.is_empty() and not seen_ids.has(deck_id), "deck IDs are unique")
		seen_ids[deck_id] = true
		var windows: Array = deck.get("windows", [])
		_check(windows.size() == 10, "deck %s has ten fixed windows" % deck_id)
		for window_index: int in windows.size():
			_validate_window(catalog, deck_id, window_index, windows[window_index])
	quit(1 if not failures.is_empty() else 0)


func _validate_window(
	catalog: GDScript,
	deck_id: String,
	window_index: int,
	window: Dictionary,
) -> void:
	var label := "deck %s window %d" % [deck_id, window_index + 1]
	var ingredients: Array = window.get("ingredients", [])
	_check(ingredients.size() == 16, "%s has sixteen plates" % label)
	for ingredient_id: Variant in ingredients:
		_check(
			ingredient_id is String and ingredient_id in catalog.INGREDIENT_IDS,
			"%s uses only public ingredients" % label,
		)

	var feasible: Array[Dictionary] = catalog.attainable_single_dishes(ingredients)
	_check(feasible.size() == 2, "%s has exactly two feasible recipes" % label)
	if feasible.size() == 2:
		_check(
			int(feasible[0]["profit"]) != int(feasible[1]["profit"]),
			"%s feasible recipes have unequal profits" % label,
		)

	var feasible_best := 0
	for recipe: Dictionary in feasible:
		feasible_best = maxi(feasible_best, int(recipe["profit"]))
	var decoy_id := String(window.get("decoy_recipe_id", ""))
	var qualifying_decoys: Array[String] = []
	for recipe: Dictionary in catalog.RECIPES:
		var missing := _missing_ingredient_count(recipe["ingredients"], ingredients)
		if missing == 1 and int(recipe["profit"]) > feasible_best:
			qualifying_decoys.append(String(recipe["id"]))
	_check(
		qualifying_decoys == [decoy_id],
		"%s has exactly its designated higher-profit one-missing decoy" % label,
	)


func _missing_ingredient_count(required: Array, available: Array) -> int:
	var remaining: Array = available.duplicate()
	var missing := 0
	for ingredient_id: Variant in required:
		var index := remaining.find(ingredient_id)
		if index < 0:
			missing += 1
		else:
			remaining.remove_at(index)
	return missing


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
