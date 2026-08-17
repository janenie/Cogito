extends SceneTree

const RoutineTrashRandomizer = preload("res://dailyroutine/scripts/routine_trash_randomizer.gd")

var failures: Array[String] = []


class FakeTrash extends Node3D:
	var spawned := false
	var room_id := ""

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

	var grouped_first := _grouped_result_for_seed(2001)
	var grouped_again := _grouped_result_for_seed(2001)
	_assert(
		grouped_first["signature"] == grouped_again["signature"],
		"same seed produces the same grouped trash signature",
	)
	_assert(grouped_first["valid"], "grouped selection activates exactly one trash per room")
	_assert(grouped_first["required"] == 4, "grouped selection reports four required trash items")

	var grouped_signatures := {}
	for seed in range(2001, 2011):
		var result := _grouped_result_for_seed(seed)
		_assert(result["valid"], "grouped seed %d keeps one trash per room" % seed)
		grouped_signatures[result["signature"]] = true
	_assert(grouped_signatures.size() > 1, "different seeds vary grouped trash positions")

	if failures.is_empty():
		print("Routine trash randomizer seed tests passed")
		quit(0)
		return
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


func _grouped_result_for_seed(seed: int) -> Dictionary:
	var fixture := Node3D.new()
	root.add_child(fixture)

	var manager := FakeManager.new()
	manager.name = "Manager"
	fixture.add_child(manager)

	var room_ids := [
		"entry", "entry",
		"living_room", "living_room",
		"kitchen", "kitchen",
		"bedroom", "bedroom",
	]
	var trash_paths: Array[NodePath] = []
	for index in range(room_ids.size()):
		var trash := FakeTrash.new()
		trash.name = "Trash%d" % index
		trash.room_id = room_ids[index]
		fixture.add_child(trash)
		trash_paths.append(NodePath("../Trash%d" % index))

	var randomizer := RoutineTrashRandomizer.new()
	randomizer.name = "Randomizer"
	randomizer.manager_path = NodePath("../Manager")
	randomizer.trash_paths = trash_paths
	randomizer.min_active_trash = 4
	randomizer.max_active_trash = 4
	randomizer.select_one_per_room = true
	randomizer.round_seed = seed
	fixture.add_child(randomizer)
	randomizer.randomize_trash()

	var active_by_room := {
		"entry": 0,
		"living_room": 0,
		"kitchen": 0,
		"bedroom": 0,
	}
	var pieces: Array[String] = []
	for index in range(room_ids.size()):
		var trash := fixture.get_node("Trash%d" % index) as FakeTrash
		pieces.append("1" if trash.spawned else "0")
		if trash.spawned:
			active_by_room[trash.room_id] = int(active_by_room[trash.room_id]) + 1
	var valid := true
	for room_id in active_by_room:
		valid = valid and int(active_by_room[room_id]) == 1
	var result := {
		"signature": "".join(pieces),
		"valid": valid,
		"required": manager.required_loose_trash_count,
	}
	fixture.free()
	return result


func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)
