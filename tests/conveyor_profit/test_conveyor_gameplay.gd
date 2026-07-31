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

	var bread := _find_interactable(path, "bread")
	var egg := _find_interactable(path, "egg")
	_check(bread != null, "default visible supply contains bread")
	_check(egg != null, "default visible supply contains egg")
	if bread != null and egg != null:
		bread.select()
		egg.select()
		environment.get_node("Stations/MakeButton").activate()
		_check(gameplay.get_profit() == 4, "egg toast earns four net profit")
		var profit_label := environment.get_node("HUD/ProfitLabel") as Label
		_check(profit_label.text.contains("$4 / $100"), "HUD publishes updated profit")

	environment.queue_free()
	quit(1 if not failures.is_empty() else 0)


func _find_interactable(path: Path3D, ingredient_id: String) -> Node:
	for follower: Node in path.get_children():
		if follower.visible and follower.get_meta("ingredient_id", "") == ingredient_id:
			return follower.get_node("IngredientPreview/Interactable")
	return null


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
