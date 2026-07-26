extends SceneTree

const RoutineTrashRandomizer = preload("res://dailyroutine/scripts/routine_trash_randomizer.gd")

var failures: Array[String] = []


class FakeTrash extends Node3D:
	var spawned := false

	func set_spawned(active: bool) -> void:
		spawned = active
		visible = active


class FakeManager extends Node:
	var required_loose_trash_count := 0

	func set_required_loose_trash_count(count: int) -> void:
		required_loose_trash_count = count


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var first := _signature_for_seed(1001)
	var again := _signature_for_seed(1001)
	_assert(first == again, "same seed produces the same visible trash signature")

	var signatures := {}
	for seed in range(1001, 1011):
		signatures[_signature_for_seed(seed)] = true
	_assert(signatures.size() > 1, "different seeds produce more than one trash signature")

	if failures.is_empty():
		print("Routine trash randomizer seed tests passed")
		quit(0)
	for failure: String in failures:
		push_error(failure)
	quit(1)


func _signature_for_seed(seed: int) -> String:
	var fixture := Node3D.new()
	root.add_child(fixture)

	var manager := FakeManager.new()
	manager.name = "Manager"
	fixture.add_child(manager)

	var randomizer := RoutineTrashRandomizer.new()
	randomizer.name = "Randomizer"
	randomizer.manager_path = NodePath("../Manager")
	randomizer.trash_paths = [
		NodePath("../Trash0"),
		NodePath("../Trash1"),
		NodePath("../Trash2"),
		NodePath("../Trash3"),
	]
	randomizer.min_active_trash = 1
	randomizer.max_active_trash = 2
	randomizer.round_seed = seed
	fixture.add_child(randomizer)

	for index in range(4):
		var trash := FakeTrash.new()
		trash.name = "Trash%d" % index
		fixture.add_child(trash)

	randomizer.randomize_trash()
	var pieces: Array[String] = []
	for index in range(4):
		var trash := fixture.get_node("Trash%d" % index) as FakeTrash
		pieces.append("1" if trash.spawned else "0")
	var signature := "".join(pieces) + ":%d" % manager.required_loose_trash_count
	fixture.free()
	return signature


func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)
