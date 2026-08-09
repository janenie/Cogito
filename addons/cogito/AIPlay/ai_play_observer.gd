class_name AIPlayObserver
extends Node

const APPROVED_ACTIONS: Array[String] = [
	"forward", "back", "left", "right", "jump", "sprint", "crouch", "interact",
	"interact2", "menu",
]
const IMAGE_WIDTH: int = 1024
const IMAGE_HEIGHT: int = 576
const MAX_JSON_DEPTH: int = 16
const DepthCapture = preload("res://addons/cogito/AIPlay/ai_play_depth_capture.gd")

@export var player: CogitoPlayer
@export_range(0.0, 1.0, 0.01) var jpeg_quality: float = 0.75

var bindings: Dictionary = {}
var _observation_id: int = 0
var _depth_capture = null


func capture_observation(last_results: Array) -> Dictionary:
	_observation_id += 1
	bindings = get_bindings()
	var image: Image
	if DisplayServer.get_name() == "headless":
		# The dummy headless renderer has no viewport texture. This blank JPEG exists only
		# so automated tests can validate the wire shape; production requires a real viewport.
		image = Image.create(IMAGE_WIDTH, IMAGE_HEIGHT, false, Image.FORMAT_RGB8)
	else:
		RenderingServer.force_draw(false)
		image = get_viewport().get_texture().get_image()
		image.resize(IMAGE_WIDTH, IMAGE_HEIGHT, Image.INTERPOLATE_LANCZOS)
	var depth_image := _capture_depth_image()

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
			"position": [
				player.position.x,
				player.position.y,
				player.position.z,
			],
			"yaw_degrees": player.body.global_rotation_degrees.y,
			"pitch_degrees": player.head.rotation_degrees.x,
			"planar_velocity": [player.velocity.x, player.velocity.z],
			"on_floor": player.is_on_floor(),
			"health_ratio": _attribute_ratio("health"),
			"stamina_ratio": _attribute_ratio("stamina"),
		},
		"interface": {
			"is_open": player.is_showing_ui,
			"visible_object_text": "",
			"available_interactions": get_available_interactions(),
		},
		"bindings": bindings,
		"last_action_results": _sanitize_last_results(last_results),
	}


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


func get_bindings() -> Dictionary:
	var result: Dictionary = {}
	for action_name: String in APPROVED_ACTIONS:
		result[action_name] = "unbound"
		for event: InputEvent in InputMap.action_get_events(action_name):
			if event is InputEventKey:
				var key_event := event as InputEventKey
				var keycode: Key = key_event.physical_keycode
				if keycode == KEY_NONE:
					keycode = key_event.keycode
				var label: String = OS.get_keycode_string(keycode)
				if not label.is_empty():
					result[action_name] = label
				break
	bindings = result
	return result


func _available_interactions() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var interaction_controller: Variant = player.player_interaction_component
	if interaction_controller.get("is_carrying") == true:
		return _available_carry_interactions(interaction_controller)
	var target: Variant = interaction_controller.interactable
	if target == null:
		return result
	for component: Variant in target.interaction_nodes:
		if component.is_disabled or component.input_map_action not in ["interact", "interact2"]:
			continue
		result.append({
			"action": component.input_map_action,
			"binding": bindings.get(component.input_map_action, "unbound"),
			"prompt": tr(component.interaction_text),
		})
	return result


func _available_carry_interactions(interaction_controller: Variant) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var target: Variant = interaction_controller.interactable
	if target != null and target.get("interaction_nodes") is Array:
		for component: Variant in target.interaction_nodes:
			if component.get("prefer_while_carrying") != true:
				continue
			if component.has_method("set_disabled") and component.set_disabled(player):
				continue
			if component.is_disabled or component.input_map_action not in ["interact", "interact2"]:
				continue
			result.append({
				"action": component.input_map_action,
				"binding": bindings.get(component.input_map_action, "unbound"),
				"prompt": tr(component.interaction_text),
			})
	if not result.is_empty():
		return result

	var carried_object: Variant = interaction_controller.carried_object
	if carried_object == null or not is_instance_valid(carried_object):
		return result
	var drop_action: Variant = carried_object.get("input_map_action")
	if not drop_action is String or drop_action not in ["interact", "interact2"]:
		return result
	result.append({
		"action": drop_action,
		"binding": bindings.get(drop_action, "unbound"),
		"prompt": tr("INTERACT_drop"),
	})
	return result


func get_available_interactions() -> Array[Dictionary]:
	return _available_interactions()


func _attribute_ratio(attribute_name: String) -> Variant:
	var attribute: Variant = player.player_attributes.get(attribute_name)
	if attribute == null or attribute.value_max == 0.0:
		return null
	return attribute.value_current / attribute.value_max


func _sanitize_last_results(last_results: Array) -> Array:
	var safe_results: Array = []
	for result: Variant in last_results:
		var sanitized: Dictionary = _sanitize_json_value(result)
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
			if is_finite(value):
				return {"valid": true, "value": value}
		TYPE_ARRAY:
			var safe_array: Array = []
			for item: Variant in value:
				var sanitized_item: Dictionary = _sanitize_json_value(item, depth + 1)
				if not sanitized_item["valid"]:
					return {"valid": false}
				safe_array.append(sanitized_item["value"])
			return {"valid": true, "value": safe_array}
		TYPE_DICTIONARY:
			var safe_dictionary: Dictionary = {}
			for key: Variant in value:
				if not key is String:
					return {"valid": false}
				var sanitized_value: Dictionary = _sanitize_json_value(value[key], depth + 1)
				if not sanitized_value["valid"]:
					return {"valid": false}
				safe_dictionary[key] = sanitized_value["value"]
			return {"valid": true, "value": safe_dictionary}
	return {"valid": false}
