extends StaticBody3D

@export var manager_path: NodePath

var manager: Node

func _ready() -> void:
	add_to_group("interactable")
	manager = get_node_or_null(manager_path)

func interact(player_interaction_component: Node = null) -> void:
	if manager == null:
		return
	var placed: bool = manager.place_trash_at_door()
	if player_interaction_component != null and player_interaction_component.has_method("send_hint"):
		if placed:
			player_interaction_component.send_hint(null, "Dropped off.")
		else:
			player_interaction_component.send_hint(null, "Nothing to drop off.")
