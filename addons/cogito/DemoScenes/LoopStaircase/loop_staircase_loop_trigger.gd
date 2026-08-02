class_name LoopStaircaseLoopTrigger
extends Area3D

@export var manager_path: NodePath


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node3D) -> void:
	var manager: Node = get_node_or_null(manager_path)
	if manager != null and manager.has_method("advance_loop_and_reset_player"):
		var manager_player: Variant = manager.get("player")
		if manager_player != null and body != manager_player:
			return
		manager.advance_loop_and_reset_player(body)
