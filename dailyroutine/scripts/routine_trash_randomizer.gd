extends Node

const ROUND_SEED_PARSER = preload(
	"res://addons/cogito/AIPlay/ai_play_round_seed.gd"
)

@export var manager_path: NodePath
@export var trash_paths: Array[NodePath] = []
@export var min_active_trash := 1
@export var max_active_trash := 2
@export var select_one_per_room := false
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
	var active_candidates := _select_active_candidates(candidates, rng)
	var active_count := active_candidates.size()
	active_trash_count = active_count

	for trash in candidates:
		var active := active_candidates.has(trash)
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
	var parsed: Dictionary = ROUND_SEED_PARSER.parse(
		OS.get_cmdline_user_args(),
		true,
	)
	if not parsed["valid"]:
		push_error("Invalid AI Play round seed argument")
		return round_seed
	if parsed["provided"]:
		return ROUND_SEED_PARSER.runtime_seed(int(parsed["value"]))
	return round_seed

func _select_active_candidates(
	candidates: Array[Node],
	rng: RandomNumberGenerator,
) -> Array[Node]:
	if not select_one_per_room:
		var active_count := rng.randi_range(
			min_active_trash,
			mini(max_active_trash, candidates.size()),
		)
		var shuffled := candidates.duplicate()
		_shuffle_candidates(shuffled, rng)
		return shuffled.slice(0, active_count)

	var candidates_by_room: Dictionary = {}
	for candidate in candidates:
		var room_id := str(candidate.get("room_id"))
		if room_id.is_empty():
			push_error("Grouped trash candidate is missing room_id")
			return []
		var room_candidates: Array = candidates_by_room.get(room_id, [])
		room_candidates.append(candidate)
		candidates_by_room[room_id] = room_candidates

	var room_ids: Array = candidates_by_room.keys()
	room_ids.sort()
	var selected: Array[Node] = []
	for room_id in room_ids:
		var room_candidates: Array = candidates_by_room[room_id]
		selected.append(room_candidates[rng.randi_range(0, room_candidates.size() - 1)])
	return selected

func _shuffle_candidates(candidates: Array[Node], rng: RandomNumberGenerator) -> void:
	for index in range(candidates.size() - 1, 0, -1):
		var swap_index := rng.randi_range(0, index)
		var current := candidates[index]
		candidates[index] = candidates[swap_index]
		candidates[swap_index] = current
