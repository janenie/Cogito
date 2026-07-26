class_name AIPlayGardenMonitor
extends Node

signal game_finished(outcome: String, reason: String)

@export var scenario_id: String = "garden_watering"
@export var watering_state: Node
@export var game_over_screen: Node

var _finished: bool = false


func _ready() -> void:
	if watering_state == null:
		watering_state = get_node_or_null("../..")
	if watering_state == null:
		push_error("AIPlayGardenMonitor is missing GardenWateringState")


func _process(_delta: float) -> void:
	if _finished or watering_state == null:
		return
	var rules: Node = watering_state.game1_rules
	if rules.is_complete():
		_emit_once("success", "garden_tasks_complete")
	elif rules.day_failed:
		_emit_once("failure", "garden_task_failed")


func _emit_once(outcome: String, reason: String) -> void:
	if _finished:
		return
	_finished = true
	game_finished.emit(outcome, reason)


func show_result(outcome: String, reason: String) -> void:
	if game_over_screen != null:
		game_over_screen.show_result(outcome, reason)
