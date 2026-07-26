class_name AIPlayPutBookBoxDropInteraction
extends InteractionComponent

var monitor: AIPlayPutBookMonitor
var box_area: Area3D
var prefer_while_carrying: bool = true


func _ready() -> void:
	input_map_action = "interact2"
	interaction_text = "放入箱子"
	ignore_open_gui = false


func interact(_player_interaction_component: PlayerInteractionComponent) -> void:
	if is_disabled:
		return
	if monitor == null or box_area == null:
		return
	if monitor.can_assisted_drop_to_box(box_area):
		monitor.assisted_drop_into_box_area(box_area)
	elif _player_interaction_component != null:
		_player_interaction_component.send_hint(null, "需要先拿起书")
	was_interacted_with.emit(interaction_text, input_map_action)


func set_disabled(_player: CogitoPlayer) -> bool:
	is_disabled = (
		monitor == null
		or box_area == null
		or not monitor.can_show_box_interaction(box_area)
	)
	return is_disabled
