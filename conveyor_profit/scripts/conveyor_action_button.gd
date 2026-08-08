class_name ConveyorActionButton
extends StaticBody3D

signal activated(action: String)

@export_enum("make") var action: String = "make"
var enabled: bool = true


func activate() -> bool:
	if not enabled:
		return false
	activated.emit(action)
	return true


func _input_event(
	_camera: Node,
	event: InputEvent,
	_event_position: Vector3,
	_normal: Vector3,
	_shape_index: int,
) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		activate()
