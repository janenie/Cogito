extends SceneTree

const SCENE_PATH := "res://conveyor_profit/scenes/conveyor_profit_environment.tscn"

var failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	var packed_scene := load(SCENE_PATH) as PackedScene
	var environment := packed_scene.instantiate()
	root.add_child(environment)
	await process_frame

	var gameplay := environment.get_node_or_null("Gameplay")
	_check(gameplay != null, "gameplay controller exists")
	if gameplay == null:
		environment.queue_free()
		quit(1)
		return
	_check(gameplay.get_profit() == 0, "initial profit is zero")
	_check(gameplay.get_selected_count() == 0, "initial tray is empty")
	_check(gameplay.get_remaining_count() > 0, "finite supply is available")
	var public_state: Dictionary = gameplay.get_public_state()
	for field: String in [
		"total_time", "window", "window_time", "dish", "net_profit", "tray", "finished",
	]:
		_check(public_state.has(field), "public state contains %s" % field)
	for hidden_field: String in [
		"ingredients", "candidate_recipes", "best_profit", "future_supply", "seed", "passing_profit",
	]:
		_check(not public_state.has(hidden_field), "public state hides %s" % hidden_field)

	var path := environment.get_node("Architecture/Conveyor/IngredientPath") as Path3D
	for follower: Node in path.get_children():
		if not follower.visible:
			continue
		var interactable := follower.get_node_or_null("IngredientPreview/Interactable") as Area3D
		_check(interactable != null, "%s has interactable" % follower.name)
		_check(
			interactable != null and interactable.get_node_or_null("CollisionShape3D") != null,
			"%s has click collision" % follower.name,
		)

	var first_interactable := path.get_child(0).get_node("IngredientPreview/Interactable")
	first_interactable.select()
	_check(gameplay.get_selected_count() == 1, "ingredient click enters tray")
	var tray_label := environment.get_node("Stations/Tray/TrayLabel") as Label3D
	_check(not tray_label.text.contains("EMPTY"), "tray label shows selection")

	var undo_button := environment.get_node("Stations/UndoButton")
	undo_button.activate()
	_check(gameplay.get_selected_count() == 0, "undo empties one-item tray")

	first_interactable.select()
	_check(gameplay.get_selected_count() == 1, "tray can hold an expiring ingredient")
	gameplay.advance_time(60.0)
	_check(gameplay.window_session.current_window_index == 1, "boundary enters window two")
	_check(gameplay.get_selected_count() == 0, "tray expires at the boundary")

	var available_ids := _available_ingredient_ids(path)
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	var candidates: Array[Dictionary] = catalog.attainable_single_dishes(available_ids)
	_check(not candidates.is_empty(), "new window has a feasible dish")
	if not candidates.is_empty():
		var recipe: Dictionary = candidates[-1]
		for ingredient_id: String in recipe["ingredients"]:
			var interactable := _find_interactable(path, ingredient_id)
			_check(interactable != null, "recipe ingredient %s is visible" % ingredient_id)
			if interactable != null:
				interactable.select()
		environment.get_node("Stations/MakeButton").activate()
		_check(gameplay.get_profit() == recipe["profit"], "legal dish earns its net profit")
		_check(gameplay.window_session.dish_made, "legal dish locks the active window")
		_check(gameplay.request_make()["outcome"] == "window_locked", "second make is rejected")
		var profit_label := environment.get_node("HUD/ProfitLabel") as Label
		_check(profit_label.text == "NET PROFIT  $%d" % recipe["profit"], "HUD publishes net profit")
	gameplay.advance_time(60.0)
	_check(gameplay.window_session.current_window_index == 2, "next boundary enters window three")
	_check(not gameplay.window_session.dish_made, "new window restores dish allowance")

	var camera := Camera3D.new()
	camera.position = Vector3(0, 6.7, -10.8)
	camera.rotation = Vector3(-0.36, PI, 0)
	camera.current = true
	root.add_child(camera)
	await process_frame
	_check(
		gameplay.request_select_ingredient("potato", camera)["outcome"] == "invalid_ingredient",
		"unknown English ingredient ID is rejected",
	)
	var visible_ids := _available_ingredient_ids(path)
	_check(not visible_ids.is_empty(), "window three has selectable ingredients")
	if not visible_ids.is_empty():
		var requested_id := visible_ids[0]
		var semantic_result: Dictionary = gameplay.request_select_ingredient(requested_id, camera)
		_check(
			semantic_result == {"outcome": "selected", "ingredient": requested_id},
			"semantic action selects a visible named ingredient",
		)
		camera.cull_mask = 0
		_check(
			gameplay.request_select_ingredient(requested_id, camera)["outcome"]
			== "ingredient_not_available",
			"semantic action rejects an ingredient outside the rendered view",
		)

	camera.queue_free()
	environment.queue_free()
	quit(1 if not failures.is_empty() else 0)


func _find_interactable(path: Path3D, ingredient_id: String) -> Node:
	for follower: Node in path.get_children():
		if follower.visible and follower.get_meta("ingredient_id", "") == ingredient_id:
			return follower.get_node("IngredientPreview/Interactable")
	return null


func _available_ingredient_ids(path: Path3D) -> Array[String]:
	var result: Array[String] = []
	for follower: Node in path.get_children():
		if follower.visible and follower.get_meta("available", false):
			result.append(String(follower.get_meta("ingredient_id", "")))
	return result


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
