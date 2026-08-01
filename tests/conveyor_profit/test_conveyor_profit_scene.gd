extends SceneTree

const SCENE_PATH := "res://conveyor_profit/scenes/conveyor_profit_environment.tscn"
const PREVIEW_PATH := "res://conveyor_profit/scenes/conveyor_profit_preview.tscn"

var failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	var packed_scene := load(SCENE_PATH) as PackedScene
	_check(packed_scene != null, "environment scene loads")
	if packed_scene == null:
		quit(1)
		return

	var environment := packed_scene.instantiate()
	root.add_child(environment)
	await process_frame
	_check(environment.has_node("Architecture/Conveyor"), "conveyor exists")
	_check(environment.has_node("Architecture/Conveyor/IngredientPath"), "path exists")
	_check(environment.has_node("Stations/MenuBoard"), "menu exists")
	_check(environment.has_node("Stations/Tray"), "tray exists")
	_check(environment.has_node("Stations/MakeButton"), "make button exists")
	_check(environment.has_node("Stations/UndoButton"), "undo button exists")
	_check(environment.has_node("HUD/TotalTimeLabel"), "total time label exists")
	_check(environment.has_node("HUD/WindowLabel"), "window label exists")
	_check(environment.has_node("HUD/DishLabel"), "dish label exists")
	_check(environment.has_node("HUD/ProfitLabel"), "profit label exists")
	_check(environment.has_node("HUD/StatusLabel"), "status label exists")
	_check_recipe_stickers(environment)

	var path := environment.get_node_or_null("Architecture/Conveyor/IngredientPath") as Path3D
	_check(path != null, "ingredient path is a Path3D")
	if path != null:
		_check(path.curve != null and path.curve.closed, "path is closed")
		_check(path.get_child_count() == 16, "sixteen food slots exist")
		var ingredient_ids: Array[String] = []
		for follower: Node in path.get_children():
			if follower.visible and follower.get_meta("available", false):
				ingredient_ids.append(String(follower.get_meta("ingredient_id", "")))
		_check(ingredient_ids.size() == 16, "all sixteen food slots are filled")
		var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
		var candidates: Array[Dictionary] = catalog.attainable_single_dishes(ingredient_ids)
		_check(candidates.size() == 2, "active window has exactly two candidate dishes")
		if candidates.size() == 2:
			_check(
				int(candidates[0]["profit"]) != int(candidates[1]["profit"]),
				"active candidate dish profits differ",
			)

	var preview := (load(PREVIEW_PATH) as PackedScene).instantiate()
	root.add_child(preview)
	await process_frame
	var controller := preview.get_node_or_null("AIPlayController")
	_check(controller != null, "preview embeds AI Play controller")
	if controller != null:
		_check(not controller.auto_start, "AI Play remains explicitly enabled")
		_check(controller.has_node("ConveyorProfitMonitor"), "conveyor monitor is wired")
		var monitor: Node = controller.get_node_or_null("ConveyorProfitMonitor")
		if monitor != null and "gameplay" in monitor:
			_check(
				monitor.gameplay == preview.get_node("Environment/Gameplay"),
				"monitor controls the preview gameplay",
			)
		var observer: Node = controller.get_node_or_null("Observer")
		_check(observer != null, "conveyor observer is wired")
		_check(observer is ConveyorAIPlayObserver, "preview uses the fixed-camera observer")
	preview.queue_free()

	environment.queue_free()
	quit(1 if not failures.is_empty() else 0)


func _check_recipe_stickers(environment: Node) -> void:
	var menu := environment.get_node("Stations/MenuBoard")
	var stickers := menu.get_node_or_null("RecipeStickers")
	_check(stickers != null, "recipe sticker container exists")
	_check(stickers != null and stickers.get_child_count() == 6, "six recipe stickers exist")
	_check(not menu.has_node("Recipes"), "abbreviated recipe paragraph removed")
	if stickers == null:
		return

	var expected_terms := {
		"Salad": ["沙拉", "SALAD", "生菜", "LETTUCE", "番茄", "TOMATO", "蘑菇", "MUSHROOM", "$7", "+$3"],
		"EggToast": ["鸡蛋吐司", "EGG TOAST", "面包", "BREAD", "鸡蛋", "EGG", "$8", "+$4"],
		"CheeseToast": ["奶酪吐司", "CHEESE TOAST", "面包", "BREAD", "奶酪", "CHEESE", "$10", "+$5"],
		"Burger": ["汉堡", "BURGER", "肉", "MEAT", "生菜", "LETTUCE", "番茄", "TOMATO", "$15", "+$6"],
		"FishSandwich": ["鱼肉三明治", "FISH SANDWICH", "鱼", "FISH", "生菜", "LETTUCE", "$14", "+$7"],
		"MushroomOmelet": ["蘑菇蛋卷", "MUSHROOM OMELET", "鸡蛋", "EGG", "奶酪", "CHEESE", "蘑菇", "MUSHROOM", "$14", "+$7"],
	}
	for sticker_name: String in expected_terms:
		var sticker := stickers.get_node_or_null(sticker_name)
		_check(sticker != null, "%s sticker exists" % sticker_name)
		if sticker == null:
			continue
		for child_name: String in ["Background", "TitleBar", "Title", "Ingredients", "Economy"]:
			_check(sticker.has_node(child_name), "%s has %s" % [sticker_name, child_name])
		var public_text := ""
		for label_name: String in ["Title", "Ingredients", "Economy"]:
			var label := sticker.get_node_or_null(label_name) as Label3D
			if label != null:
				public_text += label.text
		for term: String in expected_terms[sticker_name]:
			_check(public_text.contains(term), "%s contains %s" % [sticker_name, term])


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
