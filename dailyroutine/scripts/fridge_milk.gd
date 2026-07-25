extends StaticBody3D

@export var manager_path: NodePath
@export var fridge_door_path: NodePath

var manager: Node
var door_open := false
var _initial_collision_layer := 2
var _initial_collision_mask := 1

func _ready() -> void:
	if collision_layer != 0:
		_initial_collision_layer = collision_layer
	if collision_mask != 0:
		_initial_collision_mask = collision_mask
	add_to_group("interactable")
	manager = get_node_or_null(manager_path)
	_sync_visibility()

func _process(_delta: float) -> void:
	_sync_visibility()

func interact(player_interaction_component: Node = null) -> void:
	if not _fridge_is_open():
		if player_interaction_component != null and player_interaction_component.has_method("send_hint"):
			player_interaction_component.send_hint(null, "先打开冰箱。")
		_sync_visibility()
		return
	if manager == null:
		manager = get_node_or_null(manager_path)
	if manager == null:
		return
	var message := ""
	if manager.take_milk():
		message = "拿到过期牛奶。"
		_open_fridge_door()
	else:
		message = manager.current_objective
	if player_interaction_component != null and player_interaction_component.has_method("send_hint"):
		player_interaction_component.send_hint(null, message)
	_sync_visibility()

func _sync_visibility() -> void:
	if manager == null:
		manager = get_node_or_null(manager_path)
	if manager == null:
		return
	var available: bool = manager.get("milk_available") == true and manager.get("milk_drunk") != true
	var can_interact := available and _fridge_is_open()
	visible = available
	collision_layer = _initial_collision_layer if can_interact else 0
	collision_mask = _initial_collision_mask if can_interact else 0
	for child in get_children():
		if child is CollisionShape3D:
			child.disabled = not can_interact

func _fridge_is_open() -> bool:
	var fridge_door := get_node_or_null(fridge_door_path)
	if fridge_door == null:
		return false
	var is_open_value = fridge_door.get("is_open")
	return is_open_value is bool and is_open_value

func _open_fridge_door() -> void:
	door_open = true
	var fridge_door := get_node_or_null(fridge_door_path)
	if fridge_door == null:
		return
	if fridge_door.has_method("open"):
		fridge_door.open()
	elif fridge_door.has_method("open_door"):
		fridge_door.open_door()
	elif fridge_door is Node3D:
		(fridge_door as Node3D).rotation_degrees.y = -85.0
