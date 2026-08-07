class_name LoopStaircaseEvidenceRenderer
extends RefCounted

const SIGNAL_COLOR_VALUES: Dictionary = {
	"red": Color("d34a4a"),
	"blue": Color("4387d8"),
	"green": Color("4ba869"),
	"white": Color("e3e5dd"),
	"yellow": Color("d5ad42"),
	"purple": Color("9a65ba"),
}


func apply_state(room: Node3D, state: Dictionary) -> void:
	room.set_meta("theme_id", state["theme_id"])
	room.set_meta("room_type", state["room_type"])
	var evidence := room.get_node_or_null("Evidence") as Node3D
	if evidence == null:
		push_error("Loop staircase authored room is missing its Evidence node")
		return
	for child: Node in evidence.get_children():
		evidence.remove_child(child)
		child.free()
	_build_evidence(evidence, state)


func _build_evidence(evidence: Node3D, state: Dictionary) -> void:
	var visitor_record := Label3D.new()
	visitor_record.name = "VisitorRecord"
	visitor_record.position = Vector3(-2.2, 1.75, -2.42)
	visitor_record.pixel_size = 0.0048
	visitor_record.font_size = 30
	visitor_record.text = "访客记录\n%s" % "、".join(state["visitor_names"])
	if state["visitor_round_visible"]:
		visitor_record.text += "\n访问轮次：第%d轮" % (int(state["visitor_round"]) + 1)
	evidence.add_child(visitor_record)

	var item_slot := Node3D.new()
	item_slot.name = "ItemSlot"
	item_slot.position = Vector3(2.1, 0.25, 1.25)
	evidence.add_child(item_slot)
	for index: int in range(int(state["item_count"])):
		_add_box(
			item_slot,
			"Item_%d" % (index + 1),
			Vector3(0.3, 0.32, 0.3),
			Vector3(index * 0.38, 0.16, 0),
			Color("b39a72"),
		)
	var item_label := Label3D.new()
	item_label.name = "ItemLabel"
	item_label.position = Vector3(0.25, 0.55, 0)
	item_label.pixel_size = 0.004
	item_label.font_size = 24
	item_label.text = state["tracked_item"]
	item_slot.add_child(item_label)

	var trash := Node3D.new()
	trash.name = "Trash"
	evidence.add_child(trash)
	for index: int in range(int(state["trash_count"])):
		_add_box(
			trash,
			"Paper_%d" % (index + 1),
			Vector3(0.28, 0.025, 0.2),
			Vector3(-2.2 + index * 0.42, 0.025, 1.75 - (index % 2) * 0.3),
			Color("d6d1bd"),
		)

	var signal_light := MeshInstance3D.new()
	signal_light.name = "SignalLight"
	var sphere := SphereMesh.new()
	sphere.radius = 0.18
	sphere.height = 0.36
	signal_light.mesh = sphere
	signal_light.position = Vector3(2.45, 1.9, -2.35)
	signal_light.material_override = _material(
		SIGNAL_COLOR_VALUES.get(state["signal_color"], Color.WHITE)
	)
	evidence.add_child(signal_light)


func _add_box(
	parent: Node3D,
	node_name: String,
	size: Vector3,
	position: Vector3,
	color: Color,
) -> void:
	var mesh := MeshInstance3D.new()
	mesh.name = node_name
	var box := BoxMesh.new()
	box.size = size
	mesh.mesh = box
	mesh.position = position
	mesh.material_override = _material(color)
	parent.add_child(mesh)


func _material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.82
	return material
