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
const INTERACTION_SETTLE_CHECKS: int = 3

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
		for _settle_check: int in INTERACTION_SETTLE_CHECKS:
			await _wait_for_interaction_update()
			if generation != _generation:
				return {"status": "cancelled", "reason": _cancel_reason}
			var interactions: Variant = (
				interaction_provider.call() if interaction_provider.is_valid() else []
			)
			var public_interactions := _public_interactions(interactions)
			if not public_interactions.is_empty():
				return {
					"status": "completed",
					"type": "probe_interaction",
					"outcome": "aligned",
					"scan_steps": scan_index + 1,
					"available_interactions": public_interactions,
				}
	return {
		"status": "completed",
		"type": "probe_interaction",
		"outcome": "not_found",
		"scan_steps": SCAN_OFFSETS_DEGREES.size(),
	}


func _wait_for_interaction_update() -> void:
	await get_tree().physics_frame
	await get_tree().create_timer(0.0).timeout


func _public_interactions(value: Variant) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var seen_actions: Array[String] = []
	if not value is Array:
		return result
	for candidate: Variant in value:
		if not candidate is Dictionary:
			continue
		var interaction := candidate as Dictionary
		var action: Variant = interaction.get("action")
		var binding: Variant = interaction.get("binding")
		var prompt: Variant = interaction.get("prompt")
		if (
			not action is String
			or action not in ["interact", "interact2"]
			or action in seen_actions
			or not binding is String
			or binding.is_empty()
			or binding.length() > 32
			or not prompt is String
			or prompt.length() > 200
		):
			continue
		seen_actions.append(action)
		result.append({
			"action": action,
			"binding": binding,
			"prompt": prompt,
		})
		if result.size() == 2:
			break
	return result


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
