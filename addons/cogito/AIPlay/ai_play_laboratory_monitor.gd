class_name AIPlayLaboratoryMonitor
extends Node

signal game_finished(outcome: String, reason: String)

@export var scenario_id := "laboratory_experiment"
@export var manager: Node
@export var game_over_screen: Node

var _finished := false


func _ready() -> void:
	if manager == null:
		push_error("AIPlayLaboratoryMonitor is missing LaboratoryExperimentManager")
		return
	manager.round_finished.connect(_on_round_finished)


func _on_round_finished(outcome: String, reason: String) -> void:
	if _finished:
		return
	_finished = true
	game_finished.emit(outcome, reason)


func show_result(outcome: String, reason: String) -> void:
	if game_over_screen != null:
		game_over_screen.show_result(outcome, reason)
