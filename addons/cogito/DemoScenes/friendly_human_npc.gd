extends CharacterBody3D
class_name FriendlyHumanNPC

signal greeted(phrase: String)

@export var display_name: String = "Human NPC"

enum PromptPositionMode {
	ORIGIN,
	MARKER,
	AABB_CENTER,
}

@export var prompt_pos_mode: PromptPositionMode = PromptPositionMode.MARKER
@export var prompt_marker: Marker3D

@export_group("Route")
@export var route_root: Node
@export var final_facing_target: Node3D
@export var navigation_agent: NavigationAgent3D
@export var use_navigation_agent: bool = true
@export var arrival_distance: float = 0.45
@export var meeting_room_arrival_distance: float = 0.25
@export var loop_route: bool = false
@export var auto_open_doors: bool = true
@export var auto_close_doors: bool = true
@export var door_open_distance: float = 1.6
@export var door_close_distance: float = 2.2
@export var wait_at_route_points: bool = false
@export var wait_time_min: float = 5.0
@export var wait_time_max: float = 60.0
@export var no_wait_route_point_names: Array[String] = [
	"HumanMeetingRoomDoorInside",
	"HumanMeetingRoomDoorOutside",
]
@export var chair_search_distance: float = 2.0
@export var allow_sitting: bool = false
@export var sit_chair_parent_name: String = "MEETING_ROOM"
@export var sit_route_point_names: Array[String] = ["HumanMeetingRoomStart"]

@export_group("Greeting")
@export var greeting_enabled: bool = false
@export_multiline var default_dialogue_hint: String = "H. Voss: The LUMEN contract is in the CEO office drawer. The Archive boxes only have old packaging."
@export var greeting_phrases: Array[String] = ["你好", "要去开会了么？", "hi"]
@export var selected_greeting_phrase: String = "你好"
@export_multiline var greeting_response_hint: String = ""
@export var max_greeting_distance: float = 1.0
@export var greeting_out_of_range_hint: String = "Need to get closer."

@export_group("Movement")
@export var walk_speed: float = 0.65
@export var rotation_speed: float = 8.0
@export var navigation_probe_steps: int = 3
@export var navigation_probe_step_distance: float = 0.35

@export_group("Visual")
@export var visual_root: Node3D
@export var left_arm: Node3D
@export var right_arm: Node3D
@export var left_leg: Node3D
@export var right_leg: Node3D

var interaction_nodes: Array[Node] = []

var _route_points: Array[Node3D] = []
var _route_index := 0
var _route_direction := 1
var _has_arrived := false
var _walk_cycle := 0.0
var _pending_vertical_velocity := 0.0
var _opened_doors: Array[CogitoDoor] = []
var _rng := RandomNumberGenerator.new()
var _is_waiting := false
var _wait_timer := 0.0
var _is_sitting := false
var _active_seat: Node3D = null
var _stand_position_before_sit := Vector3.ZERO


func _ready() -> void:
	_rng.randomize()
	add_to_group("interactable")
	find_interaction_nodes()
	_collect_route_points()
	if navigation_agent and not navigation_agent.velocity_computed.is_connected(_on_navigation_agent_velocity_computed):
		navigation_agent.velocity_computed.connect(_on_navigation_agent_velocity_computed)
	_set_current_navigation_target()


func find_interaction_nodes() -> void:
	interaction_nodes = find_children("", "InteractionComponent", true)


func _physics_process(delta: float) -> void:
	if _has_arrived or _route_points.is_empty():
		velocity.x = 0.0
		velocity.z = 0.0
		_apply_gravity(delta)
		_update_walk_pose(delta, false)
		move_and_slide()
		return

	_open_nearby_doors()
	_close_opened_doors()

	if _is_waiting:
		_wait_at_route_point(delta)
		return

	var target := _route_points[_route_index]
	var flat_offset := Vector3(
		target.global_position.x - global_position.x,
		0.0,
		target.global_position.z - global_position.z
	)

	if flat_offset.length() <= _get_arrival_distance(target):
		if not wait_at_route_points:
			_advance_route()
			return
		if not _should_wait_at_route_point(target):
			_advance_route()
			return
		_begin_route_wait(target)
		return

	var next_position := _get_next_route_position(target)
	var using_navigation := next_position != target.global_position

	var move_offset := Vector3(
		next_position.x - global_position.x,
		0.0,
		next_position.z - global_position.z
	)
	if move_offset == Vector3.ZERO:
		move_offset = flat_offset

	var direction := move_offset.normalized()
	_face_direction(direction, delta)
	var desired_velocity := Vector3(direction.x * walk_speed, 0.0, direction.z * walk_speed)
	_apply_gravity(delta)
	_pending_vertical_velocity = velocity.y
	if using_navigation and navigation_agent and navigation_agent.avoidance_enabled:
		navigation_agent.velocity = desired_velocity
	else:
		_apply_horizontal_velocity(desired_velocity)
		move_and_slide()
	_update_walk_pose(delta, true)


