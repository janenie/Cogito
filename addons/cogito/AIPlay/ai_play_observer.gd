class_name AIPlayObserver
extends Node

const APPROVED_ACTIONS: Array[String] = [
	"forward", "back", "left", "right", "jump", "sprint", "crouch", "interact",
	"interact2", "menu",
]
const IMAGE_WIDTH: int = 768
const IMAGE_HEIGHT: int = 432

@export var player: CogitoPlayer
@export_range(0.0, 1.0, 0.01) var jpeg_quality: float = 0.75

var bindings: Dictionary = {}
var _observation_id: int = 0


func capture_observation(last_results: Array) -> Dictionary:
	_observation_id += 1
	bindings = get_bindings()
	var image: Image
	if DisplayServer.get_name() == "headless":
		image = Image.create(IMAGE_WIDTH, IMAGE_HEIGHT, false, Image.FORMAT_RGB8)
	else:
		image = get_viewport().get_texture().get_image()
		image.resize(IMAGE_WIDTH, IMAGE_HEIGHT, Image.INTERPOLATE_LANCZOS)

	return {
		"observation_id": _observation_id,
		"captured_at_ms": Time.get_ticks_msec(),
		"image": {
			"mime_type": "image/jpeg",
			"base64": Marshalls.raw_to_base64(image.save_jpg_to_buffer(jpeg_quality)),
			"width": IMAGE_WIDTH,
			"height": IMAGE_HEIGHT,
		},
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
			"available_interactions": _available_interactions(),
		},
		"bindings": bindings,
		"last_action_results": last_results,
	}


func get_bindings() -> Dictionary:
	var result: Dictionary = {}
	for action_name: String in APPROVED_ACTIONS:
		result[action_name] = "unbound"
		for event: InputEvent in InputMap.action_get_events(action_name):
			if event is InputEventKey:
				var key_event := event as InputEventKey
				var label: String = OS.get_keycode_string(key_event.physical_keycode)
				if not label.is_empty():
					result[action_name] = label
				break
	bindings = result
	return result


func _available_interactions() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var target: Variant = player.player_interaction_component.interactable
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


func _attribute_ratio(attribute_name: String) -> Variant:
	var attribute: Variant = player.player_attributes.get(attribute_name)
	if attribute == null or attribute.value_max == 0.0:
		return null
	return attribute.value_current / attribute.value_max
