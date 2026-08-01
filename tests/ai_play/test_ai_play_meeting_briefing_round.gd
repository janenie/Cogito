extends SceneTree

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	_test_assignment_enumeration()
	_test_clue_semantics()
	_test_seeded_generation()
	_test_snapshot_is_isolated()
	_finish()


func _test_assignment_enumeration() -> void:
	var round_state := AIPlayMeetingBriefingRound.new()
	var assignments: Array[Dictionary] = round_state.all_assignments()
	_assert(assignments.size() == 24, "four folders produce 24 assignments")
	var canonical_assignments: Dictionary = {}
	for assignment: Dictionary in assignments:
		_assert(_is_assignment_permutation(assignment), "assignment is one-to-one")
		var key: String = _assignment_key(assignment)
		_assert(key not in canonical_assignments, "assignment is not duplicated")
		canonical_assignments[key] = true


func _test_clue_semantics() -> void:
	var round_state := AIPlayMeetingBriefingRound.new()
	var public_names: Dictionary = {}
	for folder_id: String in AIPlayMeetingBriefingRound.FOLDER_IDS:
		var public_name: String = AIPlayMeetingBriefingRound.FOLDER_LABELS[folder_id]
		_assert(public_name.length() == 2, "%s has a two-character Chinese name" % folder_id)
		_assert(public_name not in public_names, "%s has a unique public name" % folder_id)
		public_names[public_name] = true
	var assignment := {
		"atlas": "tv_side",
		"birch": "door_side",
		"crown": "opposite_tv",
		"delta": "inner_wall",
	}
	var clues: Array[Dictionary] = [
		{"kind": "exact_seat", "folder": "atlas", "seat": "tv_side"},
		{"kind": "not_seat", "folder": "atlas", "seat": "inner_wall"},
		{"kind": "adjacent", "folder_a": "atlas", "folder_b": "birch"},
		{"kind": "opposite", "folder_a": "atlas", "folder_b": "crown"},
		{
			"kind": "clockwise_next",
			"from_folder": "atlas",
			"to_folder": "birch",
		},
	]
	for clue: Dictionary in clues:
		_assert(round_state.clue_matches(clue, assignment), "%s clue matches" % clue.kind)
		var text: String = round_state.clue_text(clue)
		_assert(not text.is_empty(), "%s clue has public text" % clue.kind)
		for internal_id: String in AIPlayMeetingBriefingRound.SEAT_IDS:
			_assert(internal_id not in text, "public clue hides internal seat IDs")
		for internal_id: String in AIPlayMeetingBriefingRound.FOLDER_IDS:
			_assert(internal_id not in text, "public clue hides internal folder IDs")

	_assert(
		round_state.clue_matches(
			{"kind": "adjacent", "folder_a": "birch", "folder_b": "atlas"},
			assignment,
		),
		"adjacent is symmetric",
	)
	_assert(
		round_state.clue_matches(
			{"kind": "adjacent", "folder_a": "atlas", "folder_b": "delta"},
			assignment,
		),
		"adjacent wraps around",
	)
	_assert(
		not round_state.clue_matches(
			{"kind": "adjacent", "folder_a": "atlas", "folder_b": "crown"},
			assignment,
		),
		"opposite seats are not adjacent",
	)
	_assert(
		round_state.clue_matches(
			{"kind": "opposite", "folder_a": "crown", "folder_b": "atlas"},
			assignment,
		),
		"opposite is symmetric",
	)
	_assert(
		not round_state.clue_matches(
			{
				"kind": "clockwise_next",
				"from_folder": "birch",
				"to_folder": "atlas",
			},
			assignment,
		),
		"clockwise next is directional",
	)
	_assert(
		round_state.clue_matches(
			{
				"kind": "clockwise_next",
				"from_folder": "delta",
				"to_folder": "atlas",
			},
			assignment,
		),
		"clockwise next wraps around",
	)
	_assert(
		not round_state.clue_matches(
			{"kind": "exact_seat", "folder": "atlas", "seat": "door_side"},
			assignment,
		),
		"wrong exact seat is false",
	)