func interact(player_interaction_component: PlayerInteractionComponent) -> void:
	if player_interaction_component == null:
		return
	if not greeting_enabled:
		player_interaction_component.send_hint(null, default_dialogue_hint)
		return
	var player_node := player_interaction_component.get_parent() as Node3D
	if (
		player_node != null
		and max_greeting_distance > 0.0
		and player_node.global_position.distance_to(global_position) > max_greeting_distance
	):
		player_interaction_component.send_hint(null, greeting_out_of_range_hint)
		return
	var response_hint := greeting_response_hint.strip_edges()
	if response_hint.is_empty():
		response_hint = selected_greeting_phrase
	player_interaction_component.send_hint(null, response_hint)
	greeted.emit(selected_greeting_phrase)


func configure_route_loop(start_index: int, direction: int) -> void:
	_collect_route_points()
	if _route_points.is_empty():
		return
	_start_route_loop(start_index, direction)


func configure_route_loop_from(
	first_point_name: String,
	start_offset: int,
	direction: int,
) -> void:
	_collect_route_points()
	var first_index := -1
	for index: int in range(_route_points.size()):
		if _route_points[index].name == first_point_name:
			first_index = index
			break
	if first_index < 0:
		return
	var full_route := _route_points.duplicate()
	_route_points.clear()
	for index: int in range(first_index, full_route.size()):
		_route_points.append(full_route[index])
	if _route_points.is_empty():
		return
	_start_route_loop(posmod(start_offset, _route_points.size()), direction)


func _start_route_loop(start_index: int, direction: int) -> void:
	loop_route = true
	wait_at_route_points = false
	auto_close_doors = true
	_has_arrived = false
	_is_waiting = false
	_is_sitting = false
	_route_index = clampi(start_index, 0, _route_points.size() - 1)
	_route_direction = -1 if direction < 0 else 1
	global_position = _route_points[_route_index].global_position
	velocity = Vector3.ZERO
	_advance_route()


func configure_destination(target: Node3D) -> void:
	if target == null:
		return
	configure_route_to_points([target])


func configure_stationary_seat(anchor: Node3D, chair_parent_name: String) -> void:
	if anchor == null:
		return
	global_transform = anchor.global_transform
	sit_chair_parent_name = chair_parent_name
	allow_sitting = true
	_route_points.clear()
	_has_arrived = true
	_is_waiting = false
	velocity = Vector3.ZERO
	_try_sit_nearby_chair()
	if not _is_sitting:
		_set_sitting_pose(true)


func is_sitting() -> bool:
	return _is_sitting


func configure_route_to_points(targets: Array[Node3D]) -> void:
	if targets.is_empty():
		return
	loop_route = false
	wait_at_route_points = false
	auto_close_doors = false
	_has_arrived = false
	_is_waiting = false
	_is_sitting = false
	_route_points = targets.duplicate()
	_route_index = 0
	_route_direction = 1
	velocity = Vector3.ZERO
	_set_current_navigation_target()


func route_point_by_name(point_name: String) -> Node3D:
	if _route_points.is_empty():
		_collect_route_points()
	for point: Node3D in _route_points:
		if point.name == point_name:
			return point
	if route_root != null:
		return route_root.get_node_or_null(point_name) as Node3D
	return null


func configure_public_identity(
	identity_name: String,
	shirt_color: Color,
) -> void:
	display_name = identity_name
	var body := get_node_or_null("Visual/Body") as MeshInstance3D
	if body == null:
		return
	var source_material := body.get_active_material(0) as StandardMaterial3D
	if source_material == null:
		return
	var identity_material := source_material.duplicate() as StandardMaterial3D
	identity_material.albedo_color = shirt_color
	body.set_surface_override_material(0, identity_material)


func route_point_count() -> int:
	if _route_points.is_empty():
		_collect_route_points()
	return _route_points.size()


func _advance_route() -> void:
	if _route_points.size() < 2:
		_stop_at_end()
		return

	var next_index := _route_index + _route_direction
	if next_index >= _route_points.size() or next_index < 0:
		if loop_route:
			_route_direction *= -1
			_route_index += _route_direction
		else:
			_stop_at_end()
	else:
		_route_index = next_index
	_set_current_navigation_target()


