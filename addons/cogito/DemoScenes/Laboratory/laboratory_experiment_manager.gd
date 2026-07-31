class_name LaboratoryExperimentManager
extends Node

const Cases = preload("res://addons/cogito/DemoScenes/Laboratory/laboratory_experiment_cases.gd")

signal round_finished(outcome: String, reason: String)
signal public_state_changed()

enum State {
	READY,
	RUNNING,
	RESETTING,
	FINISHED,
}

const ATTEMPTS_LIMIT := 3
const BATTERY_LABELS: Array[String] = ["alpha", "beta", "gamma"]
const SAMPLE_LABELS: Array[String] = ["a", "b", "c"]
const TREATMENTS: Array[String] = ["dry", "wet", "heated"]
const OBJECTIVES := {
	"stable_conduction": "Produce a safe, stable circuit and keep the experiment lamp lit.",
	"moisture_safety": "Complete the moisture test with safe current and a stable lamp.",
	"thermal_tolerance": "Complete the heated test without dangerous temperature or instability.",
}

@export_range(0.0, 10.0, 0.1) var stability_seconds := 3.0
@export var initial_seed := -1

var state := State.READY
var round_data: Dictionary = {}
var attempts_used := 0
var battery_installed := "none"
var selected_sample := "none"
var sample_state := "dry"
var metal_bar_installed := false
var last_result: Dictionary = {}
var result_history: Array[Dictionary] = []
var completed := false
var failed := false
var status_code := "ready"

var _round_generation := 0


func _ready() -> void:
	var seed_value := initial_seed
	if seed_value < 0:
		seed_value = int(Time.get_unix_time_from_system())
	start_round(seed_value)


func start_round(seed_value: int) -> void:
	_round_generation += 1
	round_data = Cases.build_round(seed_value)
	state = State.READY
	attempts_used = 0
	battery_installed = "none"
	selected_sample = "none"
	sample_state = "dry"
	metal_bar_installed = false
	last_result = {}
	result_history.clear()
	completed = false
	failed = false
	status_code = "ready"
	public_state_changed.emit()


func select_battery(label: String) -> void:
	if state != State.READY or label not in BATTERY_LABELS:
		return
	battery_installed = label
	status_code = "setup_changed"
	public_state_changed.emit()


func select_sample(label: String) -> void:
	if state != State.READY or label not in SAMPLE_LABELS:
		return
	selected_sample = label
	status_code = "setup_changed"
	public_state_changed.emit()


func select_treatment(treatment: String) -> void:
	if state != State.READY or treatment not in TREATMENTS:
		return
	sample_state = treatment
	status_code = "setup_changed"
	public_state_changed.emit()


func set_metal_bar_installed(installed: bool) -> void:
	if state != State.READY:
		return
	metal_bar_installed = installed
	status_code = "setup_changed"
	public_state_changed.emit()


func run_experiment() -> void:
	if state != State.READY:
		return
	if not _setup_ready():
		status_code = "setup_incomplete"
		public_state_changed.emit()
		return

	attempts_used += 1
	state = State.RUNNING
	status_code = "experiment_running"
	last_result = Cases.evaluate(
		round_data,
		battery_installed,
		selected_sample,
		sample_state,
	)
	result_history.append(last_result.duplicate(true))
	if result_history.size() > ATTEMPTS_LIMIT:
		result_history.pop_front()
	public_state_changed.emit()

	if last_result.get("success", false):
		var generation := _round_generation
		await get_tree().create_timer(stability_seconds).timeout
		if generation == _round_generation and state == State.RUNNING:
			_finish("success", "experiment_completed")
	elif attempts_used >= ATTEMPTS_LIMIT:
		_finish("failure", "experiment_attempts_exhausted")
	else:
		_reset_after_failed_experiment()


func reset_setup() -> void:
	if state != State.READY:
		return
	battery_installed = "none"
	selected_sample = "none"
	sample_state = "dry"
	metal_bar_installed = false
	status_code = "ready"
	public_state_changed.emit()


func ai_play_public_state() -> Dictionary:
	return {
		"objective": OBJECTIVES.get(round_data.get("protocol", ""), "Complete the experiment safely."),
		"protocol": round_data.get("protocol", "stable_conduction"),
		"environment": round_data.get("environment", "standard"),
		"attempts_used": attempts_used,
		"attempts_limit": ATTEMPTS_LIMIT,
		"battery_installed": battery_installed,
		"selected_sample": selected_sample,
		"sample_state": sample_state,
		"metal_bar_installed": metal_bar_installed,
		"setup_ready": _setup_ready(),
		"experiment_running": state == State.RUNNING,
		"last_power": last_result.get("power", "none"),
		"last_current": last_result.get("current", "none"),
		"last_stability": last_result.get("stability", "none"),
		"last_temperature": last_result.get("temperature", "none"),
		"last_lamp": last_result.get("lamp", "none"),
		"completed": completed,
		"failed": failed,
	}


func task_card_text() -> String:
	return "%s\nEnvironment: %s\n%s\n%s" % [
		OBJECTIVES.get(round_data.get("protocol", ""), "Complete the experiment safely."),
		round_data.get("environment", "standard").replace("_", " ").capitalize(),
		round_data.get("clues", ["", ""])[0],
		round_data.get("clues", ["", ""])[1],
	]


func _setup_ready() -> bool:
	return (
		battery_installed in BATTERY_LABELS
		and selected_sample in SAMPLE_LABELS
		and metal_bar_installed
	)


func _reset_after_failed_experiment() -> void:
	state = State.RESETTING
	status_code = "resetting"
	public_state_changed.emit()
	sample_state = "dry"
	state = State.READY
	status_code = "retry_ready"
	public_state_changed.emit()


func _finish(outcome: String, reason: String) -> void:
	if state == State.FINISHED:
		return
	state = State.FINISHED
	completed = outcome == "success"
	failed = outcome == "failure"
	status_code = reason
	public_state_changed.emit()
	round_finished.emit(outcome, reason)
