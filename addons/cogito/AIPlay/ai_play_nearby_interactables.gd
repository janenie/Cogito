class_name AIPlayNearbyInteractables
extends RefCounted

const MAX_OBJECTS: int = 5
const APPROVED_ACTIONS: Array[String] = ["interact", "interact2"]
const PROMPT_POSITION_MARKER: int = 1
const PROMPT_POSITION_AABB_CENTER: int = 2

var line_of_sight_provider: Callable
var _player: Node3D


func collect(
	player: Node3D,
	camera: Camera3D,
	candidates: Array,
	viewport_size: Vector2,
) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	if (
		player == null
		or camera == null
		or not is_instance_valid(player)
		or not is_instance_valid(camera)
		or viewport_size.x <= 0.0
		or viewport_size.y <= 0.0
	):
		return result

	_player = player
	for value: Variant in candidates:
		if not value is Node3D:
			continue
		var candidate := value as Node3D
		if not is_instance_valid(candidate) or not candidate.is_inside_tree():
			continue
		if not candidate.is_visible_in_tree():
			continue
		var interactions := _enabled_interactions(candidate)
		if interactions.is_empty():
			continue
		var point_value: Variant = _interaction_point(candidate)
		if point_value == null:
			continue
		var point := point_value as Vector3
		if not _is_in_camera(camera, point, viewport_size):
			continue
		if not _has_line_of_sight(camera, point, candidate):
			continue
		result.append(_describe_candidate(
			player,
			camera,
			candidate,
			point,
			interactions,
			viewport_size,
		))

	result.sort_custom(func(left: Dictionary, right: Dictionary) -> bool:
		return left["distance_m"] < right["distance_m"]
	)
	if result.size() > MAX_OBJECTS:
		result.resize(MAX_OBJECTS)
	return result


func _describe_candidate(
	player: Node3D,
	camera: Camera3D,
	candidate: Node3D,
	point: Vector3,
	interactions: Array[Dictionary],
	viewport_size: Vector2,
) -> Dictionary:
	var projected := camera.unproject_position(point)
	var relative := _relative_fields(camera, point - player.global_position)
	return {
		"tracking_id": candidate.get_instance_id(),
		"category": _category(candidate, interactions),
		"distance_m": player.global_position.distance_to(point),
		"world_position": _vector3_array(point),
		"relative_position": relative["position"],
		"relative_yaw_degrees": relative["yaw"],
		"relative_pitch_degrees": relative["pitch"],
		"screen_position": {
			"x": projected.x / viewport_size.x,
			"y": projected.y / viewport_size.y,
		},
		"interactions": interactions,
	}


func _enabled_interactions(candidate: Node) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	if not "interaction_nodes" in candidate:
		return result
	for value: Variant in candidate.get("interaction_nodes"):
		if not value is Node:
			continue
		var component := value as Node
		if (
			not "input_map_action" in component
			or not "interaction_text" in component
			or not "is_disabled" in component
		):
			continue
		var action := str(component.get("input_map_action"))
		if bool(component.get("is_disabled")) or action not in APPROVED_ACTIONS:
			continue
		result.append({
			"action": action,
			"prompt": tr(str(component.get("interaction_text"))),
		})
	return result


func _interaction_point(candidate: Node3D) -> Variant:
	var mode := 0
	if "prompt_pos_mode" in candidate:
		mode = int(candidate.get("prompt_pos_mode"))
	if mode == PROMPT_POSITION_MARKER and "prompt_marker" in candidate:
		var marker: Variant = candidate.get("prompt_marker")
		if marker is Node3D and is_instance_valid(marker):
			return (marker as Node3D).global_position
	if mode == PROMPT_POSITION_AABB_CENTER:
		var global_aabb: Variant = _global_aabb(candidate)
		if global_aabb != null:
			var bounds := global_aabb as AABB
			return bounds.position + bounds.size * 0.5
	return candidate.global_position


