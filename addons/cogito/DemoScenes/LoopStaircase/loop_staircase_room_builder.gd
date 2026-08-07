class_name LoopStaircaseRoomBuilder
extends RefCounted

const THEME_COLORS: Dictionary = {
	"lounge_window": Color("8d765f"),
	"lounge_reading": Color("657861"),
	"archive_paper": Color("756650"),
	"archive_digital": Color("536c78"),
	"office_manager": Color("725b50"),
	"office_open": Color("65717f"),
	"meeting_round": Color("70677f"),
	"meeting_boardroom": Color("58716d"),
}
const SIGNAL_COLOR_VALUES: Dictionary = {
	"red": Color("d34a4a"),
	"blue": Color("4387d8"),
	"green": Color("4ba869"),
	"white": Color("e3e5dd"),
	"yellow": Color("d5ad42"),
	"purple": Color("9a65ba"),
}


func build(parent: Node3D, state: Dictionary) -> void:
	parent.set_meta("theme_id", state["theme_id"])
	parent.set_meta("room_type", state["room_type"])
	_build_shell(parent, state["theme_id"])
	_build_stable_theme(parent, state["theme_id"])
	_build_evidence(parent, state)


func _build_shell(parent: Node3D, theme_id: String) -> void:
	var color: Color = THEME_COLORS.get(theme_id, Color("6d6d68"))
	_add_box(parent, "LobbyFloor", Vector3(7.0, 0.16, 5.0), Vector3(0, -0.08, 0), color.darkened(0.25))
	_add_box(parent, "BackWall", Vector3(7.0, 3.1, 0.18), Vector3(0, 1.45, -2.55), color.lightened(0.32))
	_add_box(parent, "LeftWall", Vector3(0.18, 3.1, 5.0), Vector3(-3.55, 1.45, 0), color.lightened(0.24))
	_add_box(parent, "RightWall", Vector3(0.18, 3.1, 5.0), Vector3(3.55, 1.45, 0), color.lightened(0.24))


