class_name AIPlayMeetingSeatInteraction
extends InteractionComponent

var monitor: Node
var seat_id: String = ""
var prefer_while_carrying: bool = true


func _init() -> void:
	input_map_action = "interact2"
	interaction_text = "放置资料"
	ignore_open_gui = false


func interact(player_interaction: PlayerInteractionComponent) -> void:
	if is_disabled or monitor == null:
		return
	if not monitor.has_method("place_carried_folder"):
		return
	var result: Dictionary = monitor.place_carried_folder(
		seat_id,
		player_interaction,
	)
	if not result.get("accepted", false) and player_interaction != null:
		match str(result.get("reason", "")):
			"occupied":
				player_interaction.send_hint(null, "该席位已有资料")
			"invalid_folder", "not_carrying":
				player_interaction.send_hint(null, "请先拿起会议资料")
			_:
				player_interaction.send_hint(null, "现在无法放置资料")
	was_interacted_with.emit(interaction_text, input_map_action)
