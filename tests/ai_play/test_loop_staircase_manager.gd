extends SceneTree

const EXPECTED_CANDIDATE_COUNTS: Array[int] = [6, 4, 3, 2, 1]
const EXPECTED_MURDER_CANDIDATE_COUNTS: Array[int] = [8, 6, 5, 3, 2, 1]

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	var case_script_path := (
		"res://addons/cogito/DemoScenes/LoopStaircase/loop_staircase_case.gd"
	)
	_assert(
		ResourceLoader.exists(case_script_path),
		"Loop staircase murder case model script exists",
	)
	if not ResourceLoader.exists(case_script_path):
		_finish()
		return
	var case_script: Script = load(case_script_path)
	_assert(case_script != null, "Loop staircase murder case model script loads")
	_assert(
		case_script != null and case_script.can_instantiate(),
		"Loop staircase murder case model script compiles",
	)
	if case_script == null or not case_script.can_instantiate():
		_finish()
		return
	for seed_value: int in range(1, 301):
		_assert_murder_case(case_script, seed_value)

	var manager_script: Script = load(
		"res://addons/cogito/DemoScenes/LoopStaircase/loop_staircase_manager.gd"
	)
	_assert(manager_script != null, "Loop staircase manager script loads")
	if manager_script == null:
		_finish()
		return

	var first: Node = manager_script.new()
	root.add_child(first)
	first.configure_round(424242)
	var coordinator_methods: Array[String] = [
		"get_visible_clue_lines",
		"get_missing_floor_labels",
		"mark_floor_observed",
		"toggle_candidate",
		"is_candidate_marked",
	]
	var coordinator_ready: bool = true
	for method_name: String in coordinator_methods:
		var has_method: bool = first.has_method(method_name)
		_assert(has_method, "manager provides %s" % method_name)
		coordinator_ready = coordinator_ready and has_method
	if not coordinator_ready:
		first.queue_free()
		await process_frame
		_finish()
		return
	_assert_investigation_coordinator(first)
	first.configure_round(424242)
	var first_snapshot: Dictionary = first.get_round_snapshot()
	first.queue_free()
	await process_frame

	var second: Node = manager_script.new()
	root.add_child(second)
	second.configure_round(424242)
	var second_snapshot: Dictionary = second.get_round_snapshot()
	_assert(first_snapshot == second_snapshot, "fixed round seed produces deterministic puzzle state")
	second.configure_round(424243)
	var third_snapshot: Dictionary = second.get_round_snapshot()
	_assert(
		first_snapshot["victim_name"] != third_snapshot["victim_name"]
		or first_snapshot["true_floor"] != third_snapshot["true_floor"],
		"different round seeds vary the generated case",
	)

	var terminal_results: Array[Dictionary] = []
	second.configure_round(424242)
	var true_floor: int = second.get_round_snapshot()["true_floor"]
	second.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_results.append({
				"outcome": outcome,
				"reason": reason,
			})
	)
	_unlock_final_round(second)
	second.select_floor(true_floor)
	second.select_floor(true_floor)
	_assert(
		terminal_results == [{
			"outcome": "success",
			"reason": "correct_floor_selected",
		}],
		"correct answer emits success exactly once",
	)
	var finished_floor: int = second.get_current_floor()
	second.move_up()
	second.move_down()
	_assert(
		second.get_current_floor() == finished_floor,
		"finished round ignores further floor navigation",
	)

	var third: Node = manager_script.new()
	root.add_child(third)
	third.configure_round(424242)
	var wrong_results: Array[Dictionary] = []
	third.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			wrong_results.append({
				"outcome": outcome,
				"reason": reason,
			})
	)
	var wrong_floor: int = 2
	if wrong_floor == true_floor:
		wrong_floor = 3
	_unlock_final_round(third)
	third.select_floor(wrong_floor)
	_assert(
		wrong_results == [{
			"outcome": "failure",
			"reason": "wrong_floor_selected",
		}],
		"wrong answer emits failure",
	)

	second.queue_free()
	third.queue_free()
	await process_frame
	_finish()


func _unlock_final_round(manager: Node) -> void:
	while not manager.is_final_unlocked():
		for floor_number: int in range(2, 10):
			manager.mark_floor_observed(floor_number)
		manager.set_current_floor(9)
		manager.move_up()