func _build_stable_theme(parent: Node3D, theme_id: String) -> void:
	var stable := Node3D.new()
	stable.name = "StableTheme"
	parent.add_child(stable)
	match theme_id:
		"lounge_window":
			_add_furniture(stable, "CornerSofa", Vector3(2.5, 0.72, 0.82), Vector3(-1.7, 0.36, 0.8), Color("725b4d"))
			_add_furniture(stable, "WindowBench", Vector3(1.5, 0.55, 0.55), Vector3(1.8, 0.28, -1.8), Color("c0a777"))
			_add_furniture(stable, "GlassTeaTable", Vector3(1.3, 0.18, 0.8), Vector3(0, 0.42, 0.45), Color("8fb4b4"))
		"lounge_reading":
			_add_furniture(stable, "ReadingChairLeft", Vector3(0.85, 1.0, 0.85), Vector3(-1.2, 0.5, 0.4), Color("496a59"))
			_add_furniture(stable, "ReadingChairRight", Vector3(0.85, 1.0, 0.85), Vector3(1.2, 0.5, 0.1), Color("496a59"))
			_add_furniture(stable, "LowBookcase", Vector3(2.0, 0.9, 0.35), Vector3(0, 0.45, -2.15), Color("6d513c"))
		"archive_paper":
			_add_furniture(stable, "PaperShelfLeft", Vector3(1.0, 2.3, 0.45), Vector3(-2.5, 1.15, -1.9), Color("6b5b45"))
			_add_furniture(stable, "PaperShelfRight", Vector3(1.0, 2.3, 0.45), Vector3(-1.15, 1.15, -1.9), Color("6b5b45"))
			_add_furniture(stable, "ReadingStand", Vector3(1.4, 0.78, 0.75), Vector3(1.1, 0.39, 0.2), Color("876b4e"))
		"archive_digital":
			_add_furniture(stable, "ArchiveCabinet", Vector3(1.25, 1.65, 0.55), Vector3(-2.25, 0.82, -1.85), Color("59646a"))
			_add_furniture(stable, "DigitalWorkbench", Vector3(2.3, 0.78, 0.8), Vector3(0.7, 0.39, -0.3), Color("48565e"))
			_add_furniture(stable, "ScannerConsole", Vector3(0.9, 1.15, 0.6), Vector3(2.35, 0.58, -1.55), Color("78919b"))
		"office_manager":
			_add_furniture(stable, "ManagerDesk", Vector3(2.4, 0.78, 0.85), Vector3(0.45, 0.39, -0.7), Color("6e4c3a"))
			_add_furniture(stable, "ExecutiveChair", Vector3(0.8, 1.2, 0.75), Vector3(0.45, 0.6, -1.65), Color("383b42"))
			_add_furniture(stable, "GuestSofa", Vector3(1.9, 0.72, 0.78), Vector3(-2.15, 0.36, 0.75), Color("66544d"))
		"office_open":
			_add_furniture(stable, "OpenDeskLeft", Vector3(1.8, 0.76, 0.72), Vector3(-1.35, 0.38, -0.65), Color("62717d"))
			_add_furniture(stable, "OpenDeskRight", Vector3(1.8, 0.76, 0.72), Vector3(1.2, 0.38, 0.55), Color("62717d"))
			_add_furniture(stable, "SharedStorage", Vector3(1.2, 1.25, 0.5), Vector3(2.6, 0.62, -1.75), Color("4d5860"))
		"meeting_round":
			_add_furniture(stable, "RoundMeetingTable", Vector3(2.0, 0.74, 2.0), Vector3(0, 0.37, 0.1), Color("65516e"))
			_add_furniture(stable, "FourSeatCluster", Vector3(3.2, 0.82, 3.0), Vector3(0, 0.41, 0.1), Color("4d4658"))
			_add_furniture(stable, "WallDisplay", Vector3(2.0, 1.1, 0.12), Vector3(0.8, 1.65, -2.38), Color("314354"))
		"meeting_boardroom":
			_add_furniture(stable, "LongBoardroomTable", Vector3(1.7, 0.76, 3.2), Vector3(0, 0.38, 0.15), Color("53645f"))
			_add_furniture(stable, "SixSeatRows", Vector3(3.5, 0.86, 3.6), Vector3(0, 0.43, 0.15), Color("3f4b49"))
			_add_furniture(stable, "WideWhiteboard", Vector3(2.8, 1.2, 0.12), Vector3(-0.4, 1.65, -2.38), Color("d3d4c9"))


func _build_evidence(parent: Node3D, state: Dictionary) -> void:
	var evidence := Node3D.new()
	evidence.name = "Evidence"
	parent.add_child(evidence)
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
		_add_furniture(item_slot, "Item_%d" % (index + 1), Vector3(0.3, 0.32, 0.3), Vector3(index * 0.38, 0.16, 0), Color("b39a72"))
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
		_add_furniture(trash, "Paper_%d" % (index + 1), Vector3(0.28, 0.025, 0.2), Vector3(-2.2 + index * 0.42, 0.025, 1.75 - (index % 2) * 0.3), Color("d6d1bd"))
	var signal_light := MeshInstance3D.new()
	signal_light.name = "SignalLight"
	var sphere := SphereMesh.new()
	sphere.radius = 0.18
	sphere.height = 0.36
	signal_light.mesh = sphere
	signal_light.position = Vector3(2.45, 1.9, -2.35)
	signal_light.material_override = _material(SIGNAL_COLOR_VALUES.get(state["signal_color"], Color.WHITE))
	evidence.add_child(signal_light)


func _add_furniture(parent: Node3D, node_name: String, size: Vector3, position: Vector3, color: Color) -> void:
	var mesh := MeshInstance3D.new()
	mesh.name = node_name
	var box := BoxMesh.new()
	box.size = size
	mesh.mesh = box
	mesh.position = position
	mesh.material_override = _material(color)
	parent.add_child(mesh)


func _add_box(parent: Node3D, node_name: String, size: Vector3, position: Vector3, color: Color) -> void:
	var box := CSGBox3D.new()
	box.name = node_name
	box.size = size
	box.position = position
	box.material = _material(color)
	parent.add_child(box)


func _material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.82
	return material
