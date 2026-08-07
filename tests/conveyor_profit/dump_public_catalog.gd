extends SceneTree


func _initialize() -> void:
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	var executor: GDScript = load("res://addons/cogito/AIPlay/ai_play_executor.gd")
	var economy: GDScript = load("res://conveyor_profit/scripts/market_economy.gd")
	var recipe_ids: Array[String] = []
	for recipe: Dictionary in catalog.RECIPES:
		recipe_ids.append(String(recipe["id"]))
	print("CONVEYOR_PUBLIC_CATALOG=" + JSON.stringify({
		"ingredient_ids": catalog.INGREDIENT_IDS,
		"recipe_ids": recipe_ids,
		"category_ids": economy.CATEGORIES,
		"executor_ingredient_ids": executor.CONVEYOR_INGREDIENT_IDS,
		"executor_action_types": executor.CONVEYOR_ACTIONS,
	}))
	quit(0)
