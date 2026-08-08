class_name AIPlayLobbyNPCs
extends Node3D

@export var visible_scenarios: Array[String] = ["find_key", "greet_npc_meeting"]


func _ready() -> void:
	var scenario_id := "find_contract"
	var controller := get_node_or_null("../AIPlayController")
	if controller != null and controller.has_method("get_requested_scenario_id"):
		scenario_id = controller.get_requested_scenario_id(OS.get_cmdline_user_args())
	configure_for_scenario(scenario_id)


func npcs() -> Array[FriendlyHumanNPC]:
	var result: Array[FriendlyHumanNPC] = []
	for child: Node in get_children():
		var npc := child as FriendlyHumanNPC
		if npc != null:
			result.append(npc)
	return result


func configure_for_scenario(scenario_id: String) -> void:
	var active := scenario_id in visible_scenarios
	visible = active
	process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED
	for npc: FriendlyHumanNPC in npcs():
		npc.visible = active
		npc.process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED
		if not npc.has_meta("ai_play_lobby_base_collision_layer"):
			npc.set_meta("ai_play_lobby_base_collision_layer", npc.collision_layer)
		npc.collision_layer = (
			int(npc.get_meta("ai_play_lobby_base_collision_layer")) if active else 0
		)
