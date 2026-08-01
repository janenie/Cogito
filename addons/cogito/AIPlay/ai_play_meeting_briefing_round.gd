class_name AIPlayMeetingBriefingRound
extends RefCounted

const FOLDER_IDS: Array[String] = ["atlas", "birch", "crown", "delta"]
const SEAT_IDS: Array[String] = [
	"tv_side",
	"door_side",
	"opposite_tv",
	"inner_wall",
]
const RECORD_IDS: Array[String] = ["ceo", "archive", "break_room"]
const FOLDER_LABELS := {
	"atlas": "李明",
	"birch": "王芳",
	"crown": "陈宇",
	"delta": "赵宁",
}
const SEAT_LABELS := {
	"tv_side": "电视侧 (TV SIDE)",
	"door_side": "会议室门侧 (DOOR SIDE)",
	"opposite_tv": "电视对面侧 (OPPOSITE TV)",
	"inner_wall": "内墙侧 (INNER WALL)",
}

var _configured: bool = false
var _seed: int = 0
var _solution: Dictionary = {}
var _clues: Array[Dictionary] = []
var _record_clues: Dictionary = {}
var _assignments: Array[Dictionary] = []


func configure(seed_value: int) -> bool:
	_configured = false
	_seed = 0
	_solution.clear()
	_clues.clear()
	_record_clues.clear()
	_assignments = _enumerate_assignments()

	var rng := RandomNumberGenerator.new()
	if seed_value == 0:
		rng.randomize()
	else:
		rng.seed = seed_value
	_seed = int(rng.seed)

	var shuffled_seats: Array[String] = SEAT_IDS.duplicate()
	_shuffle_with_rng(shuffled_seats, rng)
	for index: int in range(FOLDER_IDS.size()):
		_solution[FOLDER_IDS[index]] = shuffled_seats[index]

	var candidates: Array[Dictionary] = _true_candidate_clues(_solution)
	var candidate_masks: Array[int] = []
	var all_mask: int = (1 << _assignments.size()) - 1
	for clue: Dictionary in candidates:
		var mask: int = _clue_mask(clue, _assignments)
		if mask != all_mask:
			candidate_masks.append(mask)
		else:
			push_error("Meeting briefing generator produced an ineffective clue")
			return false

	var eligible_triplets: Array[Array] = []
	for first_index: int in range(candidates.size() - 2):
		for second_index: int in range(first_index + 1, candidates.size() - 1):
			var first_second_mask: int = (
				candidate_masks[first_index] & candidate_masks[second_index]
			)
			if _bit_count(first_second_mask) < 2:
				continue
			for third_index: int in range(second_index + 1, candidates.size()):
				if _bit_count(
					candidate_masks[first_index] & candidate_masks[third_index]
				) < 2:
					continue
				if _bit_count(
					candidate_masks[second_index] & candidate_masks[third_index]
				) < 2:
					continue
				var combined_mask: int = first_second_mask & candidate_masks[third_index]
				if _bit_count(combined_mask) == 1:
					eligible_triplets.append([
						first_index,
						second_index,
						third_index,
					])

	if eligible_triplets.is_empty():
		push_error("Meeting briefing generator found no minimal unique clue set")
		return false

	var selected_indexes: Array = eligible_triplets[
		rng.randi_range(0, eligible_triplets.size() - 1)
	]
	for candidate_index: int in selected_indexes:
		_clues.append(candidates[candidate_index].duplicate(true))
	_shuffle_with_rng(_clues, rng)

	var shuffled_records: Array[String] = RECORD_IDS.duplicate()
	_shuffle_with_rng(shuffled_records, rng)
	for clue_index: int in range(_clues.size()):
		_record_clues[shuffled_records[clue_index]] = clue_index

	_configured = true
	return true


func all_assignments() -> Array[Dictionary]:
	if _assignments.is_empty():
		_assignments = _enumerate_assignments()
	return _assignments.duplicate(true)


func solve(clues: Array) -> Array[Dictionary]:
	var matches: Array[Dictionary] = []
	for assignment: Dictionary in all_assignments():
		var matches_all: bool = true
		for clue: Variant in clues:
			if not clue is Dictionary or not clue_matches(clue, assignment):
				matches_all = false
				break
		if matches_all:
			matches.append(assignment.duplicate(true))
	return matches


