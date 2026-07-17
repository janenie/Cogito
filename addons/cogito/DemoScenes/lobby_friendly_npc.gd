extends "res://addons/cogito/CogitoNPC/cogito_npc.gd"

@export var arrival_distance: float = 0.6
@export var final_facing_target: Node3D
@export var loop_route: bool = true
@export var route_root: Node

var _route_index := 0
var _route_direction := 1
var _has_arrived := false
var _route_points: Array[Node3D] = []


func _ready() -> void:
	add_to_group("interactable")
	add_to_group("Persist")
	find_interaction_nodes()
	find_cogito_properties()
	_collect_route_points()
	_set_talk_interaction()


func _physics_process(delta: float) -> void:
	if _has_arrived or _route_points.is_empty():
		return

	var target := _route_points[_route_index]
	if target == null:
		_advance_route()
		return

	var target_position := target.global_position
	var flat_offset := Vector3(target_position.x - global_position.x, 0.0, target_position.z - global_position.z)

	if flat_offset.length() <= arrival_distance:
		_advance_route()
		return

	var direction := flat_offset.normalized()
	face_direction(global_position + direction)
	velocity.x = direction.x * walk_speed
	velocity.z = direction.z * walk_speed

	if not is_on_floor():
		velocity += get_gravity() * delta

	update_animations(delta)
	move_and_slide()


func interact(player_interaction_component: PlayerInteractionComponent) -> void:
	if player_interaction_component:
		player_interaction_component.send_hint(null, "Hey, I am walking my lobby route.")


func _advance_route() -> void:
	if _route_points.size() < 2:
		_stop_at_sofa()
		return

	var next_index := _route_index + _route_direction
	if next_index >= _route_points.size() or next_index < 0:
		if loop_route:
			_route_direction *= -1
			_route_index += _route_direction
		else:
			_stop_at_sofa()
	else:
		_route_index = next_index


func _stop_at_sofa() -> void:
	_has_arrived = true
	velocity = Vector3.ZERO
	if final_facing_target:
		face_direction(final_facing_target.global_position)
	update_animations(0.0)
	if npc_state_machine:
		npc_state_machine.goto("idle")


func _set_talk_interaction() -> void:
	var basic_interaction := get_node_or_null("BasicInteraction")
	if basic_interaction:
		basic_interaction.interaction_text = "Talk"
		for connection: Dictionary in basic_interaction.basic_signal.get_connections():
			var connected_callable: Callable = connection.callable
			if connected_callable.get_object() == npc_state_machine:
				basic_interaction.basic_signal.disconnect(connected_callable)


func _collect_route_points() -> void:
	_route_points.clear()
	if route_root == null:
		route_root = patrol_path
	if route_root == null:
		return

	for child in route_root.get_children():
		if child is Node3D and child.name != "SofaLookTarget":
			_route_points.append(child)
