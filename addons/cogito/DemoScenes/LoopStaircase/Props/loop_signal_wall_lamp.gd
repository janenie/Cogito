extends Node3D


func set_signal_color(color: Color) -> void:
	_set_color_recursive(self, color)


func _set_color_recursive(node: Node, color: Color) -> void:
	if node is Light3D:
		(node as Light3D).light_color = color
	if node is MeshInstance3D:
		var mesh_instance := node as MeshInstance3D
		var material := StandardMaterial3D.new()
		material.albedo_color = color.darkened(0.25)
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = 0.6
		material.roughness = 0.42
		mesh_instance.material_override = material
	for child: Node in node.get_children():
		_set_color_recursive(child, color)
