extends StaticBody3D

var interaction_text := "DOOR_Open"
var is_open := false
var interact_called := false

func interact(_interactor: Node = null) -> void:
	interact_called = true

func open_door(_interactor: Node3D) -> void:
	is_open = true
	interaction_text = "DOOR_Close"

func close_door(_interactor: Node3D) -> void:
	is_open = false
	interaction_text = "DOOR_Open"
