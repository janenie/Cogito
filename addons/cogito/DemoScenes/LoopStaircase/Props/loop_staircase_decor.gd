class_name LoopStaircaseDecor
extends RefCounted


static func freeze_tree(node: Node) -> void:
	if node is RigidBody3D:
		var body := node as RigidBody3D
		body.freeze = true
		body.sleeping = true
		body.lock_rotation = true
	if node is Area3D:
		var area := node as Area3D
		area.monitoring = false
		area.monitorable = false
		area.collision_layer = 0
		area.collision_mask = 0
	for child: Node in node.get_children():
		freeze_tree(child)