func _assert_investigation_coordinator(manager: Node) -> void:
	var lines: Array[String] = manager.get_visible_clue_lines()
	_assert(lines.size() == 1, "round one exposes exactly one clue")
	_assert(lines[0].begins_with("本轮线索："), "round one clue uses the current label")
	manager.mark_floor_observed(2)
	manager.set_current_floor(9)
	manager.mark_floor_observed(9)
	manager.move_up()
	_assert(manager.current_loop == 0, "incomplete observation cannot advance")
	_assert(
		manager.get_missing_floor_labels() == ["3F", "4F", "5F", "6F", "7F", "8F"],
		"incomplete feedback lists only missing floors",
	)
	for floor_number: int in range(2, 10):
		manager.mark_floor_observed(floor_number)
	manager.move_up()
	_assert(manager.current_loop == 1, "eight observed floors advance the round")
	lines = manager.get_visible_clue_lines()
	_assert(lines.size() == 2, "round two exposes no future clues")
	_assert(lines[0].begins_with("第一轮线索："), "old clue receives a fixed round label")
	_assert(lines[1].begins_with("本轮线索："), "new clue retains the current label")
	var terminal_results: Array[Dictionary] = []
	manager.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_results.append({"outcome": outcome, "reason": reason})
	)
	manager.submit_current_floor()
	_assert(terminal_results.is_empty(), "round two cannot submit an answer")
	manager.toggle_candidate(3)
	_assert(manager.is_candidate_marked(3), "manual candidate mark is stored")
	_assert(terminal_results.is_empty(), "manual candidate mark has no correctness feedback")


func _assert_murder_case(case_script: Script, seed_value: int) -> void:
	var first: RefCounted = case_script.generate(seed_value)
	var second: RefCounted = case_script.generate(seed_value)
	var snapshot: Dictionary = first.test_snapshot()
	_assert(snapshot == second.test_snapshot(), "case seed %d is deterministic" % seed_value)
	_assert(first.is_consistent(), "case seed %d is internally consistent" % seed_value)
	var candidates: Array = snapshot.get("candidate_sets", [])
	_assert(
		candidates.size() == EXPECTED_MURDER_CANDIDATE_COUNTS.size(),
		"case seed %d stores every candidate stage" % seed_value,
	)
	if candidates.size() != EXPECTED_MURDER_CANDIDATE_COUNTS.size():
		return
	for index: int in range(candidates.size()):
		_assert(
			candidates[index].size() == EXPECTED_MURDER_CANDIDATE_COUNTS[index],
			"case seed %d stage %d has the required candidate count" % [seed_value, index],
		)
	var true_floor: int = snapshot.get("true_floor", 0)
	_assert(candidates[-1] == [true_floor], "case seed %d has one final floor" % seed_value)
	var floors: Dictionary = snapshot.get("floors", {})
	_assert(floors.size() == 8, "case seed %d stores eight floors" % seed_value)
	var theme_ids: Array[String] = []
	var expected_types: Dictionary = {
		2: "lounge", 3: "lounge", 4: "archive", 5: "archive",
		6: "office", 7: "office", 8: "meeting", 9: "meeting",
	}
	for floor_number: int in range(2, 10):
		var floor_data: Dictionary = floors.get(floor_number, {})
		_assert(
			floor_data.get("room_type", "") == expected_types[floor_number],
			"case seed %d floor %d has its fixed function" % [seed_value, floor_number],
		)
		var theme_id: String = floor_data.get("theme_id", "")
		_assert(not theme_id.is_empty(), "case seed %d floor %d has a theme" % [seed_value, floor_number])
		_assert(not theme_id in theme_ids, "case seed %d floor themes are distinct" % seed_value)
		theme_ids.append(theme_id)
		_assert(
			floor_data.get("paired_floor", 0) == (floor_number + 1 if floor_number % 2 == 0 else floor_number - 1),
			"case seed %d floor %d points to its functional pair" % [seed_value, floor_number],
		)
	var victim_name: String = snapshot.get("victim_name", "")
	var victim_floors: Array[int] = []
	for floor_number: int in range(2, 10):
		if victim_name in floors[floor_number].get("visitor_names", []):
			victim_floors.append(floor_number)
	_assert(victim_floors == candidates[1], "case seed %d victim rule leaves six floors" % seed_value)
	var item_floors: Array[int] = []
	for floor_number: int in candidates[1]:
		var counts: Array = floors[floor_number].get("item_counts", [])
		if counts.size() == 5 and counts[1] != counts[0]:
			item_floors.append(floor_number)
	_assert(item_floors == candidates[2], "case seed %d item rule leaves five floors" % seed_value)
	var paired_floor: int = floors[true_floor].get("paired_floor", 0)
	var true_item_counts: Array = floors[true_floor].get("item_counts", [])
	var paired_item_counts: Array = floors.get(paired_floor, {}).get("item_counts", [])
	_assert(
		true_item_counts.size() == 5
		and paired_item_counts.size() == 5
		and true_item_counts[1] - true_item_counts[0] == 1
		and paired_item_counts[1] - paired_item_counts[0] == -1,
		"case seed %d shows a same-time transfer from the paired room" % seed_value,
	)
	var exact_trash: Array[int] = []
	var zero_trash: Array[int] = []
	var noisy_trash: Array[int] = []
	for floor_number: int in candidates[2]:
		var counts: Array = floors[floor_number].get("trash_counts", [])
		if counts.slice(0, 3) == [0, 0, 0]:
			zero_trash.append(floor_number)
		elif counts.size() == 5 and counts[1] == counts[0] - 1 and counts[2] == counts[1] - 1:
			exact_trash.append(floor_number)
		else:
			noisy_trash.append(floor_number)
	_assert(exact_trash == candidates[3], "case seed %d cleaner rule leaves three floors" % seed_value)
	_assert(zero_trash.size() == 1, "case seed %d has one zero-trash role" % seed_value)
	_assert(noisy_trash.size() == 1, "case seed %d has one noisy-trash role" % seed_value)
	_assert(_has_shared_current_value(floors, exact_trash, noisy_trash, "trash_counts", 2), "case seed %d trash needs history" % seed_value)
	var abab_floors: Array[int] = []
	var signal_decoys: Array[int] = []
	for floor_number: int in candidates[3]:
		var colors: Array = floors[floor_number].get("signal_colors", [])
		if colors.size() == 5 and colors[0] == colors[2] and colors[1] == colors[3] and colors[0] != colors[1]:
			abab_floors.append(floor_number)
		else:
			signal_decoys.append(floor_number)
	_assert(abab_floors == candidates[4], "case seed %d signal rule leaves two floors" % seed_value)
	_assert(signal_decoys.size() == 1, "case seed %d has one signal decoy" % seed_value)
	_assert(_has_shared_current_value(floors, abab_floors, signal_decoys, "signal_colors", 3), "case seed %d signal needs history" % seed_value)
	for evidence_kind: String in ["visitor", "item", "trash", "signal"]:
		_assert(
			first.matching_floors_without(evidence_kind).size() > 1,
			"case seed %d final answer needs %s evidence" % [seed_value, evidence_kind],
		)
	_assert(first.matching_floors_without("") == [true_floor], "case seed %d four-way timing is unique" % seed_value)