func clue_matches(clue: Dictionary, assignment: Dictionary) -> bool:
	var kind: String = str(clue.get("kind", ""))
	match kind:
		"exact_seat":
			var exact_folder: String = str(clue.get("folder", ""))
			var exact_seat: String = str(clue.get("seat", ""))
			return (
				exact_folder in FOLDER_IDS
				and exact_seat in SEAT_IDS
				and assignment.get(exact_folder, "") == exact_seat
			)
		"not_seat":
			var excluded_folder: String = str(clue.get("folder", ""))
			var excluded_seat: String = str(clue.get("seat", ""))
			return (
				excluded_folder in FOLDER_IDS
				and excluded_seat in SEAT_IDS
				and assignment.has(excluded_folder)
				and assignment[excluded_folder] != excluded_seat
			)
		"adjacent", "opposite":
			var folder_a: String = str(clue.get("folder_a", ""))
			var folder_b: String = str(clue.get("folder_b", ""))
			if (
				folder_a not in FOLDER_IDS
				or folder_b not in FOLDER_IDS
				or folder_a == folder_b
			):
				return false
			var first_seat_index: int = SEAT_IDS.find(assignment.get(folder_a, ""))
			var second_seat_index: int = SEAT_IDS.find(assignment.get(folder_b, ""))
			if first_seat_index < 0 or second_seat_index < 0:
				return false
			var distance: int = abs(first_seat_index - second_seat_index)
			if kind == "adjacent":
				return distance == 1 or distance == SEAT_IDS.size() - 1
			return distance == SEAT_IDS.size() / 2
		"clockwise_next":
			var from_folder: String = str(clue.get("from_folder", ""))
			var to_folder: String = str(clue.get("to_folder", ""))
			if (
				from_folder not in FOLDER_IDS
				or to_folder not in FOLDER_IDS
				or from_folder == to_folder
			):
				return false
			var from_index: int = SEAT_IDS.find(assignment.get(from_folder, ""))
			var to_index: int = SEAT_IDS.find(assignment.get(to_folder, ""))
			return (
				from_index >= 0
				and to_index == (from_index + 1) % SEAT_IDS.size()
			)
	return false


func canonical_clue_key(clue: Dictionary) -> String:
	var kind: String = str(clue.get("kind", ""))
	match kind:
		"exact_seat", "not_seat":
			return "%s:%s:%s" % [
				kind,
				str(clue.get("folder", "")),
				str(clue.get("seat", "")),
			]
		"adjacent", "opposite":
			var pair: Array[String] = _canonical_folder_pair(
				str(clue.get("folder_a", "")),
				str(clue.get("folder_b", "")),
			)
			return "%s:%s:%s" % [kind, pair[0], pair[1]]
		"clockwise_next":
			return "%s:%s:%s" % [
				kind,
				str(clue.get("from_folder", "")),
				str(clue.get("to_folder", "")),
			]
	return "invalid:%s" % str(clue)


func clue_text(clue: Dictionary) -> String:
	var kind: String = str(clue.get("kind", ""))
	match kind:
		"exact_seat":
			return "%s的资料属于%s席位。" % [
				_folder_label(clue.get("folder", "")),
				_seat_label(clue.get("seat", "")),
			]
		"not_seat":
			return "%s的资料不属于%s席位。" % [
				_folder_label(clue.get("folder", "")),
				_seat_label(clue.get("seat", "")),
			]
		"adjacent":
			return "%s与%s的资料席位相邻。" % [
				_folder_label(clue.get("folder_a", "")),
				_folder_label(clue.get("folder_b", "")),
			]
		"opposite":
			return "%s与%s的资料席位相对。" % [
				_folder_label(clue.get("folder_a", "")),
				_folder_label(clue.get("folder_b", "")),
			]
		"clockwise_next":
			return "%s的资料席位是%s资料席位的顺时针下一席。" % [
				_folder_label(clue.get("to_folder", "")),
				_folder_label(clue.get("from_folder", "")),
			]
	return ""


