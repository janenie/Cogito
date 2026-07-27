extends SceneTree

const APPROVED_ACTIONS: Array[String] = [
	"forward", "back", "left", "right", "jump", "sprint", "crouch", "interact",
	"interact2", "menu",
]

var _failures: Array[String] = []


class FakeInteractable extends Node:
	var interaction_nodes: Array[Node] = []


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	var observer_script: GDScript = load("res://addons/cogito/AIPlay/ai_play_observer.gd")
	var observer: Node = observer_script.new()
	root.add_child(observer)
	var player_script: GDScript = load("res://addons/cogito/CogitoObjects/cogito_player.gd")
	var player: CharacterBody3D = player_script.new()
	player.name = "secret_player_node"
	player.body = Node3D.new()
	player.head = Node3D.new()
	var interaction_controller_script: GDScript = load(
		"res://addons/cogito/Components/PlayerInteractionComponent.gd"
	)
	var interaction_controller: Node = interaction_controller_script.new()
	player.player_interaction_component = interaction_controller
	player.player_attributes = {}
	root.add_child(player.body)
	player.body.global_rotation_degrees = Vector3(0.0, 37.0, 0.0)
	player.head.rotation_degrees = Vector3(-12.0, 0.0, 0.0)
	player.velocity = Vector3(3.0, 9.0, -4.0)
	observer.player = player

	var target := FakeInteractable.new()
	target.name = "secret_target_node"
	var interaction_script: GDScript = load(
		"res://addons/cogito/Components/Interactions/InteractionComponent.gd"
	)
	var primary: Node = interaction_script.new()
	primary.name = "secret_primary_component"
	primary.input_map_action = "interact"
	primary.interaction_text = "Read"
	var secondary: Node = interaction_script.new()
	secondary.input_map_action = "interact2"
	secondary.interaction_text = "Move"
	var disabled: Node = interaction_script.new()
	disabled.input_map_action = "interact"
	disabled.interaction_text = "Hidden"
	disabled.is_disabled = true
	var unapproved: Node = interaction_script.new()
	unapproved.input_map_action = "reload"
	unapproved.interaction_text = "Reload"
	target.interaction_nodes.assign([primary, secondary, disabled, unapproved])
	target.add_child(primary)
	target.add_child(secondary)
	target.add_child(disabled)
	target.add_child(unapproved)
	player.player_interaction_component.interactable = target
	observer.get_bindings()
	_assert(
		observer.get_available_interactions() == [
			{"action": "interact", "binding": "F", "prompt": "Read"},
			{"action": "interact2", "binding": "E", "prompt": "Move"},
		],
		"observer publicly exposes only approved visible interactions",
	)

	await process_frame
	var observation: Dictionary = observer.capture_observation([{"status": "completed"}])
	var bindings: Dictionary = observer.get_bindings()
	_assert(bindings.keys().size() == APPROVED_ACTIONS.size(), "bindings contain ten actions")
	for action_name: String in bindings:
		_assert(action_name in APPROVED_ACTIONS, "binding action %s is approved" % action_name)
	_assert(bindings.get("interact") == "F", "default interact binding is F")
	_assert(bindings.get("interact2") == "E", "default interact2 binding is E")

	var interactions: Array = observation.get("interface", {}).get("available_interactions", [])
	_assert(interactions == [
		{"action": "interact", "binding": "F", "prompt": "Read"},
		{"action": "interact2", "binding": "E", "prompt": "Move"},
	], "only enabled approved interactions on current target are visible")

	var player_state: Dictionary = observation.get("player", {})
	_assert(player_state.get("position") == [0.0, 0.0, 0.0], "position is numeric array")
	_assert(is_equal_approx(player_state.get("yaw_degrees", 0.0), 37.0), "yaw comes from body")
	_assert(is_equal_approx(player_state.get("pitch_degrees", 0.0), -12.0), "pitch comes from head")
	_assert(player_state.get("planar_velocity") == [3.0, -4.0], "velocity is planar")
	_assert(player_state.get("health_ratio") == null, "missing health ratio is null")
	_assert(player_state.get("stamina_ratio") == null, "missing stamina ratio is null")
	_assert(observation.get("last_action_results") == [{"status": "completed"}], "last results pass through")
	var safe_nested: Array = [1, "safe"]
	var injected_node := Node.new()
	injected_node.name = "secret_injected_result_node"
	var filtered_observation: Dictionary = observer.capture_observation([
		{"status": "completed", "nested": safe_nested},
		{"status": "bad", "value": injected_node},
		{"status": "bad", "value": NodePath("/root/secret_result_path")},
		{"status": "bad", "value": INF},
	])
	safe_nested.append("mutated_after_capture")
	_assert(filtered_observation.get("last_action_results") == [
		{"status": "completed", "nested": [1, "safe"]},
	], "last results filter invalid entries and deep-copy safe values")
	_assert(
		_contains_only_json_values(filtered_observation),
		"filtered observation remains JSON-compatible",
	)
	_assert(not _contains_only_json_values(INF), "JSON test helper rejects non-finite floats")

	var find_contract_script: GDScript = load(
		"res://addons/cogito/AIPlay/ai_play_find_contract_observer.gd"
	)
	var find_contract_observer: Node = find_contract_script.new()
	find_contract_observer.player = player
	root.add_child(find_contract_observer)
	var find_contract_observation: Dictionary = find_contract_observer.capture_observation([])
	var find_contract_player: Dictionary = find_contract_observation.get("player", {})
	_assert(
		not find_contract_player.has("health_ratio"),
		"find_contract observer omits health ratio",
	)
	_assert(
		not find_contract_player.has("stamina_ratio"),
		"find_contract observer omits stamina ratio",
	)

	var image_payload: Dictionary = observation.get("image", {})
	_assert(image_payload.get("mime_type") == "image/jpeg", "image MIME type is JPEG")
	_assert(image_payload.get("width") == 768 and image_payload.get("height") == 432, "image reports 768x432")
	var jpeg_bytes: PackedByteArray = Marshalls.base64_to_raw(image_payload.get("base64", ""))
	var decoded := Image.new()
	_assert(decoded.load_jpg_from_buffer(jpeg_bytes) == OK, "image base64 decodes as JPEG")
	_assert(decoded.get_size() == Vector2i(768, 432), "JPEG is resized to 768x432")
	var depth_payload: Dictionary = observation.get("depth_image", {})
	_assert(depth_payload.get("mime_type") == "image/png", "observation includes PNG depth")
	_assert(
		depth_payload.get("width") == 768 and depth_payload.get("height") == 432,
		"depth dimensions match screenshot",
	)
	_assert(
		depth_payload.get("encoding") == "linear_depth_normalized_8bit",
		"depth encoding is public",
	)
	var decoded_depth := Image.new()
	_assert(
		decoded_depth.load_png_from_buffer(
			Marshalls.base64_to_raw(depth_payload.get("base64", ""))
		) == OK,
		"depth base64 decodes as PNG",
	)
	_assert(decoded_depth.get_size() == Vector2i(768, 432), "depth is resized to 768x432")

	var serialized: String = str(observation)
	for forbidden: String in [
		"secret_player_node", "secret_target_node", "secret_primary_component", "NodePath",
		".gd", ".tscn", "script", "filename",
	]:
		_assert(forbidden.to_lower() not in serialized.to_lower(), "observation omits %s" % forbidden)
	_assert(_contains_only_json_values(observation), "observation contains only JSON-compatible values")

	var saved_events: Array[InputEvent] = InputMap.action_get_events("interact")
	InputMap.action_erase_events("interact")
	var rebound := InputEventKey.new()
	rebound.physical_keycode = KEY_Q
	InputMap.action_add_event("interact", rebound)
	_assert(observer.get_bindings().get("interact") == "Q", "bindings reflect runtime remapping")
	InputMap.action_erase_events("interact")
	for event: InputEvent in saved_events:
		InputMap.action_add_event("interact", event)

	observer.free()
	find_contract_observer.free()
	player.body.free()
	player.head.free()
	interaction_controller.free()
	injected_node.free()
	player.free()
	target.free()
	if _failures.is_empty():
		print("AIPlay observer tests passed")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _contains_only_json_values(value: Variant) -> bool:
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_STRING:
			return true
		TYPE_FLOAT:
			return is_finite(value)
		TYPE_ARRAY:
			for item: Variant in value:
				if not _contains_only_json_values(item):
					return false
			return true
		TYPE_DICTIONARY:
			for key: Variant in value:
				if not key is String or not _contains_only_json_values(value[key]):
					return false
			return true
		_:
			return false


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
