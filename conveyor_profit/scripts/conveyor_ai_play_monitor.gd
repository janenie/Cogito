class_name ConveyorAIPlayMonitor
extends Node

signal game_finished(outcome: String, reason: String)

@export var scenario_id: String = "conveyor_profit"
@export var gameplay: ConveyorGameplay
@export var camera: Camera3D


func _ready() -> void:
	if gameplay != null and not gameplay.game_finished.is_connected(_on_game_finished):
		gameplay.game_finished.connect(_on_game_finished)


func set_ai_control_active(value: bool) -> void:
	if gameplay != null:
		gameplay.set_ai_control_active(value)


func execute_semantic_action(action: Dictionary) -> Dictionary:
	if gameplay == null:
		return {"status": "error", "error": "semantic action is unavailable"}
	var action_type := String(action.get("type", ""))
	var result: Dictionary
	match action_type:
		"select_ingredient":
			result = gameplay.request_select_ingredient(String(action.get("ingredient", "")), camera)
		"undo":
			result = gameplay.request_undo()
		"make":
			result = gameplay.request_make()
		"wait_next_window":
			result = gameplay.request_wait_next_window()
		_:
			return {"status": "error", "error": "semantic action is unavailable"}
	var public_result := {
		"status": "completed",
		"type": action_type,
		"outcome": String(result.get("outcome", "game_finished")),
	}
	if action_type == "select_ingredient" and result.has("ingredient"):
		public_result["ingredient"] = String(result["ingredient"])
	return public_result


func _on_game_finished(outcome: String, reason: String) -> void:
	game_finished.emit(outcome, reason)
