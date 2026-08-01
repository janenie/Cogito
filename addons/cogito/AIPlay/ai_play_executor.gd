class_name AIPlayExecutor
extends Node

signal batch_finished(results: Array)

const ACTION_FIELDS: Dictionary = {
	"look": ["type", "direction", "degrees"],
	"move": ["type", "forward", "right", "duration_ms"],
	"sprint": ["type", "forward", "right", "duration_ms"],
	"jump": ["type"],
	"crouch": ["type"],
	"interact": ["type", "action"],
	"probe_interaction": ["type", "target_x", "target_y"],
	"enter_digits": ["type", "digits"],
	"close_ui": ["type"],
	"wait": ["type", "duration_ms"],
	"stop": ["type"],
	"select_ingredient": ["type", "ingredient"],
	"undo": ["type"],
	"make": ["type"],
}
const CONVEYOR_ACTIONS: Array[String] = ["select_ingredient", "undo", "make"]
const CONVEYOR_INGREDIENT_IDS: Array[String] = [
	"lettuce", "tomato", "bread", "egg", "mushroom", "cheese", "fish", "meat",
]
const HELD_INPUTS: Array[String] = ["forward", "back", "left", "right", "sprint"]
const SYNTHETIC_DEVICE_ID: int = 0x7ffffffe
const MIN_BLOCKED_DISTANCE_THRESHOLD: float = 0.01
const LOOK_DIRECTIONS: Array[String] = ["left", "right", "up", "down"]
const LOOK_MAX_DEGREES: float = 45.0
const MOVE_MAX_DURATION_MS: float = 250.0

@export var player: Node3D
@export_range(0.01, 10.0, 0.01) var blocked_distance_threshold: float = 0.05

var held_actions: Dictionary = {}
var interaction_probe: Node
var semantic_action_provider: Node
var active_scenario_id: String = ""
var _cancel_generation: int = 0


func _exit_tree() -> void:
	_cancel_generation += 1
	if interaction_probe != null:
		interaction_probe.cancel("executor_teardown")
	_release_held_actions()


func validate_action(action: Variant, context: Dictionary) -> Dictionary:
	if not action is Dictionary:
		return _invalid("action must be an object")
	var action_dictionary: Dictionary = action
	var action_type_value: Variant = action_dictionary.get("type")
	if not action_type_value is String or not ACTION_FIELDS.has(action_type_value):
		return _invalid("action type is not allowed")
	var action_type: String = action_type_value
	if not _has_exact_fields(action_dictionary, ACTION_FIELDS[action_type]):
		return _invalid("action has invalid fields")
	if action_type in CONVEYOR_ACTIONS and active_scenario_id != "conveyor_profit":
		return _invalid("action is not allowed for this scenario")

	match action_type:
		"look":
			var direction: Variant = action_dictionary["direction"]
			if not direction is String or direction not in LOOK_DIRECTIONS:
				return _invalid("look direction is not allowed")
			var error: String = _number_error(
				action_dictionary["degrees"], 1.0, LOOK_MAX_DEGREES, "degrees"
			)
			if not error.is_empty():
				return _invalid(error)
		"move", "sprint":
			for field: String in ["forward", "right"]:
				var error: String = _number_error(action_dictionary[field], -1.0, 1.0, field)
				if not error.is_empty():
					return _invalid(error)
			var duration_error: String = _number_error(
				action_dictionary["duration_ms"], 50.0, MOVE_MAX_DURATION_MS, "duration_ms"
			)
			if not duration_error.is_empty():
				return _invalid(duration_error)
		"wait":
			var error: String = _number_error(
				action_dictionary["duration_ms"], 50.0, 2000.0, "duration_ms"
			)
			if not error.is_empty():
				return _invalid(error)
		"interact":
			var interaction: Variant = action_dictionary["action"]
			if not interaction is String or interaction not in ["interact", "interact2"]:
				return _invalid("interaction action is not allowed")
			var available: Variant = context.get("available_interactions", [])
			if not available is Array or interaction not in available:
				return _invalid("interaction is not currently available")
		"probe_interaction":
			for field: String in ["target_x", "target_y"]:
				var error: String = _number_error(
					action_dictionary[field], 0.0, 1.0, field
				)
				if not error.is_empty():
					return _invalid(error)
			if context.get("interface_open", false) == true:
				return _invalid("probe_interaction requires a closed interface")
		"enter_digits":
			var digits: Variant = action_dictionary["digits"]
			if not digits is String or not _digits_are_valid(digits):
				return _invalid("digits must contain one to six decimal digits")
			if context.get("interface_open", false) != true:
				return _invalid("enter_digits requires an open interface")
		"close_ui":
			if context.get("interface_open", false) != true:
				return _invalid("close_ui requires an open interface")
		"select_ingredient":
			var ingredient: Variant = action_dictionary["ingredient"]
			if not ingredient is String or ingredient not in CONVEYOR_INGREDIENT_IDS:
				return _invalid("ingredient is not allowed")

	return {"valid": true}