func _test_seeded_generation() -> void:
	var first := AIPlayMeetingBriefingRound.new()
	var second := AIPlayMeetingBriefingRound.new()
	_assert(first.configure(87123), "first deterministic round configures")
	_assert(second.configure(87123), "second deterministic round configures")
	_assert(first.snapshot() == second.snapshot(), "same seed is deterministic")

	var observed_kinds: Dictionary = {}
	for seed_value: int in range(1, 513):
		var round_state := AIPlayMeetingBriefingRound.new()
		_assert(round_state.configure(seed_value), "seed %d configures" % seed_value)
		var state: Dictionary = round_state.snapshot()
		_assert(
			_is_assignment_permutation(state.solution),
			"solution is one-to-one for seed %d" % seed_value,
		)
		_assert(state.clues.size() == 3, "seed %d has three clues" % seed_value)
		var matches: Array[Dictionary] = round_state.solve(state.clues)
		_assert(matches.size() == 1, "seed %d has one solution" % seed_value)
		if matches.size() == 1:
			_assert(
				matches[0] == state.solution,
				"seed %d resolves to hidden solution" % seed_value,
			)

		var clue_keys: Dictionary = {}
		for clue: Dictionary in state.clues:
			observed_kinds[clue.kind] = true
			_assert(
				round_state.clue_matches(clue, state.solution),
				"seed %d clue is true" % seed_value,
			)
			_assert(
				round_state.solve([clue]).size() < 24,
				"seed %d clue eliminates candidates" % seed_value,
			)
			var clue_key: String = round_state.canonical_clue_key(clue)
			_assert(
				clue_key not in clue_keys,
				"seed %d clues are not duplicated" % seed_value,
			)
			clue_keys[clue_key] = true

		for removed_index: int in range(3):
			var reduced: Array = state.clues.duplicate(true)
			reduced.remove_at(removed_index)
			_assert(
				round_state.solve(reduced).size() >= 2,
				"seed %d needs clue %d" % [seed_value, removed_index],
			)

		var record_keys: Array = state.record_clues.keys()
		record_keys.sort()
		_assert(
			record_keys == ["archive", "break_room", "ceo"],
			"seed %d assigns all records" % seed_value,
		)
		var clue_indexes: Array = state.record_clues.values()
		clue_indexes.sort()
		_assert(
			clue_indexes == [0, 1, 2],
			"seed %d record assignment is one-to-one" % seed_value,
		)
	var kind_keys: Array = observed_kinds.keys()
	kind_keys.sort()
	_assert(
		kind_keys == [
			"adjacent",
			"clockwise_next",
			"exact_seat",
			"not_seat",
			"opposite",
		],
		"seed sample exercises all five clue kinds",
	)


func _test_snapshot_is_isolated() -> void:
	var round_state := AIPlayMeetingBriefingRound.new()
	round_state.configure(42)
	var snapshot: Dictionary = round_state.snapshot()
	snapshot.solution["atlas"] = "mutated"
	snapshot.clues[0]["kind"] = "mutated"
	snapshot.record_clues["ceo"] = 99
	var fresh: Dictionary = round_state.snapshot()
	_assert(fresh.solution.atlas != "mutated", "solution snapshot is duplicated")
	_assert(fresh.clues[0].kind != "mutated", "clue snapshot is duplicated")
	_assert(fresh.record_clues.ceo != 99, "record snapshot is duplicated")


func _is_assignment_permutation(assignment: Dictionary) -> bool:
	var folder_keys: Array = assignment.keys()
	folder_keys.sort()
	var expected_folders: Array = AIPlayMeetingBriefingRound.FOLDER_IDS.duplicate()
	expected_folders.sort()
	var seat_values: Array = assignment.values()
	seat_values.sort()
	var expected_seats: Array = AIPlayMeetingBriefingRound.SEAT_IDS.duplicate()
	expected_seats.sort()
	return folder_keys == expected_folders and seat_values == expected_seats


func _assignment_key(assignment: Dictionary) -> String:
	var parts: Array[String] = []
	for folder_id: String in AIPlayMeetingBriefingRound.FOLDER_IDS:
		parts.append("%s=%s" % [folder_id, assignment.get(folder_id, "")])
	return "|".join(parts)


func _finish() -> void:
	if _failures.is_empty():
		print("AIPlay meeting briefing round tests passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
