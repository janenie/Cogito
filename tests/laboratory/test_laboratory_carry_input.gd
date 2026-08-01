extends SceneTree

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	var player_scene: PackedScene = load(
		"res://addons/cogito/PackedScenes/cogito_player.tscn"
	)
	var component_scene: PackedScene = load(
		"res://addons/cogito/DemoScenes/Laboratory/laboratory_experiment_component.tscn"
	)
	var player: Node = player_scene.instantiate()
	var component: Node = component_scene.instantiate()
	root.add_child(player)
	root.add_child(component)
	await process_frame

	var interaction: Node = player.get_node("PlayerInteractionComponent")
	var carryable: Node = component.get_node("CarryableComponent")
	component.global_position = player.global_position + Vector3(0.0, 0.7, -0.35)
	carryable.interact(interaction)
	_assert(carryable.is_being_carried, "first E press starts carrying")
	await physics_frame
	await physics_frame
	_assert(
		carryable.is_being_carried,
		"a close floor component remains carried after physics contact",
	)

	component.queue_free()
	player.queue_free()
	await process_frame
	_finish()


func _finish() -> void:
	if _failures.is_empty():
		print("Laboratory carry input test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
