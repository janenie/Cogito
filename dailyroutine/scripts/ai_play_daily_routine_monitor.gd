class_name AIPlayDailyRoutineMonitor
extends Node

signal game_finished(outcome: String, reason: String)

@export var scenario_id: String = "daily_routine_cleanup"
@export var manager: Node
@export var game_over_screen: Node

var _finished: bool = false


func _ready() -> void:
	if manager == null:
		manager = get_node_or_null("../../DailyRoutineManager")
	if manager == null:
		push_error("AIPlayDailyRoutineMonitor is missing DailyRoutineManager")
		return
	if not manager.routine_completed.is_connected(_on_routine_completed):
		manager.routine_completed.connect(_on_routine_completed)
	if not manager.routine_failed_changed.is_connected(_on_routine_failed):
		manager.routine_failed_changed.connect(_on_routine_failed)


func _on_routine_completed() -> void:
	_emit_once("success", "cleanup_complete")


func _on_routine_failed(_reason: String) -> void:
	_emit_once("failure", "cleanup_incomplete")


func _emit_once(outcome: String, reason: String) -> void:
	if _finished:
		return
	_finished = true
	game_finished.emit(outcome, reason)


func show_result(outcome: String, reason: String) -> void:
	if game_over_screen != null:
		game_over_screen.show_result(outcome, reason)
