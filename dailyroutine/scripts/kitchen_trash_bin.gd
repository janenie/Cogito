extends StaticBody3D

@export var manager_path: NodePath
@export var room_id := "kitchen"

var manager: Node
var lid_open := false

func _ready() -> void:
	add_to_group("interactable")
	manager = get_node_or_null(manager_path)

func interact(player_interaction_component: Node = null) -> void:
	if manager == null:
		return
	var message := ""
	if manager.has_loose_trash:
		if manager.deposit_held_trash(room_id):
			message = "已扔进垃圾桶。"
			_open_lid()
		else:
			message = manager.current_objective
	elif manager.take_room_bin(room_id, player_interaction_component, global_position):
		message = "已拿起。"
	else:
		message = manager.current_objective
	if player_interaction_component != null and player_interaction_component.has_method("send_hint"):
		player_interaction_component.send_hint(null, message)

func _open_lid() -> void:
	lid_open = true
	var lid := get_node_or_null("Lid") as Node3D
	if lid != null:
		lid.rotation_degrees.x = -70.0
