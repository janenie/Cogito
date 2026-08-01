class_name AIPlayHomeObserver
extends Node

const APPROVED_ACTIONS: Array[String] = [
	"forward", "back", "left", "right", "jump", "sprint", "interact",
	"crouch", "interact2", "menu",
]
const IMAGE_WIDTH: int = 1024
const IMAGE_HEIGHT: int = 576
const MAX_JSON_DEPTH: int = 16
const DepthCapture = preload("res://addons/cogito/AIPlay/ai_play_depth_capture.gd")

@export var player: Node3D
@export var manager: Node
@export_range(0.0, 1.0, 0.01) var jpeg_quality: float = 0.75

var bindings: Dictionary = {}
var _observation_id: int = 0
var _depth_capture = null


func capture_observation(last_results: Array) -> Dictionary:
	_observation_id += 1
	bindings = get_bindings()
	var image := _capture_image()
	var depth_image := _capture_depth_image()
	var orientation := _orientation()
	return {
		"observation_id": _observation_id,
		"captured_at_ms": Time.get_ticks_msec(),
		"image": {
			"mime_type": "image/jpeg",
			"base64": Marshalls.raw_to_base64(image.save_jpg_to_buffer(jpeg_quality)),
			"width": IMAGE_WIDTH,
			"height": IMAGE_HEIGHT,
		},
		"depth_image": depth_image,
		"player": {
			"position": [player.position.x, player.position.y, player.position.z],
			"yaw_degrees": orientation.x,
			"pitch_degrees": orientation.y,
			"planar_velocity": [player.velocity.x, player.velocity.z],
			"on_floor": player.is_on_floor(),
			"health_ratio": null,
			"stamina_ratio": null,
		},
		"interface": {
			"is_open": player.has_method("is_readable_open") and player.is_readable_open(),
			"visible_object_text": "",
			"available_interactions": get_available_interactions(),
		},
		"routine": {
			"objective": manager.current_objective,
			"trash_collected": manager.collected_trash_count,
			"trash_required": manager.required_trash_count,
			"held_item": manager.held_item_label(),
			"completed": manager.routine_complete,
			"failed": manager.routine_failed,
		},
		"bindings": bindings,
		"last_action_results": _sanitize_last_results(last_results),
	}


func get_bindings() -> Dictionary:
	var result: Dictionary = {}
	for action_name: String in APPROVED_ACTIONS:
		result[action_name] = "unbound"
		for event: InputEvent in InputMap.action_get_events(action_name):
			if event is InputEventKey:
				var key_event := event as InputEventKey
				var label := OS.get_keycode_string(key_event.physical_keycode)
				if not label.is_empty():
					result[action_name] = label
				break
	bindings = result
	return result


func get_available_interactions() -> Array[Dictionary]:
	var target: Node = null
	if player != null and player.has_method("current_interaction_target"):
		target = player.current_interaction_target()
	if target == null:
		return []
	var prompt := ""
	if player != null and player.has_method("get_interaction_prompt_for_test"):
		prompt = player.get_interaction_prompt_for_test(target)
	if prompt.is_empty():
		return []
	return [{
		"action": "interact",
		"binding": bindings.get("interact", "unbound"),
		"prompt": prompt,
	}]


func _capture_image() -> Image:
	if DisplayServer.get_name() == "headless":
		return Image.create(IMAGE_WIDTH, IMAGE_HEIGHT, false, Image.FORMAT_RGB8)
	var image := get_viewport().get_texture().get_image()
	image.resize(IMAGE_WIDTH, IMAGE_HEIGHT, Image.INTERPOLATE_LANCZOS)
	return image


func _capture_depth_image() -> Dictionary:
	if _depth_capture == null or not is_instance_valid(_depth_capture):
		_depth_capture = DepthCapture.new()
		add_child(_depth_capture)
	return _depth_capture.capture(_active_camera(), IMAGE_WIDTH, IMAGE_HEIGHT)


func _active_camera() -> Camera3D:
	if player != null and "camera" in player:
		var active_camera := player.get("camera") as Camera3D
		if active_camera != null:
			return active_camera
	var viewport := get_viewport()
	return viewport.get_camera_3d() if viewport != null else null


func _orientation() -> Vector2:
	if player != null and player.has_method("ai_play_orientation_degrees"):
		return player.ai_play_orientation_degrees()
	return Vector2.ZERO


func _sanitize_last_results(last_results: Array) -> Array:
	var safe_results: Array = []
	for result: Variant in last_results:
		var sanitized := _sanitize_json_value(result)
		if sanitized["valid"]:
			safe_results.append(sanitized["value"])
	return safe_results


func _sanitize_json_value(value: Variant, depth: int = 0) -> Dictionary:
	if depth > MAX_JSON_DEPTH:
		return {"valid": false}
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_STRING:
			return {"valid": true, "value": value}
		TYPE_FLOAT:
			return {"valid": is_finite(value), "value": value}
		TYPE_ARRAY:
			var safe_array: Array = []
			for item: Variant in value:
				var sanitized_item := _sanitize_json_value(item, depth + 1)
				if not sanitized_item["valid"]:
					return {"valid": false}
				safe_array.append(sanitized_item["value"])
			return {"valid": true, "value": safe_array}
		TYPE_DICTIONARY:
			var safe_dictionary: Dictionary = {}
			for key: Variant in value:
				if not key is String:
					return {"valid": false}
				var sanitized_value := _sanitize_json_value(value[key], depth + 1)
				if not sanitized_value["valid"]:
					return {"valid": false}
				safe_dictionary[key] = sanitized_value["value"]
			return {"valid": true, "value": safe_dictionary}
	return {"valid": false}
