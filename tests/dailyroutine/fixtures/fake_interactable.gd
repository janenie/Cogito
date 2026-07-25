extends StaticBody3D

var interaction_text := "Open"
var interacted := false

func interact(_interactor: Node = null) -> void:
	interacted = true
