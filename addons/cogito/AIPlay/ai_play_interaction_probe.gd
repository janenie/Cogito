class_name AIPlayInteractionProbe
extends Node

const SYNTHETIC_DEVICE_ID: int = 0x7ffffffe
const SCAN_OFFSETS_DEGREES: Array[Vector2] = [
	Vector2.ZERO,
	Vector2(2.0, 0.0),
	Vector2(-2.0, 0.0),
	Vector2(0.0, 2.0),
	Vector2(0.0, -2.0),
	Vector2(4.0, 4.0),
	Vector2(-4.0, 4.0),
	Vector2(4.0, -4.0),
	Vector2(-4.0, -4.0),
]

var player: Node
var interaction_provider: Callable
var input_sender: Callable
var _generation: int = 0
var _cancel_reason: String = "cancelled"


func probe(target_x: float, target_y: float) -> Dictionary:
	_generation += 1
	var generation: int = _generation
	_cancel_reason = "cancelled"
	var starting_orientation := _orientation_degrees()
	var target_rotation := target_rotation_degrees(
		target_x,
		target_y,
		_active_camera().fov,
		_viewport_aspect_ratio(),
	)
	var previous_rotation := Vector2.ZERO

	for scan_index: int in SCAN_OFFSETS_DEGREES.size():
		var scan_rotation: Vector2 = target_rotation + SCAN_OFFSETS_DEGREES[scan_index]
		_emit_mouse_rotation(scan_rotation - previous_rotation)
		previous_rotation = scan_rotation
		await get_tree().process_frame
		if generation != _generation:
			return {"status": "cancelled", "reason": _cancel_reason}
		var interactions: Variant = interaction_provider.call() if interaction_provider.is_valid() else []
		if interactions is Array and not interactions.is_empty():
			return {
				"status": "completed",
				"type": "probe_interaction",
				"outcome": "aligned",
				"scan_steps": scan_index + 1,
			}

	_restore_orientation(starting_orientation)
	await get_tree().process_frame
	if generation != _generation:
		return {"status": "cancelled", "reason": _cancel_reason}
	return {
		"status": "completed",
		"type": "probe_interaction",
		"outcome": "not_found",
		"scan_steps": SCAN_OFFSETS_DEGREES.size(),
	}


func cancel(reason: String) -> void:
	_cancel_reason = reason
	_generation += 1


func target_rotation_degrees(
	target_x: float,
	target_y: float,
	vertical_fov_degrees: float,
	aspect_ratio: float
) -> Vector2:
	var vertical_tangent := tan(deg_to_rad(vertical_fov_degrees * 0.5))
	var ndc_x := target_x * 2.0 - 1.0
	var ndc_y := target_y * 2.0 - 1.0
	var yaw := rad_to_deg(atan(ndc_x * vertical_tangent * aspect_ratio))
	var pitch := rad_to_deg(atan(ndc_y * vertical_tangent))
	return Vector2(yaw, pitch)


func _active_camera() -> Camera3D:
	var active_camera: Camera3D = get_viewport().get_camera_3d()
	if active_camera != null:
		return active_camera
	return player.get("camera") as Camera3D


func _viewport_aspect_ratio() -> float:
	var viewport_size := get_viewport().get_visible_rect().size
	if viewport_size.y <= 0.0:
		return 1.0
	return viewport_size.x / viewport_size.y


func _orientation_degrees() -> Vector2:
	var body: Node3D = player.get("body") as Node3D
	var head: Node3D = player.get("head") as Node3D
	return Vector2(body.global_rotation_degrees.y, head.rotation_degrees.x)


func _restore_orientation(starting_orientation: Vector2) -> void:
	var current_orientation := _orientation_degrees()
	var yaw_to_start := wrapf(starting_orientation.x - current_orientation.x, -180.0, 180.0)
	var pitch_to_start := clampf(starting_orientation.y - current_orientation.y, -90.0, 90.0)
	_emit_mouse_rotation(Vector2(-yaw_to_start, -pitch_to_start))


func _emit_mouse_rotation(target_rotation: Vector2) -> void:
	var mouse_sensitivity: float = float(player.get("MOUSE_SENS"))
	var invert_y_axis: bool = bool(player.get("INVERT_Y_AXIS"))
	var yaw_to_right: float = target_rotation.x
	var pitch_to_bottom: float = target_rotation.y
	var desired_yaw_delta := -yaw_to_right
	var desired_pitch_delta := -pitch_to_bottom
	var relative_x := -desired_yaw_delta / mouse_sensitivity
	var relative_y := (
		desired_pitch_delta / mouse_sensitivity
		if invert_y_axis
		else -desired_pitch_delta / mouse_sensitivity
	)
	var motion := InputEventMouseMotion.new()
	motion.device = SYNTHETIC_DEVICE_ID
	motion.relative = Vector2(relative_x, relative_y)
	motion.screen_relative = motion.relative
	if input_sender.is_valid():
		input_sender.call(motion)
	else:
		Input.parse_input_event(motion)
