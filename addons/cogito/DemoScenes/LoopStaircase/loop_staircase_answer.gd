class_name LoopStaircaseAnswer
extends StaticBody3D

@export var answer_floor: int = 2
@export var manager_path: NodePath

var interaction_nodes: Array[Node] = []


func _ready() -> void:
	interaction_nodes = find_children("", "InteractionComponent", true)


func interact(_player_interaction_component: PlayerInteractionComponent) -> void:
	var manager: Node = get_node_or_null(manager_path)
	if manager != null and manager.has_method("select_floor"):
		manager.select_floor(answer_floor)
