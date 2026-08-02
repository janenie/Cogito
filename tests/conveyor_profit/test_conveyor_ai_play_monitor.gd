extends SceneTree

const ENVIRONMENT_PATH := "res://conveyor_profit/scenes/conveyor_profit_environment.tscn"
const MONITOR_PATH := "res://conveyor_profit/scripts/conveyor_ai_play_monitor.gd"

var failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	var monitor_script := load(MONITOR_PATH) as GDScript
	_check(monitor_script != null, "conveyor AI Play monitor loads")
	if monitor_script == null:
		quit(1)
		return
	var environment := (load(ENVIRONMENT_PATH) as PackedScene).instantiate()
	root.add_child(environment)
	var camera := Camera3D.new()
	camera.position = Vector3(0, 6.7, -10.8)
	camera.rotation = Vector3(-0.36, PI, 0)
	camera.current = true
	root.add_child(camera)
	var monitor: Node = monitor_script.new()
	monitor.gameplay = environment.get_node("Gameplay")
	monitor.camera = camera
	root.add_child(monitor)
	await process_frame

	var gameplay: Node = monitor.gameplay
	var path := environment.get_node("Architecture/Conveyor/IngredientPath") as Path3D
	var ingredient_id := String(path.get_child(0).get_meta("ingredient_id", ""))
	var selected: Dictionary = monitor.execute_semantic_action({
		"type": "select_ingredient",
		"ingredient": ingredient_id,
	})
	_check(
		selected == {
			"status": "completed",
			"type": "select_ingredient",
			"outcome": "selected",
			"ingredient": ingredient_id,
		},
		"monitor exposes only the public selected ingredient",
	)
	for _index: int in 4:
		ingredient_id = String(path.get_child(0).get_meta("ingredient_id", ""))
		_check(
			monitor.execute_semantic_action({
				"type": "select_ingredient",
				"ingredient": ingredient_id,
			})["outcome"] == "selected",
			"monitor fills the bounded tray",
		)
	ingredient_id = String(path.get_child(0).get_meta("ingredient_id", ""))
	_check(
		monitor.execute_semantic_action({
			"type": "select_ingredient",
			"ingredient": ingredient_id,
		}) == {
			"status": "completed",
			"type": "select_ingredient",
			"outcome": "tray_full",
		},
		"monitor exposes a recoverable full-tray result without hidden fields",
	)
	_check(gameplay.get_selected_count() == 5, "monitor cannot grow the tray past five items")
	_check(
		monitor.execute_semantic_action({"type": "wait_next_window"}) == {
			"status": "completed",
			"type": "wait_next_window",
			"outcome": "window_not_complete",
		},
		"unlocked window cannot be skipped",
	)
	monitor.execute_semantic_action({"type": "make"})
	var previous_window: int = gameplay.window_session.current_window_index
	_check(
		monitor.execute_semantic_action({"type": "wait_next_window"})["outcome"]
		== "window_advanced",
		"locked window advances",
	)
	_check(
		gameplay.window_session.current_window_index == previous_window + 1,
		"adapter advances exactly one window",
	)
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	var available: Array[String] = []
	for follower: Node in path.get_children():
		if follower.visible and follower.get_meta("available", false):
			available.append(String(follower.get_meta("ingredient_id", "")))
	var recipes: Array[Dictionary] = catalog.attainable_single_dishes(available)
	_check(not recipes.is_empty(), "advanced window has a public feasible recipe")
	if not recipes.is_empty():
		var recipe: Dictionary = recipes[0]
		for required_id: String in recipe["ingredients"]:
			_check(
				monitor.execute_semantic_action({
					"type": "select_ingredient",
					"ingredient": required_id,
				})["outcome"] == "selected",
				"monitor selects %s for an exact recipe" % required_id,
			)
		_check(
			monitor.execute_semantic_action({"type": "make"}) == {
				"status": "completed",
				"type": "make",
				"outcome": "accepted",
				"recipe_id": recipe["id"],
			},
			"accepted make exposes the current recipe receipt",
		)
	monitor.set_ai_control_active(true)
	var elapsed: float = gameplay.window_session.elapsed_seconds
	gameplay._process(5.0)
	_check(is_equal_approx(gameplay.window_session.elapsed_seconds, elapsed), "AI clock pauses")

	monitor.queue_free()
	camera.queue_free()
	environment.queue_free()
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
