class_name IngredientInteractable
extends Area3D

signal select_requested(selection_id: int)

@export var selection_id: int = -1
var enabled: bool = true


func select() -> bool:
	if not enabled or selection_id < 0:
		return false
	select_requested.emit(selection_id)
	return true


func _input_event(
	_camera: Node,
	event: InputEvent,
	_event_position: Vector3,
	_normal: Vector3,
	_shape_index: int,
) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		select()
