class_name AIPlayFindContractTerminal
extends Node

signal game_finished(outcome: String, reason: String)

@export var keypad: CogitoKeypad


func _ready() -> void:
	if keypad == null:
		push_error("AIPlayFindContractTerminal requires a keypad")
		return
	keypad.code_checked.connect(_on_code_checked)


func _on_code_checked(is_correct: bool) -> void:
	if is_correct:
		game_finished.emit("success", "correct_password")
	else:
		game_finished.emit("failure", "wrong_password")
