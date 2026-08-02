extends SceneTree

var _failures: Array[String] = []
var _test_scene_root: Node


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	_ensure_current_scene()
	var scene: PackedScene = load(
		"res://addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn"
	)
	_assert(scene != null, "Laboratory scene loads")
	if scene == null:
		_finish()
		return

	var laboratory: Node = scene.instantiate()
	root.add_child(laboratory)
	await process_frame

	var controller: Node = laboratory.get_node_or_null("AIPlayController")
	var manager: Node = laboratory.get_node_or_null(
		"NavigationRegion3D/SYSTEMIC_PROPERTIES/LaboratoryExperiment/Manager"
	)
	var observer: Node = laboratory.get_node_or_null("AIPlayController/Observer")
	var monitor: Node = laboratory.get_node_or_null("AIPlayController/LaboratoryMonitor")
	_assert(controller != null, "scene includes an AIPlayController")
	_assert(manager != null, "scene includes the experiment manager")
	_assert(observer != null and observer.manager == manager, "observer uses the experiment manager")
	_assert(monitor != null and monitor.manager == manager, "monitor uses the experiment manager")
	_assert(controller != null and not controller.auto_start, "AI Play remains explicitly enabled")
	_assert(controller != null and controller.host == "127.0.0.1", "bridge stays on numeric loopback")
	_assert(
		controller != null
		and controller.get_requested_scenario_id([
			"--ai-play-scenario=laboratory_experiment",
		]) == "laboratory_experiment",
		"controller accepts the laboratory scenario id",
	)

	if manager != null:
		manager.start_round(314159)
		var public_state: Dictionary = manager.ai_play_public_state()
		var has_hidden_field := false
		for key: Variant in public_state:
			if key in ["round_seed", "round_data", "answer", "solution"]:
				has_hidden_field = true
		_assert(
			not has_hidden_field,
			"public state excludes the seed and hidden solution",
		)
		if _is_selected_scenario():
			_assert(
				controller.get_active_scenario_id() == "laboratory_experiment",
				"selected launch activates the laboratory scenario",
			)
		_assert(public_state["attempts_limit"] == 3, "public state exposes the three-attempt limit")
		_assert(public_state["sample_state"] == "none", "empty treatment slot is explicit")

	if monitor != null and manager != null:
		var terminal_results: Array[Dictionary] = []
		monitor.game_finished.connect(
			func(outcome: String, reason: String) -> void:
				terminal_results.append({"outcome": outcome, "reason": reason})
		)
		manager.round_finished.emit("failure", "experiment_attempts_exhausted")
		manager.round_finished.emit("failure", "experiment_attempts_exhausted")
		_assert(
			terminal_results == [{
				"outcome": "failure",
				"reason": "experiment_attempts_exhausted",
			}],
			"experiment terminal result is emitted exactly once",
		)
		if _is_selected_scenario():
			_assert(
				monitor.game_over_screen != null
				and monitor.game_over_screen.visible,
				"selected laboratory terminal shows the shared exit screen",
			)
		paused = false

	laboratory.queue_free()
	if _test_scene_root != null:
		_test_scene_root.queue_free()
	await process_frame
	_finish()


func _is_selected_scenario() -> bool:
	return "--ai-play-scenario=laboratory_experiment" in OS.get_cmdline_user_args()


func _ensure_current_scene() -> void:
	if current_scene != null:
		return
	_test_scene_root = Node.new()
	_test_scene_root.name = "AIPlayHeadlessTestScene"
	root.add_child(_test_scene_root)
	current_scene = _test_scene_root


func _finish() -> void:
	paused = false
	if _failures.is_empty():
		print("AIPlay laboratory integration test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