func validate_batch(actions: Variant, context: Dictionary) -> Dictionary:
	if not actions is Array or actions.size() < 1 or actions.size() > 3:
		return _invalid("actions must contain 1..3 entries")
	for index: int in actions.size():
		var action_validation: Dictionary = validate_action(actions[index], context)
		if not action_validation.get("valid", false):
			return action_validation
		if actions[index]["type"] == "probe_interaction" and actions.size() != 1:
			return _invalid("probe_interaction must be the only action")
		if (
			actions[index]["type"] in ["stop", "interact", "enter_digits", "close_ui", "make"]
			and index != actions.size() - 1
		):
			return _invalid("context-changing action must be last")
	return {"valid": true}


func execute_batch(actions: Variant, context: Dictionary) -> void:
	_cancel_generation += 1
	var generation: int = _cancel_generation
	_release_held_actions()
	var results: Array = []

	var validation: Dictionary = validate_batch(actions, context)
	if not validation.get("valid", false):
		results.append({"status": "error", "error": validation.get("error", "invalid action")})
		batch_finished.emit(results)
		return

	for action: Variant in actions:
		var result: Dictionary = await _execute_action(action, generation)
		if generation != _cancel_generation:
			return
		results.append(result)
		if result.get("status") in ["error", "stopped", "blocked"]:
			_release_held_actions()
			batch_finished.emit(results)
			return

	_release_held_actions()
	batch_finished.emit(results)


func cancel_all(reason: String) -> void:
	_release_held_actions()
	_cancel_generation += 1
	if interaction_probe != null:
		interaction_probe.cancel(reason)
	batch_finished.emit([{"status": "cancelled", "reason": reason}])


func _execute_action(action: Dictionary, generation: int) -> Dictionary:
	var action_type: String = action["type"]
	match action_type:
		"look":
			var look_delta := _semantic_look_delta(
				action["direction"], float(action["degrees"])
			)
			if player != null and player.has_method("ai_play_look_degrees"):
				player.ai_play_look_degrees(look_delta.x, look_delta.y)
			else:
				var motion := InputEventMouseMotion.new()
				motion.device = SYNTHETIC_DEVICE_ID
				motion.relative = _look_degrees_to_mouse_relative(look_delta.x, look_delta.y)
				motion.screen_relative = motion.relative
				Input.parse_input_event(motion)
		"move", "sprint":
			var movement_requested: bool = (
				not is_zero_approx(float(action["forward"]))
				or not is_zero_approx(float(action["right"]))
			)
			var start_position := Vector2.ZERO
			if player != null and movement_requested:
				start_position = Vector2(player.global_position.x, player.global_position.z)
			_press_axis("forward", "back", float(action["forward"]))
			_press_axis("right", "left", float(action["right"]))
			if action_type == "sprint":
				_press_held("sprint", 1.0)
			await get_tree().create_timer(float(action["duration_ms"]) / 1000.0).timeout
			if generation != _cancel_generation:
				return {"status": "cancelled"}
			_release_held_actions()
			if player != null and movement_requested:
				var end_position := Vector2(player.global_position.x, player.global_position.z)
				if start_position.distance_to(end_position) < _effective_blocked_distance_threshold():
					return {"status": "blocked", "type": action_type}
		"jump", "crouch":
			_emit_action_pair(action_type)
		"interact":
			_emit_action_pair(action["action"])
		"probe_interaction":
			if interaction_probe == null:
				return {"status": "error", "error": "interaction probe is unavailable"}
			return await interaction_probe.probe(
				float(action["target_x"]),
				float(action["target_y"]),
			)
		"enter_digits":
			for digit: String in action["digits"]:
				_emit_digit_pair(digit)
		"close_ui":
			_emit_action_pair("menu")
		"wait":
			await get_tree().create_timer(float(action["duration_ms"]) / 1000.0).timeout
			if generation != _cancel_generation:
				return {"status": "cancelled"}
		"stop":
			_release_held_actions()
			return {"status": "stopped", "type": "stop"}
		"select_ingredient", "undo", "make":
			if semantic_action_provider == null:
				return {"status": "error", "error": "semantic action provider is unavailable"}
			return semantic_action_provider.execute_semantic_action(action)
		_:
			return {"status": "error", "error": "action type is not allowed"}
	return {"status": "completed", "type": action_type}


