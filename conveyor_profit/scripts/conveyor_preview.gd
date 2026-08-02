class_name ConveyorPreview
extends Path3D

@export_range(-10.0, 10.0, 0.05) var speed_meters_per_second: float = 1.2


func _process(delta: float) -> void:
	if curve == null:
		return
	var path_length: float = curve.get_baked_length()
	if path_length <= 0.0:
		return
	for child: Node in get_children():
		if child is PathFollow3D:
			child.progress = ConveyorMotion.advance(
				child.progress,
				speed_meters_per_second,
				delta,
				path_length,
			)
