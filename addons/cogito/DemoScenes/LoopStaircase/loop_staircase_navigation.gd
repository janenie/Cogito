class_name LoopStaircaseNavigation
extends Area3D

@export_enum("up", "down", "answer") var action: String = "up"
@export var manager_path: NodePath

var interaction_nodes: Array[Node] = []
var _triggered: bool = false


func _ready() -> void:
	interaction_nodes = find_children("", "InteractionComponent", true)
	body_entered.connect(_on_body_entered, CONNECT_DEFERRED)


func interact(_player_interaction_component: PlayerInteractionComponent) -> void:
	_run_action()


func _on_body_entered(body: Node3D) -> void:
	if _triggered:
		return
	var manager: Node = get_node_or_null(manager_path)
	if manager == null:
		return
	var manager_player: Variant = manager.get("player")
	if manager_player != null and body != manager_player:
		return
	if action in ["up", "down"]:
		_triggered = true
		_run_action()


func _run_action() -> void:
	var manager: Node = get_node_or_null(manager_path)
	if manager == null:
		return
	match action:
		"up":
			manager.move_up()
			manager.reset_player_to_spawn()
		"down":
			manager.move_down()
			manager.reset_player_to_spawn()
		"answer":
			manager.submit_current_floor()