func snapshot() -> Dictionary:
	if not _configured:
		return {}
	return {
		"seed": _seed,
		"solution": _solution.duplicate(true),
		"clues": _clues.duplicate(true),
		"record_clues": _record_clues.duplicate(true),
	}


func _enumerate_assignments() -> Array[Dictionary]:
	var results: Array[Dictionary] = []
	_append_assignments(0, SEAT_IDS.duplicate(), {}, results)
	return results


func _append_assignments(
	folder_index: int,
	remaining_seats: Array[String],
	current: Dictionary,
	results: Array[Dictionary],
) -> void:
	if folder_index == FOLDER_IDS.size():
		results.append(current.duplicate(true))
		return
	for seat_index: int in range(remaining_seats.size()):
		var next_remaining: Array[String] = remaining_seats.duplicate()
		var seat_id: String = next_remaining[seat_index]
		next_remaining.remove_at(seat_index)
		current[FOLDER_IDS[folder_index]] = seat_id
		_append_assignments(folder_index + 1, next_remaining, current, results)
	current.erase(FOLDER_IDS[folder_index])


func _true_candidate_clues(solution: Dictionary) -> Array[Dictionary]:
	var candidates: Array[Dictionary] = []
	for folder_id: String in FOLDER_IDS:
		for seat_id: String in SEAT_IDS:
			var clue: Dictionary
			if solution[folder_id] == seat_id:
				clue = {
					"kind": "exact_seat",
					"folder": folder_id,
					"seat": seat_id,
				}
			else:
				clue = {
					"kind": "not_seat",
					"folder": folder_id,
					"seat": seat_id,
				}
			candidates.append(clue)

	for first_index: int in range(FOLDER_IDS.size() - 1):
		for second_index: int in range(first_index + 1, FOLDER_IDS.size()):
			var folder_a: String = FOLDER_IDS[first_index]
			var folder_b: String = FOLDER_IDS[second_index]
			for kind: String in ["adjacent", "opposite"]:
				var relation_clue := {
					"kind": kind,
					"folder_a": folder_a,
					"folder_b": folder_b,
				}
				if clue_matches(relation_clue, solution):
					candidates.append(relation_clue)

	for from_folder: String in FOLDER_IDS:
		for to_folder: String in FOLDER_IDS:
			if from_folder == to_folder:
				continue
			var direction_clue := {
				"kind": "clockwise_next",
				"from_folder": from_folder,
				"to_folder": to_folder,
			}
			if clue_matches(direction_clue, solution):
				candidates.append(direction_clue)

	var unique_candidates: Array[Dictionary] = []
	var seen_keys: Dictionary = {}
	for clue: Dictionary in candidates:
		var key: String = canonical_clue_key(clue)
		if key in seen_keys:
			continue
		seen_keys[key] = true
		unique_candidates.append(clue.duplicate(true))
	unique_candidates.sort_custom(
		func(left: Dictionary, right: Dictionary) -> bool:
			return canonical_clue_key(left) < canonical_clue_key(right)
	)
	return unique_candidates


func _clue_mask(clue: Dictionary, assignments: Array[Dictionary]) -> int:
	var mask: int = 0
	for index: int in range(assignments.size()):
		if clue_matches(clue, assignments[index]):
			mask |= 1 << index
	return mask


func _bit_count(value: int) -> int:
	var count: int = 0
	var remaining: int = value
	while remaining != 0:
		count += remaining & 1
		remaining >>= 1
	return count


func _canonical_folder_pair(folder_a: String, folder_b: String) -> Array[String]:
	if FOLDER_IDS.find(folder_a) <= FOLDER_IDS.find(folder_b):
		return [folder_a, folder_b]
	return [folder_b, folder_a]


func _folder_label(folder_id: Variant) -> String:
	return str(FOLDER_LABELS.get(str(folder_id), ""))


func _seat_label(seat_id: Variant) -> String:
	return str(SEAT_LABELS.get(str(seat_id), ""))


func _shuffle_with_rng(values: Array, rng: RandomNumberGenerator) -> void:
	for index: int in range(values.size() - 1, 0, -1):
		var swap_index: int = rng.randi_range(0, index)
		var temporary: Variant = values[index]
		values[index] = values[swap_index]
		values[swap_index] = temporary
