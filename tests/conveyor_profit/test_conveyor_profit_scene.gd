extends SceneTree

const SCENE_PATH := "res://conveyor_profit/scenes/conveyor_profit_environment.tscn"

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
	_check(environment.has_node("HUD/ProfitLabel"), "profit label exists")

	var path := environment.get_node_or_null("Architecture/Conveyor/IngredientPath") as Path3D
	_check(path != null, "ingredient path is a Path3D")
	if path != null:
		_check(path.curve != null and path.curve.closed, "path is closed")
		_check(path.get_child_count() == 16, "sixteen food slots exist")
		var ingredient_ids: Dictionary = {}
		for follower: Node in path.get_children():
			ingredient_ids[follower.get_meta("ingredient_id", "")] = true
		ingredient_ids.erase("")
		_check(ingredient_ids.keys().size() == 8, "all ingredient types exist")

	environment.queue_free()
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
