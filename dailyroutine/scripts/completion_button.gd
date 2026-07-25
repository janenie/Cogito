extends StaticBody3D

@export var manager_path: NodePath

var manager: Node
var interaction_text := "完成任务"

func _ready() -> void:
	add_to_group("interactable")
	manager = get_node_or_null(manager_path)

func interact(player_interaction_component: Node = null) -> void:
	if manager == null:
		manager = get_node_or_null(manager_path)
	if manager == null:
		return
	var succeeded := false
	if manager.has_method("submit_cleanup"):
		succeeded = manager.submit_cleanup()
	if player_interaction_component != null and player_interaction_component.has_method("send_hint"):
		player_interaction_component.send_hint(null, "任务成功。" if succeeded else "任务失败。")