func _begin_route_wait(target: Node3D) -> void:
	_is_waiting = true
	_wait_timer = _get_random_wait_time()
	velocity.x = 0.0
	velocity.z = 0.0
	_stand_position_before_sit = global_position
	if _can_sit_at_route_point(target):
		_try_sit_nearby_chair()
	if not _is_sitting:
		_update_walk_pose(0.0, false)


func _wait_at_route_point(delta: float) -> void:
	velocity.x = 0.0
	velocity.z = 0.0
	_apply_gravity(delta)
	if _is_sitting:
		_set_sitting_pose(true)
	else:
		_update_walk_pose(delta, false)
	move_and_slide()

	_wait_timer -= delta
	if _wait_timer > 0.0:
		return

	_is_waiting = false
	_restore_standing_position_after_sit()
	_set_sitting_pose(false)
	_advance_route()


func _get_random_wait_time() -> float:
	var wait_min := max(wait_time_min, 0.0)
	var wait_max := max(wait_time_max, wait_min)
	return _rng.randf_range(wait_min, wait_max)


func _get_next_route_position(target: Node3D) -> Vector3:
	if not use_navigation_agent or navigation_agent == null:
		return target.global_position

	navigation_agent.target_position = target.global_position
	if not navigation_agent.is_target_reachable():
		return target.global_position

	var next_position := navigation_agent.get_next_path_position()
	if not _is_navigation_path_clear(next_position):
		return target.global_position

	return next_position


func _is_navigation_path_clear(next_position: Vector3) -> bool:
	var flat_offset := Vector3(
		next_position.x - global_position.x,
		0.0,
		next_position.z - global_position.z
	)
	if flat_offset == Vector3.ZERO:
		return true

	var probe_direction := flat_offset.normalized()
	var probe_count = max(navigation_probe_steps, 0)
	for step in range(probe_count):
		var probe_distance := navigation_probe_step_distance * float(step + 1)
		var probe_motion := probe_direction * probe_distance
		if move_and_collide(probe_motion, true):
			return false

	return true


func _should_wait_at_route_point(target: Node3D) -> bool:
	return not no_wait_route_point_names.has(target.name)


func _get_arrival_distance(target: Node3D) -> float:
	if target.name == "HumanMeetingRoomStart":
		return meeting_room_arrival_distance
	return arrival_distance


func _stop_at_end() -> void:
	_has_arrived = true
	velocity = Vector3.ZERO
	if final_facing_target:
		var flat_direction := Vector3(
			final_facing_target.global_position.x - global_position.x,
			0.0,
			final_facing_target.global_position.z - global_position.z
		)
		if flat_direction != Vector3.ZERO:
			_face_direction(flat_direction.normalized(), 1.0)
	_update_walk_pose(0.0, false)


func _collect_route_points() -> void:
	_route_points.clear()
	if route_root == null:
		return

	for child in route_root.get_children():
		if child is Node3D and not child.name.to_lower().contains("looktarget"):
			_route_points.append(child)


func _set_current_navigation_target() -> void:
	if navigation_agent == null or _route_points.is_empty() or _has_arrived:
		return
	navigation_agent.target_position = _route_points[_route_index].global_position


func _open_nearby_doors() -> void:
	if not auto_open_doors:
		return

	for node in get_tree().get_nodes_in_group("interactable"):
		var door := node as CogitoDoor
		if door == null or door.is_open or door.is_locked:
			continue

		if global_position.distance_to(door.global_position) <= door_open_distance:
			door.open_door(self)
			if not _opened_doors.has(door):
				_opened_doors.append(door)


func _close_opened_doors() -> void:
	if not auto_close_doors:
		return
	for index in range(_opened_doors.size() - 1, -1, -1):
		var door := _opened_doors[index]
		if not is_instance_valid(door):
			_opened_doors.remove_at(index)
			continue

		if not door.is_open:
			_opened_doors.remove_at(index)
			continue

		if global_position.distance_to(door.global_position) > door_close_distance:
			door.close_door(self)
			_opened_doors.remove_at(index)


