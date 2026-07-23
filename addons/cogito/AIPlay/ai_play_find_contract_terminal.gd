class_name AIPlayFindContractTerminal
extends Node

signal game_finished(outcome: String, reason: String)

@export var keypad: CogitoKeypad
@export var game_over_screen: AIPlayGameOverScreen


func _ready() -> void:
	if keypad == null:
		push_error("AIPlayFindContractTerminal requires a keypad")
		return
	if game_over_screen == null:
		push_error("AIPlayFindContractTerminal requires a game-over screen")
	keypad.code_checked.connect(_on_code_checked)


func _on_code_checked(is_correct: bool) -> void:
	if is_correct:
		game_finished.emit("success", "correct_password")
	else:
		game_finished.emit("failure", "wrong_password")


func show_result(outcome: String, reason: String) -> void:
	if game_over_screen == null:
		push_error("AIPlayFindContractTerminal cannot display the game result")
		return
	game_over_screen.show_result(outcome, reason)
