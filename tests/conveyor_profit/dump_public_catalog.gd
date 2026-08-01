extends SceneTree


func _initialize() -> void:
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	var recipe_ids: Array[String] = []
	for recipe: Dictionary in catalog.RECIPES:
		recipe_ids.append(String(recipe["id"]))
	print("CONVEYOR_PUBLIC_CATALOG=" + JSON.stringify({
		"ingredient_ids": catalog.INGREDIENT_IDS,
		"recipe_ids": recipe_ids,
	}))
	quit(0)