func _has_shared_current_value(
	floors: Dictionary,
	left_floors: Array[int],
	right_floors: Array[int],
	field: String,
	round_index: int,
) -> bool:
	for left_floor: int in left_floors:
		for right_floor: int in right_floors:
			if floors[left_floor][field][round_index] == floors[right_floor][field][round_index]:
				return true
	return false


func _assert_long_clue_round(manager: Node, snapshot: Dictionary, label: String) -> void:
	var floors: Array = snapshot["floors"]
	_assert(floors.size() == 8, "%s contains floors 2F through 9F" % label)
	var true_floor: int = snapshot["true_floor"]
	_assert(true_floor >= 2 and true_floor <= 9, "%s true floor is in range" % label)
	_assert(snapshot["total_loops"] == 5, "%s has five observation loops" % label)
	_assert(snapshot["loops"].size() == 5, "%s stores five loop states" % label)
	var clues: Array = snapshot.get("clues", [])
	_assert(clues.size() == 5, "%s exposes five cumulative clues for tests" % label)
	var clue_texts: Array[String] = []
	for clue_index: int in range(clues.size()):
		var clue: Dictionary = clues[clue_index]
		var remaining: Array = clue.get("remaining_floors", [])
		_assert(remaining.size() == EXPECTED_CANDIDATE_COUNTS[clue_index], "%s clue %d narrows to expected candidate count" % [label, clue_index + 1])
		_assert(true_floor in remaining, "%s clue %d keeps the true floor possible" % [label, clue_index + 1])
		var text: String = clue.get("text", "")
		_assert(not text.is_empty(), "%s clue %d has visible text" % [label, clue_index + 1])
		_assert(not text in clue_texts, "%s clue %d text is unique" % [label, clue_index + 1])
		_assert(not "候选中" in text, "%s clue %d does not reveal the candidate list" % [label, clue_index + 1])
		_assert(not "排除" in text, "%s clue %d does not directly eliminate a named floor" % [label, clue_index + 1])
		_assert(not "F" in text, "%s clue %d does not reveal a floor label" % [label, clue_index + 1])
		_assert(not "椅子位置" in text, "%s clue %d does not require memorizing chair positions" % [label, clue_index + 1])
		var eliminated_floor: int = int(clue.get("eliminated_floor", 0))
		if eliminated_floor != 0:
			_assert(eliminated_floor != true_floor, "%s clue %d never eliminates the true floor" % [label, clue_index + 1])
		clue_texts.append(text)
	if clues.size() == 5:
		_assert(clues[-1]["remaining_floors"] == [true_floor], "%s final clue uniquely identifies the answer" % label)
	var answer_candidates: Array[int] = []
	for floor_state: Dictionary in floors:
		if floor_state["is_solution"]:
			answer_candidates.append(floor_state["floor"])
		_assert(
			floor_state.has("chair_count")
			and floor_state.has("computer_count")
			and floor_state.has("book_count")
			and floor_state.has("layout_variant"),
			"%s floor state exposes visible room variables" % label,
		)
	_assert(answer_candidates == [true_floor], "%s puzzle has one unique answer" % label)
	manager.set_current_floor(9)
	manager.move_up()
	_assert(manager.get_current_floor() == 2, "%s pressing Up from 9F wraps to 2F" % label)


func _clue_texts(snapshot: Dictionary) -> Array[String]:
	var result: Array[String] = []
	for clue: Dictionary in snapshot.get("clues", []):
		result.append(str(clue.get("text", "")))
	return result


func _finish() -> void:
	if _failures.is_empty():
		print("Loop staircase manager test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