func _try_sit_nearby_chair() -> void:
	var chair := _find_nearest_chair()
	if chair == null:
		_set_sitting_pose(false)
		return

	var seat_marker := _get_sit_marker(chair)
	if seat_marker:
		var seat_position := seat_marker.global_position
		global_position = Vector3(seat_position.x, global_position.y, seat_position.z)
		_active_seat = seat_marker
	else:
		_active_seat = chair

	var look_marker := _get_look_marker(chair)
	if look_marker:
		var look_direction := Vector3(
			look_marker.global_position.x - global_position.x,
			0.0,
			look_marker.global_position.z - global_position.z
		)
		if look_direction != Vector3.ZERO:
			_face_direction(look_direction.normalized(), 1.0)
	else:
		var chair_direction := Vector3(
			chair.global_position.x - global_position.x,
			0.0,
			chair.global_position.z - global_position.z
		)
		if chair_direction != Vector3.ZERO:
			_face_direction(chair_direction.normalized(), 1.0)

	_set_sitting_pose(true)


func _can_sit_at_route_point(target: Node3D) -> bool:
	if not allow_sitting:
		return false
	if sit_route_point_names.is_empty():
		return true
	return sit_route_point_names.has(target.name)


func _restore_standing_position_after_sit() -> void:
	if not _is_sitting:
		return

	global_position = _stand_position_before_sit
	velocity = Vector3.ZERO


func _find_nearest_chair() -> Node3D:
	var nearest_chair: Node3D = null
	var nearest_distance := chair_search_distance

	for node in get_tree().get_nodes_in_group("interactable"):
		var chair := node as Node3D
		if chair == null:
			continue

		var lower_name := chair.name.to_lower()
		if not (chair is CogitoSittable or lower_name.contains("chair") or lower_name.contains("seat")):
			continue
		if sit_chair_parent_name != "" and not _is_node_inside_named_parent(chair, sit_chair_parent_name):
			continue

		var distance := global_position.distance_to(chair.global_position)
		if distance <= nearest_distance:
			nearest_distance = distance
			nearest_chair = chair

	return nearest_chair


func _is_node_inside_named_parent(node: Node, parent_name: String) -> bool:
	var current := node
	while current:
		if current.name == parent_name:
			return true
		current = current.get_parent()
	return false


func _get_sit_marker(chair: Node3D) -> Node3D:
	if chair is CogitoSittable and chair.sit_position_node:
		return chair.sit_position_node
	return chair.find_child("Sit Marker", true, false) as Node3D


func _get_look_marker(chair: Node3D) -> Node3D:
	if chair is CogitoSittable and chair.look_marker_node:
		return chair.look_marker_node
	return chair.find_child("Look Marker", true, false) as Node3D


func _set_sitting_pose(is_sitting: bool) -> void:
	_is_sitting = is_sitting
	if not is_sitting:
		_active_seat = null
		_set_limb_pitch(0.0)
		if visual_root:
			visual_root.position.y = 0.0
		return

	if visual_root:
		visual_root.position.y = -0.22
	if left_arm:
		left_arm.rotation.x = 0.35
	if right_arm:
		right_arm.rotation.x = -0.35
	if left_leg:
		left_leg.rotation.x = -1.15
	if right_leg:
		right_leg.rotation.x = -1.15


func _apply_gravity(delta: float) -> void:
	if not is_on_floor():
		velocity += get_gravity() * delta


func _apply_horizontal_velocity(horizontal_velocity: Vector3) -> void:
	velocity.x = horizontal_velocity.x
	velocity.y = _pending_vertical_velocity
	velocity.z = horizontal_velocity.z


func _on_navigation_agent_velocity_computed(safe_velocity: Vector3) -> void:
	if not is_inside_tree() or not can_process():
		return
	_apply_horizontal_velocity(safe_velocity)
	move_and_slide()


func _face_direction(direction: Vector3, delta: float) -> void:
	if direction == Vector3.ZERO:
		return

	var target_basis := Basis.looking_at(direction, Vector3.UP, false)
	var current_scale := scale
	basis = basis.orthonormalized().slerp(target_basis, min(rotation_speed * delta, 1.0))
	scale = current_scale


func _update_walk_pose(delta: float, is_walking: bool) -> void:
	if _is_sitting:
		_set_sitting_pose(true)
		return

	if not is_walking:
		_set_limb_pitch(0.0)
		if visual_root:
			visual_root.position.y = 0.0
		return

	_walk_cycle += delta * 5.5
	var swing := sin(_walk_cycle) * 0.45
	_set_limb_pitch(swing)
	if visual_root:
		visual_root.position.y = abs(sin(_walk_cycle * 2.0)) * 0.025


func _set_limb_pitch(swing: float) -> void:
	if left_arm:
		left_arm.rotation.x = swing
	if right_arm:
		right_arm.rotation.x = -swing
	if left_leg:
		left_leg.rotation.x = -swing
	if right_leg:
		right_leg.rotation.x = swing
