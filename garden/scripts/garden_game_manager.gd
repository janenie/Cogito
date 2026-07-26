class_name GardenGameManager
extends Node

const GardenPlantScript = preload("res://garden/scripts/garden_plant.gd")

signal objective_changed(text: String)
signal day_failure(reason: String)
signal day_retried

@export var time_system_path: NodePath
@export var sunflower_group_path: NodePath

var time_system: Node
var sunflower_group: Node
var current_objective := ""
var failure_reason := ""
var day_failed := false

func _ready() -> void:
	if time_system == null:
		time_system = get_node_or_null(time_system_path)
	if sunflower_group == null:
		sunflower_group = get_node_or_null(sunflower_group_path)
	_connect_systems()
	start_day()

func start_day() -> void:
	day_failed = false
	failure_reason = ""
	current_objective = "Collect the watering can and water every sunflower before 10:00."
	if time_system != null:
		time_system.paused = false
	objective_changed.emit(current_objective)
	_connect_plant_deaths()

func evaluate_deadlines() -> void:
	if day_failed or time_system == null:
		return
	if time_system.minutes_since_midnight >= 10.0 * 60.0:
		if sunflower_group == null or not sunflower_group.is_complete():
			fail_day("The sunflowers were not watered before 10:00.")

func fail_day(reason: String) -> void:
	if day_failed:
		return
	day_failed = true
	failure_reason = reason
	if time_system != null:
		time_system.paused = true
	day_failure.emit(reason)

func retry_day() -> void:
	if sunflower_group != null:
		sunflower_group.reset_group()
	if time_system != null:
		time_system.reset_clock()
	day_failed = false
	failure_reason = ""
	start_day()
	day_retried.emit()

func complete_sunflower_window() -> void:
	if sunflower_group == null:
		return
	for child in sunflower_group.get_children():
		if child.get_script() == GardenPlantScript:
			child.mark_window("sunflower_morning")
	current_objective = "Sunflowers are watered. Keep the can filled and inspect the garden."
	objective_changed.emit(current_objective)

func _connect_systems() -> void:
	if time_system != null and not time_system.deadline_reached.is_connected(_on_deadline_reached):
		time_system.deadline_reached.connect(_on_deadline_reached)
	_connect_plant_deaths()

func _connect_plant_deaths() -> void:
	if sunflower_group == null:
		return
	for child in sunflower_group.get_children():
		if child.get_script() == GardenPlantScript and not child.died.is_connected(_on_plant_died):
			child.died.connect(_on_plant_died)

func _on_deadline_reached(deadline_id: String) -> void:
	if deadline_id == "sunflower_morning":
		evaluate_deadlines()
	elif deadline_id == "day_end" and not day_failed:
		evaluate_deadlines()

func _on_plant_died() -> void:
	fail_day("A sunflower died.")
