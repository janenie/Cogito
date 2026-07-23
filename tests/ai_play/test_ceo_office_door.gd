extends SceneTree

const LOBBY_SCENE := "res://addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
const CEO_DOOR_PATH := "UPPER_OFFICE_CEO/WindowedDoor/FrontDoor"


func _initialize() -> void:
	var packed: PackedScene = load(LOBBY_SCENE)
	if packed == null:
		push_error("CEO door test could not load the Lobby")
		quit(1)
		return
	var lobby: Node = packed.instantiate()
	var door: Node = lobby.get_node_or_null(CEO_DOOR_PATH)
	var valid: bool = false
	if door != null:
		var basic: Node = door.get_node_or_null("BasicInteraction")
		valid = (
			door.get("is_locked") == false
			and basic != null
			and basic.get("is_disabled") == false
			and not door.has_node("LockInteraction")
			and not door.has_node("DualInteraction")
		)
	lobby.free()
	if valid:
		print("CEO office door test passed")
		quit(0)
	else:
		push_error("CEO office door must be an unlocked ordinary door")
		quit(1)
