extends StaticBody3D

func _ready() -> void:
	var readable := Node.new()
	readable.name = "ReadableComponent"
	readable.set_script(load("res://tests/dailyroutine/fixtures/fake_readable_component.gd"))
	add_child(readable)
