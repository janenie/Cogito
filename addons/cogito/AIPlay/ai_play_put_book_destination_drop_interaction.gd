class_name AIPlayPutBookDestinationDropInteraction
extends InteractionComponent

var monitor: AIPlayPutBookMonitor
var prefer_while_carrying: bool = true


func _ready() -> void:
	input_map_action = "interact2"
	interaction_text = "放置任务书"
	ignore_open_gui = false


func interact(player_interaction_component: PlayerInteractionComponent) -> void:
	if is_disabled or monitor == null:
		return
	if monitor.can_assisted_drop_to_destination():
		monitor.assisted_drop_to_destination()
	elif player_interaction_component != null:
		player_interaction_component.send_hint(null, "需要先拿起当前任务书")
	was_interacted_with.emit(interaction_text, input_map_action)


func set_disabled(_player: CogitoPlayer) -> bool:
	is_disabled = monitor == null or not monitor.can_show_destination_interaction()
	return is_disabled
