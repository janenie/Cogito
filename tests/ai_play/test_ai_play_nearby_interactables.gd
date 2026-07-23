extends SceneTree

const NearbyCollector = preload(
	"res://addons/cogito/AIPlay/ai_play_nearby_interactables.gd"
)

var _failures: Array[String] = []


class FakeInteractable extends Node3D:
	var interaction_nodes: Array[Node] = []
	var prompt_pos_mode: int = 0
	var prompt_marker: Marker3D
	var ai_play_category: String = "interactable"


class FakeInteraction extends Node:
	var input_map_action: String = "interact"
	var interaction_text: String = "Read"
	var is_disabled: bool = false


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	var viewport := SubViewport.new()
	viewport.size = Vector2i(768, 432)
	root.add_child(viewport)
	var world_root := Node3D.new()
	viewport.add_child(world_root)
	var camera := Camera3D.new()
	camera.current = true
	world_root.add_child(camera)
	var player := Node3D.new()
	world_root.add_child(player)

	var collector = NearbyCollector.new()
	collector.line_of_sight_provider = func(
		_camera_position: Vector3,
		_point: Vector3,
		candidate: Node3D,
	) -> bool:
		return candidate.name != "occluded"

	var candidates: Array = []
	for index: int in range(6):
		var candidate := _candidate("candidate_%d" % index, Vector3(0.0, 0.0, -2.0 * (index + 1)))
		world_root.add_child(candidate)
		candidates.append(candidate)

	var behind := _candidate("behind", Vector3(0.0, 0.0, 2.0))
	world_root.add_child(behind)
	candidates.append(behind)
	var occluded := _candidate("occluded", Vector3(0.0, 0.0, -1.0))
	world_root.add_child(occluded)
	candidates.append(occluded)
	var disabled := _candidate("disabled", Vector3(0.0, 0.0, -1.5), true)
	world_root.add_child(disabled)
	candidates.append(disabled)
	var unapproved := _candidate("unapproved", Vector3(0.0, 0.0, -1.75), false, "reload")
	world_root.add_child(unapproved)
	candidates.append(unapproved)

	var result: Array[Dictionary] = collector.collect(
		player,
		camera,
		candidates,
		Vector2(viewport.size),
	)
	_assert(result.size() == 5, "collector caps output at five")
	_assert(
		result.map(func(item: Dictionary): return item["distance_m"]) == [
			2.0, 4.0, 6.0, 8.0, 10.0,
		],
		"collector sorts by player-to-interaction-point distance",
	)
	var centered: Dictionary = result[0]
	_assert(centered.keys() == [
		"tracking_id", "category", "distance_m", "world_position",
		"relative_position", "relative_yaw_degrees", "relative_pitch_degrees",
		"screen_position", "interactions",
	], "collector emits only the public DTO fields")
	_assert(
		is_equal_approx(centered["screen_position"]["x"], 0.5)
		and is_equal_approx(centered["screen_position"]["y"], 0.5),
		"centered candidate projects to screen center",
	)
	_assert(is_zero_approx(centered["relative_yaw_degrees"]), "centered candidate has zero yaw")
	_assert(is_zero_approx(centered["relative_position"]["right"]), "centered candidate has zero right offset")
	_assert(centered["relative_position"]["forward"] > 0.0, "centered candidate is forward")

	var marker_candidate := _candidate("marker_secret_name", Vector3(2.0, 0.0, -6.0))
	marker_candidate.prompt_pos_mode = 1
	var marker := Marker3D.new()
	marker.position = Vector3(-2.0, 0.0, 0.0)
	marker_candidate.add_child(marker)
	marker_candidate.prompt_marker = marker
	world_root.add_child(marker_candidate)
	var marker_result: Array[Dictionary] = collector.collect(
		player, camera, [marker_candidate], Vector2(viewport.size)
	)
	_assert(marker_result.size() == 1, "marker candidate is collected")
	_assert(
		marker_result[0]["world_position"] == [0.0, 0.0, -6.0],
		"marker mode uses marker global position",
	)

	var aabb_candidate := _candidate("aabb_secret_name", Vector3(2.0, 0.0, -6.0))
	aabb_candidate.prompt_pos_mode = 2
	var mesh := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(2.0, 2.0, 2.0)
	mesh.mesh = box
	mesh.position = Vector3(-2.0, 1.0, 0.0)
	aabb_candidate.add_child(mesh)
	world_root.add_child(aabb_candidate)
	var aabb_result: Array[Dictionary] = collector.collect(
		player, camera, [aabb_candidate], Vector2(viewport.size)
	)
	_assert(aabb_result.size() == 1, "AABB candidate is collected")
	_assert(
		aabb_result[0]["world_position"] == [0.0, 1.0, -6.0],
		"AABB mode uses global visual center",
	)

	var serialized := JSON.stringify(result + marker_result + aabb_result)
	_assert("secret_name" not in serialized, "DTO omits developer node names")
	_assert("contract password 1234" not in serialized, "DTO omits readable contents")

	viewport.free()
	if _failures.is_empty():
		print("AIPlay nearby interactables tests passed")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _candidate(
	candidate_name: String,
	position: Vector3,
	disabled: bool = false,
	action: String = "interact",
) -> FakeInteractable:
	var candidate := FakeInteractable.new()
	candidate.name = candidate_name
	candidate.position = position
	var component := FakeInteraction.new()
	component.input_map_action = action
	component.interaction_text = "Read"
	component.is_disabled = disabled
	component.set_meta("readable_content", "contract password 1234")
	candidate.interaction_nodes.append(component)
	candidate.add_child(component)
	return candidate


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
