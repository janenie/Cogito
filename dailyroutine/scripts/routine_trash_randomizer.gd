extends Node

@export var manager_path: NodePath
@export var trash_paths: Array[NodePath] = []
@export var min_active_trash := 1
@export var max_active_trash := 2
@export var round_seed := 0

var active_trash_count := 0
var _retry_generation := 0

func _ready() -> void:
	round_seed = _resolve_round_seed()
	var manager := get_node_or_null(manager_path)
	if manager != null and manager.has_signal("routine_retried"):
		manager.routine_retried.connect(_on_routine_retried)
	randomize_trash()

func randomize_trash() -> void:
	var candidates: Array[Node] = []
	for trash_path in trash_paths:
		var trash := get_node_or_null(trash_path)
		if trash != null:
			candidates.append(trash)
	if candidates.is_empty():
		return

	var rng := RandomNumberGenerator.new()
	rng.seed = _effective_seed()
	var active_count := rng.randi_range(min_active_trash, mini(max_active_trash, candidates.size()))
	_shuffle_candidates(candidates, rng)
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

func _on_routine_retried() -> void:
	_retry_generation += 1
	randomize_trash()

func _effective_seed() -> int:
	if round_seed != 0:
		return round_seed + _retry_generation
	return int(Time.get_ticks_usec()) + _retry_generation

func _resolve_round_seed() -> int:
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("--ai-play-seed="):
			var value := argument.trim_prefix("--ai-play-seed=")
			if value.is_valid_int():
				return int(value)
	return round_seed

func _shuffle_candidates(candidates: Array[Node], rng: RandomNumberGenerator) -> void:
	for index in range(candidates.size() - 1, 0, -1):
		var swap_index := rng.randi_range(0, index)
		var current := candidates[index]
		candidates[index] = candidates[swap_index]
		candidates[swap_index] = current