func _global_aabb(node: Node) -> Variant:
	var bounds: Variant = null
	if node is VisualInstance3D:
		var visual := node as VisualInstance3D
		var local_aabb := visual.get_aabb()
		var transformed := _transform_aabb(local_aabb, visual.global_transform)
		bounds = transformed
	for child: Node in node.get_children():
		var child_bounds: Variant = _global_aabb(child)
		if child_bounds == null:
			continue
		if bounds == null:
			bounds = child_bounds
		else:
			bounds = (bounds as AABB).merge(child_bounds as AABB)
	return bounds


func _transform_aabb(bounds: AABB, transform: Transform3D) -> AABB:
	var first := transform * bounds.position
	var result := AABB(first, Vector3.ZERO)
	for x: int in range(2):
		for y: int in range(2):
			for z: int in range(2):
				var corner := bounds.position + Vector3(
					bounds.size.x * x,
					bounds.size.y * y,
					bounds.size.z * z,
				)
				result = result.expand(transform * corner)
	return result


func _is_in_camera(camera: Camera3D, point: Vector3, viewport_size: Vector2) -> bool:
	if camera.is_position_behind(point) or not camera.is_position_in_frustum(point):
		return false
	var projected := camera.unproject_position(point)
	return (
		projected.x >= 0.0
		and projected.y >= 0.0
		and projected.x <= viewport_size.x
		and projected.y <= viewport_size.y
	)


func _has_line_of_sight(camera: Camera3D, point: Vector3, candidate: Node3D) -> bool:
	if line_of_sight_provider.is_valid():
		return bool(line_of_sight_provider.call(camera.global_position, point, candidate))
	var world := camera.get_world_3d()
	if world == null:
		return false
	var query := PhysicsRayQueryParameters3D.create(camera.global_position, point)
	if _player is CollisionObject3D:
		query.exclude = [(_player as CollisionObject3D).get_rid()]
	var hit := world.direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return true
	return _belongs_to_candidate(hit.get("collider"), candidate)


func _belongs_to_candidate(collider: Variant, candidate: Node) -> bool:
	if not collider is Node:
		return false
	var current := collider as Node
	while current != null:
		if current == candidate:
			return true
		current = current.get_parent()
	return false


func _category(candidate: Node, _interactions: Array[Dictionary]) -> String:
	if "interaction_nodes" in candidate:
		for component: Variant in candidate.get("interaction_nodes"):
			if component is Object and _script_class_name(component) == "ReadableComponent":
				return "readable"
	var script_class := _script_class_name(candidate)
	if script_class == "CogitoKeypad":
		return "keypad"
	if script_class == "CogitoDoor":
		return "door"
	if script_class == "CogitoButton":
		return "button"
	if candidate is CharacterBody3D:
		return "character"
	if script_class == "CogitoObject":
		return "object"
	return "interactable"


func _script_class_name(value: Object) -> String:
	var script: Variant = value.get_script()
	if script is GDScript:
		return (script as GDScript).get_global_name()
	return ""


func _relative_fields(camera: Camera3D, delta: Vector3) -> Dictionary:
	var flat_forward := -camera.global_basis.z
	flat_forward.y = 0.0
	if flat_forward.is_zero_approx():
		flat_forward = Vector3.FORWARD
	else:
		flat_forward = flat_forward.normalized()
	var flat_right := flat_forward.cross(Vector3.UP).normalized()
	var forward := delta.dot(flat_forward)
	var right := delta.dot(flat_right)
	var up := delta.y
	return {
		"position": {
			"forward": forward,
			"right": right,
			"up": up,
		},
		"yaw": rad_to_deg(atan2(right, forward)),
		"pitch": -rad_to_deg(atan2(up, Vector2(forward, right).length())),
	}


func _vector3_array(value: Vector3) -> Array[float]:
	return [value.x, value.y, value.z]
