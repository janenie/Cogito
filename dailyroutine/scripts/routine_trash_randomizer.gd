extends Node

@export var manager_path: NodePath
@export var trash_paths: Array[NodePath] = []
@export var min_active_trash := 1
@export var max_active_trash := 2

var active_trash_count := 0

func _ready() -> void:
	randomize()
	randomize_trash()

func randomize_trash() -> void:
	var candidates: Array[Node] = []
	for trash_path in trash_paths:
		var trash := get_node_or_null(trash_path)
		if trash != null:
			candidates.append(trash)
	if candidates.is_empty():
		return

	var active_count := randi_range(min_active_trash, mini(max_active_trash, candidates.size()))
	candidates.shuffle()
	active_trash_count = active_count

	for index in range(candidates.size()):
		var trash := candidates[index]
		var active := index < active_count
		if trash.has_method("set_spawned"):
			trash.set_spawned(active)
		else:
			trash.visible = active

	var manager := get_node_or_null(manager_path)
	if manager != null and manager.has_method("set_required_loose_trash_count"):
		manager.set_required_loose_trash_count(active_count)
