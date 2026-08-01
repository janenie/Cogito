extends SceneTree

const Manager = preload(
	"res://addons/cogito/DemoScenes/Laboratory/laboratory_experiment_manager.gd"
)

const PUBLIC_FIELDS: Array[String] = [
	"objective",
	"protocol",
	"environment",
	"attempts_used",
	"attempts_limit",
	"battery_installed",
	"selected_sample",
	"sample_state",
	"metal_bar_installed",
	"setup_ready",
	"experiment_running",
	"last_power",
	"last_current",
	"last_stability",
	"last_temperature",
	"last_lamp",
	"completed",
	"failed",
]

var failures := 0


func _initialize() -> void:
	var manager: Node = Manager.new()
	root.add_child(manager)
	await process_frame
	manager.stability_seconds = 0.01
	manager.start_round(31)

	manager.run_experiment()
	_assert(manager.attempts_used == 0, "incomplete setup consumes no attempt")
	_assert(manager.status_code == "setup_incomplete", "incomplete setup is visible")
	manager.select_battery("alpha")
	manager.select_sample("a")
	manager.set_metal_bar_installed(true)
	manager.run_experiment()
	_assert(manager.attempts_used == 0, "missing physical treatment consumes no attempt")
	manager.reset_setup()

	var terminal_events: Array[Array] = []
	manager.round_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_events.append([outcome, reason])
	)
	var wrong_setup: Dictionary = _setup_for(manager, false)
	for attempt: int in 2:
		_apply_setup(manager, wrong_setup)
		manager.run_experiment()
		_assert(manager.attempts_used == attempt + 1, "wrong run consumes one attempt")
		_assert(not manager.completed and not manager.failed, "first two failures are retryable")

	_apply_setup(manager, _setup_for(manager, true))
	manager.run_experiment()
	await manager.round_finished
	_assert(
		terminal_events == [["success", "experiment_completed"]],
		"a correct third experiment emits success exactly once",
	)

	var failed_manager: Node = Manager.new()
	root.add_child(failed_manager)
	failed_manager.start_round(87)
	var failure_events: Array[Array] = []
	failed_manager.round_finished.connect(
		func(outcome: String, reason: String) -> void:
			failure_events.append([outcome, reason])
	)
	var failed_setup: Dictionary = _setup_for(failed_manager, false)
	for _attempt: int in 3:
		_apply_setup(failed_manager, failed_setup)
		failed_manager.run_experiment()
	_assert(
		failure_events == [["failure", "experiment_attempts_exhausted"]],
		"a wrong third experiment emits exhaustion exactly once",
	)

	var public_state: Dictionary = manager.ai_play_public_state()
	var actual_fields: Array[String] = []
	for key: Variant in public_state.keys():
		actual_fields.append(str(key))
	actual_fields.sort()
	var expected_fields := PUBLIC_FIELDS.duplicate()
	expected_fields.sort()
	_assert(actual_fields == expected_fields, "public state has exact allowlisted fields")
	_assert(not public_state.has("round_data"), "public state excludes hidden round data")

	manager.queue_free()
	failed_manager.queue_free()
	if failures == 0:
		print("Laboratory experiment manager tests passed")
		quit(0)
	else:
		push_error("%d laboratory manager test(s) failed" % failures)
		quit(1)


func _setup_for(manager: Node, correct: bool) -> Dictionary:
	var battery := _label_for_profile(
		manager.round_data["battery_map"],
		manager.round_data["correct_battery_profile"],
	)
	var sample := _label_for_profile(
		manager.round_data["sample_map"],
		manager.round_data["correct_sample_profile"],
	)
	if not correct:
		for candidate: String in ["alpha", "beta", "gamma"]:
			if candidate != battery:
				battery = candidate
				break
	return {
		"battery": battery,
		"sample": sample,
		"treatment": manager.round_data["correct_treatment"],
	}


func _apply_setup(manager: Node, setup: Dictionary) -> void:
	manager.select_battery(setup["battery"])
	manager.select_sample(setup["sample"])
	manager.select_treatment(setup["treatment"])
	manager.set_metal_bar_installed(true)


func _label_for_profile(mapping: Dictionary, profile: String) -> String:
	for label: String in mapping:
		if mapping[label] == profile:
			return label
	return ""


func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
