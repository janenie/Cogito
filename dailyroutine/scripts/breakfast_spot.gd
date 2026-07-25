extends StaticBody3D

@export var manager_path: NodePath

var manager: Node

func _ready() -> void:
	add_to_group("interactable")
	manager = get_node_or_null(manager_path)

func interact(player_interaction_component: Node = null) -> void:
	if manager == null:
		return
	if player_interaction_component != null and player_interaction_component.has_method("send_hint"):
		player_interaction_component.send_hint(null, manager.current_objective)
