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
	_check(environment.has_node("HUD/MarketPanel/Content/DemandLabel"), "market demand label exists")
	_check(environment.has_node("HUD/MarketPanel/Content/SignalOneLabel"), "first market signal exists")
	_check(environment.has_node("HUD/MarketPanel/Content/SignalTwoLabel"), "second market signal exists")
	var market_panel := environment.get_node("HUD/MarketPanel") as PanelContainer
	_check(market_panel != null, "market panel uses automatic container layout")
	_check(
		(environment.get_node("HUD/StatusLabel") as Label).offset_right
			<= market_panel.offset_left,
		"status text and market panel occupy separate HUD regions",
	)
	_check(
		environment.get_node("HUD/MarketPanel/Content") is VBoxContainer,
		"market labels stack without overlap",
	)
	_check(market_panel.modulate == Color.WHITE, "market panel does not dim child labels")
	_check(market_panel.self_modulate.r < 0.2, "market panel darkens only its own background")
	for label_name: String in ["DemandLabel", "SignalOneLabel", "SignalTwoLabel"]:
		var market_label := environment.get_node("HUD/MarketPanel/Content/%s" % label_name) as Label
		_check(market_label.get_theme_font_size("font_size") >= 22, "%s is readable" % label_name)
	_check_recipe_pages(environment)

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
		_check(candidates.size() == 3, "active window has exactly three candidate dishes")

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
			_check(
				monitor.game_over_screen
				== monitor.get_node_or_null("GameOverScreen"),
				"conveyor monitor uses the shared terminal exit screen",
			)
		var observer: Node = controller.get_node_or_null("Observer")
		_check(observer != null, "conveyor observer is wired")
		_check(observer is ConveyorAIPlayObserver, "preview uses the fixed-camera observer")
	preview.queue_free()

	environment.queue_free()
	quit(1 if not failures.is_empty() else 0)


func _check_recipe_pages(environment: Node) -> void:
	var menu := environment.get_node("Stations/MenuBoard")
	var pages := menu.get_node_or_null("Pages")
	_check(pages != null, "recipe pages container exists")
	_check(pages != null and pages.get_child_count() == 2, "two menu pages exist")
	_check(menu.has_node("PreviousButton"), "previous page control exists")
	_check(menu.has_node("NextButton"), "next page control exists")
	_check(menu.has_node("PageLabel"), "page indicator exists")
	_check(not menu.has_node("RecipeStickers"), "legacy six-sticker menu is removed")


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
