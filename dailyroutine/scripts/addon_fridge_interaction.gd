extends StaticBody3D

@export var open_animation := "open"
@export var use_reverse_open_as_close_anim := true
@export var open_angle_radians := PI / 2.0
@export var fridge_node_path: NodePath
@export var milk_node_path: NodePath

var is_open := false
var interaction_text := "打开冰箱"

func _ready() -> void:
	add_to_group("interactable")
	_apply_prompt()

func interact(player_interaction_component: Node = null) -> void:
	if is_open:
		var milk := get_node_or_null(milk_node_path)
		if _milk_is_available(milk):
			milk.interact(player_interaction_component)
			_apply_prompt()
		else:
			close(player_interaction_component)
	else:
		open(player_interaction_component)

func open(player_interaction_component: Node = null) -> void:
	is_open = true
	var animation_player := get_node_or_null("AnimationPlayer") as AnimationPlayer
	if animation_player != null:
		animation_player.stop()
		animation_player.active = false
	_set_door_rotation(open_angle_radians)
	_apply_prompt()
	if player_interaction_component != null and player_interaction_component.has_method("send_hint"):
		player_interaction_component.send_hint(null, "已打开。")

func close(player_interaction_component: Node = null) -> void:
	is_open = false
	var animation_player := get_node_or_null("AnimationPlayer") as AnimationPlayer
	if animation_player != null:
		animation_player.stop()
		animation_player.active = false
	_set_door_rotation(0.0)
	_apply_prompt()
	if player_interaction_component != null and player_interaction_component.has_method("send_hint"):
		player_interaction_component.send_hint(null, "已关闭。")

func _apply_prompt() -> void:
	var milk := get_node_or_null(milk_node_path)
	if is_open and _milk_is_available(milk):
		interaction_text = "拿过期牛奶"
	else:
		interaction_text = "关闭冰箱" if is_open else "打开冰箱"

func _set_door_rotation(angle: float) -> void:
	var fridge := _fridge()
	var left_door := get_node_or_null("FridgeDoorLeft") as Node3D
	var right_door := get_node_or_null("FridgeDoorRight") as Node3D
	if (left_door == null or right_door == null) and fridge != null and fridge != self:
		left_door = fridge.get_node_or_null("FridgeDoorLeft") as Node3D
		right_door = fridge.get_node_or_null("FridgeDoorRight") as Node3D
	if left_door != null:
		left_door.transform = Transform3D(
			Basis(Vector3.UP, -angle),
			left_door.transform.origin
		)
		var left_mesh := left_door.get_node_or_null("doorLeft") as Node3D
		if left_mesh != null:
			left_mesh.rotation = Vector3(left_mesh.rotation.x, -angle, left_mesh.rotation.z)
	if right_door != null:
		right_door.transform = Transform3D(
			Basis(Vector3.UP, angle),
			right_door.transform.origin
		)
		var right_mesh := right_door.get_node_or_null("doorRight") as Node3D
		if right_mesh != null:
			right_mesh.rotation = Vector3(right_mesh.rotation.x, angle, right_mesh.rotation.z)

func _milk_is_available(milk: Node) -> bool:
	return milk != null and milk.visible

func _fridge() -> Node:
	if get_node_or_null("FridgeDoorLeft") != null:
		return self
	if not str(fridge_node_path).is_empty():
		return get_node_or_null(fridge_node_path)
	return get_parent()