func _semantic_look_delta(direction: String, degrees: float) -> Vector2:
	match direction:
		"left":
			return Vector2(-degrees, 0.0)
		"right":
			return Vector2(degrees, 0.0)
		"up":
			return Vector2(0.0, -degrees)
		"down":
			return Vector2(0.0, degrees)
	return Vector2.ZERO


func _look_degrees_to_mouse_relative(yaw_degrees: float, pitch_degrees: float) -> Vector2:
	if player != null:
		var home_sensitivity_value: Variant = player.get("mouse_sensitivity")
		if typeof(home_sensitivity_value) in [TYPE_INT, TYPE_FLOAT]:
			var home_sensitivity := maxf(float(home_sensitivity_value), 0.0001)
			return Vector2(
				deg_to_rad(yaw_degrees) / home_sensitivity,
				deg_to_rad(pitch_degrees) / home_sensitivity
			)
		var cogito_sensitivity_value: Variant = player.get("MOUSE_SENS")
		if typeof(cogito_sensitivity_value) in [TYPE_INT, TYPE_FLOAT]:
			var cogito_sensitivity := maxf(float(cogito_sensitivity_value), 0.0001)
			var relative_pitch := pitch_degrees / cogito_sensitivity
			if (
				"INVERT_Y_AXIS" in player
				and typeof(player.get("INVERT_Y_AXIS")) == TYPE_BOOL
				and bool(player.get("INVERT_Y_AXIS"))
			):
				relative_pitch = -relative_pitch
			return Vector2(yaw_degrees / cogito_sensitivity, relative_pitch)
	return Vector2(yaw_degrees, pitch_degrees)


func _effective_blocked_distance_threshold() -> float:
	return maxf(MIN_BLOCKED_DISTANCE_THRESHOLD, blocked_distance_threshold)


func _press_axis(positive_action: String, negative_action: String, value: float) -> void:
	if value > 0.0:
		_press_held(positive_action, value)
	elif value < 0.0:
		_press_held(negative_action, -value)


func _press_held(action_name: String, strength: float) -> void:
	Input.action_press(action_name, strength)
	held_actions[action_name] = true


func _release_held_actions() -> void:
	for action_name: String in held_actions.keys():
		Input.action_release(action_name)
	held_actions.clear()


func _emit_action_pair(action_name: String) -> void:
	var event := InputEventAction.new()
	event.device = SYNTHETIC_DEVICE_ID
	event.action = action_name
	event.pressed = true
	Input.parse_input_event(event)
	var release := InputEventAction.new()
	release.device = SYNTHETIC_DEVICE_ID
	release.action = action_name
	release.pressed = false
	Input.parse_input_event(release)


func _emit_digit_pair(digit: String) -> void:
	var code: int = digit.unicode_at(0)
	var event := InputEventKey.new()
	event.device = SYNTHETIC_DEVICE_ID
	event.keycode = code as Key
	event.unicode = code
	event.pressed = true
	Input.parse_input_event(event)
	var release := InputEventKey.new()
	release.device = SYNTHETIC_DEVICE_ID
	release.keycode = code as Key
	release.unicode = code
	release.pressed = false
	Input.parse_input_event(release)


func _has_exact_fields(action: Dictionary, expected: Array) -> bool:
	if action.size() != expected.size():
		return false
	for field: Variant in expected:
		if not action.has(field):
			return false
	return true


func _number_error(value: Variant, minimum: float, maximum: float, field: String) -> String:
	if typeof(value) not in [TYPE_INT, TYPE_FLOAT]:
		return "%s must be a finite number between %s and %s" % [field, minimum, maximum]
	var number: float = float(value)
	if not is_finite(number) or number < minimum or number > maximum:
		return "%s must be a finite number between %s and %s" % [field, minimum, maximum]
	return ""


func _digits_are_valid(digits: String) -> bool:
	if digits.length() < 1 or digits.length() > 6:
		return false
	for index: int in digits.length():
		var code: int = digits.unicode_at(index)
		if code < 48 or code > 57:
			return false
	return true


func _invalid(error: String) -> Dictionary:
	return {"valid": false, "error": error}
