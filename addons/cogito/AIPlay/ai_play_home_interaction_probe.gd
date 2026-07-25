class_name AIPlayHomeInteractionProbe
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
	if not _is_available():
		return {"status": "error", "error": "interaction probe is unavailable"}
	_generation += 1
	var generation: int = _generation
	_cancel_reason = "cancelled"
	var active_camera := _active_camera()
	var target_rotation := target_rotation_degrees(
		target_x,
		target_y,
		active_camera.fov,
		_viewport_aspect_ratio(),
	)
	var previous_rotation := Vector2.ZERO
	for scan_index: int in SCAN_OFFSETS_DEGREES.size():
		var scan_rotation := target_rotation + SCAN_OFFSETS_DEGREES[scan_index]
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
	aspect_ratio: float,
) -> Vector2:
	var vertical_tangent := tan(deg_to_rad(vertical_fov_degrees * 0.5))
	var ndc_x := target_x * 2.0 - 1.0
	var ndc_y := target_y * 2.0 - 1.0
	var yaw := rad_to_deg(atan(ndc_x * vertical_tangent * aspect_ratio))
	var pitch := rad_to_deg(atan(ndc_y * vertical_tangent))
	return Vector2(yaw, pitch)


func _active_camera() -> Camera3D:
	if player != null and "camera" in player:
		return player.get("camera") as Camera3D
	return get_viewport().get_camera_3d()


func _is_available() -> bool:
	return (
		player != null
		and is_instance_valid(player)
		and _active_camera() != null
		and "mouse_sensitivity" in player
		and interaction_provider.is_valid()
	)


func _viewport_aspect_ratio() -> float:
	var viewport_size := get_viewport().get_visible_rect().size
	return 1.0 if viewport_size.y <= 0.0 else viewport_size.x / viewport_size.y


func _emit_mouse_rotation(target_rotation: Vector2) -> void:
	var sensitivity := maxf(float(player.get("mouse_sensitivity")), 0.0001)
	var motion := InputEventMouseMotion.new()
	motion.device = SYNTHETIC_DEVICE_ID
	motion.relative = Vector2(target_rotation.x / sensitivity, target_rotation.y / sensitivity)
	motion.screen_relative = motion.relative
	if input_sender.is_valid():
		input_sender.call(motion)
	else:
		Input.parse_input_event(motion)
