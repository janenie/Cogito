extends SceneTree

const EXPECTED_CANDIDATE_COUNTS: Array[int] = [6, 4, 3, 2, 1]

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
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
	var first_snapshot: Dictionary = first.get_round_snapshot()
	first.queue_free()
	await process_frame

	var second: Node = manager_script.new()
	root.add_child(second)
	second.configure_round(424242)
	var second_snapshot: Dictionary = second.get_round_snapshot()
	_assert(first_snapshot == second_snapshot, "fixed round seed produces deterministic puzzle state")
	_assert_long_clue_round(second, second_snapshot, "fixed seed")
	second.configure_round(424243)
	var third_snapshot: Dictionary = second.get_round_snapshot()
	_assert(
		_clue_texts(first_snapshot) != _clue_texts(third_snapshot),
		"different round seeds produce different visible clue sequence",
	)

	for seed: int in range(1, 301):
		second.configure_round(seed)
		_assert_long_clue_round(second, second.get_round_snapshot(), "seed %d" % seed)

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
