class_name AIPlayFindKeySetup
extends Node3D

@export var spawned_key_paths: Array[NodePath]
@export var contract_documents: Array[ReadableComponent]
@export var key_candidate_root_paths: Array[NodePath]

var _external_npcs: Array[FriendlyHumanNPC] = []


func _ready() -> void:
	set_scenario_active(false)


func register_external_npc(npc: FriendlyHumanNPC, region_id: String) -> void:
	if npc == null:
		return
	npc.set_meta("region_id", region_id)
	if npc not in _external_npcs:
		_external_npcs.append(npc)


func keys() -> Array[RigidBody3D]:
	var result: Array[RigidBody3D] = []
	for key_path: NodePath in spawned_key_paths:
		var key := get_node_or_null(key_path) as RigidBody3D
		if key != null:
			result.append(key)
	return result


func documents() -> Array[ReadableComponent]:
	return contract_documents.duplicate()


func key_by_region() -> Dictionary:
	var result := {}
	for key: RigidBody3D in keys():
		result[str(key.get_meta("region_id", ""))] = key
	return result


func key_candidates_by_region() -> Dictionary:
	var result := {}
	for candidate_root_path: NodePath in key_candidate_root_paths:
		var candidate_root := get_node_or_null(candidate_root_path) as Node3D
		if candidate_root == null:
			continue
		var region_id := str(candidate_root.get_meta("region_id", ""))
		var candidates: Array[Marker3D] = []
		for child: Node in candidate_root.get_children():
			if child is Marker3D:
				candidates.append(child as Marker3D)
		candidates.sort_custom(
			func(left: Marker3D, right: Marker3D) -> bool:
				return left.name.naturalnocasecmp_to(right.name) < 0
		)
		result[region_id] = candidates
	return result


func place_keys(seed_value: int) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var candidates_by_region := key_candidates_by_region()
	var regions: Array = key_by_region().keys()
	regions.sort()
	for region_value: Variant in regions:
		var region_id := str(region_value)
		var candidates: Array[Marker3D] = candidates_by_region.get(region_id, [])
		if candidates.is_empty():
			push_error("find_key region has no authored candidates: %s" % region_id)
			continue
		var key: RigidBody3D = key_by_region()[region_id]
		var candidate_index := rng.randi_range(0, candidates.size() - 1)
		key.global_transform = candidates[candidate_index].global_transform


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
		key.visible = active
		key.collision_layer = 3 if active else 0
		key.process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED
	for document: ReadableComponent in contract_documents:
		document.is_disabled = not active
		var body := document.get_parent() as CollisionObject3D
		if body != null:
			body.collision_layer = 3 if active else 0
