class_name AIPlayFindKeySetup
extends Node3D

@export var spawned_keys: Array[RigidBody3D]
@export var contract_documents: Array[ReadableComponent]

var _external_keys: Array[RigidBody3D] = []
var _external_npcs: Array[FriendlyHumanNPC] = []


func _ready() -> void:
	set_scenario_active(false)


func register_external_key(
	key: RigidBody3D,
	region_id: String,
	placement_kind: String,
) -> void:
	if key == null:
		return
	key.set_meta("region_id", region_id)
	key.set_meta("placement_kind", placement_kind)
	if key not in _external_keys:
		_external_keys.append(key)


func register_external_npc(npc: FriendlyHumanNPC, region_id: String) -> void:
	if npc == null:
		return
	npc.set_meta("region_id", region_id)
	if npc not in _external_npcs:
		_external_npcs.append(npc)


func keys() -> Array[RigidBody3D]:
	var result: Array[RigidBody3D] = spawned_keys.duplicate()
	result.append_array(_external_keys)
	return result


func documents() -> Array[ReadableComponent]:
	return contract_documents.duplicate()


func key_by_region() -> Dictionary:
	var result := {}
	for key: RigidBody3D in keys():
		result[str(key.get_meta("region_id", ""))] = key
	return result


func npc_by_region() -> Dictionary:
	var result := {}
	for npc: FriendlyHumanNPC in _external_npcs:
		result[str(npc.get_meta("region_id", ""))] = npc
	return result


func document_by_region() -> Dictionary:
	var result := {}
	for document: ReadableComponent in contract_documents:
		result[str(document.get_meta("region_id", ""))] = document
	return result


func layout_snapshot() -> Dictionary:
	var key_layout := {}
	for region_id: String in key_by_region():
		var key: RigidBody3D = key_by_region()[region_id]
		key_layout[region_id] = {
			"position": key.global_position,
			"placement_kind": key.get_meta("placement_kind"),
		}
	var npc_layout := {}
	for region_id: String in npc_by_region():
		npc_layout[region_id] = npc_by_region()[region_id].global_position
	return {"keys": key_layout, "npcs": npc_layout}


func set_scenario_active(active: bool) -> void:
	visible = active
	process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED
	for object: Node in find_children("*", "CollisionObject3D", true, false):
		var collision_object := object as CollisionObject3D
		if not collision_object.has_meta("find_key_base_collision_layer"):
			collision_object.set_meta(
				"find_key_base_collision_layer",
				collision_object.collision_layer,
			)
		collision_object.collision_layer = (
			int(collision_object.get_meta("find_key_base_collision_layer"))
			if active
			else 0
		)
	for key: RigidBody3D in keys():
		key.collision_layer = 3 if active else 0
		key.process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED
	for document: ReadableComponent in contract_documents:
		document.is_disabled = not active
		var body := document.get_parent() as CollisionObject3D
		if body != null:
			body.collision_layer = 3 if active else 0
