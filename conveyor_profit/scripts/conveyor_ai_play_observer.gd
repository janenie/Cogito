class_name ConveyorAIPlayObserver
extends Node

const APPROVED_ACTIONS: Array[String] = [
	"forward", "back", "left", "right", "jump", "sprint", "crouch", "interact",
	"interact2", "menu",
]
const IMAGE_WIDTH: int = 1024
const IMAGE_HEIGHT: int = 576
const MAX_JSON_DEPTH: int = 16

@export var gameplay: ConveyorGameplay
@export_range(0.0, 1.0, 0.01) var jpeg_quality: float = 0.75

var _observation_id: int = 0


func capture_observation(last_results: Array) -> Dictionary:
	_observation_id += 1
	var image := _capture_image()
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
			"position": [0.0, 0.0, 0.0],
			"yaw_degrees": 0.0,
			"pitch_degrees": 0.0,
			"planar_velocity": [0.0, 0.0],
			"on_floor": true,
			"health_ratio": null,
			"stamina_ratio": null,
		},
		"interface": {
			"is_open": false,
			"visible_object_text": "",
			"available_interactions": [],
		},
		"bindings": _unbound_bindings(),
		"last_action_results": _sanitize_last_results(last_results),
		"conveyor": _public_conveyor_state(),
	}


func get_available_interactions() -> Array[Dictionary]:
	return []


func _public_conveyor_state() -> Dictionary:
	var state: Dictionary = gameplay.get_public_state()
	var market: Dictionary = state.get("market", {})
	return {
		"total_time": state.get("total_time", "00:00"),
		"window": state.get("window", "1 / 10"),
		"window_time": state.get("window_time", "00:00"),
		"dish": state.get("dish", "0 / 1"),
		"net_profit": state.get("net_profit", 0),
		"tray": state.get("tray", []).duplicate(),
		"last_receipt": state.get("last_receipt", {}).duplicate(true),
		"market": {
			"category_multipliers": market.get("category_multipliers", {}).duplicate(),
			"signals": market.get("signals", []).duplicate(),
		},
		"contracts": state.get("contracts", []).duplicate(true),
		"finished": state.get("finished", false),
	}


func _capture_image() -> Image:
	if DisplayServer.get_name() == "headless":
		return Image.create(IMAGE_WIDTH, IMAGE_HEIGHT, false, Image.FORMAT_RGB8)
	var image := get_viewport().get_texture().get_image()
	image.resize(IMAGE_WIDTH, IMAGE_HEIGHT, Image.INTERPOLATE_LANCZOS)
	return image


func _unbound_bindings() -> Dictionary:
	var result: Dictionary = {}
	for action_name: String in APPROVED_ACTIONS:
		result[action_name] = "unbound"
	return result


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
