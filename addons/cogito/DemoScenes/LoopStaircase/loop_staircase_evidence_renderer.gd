class_name LoopStaircaseEvidenceRenderer
extends RefCounted

const Decor := preload(
	"res://addons/cogito/DemoScenes/LoopStaircase/Props/loop_staircase_decor.gd"
)
const ITEM_SCENES: Dictionary = {
	"马克杯": preload("res://addons/cogito/DemoScenes/DemoPrefabs/coffee_mug.tscn"),
	"台灯": preload("res://addons/cogito/Assets/Models/Kenney/Furniture/GLTF format/lampRoundTable.glb"),
	"电脑": preload("res://addons/cogito/DemoScenes/DemoPrefabs/laptop_real.tscn"),
	"纸箱": preload("res://addons/cogito/DemoScenes/DemoPrefabs/cardboard_box_closed.tscn"),
}
const ITEM_SCALES: Dictionary = {
	"马克杯": Vector3(0.72, 0.72, 0.72),
	"台灯": Vector3(0.62, 0.62, 0.62),
	"电脑": Vector3(0.62, 0.62, 0.62),
	"纸箱": Vector3(0.25, 0.25, 0.25),
}
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
	_update_visitor_record(evidence, state)
	_update_items(evidence, state)
	_update_trash(evidence, state)
	_update_signal_lamp(evidence, state)
	Decor.freeze_tree(room.get_node("StableTheme"))
	Decor.freeze_tree(evidence)


func _update_visitor_record(evidence: Node3D, state: Dictionary) -> void:
	var visitor_record := evidence.get_node_or_null("VisitorRecord") as Label3D
	if visitor_record == null:
		push_error("Loop staircase room is missing VisitorRecord")
		return
	visitor_record.text = "访客记录\n%s" % "、".join(state["visitor_names"])
	if state["visitor_round_visible"]:
		visitor_record.text += "\n访问轮次：第%d轮" % (int(state["visitor_round"]) + 1)


func _update_items(evidence: Node3D, state: Dictionary) -> void:
	var props := evidence.get_node_or_null("ItemSlot/Props") as Node3D
	var book_slots := evidence.get_node_or_null("ItemSlot/BookSlots") as Node3D
	var item_label := evidence.get_node_or_null("ItemSlot/ItemLabel") as Label3D
	if props == null or book_slots == null or item_label == null:
		push_error("Loop staircase room is missing its item anchor")
		return
	for child: Node in props.get_children():
		props.remove_child(child)
		child.free()
	var item_name: String = state["tracked_item"]
	var item_count: int = clampi(int(state["item_count"]), 0, book_slots.get_child_count())
	for index: int in range(book_slots.get_child_count()):
		var book := book_slots.get_child(index) as Node3D
		if book != null:
			book.visible = item_name == "书本" and index < item_count
	if item_name == "书本":
		item_label.text = item_name
		return
	var packed_scene := ITEM_SCENES.get(item_name) as PackedScene
	if packed_scene == null:
		return
	for index: int in range(item_count):
		var item := packed_scene.instantiate() as Node3D
		item.name = "Item_%d" % (index + 1)
		item.position = Vector3((index % 3) * 0.32 - 0.32, 0, (index / 3) * 0.3)
		item.scale = ITEM_SCALES.get(item_name, Vector3.ONE)
		props.add_child(item)
	item_label.text = item_name


func _update_trash(evidence: Node3D, state: Dictionary) -> void:
	var trash := evidence.get_node_or_null("Trash") as Node3D
	if trash == null:
		push_error("Loop staircase room is missing its trash slots")
		return
	var count: int = clampi(int(state["trash_count"]), 0, trash.get_child_count())
	var floor_offset: int = (int(state["floor"]) - 2) % maxi(trash.get_child_count(), 1)
	for index: int in range(trash.get_child_count()):
		var slot := trash.get_child((index + floor_offset) % trash.get_child_count()) as Node3D
		if slot != null:
			slot.visible = index < count


func _update_signal_lamp(evidence: Node3D, state: Dictionary) -> void:
	var signal_lamp := evidence.get_node_or_null("SignalLight") as Node3D
	if signal_lamp == null or not signal_lamp.has_method("set_signal_color"):
		push_error("Loop staircase room is missing its signal wall lamp")
		return
	signal_lamp.call(
		"set_signal_color",
		SIGNAL_COLOR_VALUES.get(state["signal_color"], Color.WHITE),
	)
