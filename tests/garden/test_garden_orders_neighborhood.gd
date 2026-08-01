extends SceneTree

const HOUSE_SCENE_PATH := "res://garden/scenes/components/garden_order_house.tscn"
const NEIGHBORHOOD_SCENE_PATH := "res://garden/scenes/garden_orders_neighborhood.tscn"
const PLAYER_SCENE_PATH := "res://garden/scenes/components/garden_order_third_person_player.tscn"
const TOOL_AREA_SCENE_PATH := "res://garden/scenes/components/garden_order_tool_area.tscn"
const ROUTE_RULES_TEXT := "路程规则\n工具区 → 任意住宅：10 分钟\n相隔 1 栋：5 分钟\n相隔 2 栋：10 分钟\n相隔 3 栋：15 分钟\n相隔 4–5 栋：20 分钟"

var failures := 0


func _init() -> void:
	_run.call_deferred()


func _run() -> void:
	await _test_house_component()
	await _test_tool_area_component()
	await _test_third_person_player_component()
	await _test_complete_neighborhood()
	if failures == 0:
		print("Garden orders neighborhood tests passed")
		quit(0)
	else:
		push_error("%d garden orders neighborhood test(s) failed" % failures)
		quit(1)


func _test_house_component() -> void:
	_assert(ResourceLoader.exists(HOUSE_SCENE_PATH), "house component scene exists")
	if not ResourceLoader.exists(HOUSE_SCENE_PATH):
		return
	var packed := load(HOUSE_SCENE_PATH) as PackedScene
	_assert(packed != null, "house component scene loads")
	if packed == null:
		return
	var house := packed.instantiate()
	house.set("house_number", 7)
	house.set("garden_size", "large")
	root.add_child(house)
	await process_frame
	_assert(house.get_script() != null, "house component has a configuration script")
	_assert(house.call("get_garden_size") == "large", "house exposes its garden size")
	_assert((house.get_node("AddressLabel") as Label3D).text == "7", "house label follows its number")
	var size_label := house.get_node_or_null("Garden/SizeLabel") as Label3D
	_assert(size_label != null, "house garden has a visible size label")
	var expected_sizes := {
		"small": {"label": "7号 · 小型花园", "scale": 0.5},
		"medium": {"label": "7号 · 中型花园", "scale": 0.875},
		"large": {"label": "7号 · 大型花园", "scale": 1.25},
	}
	for size in ["small", "medium", "large"]:
		house.set("garden_size", size)
		if size_label != null:
			_assert(size_label.text == expected_sizes[size]["label"], "%s garden has a Chinese size label" % size)
		_assert(is_equal_approx((house.get_node("Garden/SoilBed") as MeshInstance3D).scale.x, expected_sizes[size]["scale"]), "%s garden has the approved footprint" % size)
	_assert(house.get_node_or_null("Garden/Destination") != null, "house has a destination marker")
	_assert(house.get_node_or_null("Garden/GardenWorkPoint") != null, "house has a work marker")
	_assert(house.get_node_or_null("HouseBody/CollisionShape3D") != null, "house has collision")
	_assert(_count_garden_fences(house) == 0, "house garden stays open without perimeter fences")
	house.queue_free()
	await process_frame


func _test_tool_area_component() -> void:
	_assert(ResourceLoader.exists(TOOL_AREA_SCENE_PATH), "tool area component scene exists")
	if not ResourceLoader.exists(TOOL_AREA_SCENE_PATH):
		return
	var packed := load(TOOL_AREA_SCENE_PATH) as PackedScene
	_assert(packed != null, "tool area component scene loads")
	if packed == null:
		return
	var tool_area := packed.instantiate()
	root.add_child(tool_area)
	for node_name in ["WateringCan", "Shovel", "FertilizerSpreader", "FertilizerStock"]:
		_assert(tool_area.get_node_or_null(node_name) != null, "tool area displays %s" % node_name)
	var labels := [
		(tool_area.get_node("FertilizerStock/Label") as Label3D).text,
		(tool_area.get_node("FertilizerSpreader/Label") as Label3D).text,
		(tool_area.get_node("Shovel/Label") as Label3D).text,
		(tool_area.get_node("WateringCan/Label") as Label3D).text,
	]
	_assert(labels == ["肥料 ×2", "施肥器", "松土铲", "浇水壶"], "tool labels explain each central display in Chinese")
	_assert(tool_area.get_node_or_null("FertilizerStock/Bag01") != null, "first fertilizer bag remains visible")
	_assert(tool_area.get_node_or_null("FertilizerStock/Bag02") != null, "second fertilizer bag remains visible")
	_assert(tool_area.get_node_or_null("Destination") != null, "tool area has a destination marker")
	_assert(tool_area.get_node_or_null("Shelter/CollisionShape3D") != null, "tool shelter has collision")
	tool_area.queue_free()
	await process_frame


func _test_third_person_player_component() -> void:
	_assert(ResourceLoader.exists(PLAYER_SCENE_PATH), "third-person player scene exists")
	if not ResourceLoader.exists(PLAYER_SCENE_PATH):
		return
	var packed := load(PLAYER_SCENE_PATH) as PackedScene
	_assert(packed != null, "third-person player scene loads")
	if packed == null:
		return
	var player := packed.instantiate()
	root.add_child(player)
	_assert(player is CharacterBody3D, "inspection player is a character body")
	_assert(player.get_node_or_null("CollisionShape3D") != null, "player has capsule collision")
	_assert(player.get_node_or_null("Avatar") != null, "player has a visible avatar")
	_assert(player.get_node_or_null("CameraPivot/SpringArm3D/Camera3D") != null, "player has a third-person camera")
	player.queue_free()
	await process_frame


func _test_complete_neighborhood() -> void:
	_assert(ResourceLoader.exists(NEIGHBORHOOD_SCENE_PATH), "neighborhood entry scene exists")
	if not ResourceLoader.exists(NEIGHBORHOOD_SCENE_PATH):
		return
	var packed := load(NEIGHBORHOOD_SCENE_PATH) as PackedScene
	_assert(packed != null, "neighborhood entry scene loads")
	if packed == null:
		return
	var neighborhood := packed.instantiate()
	root.add_child(neighborhood)
	await process_frame
	for path in [
		"WorldEnvironment",
		"Ground",
		"Roads",
		"Roads/TravelTimeSigns",
		"RouteInformation/RulesLabel",
		"CentralToolArea",
		"CentralToolArea/Destination",
		"PlayerSpawn",
		"GardenOrderPlayer",
		"GardenOrderPlayer/CameraPivot/SpringArm3D/Camera3D",
		"Houses",
		"NeighborhoodUI",
	]:
		_assert(neighborhood.get_node_or_null(path) != null, "neighborhood has %s" % path)
	var houses := neighborhood.get_node_or_null("Houses")
	if houses != null:
		_assert(houses.get_child_count() == 10, "neighborhood has exactly ten houses")
		var house_numbers: Array[int] = []
		var size_counts := {"small": 0, "medium": 0, "large": 0}
		for house in houses.get_children():
			house_numbers.append(int(house.get("house_number")))
			var size := str(house.call("get_garden_size"))
			size_counts[size] = int(size_counts.get(size, 0)) + 1
			_assert(house.get_node_or_null("Garden/Destination") != null, "%s has a destination" % house.name)
			_assert(house.get_node_or_null("Garden/GardenWorkPoint") != null, "%s has a work point" % house.name)
			_assert(house.get_node_or_null("HouseBody/CollisionShape3D") != null, "%s has collision" % house.name)
		house_numbers.sort()
		_assert(house_numbers == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "house numbers cover 1 through 10")
		_assert(size_counts == {"small": 5, "medium": 3, "large": 2}, "garden sizes use the approved distribution")
		_assert(houses.get_node("House03").get("garden_size") == "large", "House 3 is large")
		_assert(houses.get_node("House06").get("garden_size") == "large", "House 6 is large")
		_assert(houses.get_node("House09").get("garden_size") == "small", "House 9 is small")
	var route_rules := neighborhood.get_node_or_null("RouteInformation/RulesLabel") as Label3D
	if route_rules != null:
		_assert(route_rules.text == ROUTE_RULES_TEXT, "central board shows the complete route-cost rules")
	var travel_time_signs := neighborhood.get_node_or_null("Roads/TravelTimeSigns")
	if travel_time_signs != null:
		_assert(travel_time_signs.get_child_count() == 10, "ring road has ten adjacent travel-time signs")
		for sign in travel_time_signs.get_children():
			_assert(sign is Label3D and sign.text == "步行 5 分钟", "%s shows the adjacent travel cost" % sign.name)
	var player := neighborhood.get_node_or_null("GardenOrderPlayer") as Node3D
	if player != null:
		_assert(player.global_position.distance_to(Vector3.ZERO) < 3.0, "player starts near the central plaza")
	var title := neighborhood.get_node_or_null("NeighborhoodUI/Panel/Margin/Rows/Title") as Label
	var controls := neighborhood.get_node_or_null("NeighborhoodUI/Panel/Margin/Rows/Controls") as Label
	if title != null:
		_assert(title.text == "园艺订单社区", "central HUD title is Chinese")
	if controls != null:
		_assert(controls.text == "WASD 移动 · Shift 加速 · 鼠标旋转视角 · Esc 释放鼠标", "central HUD controls are Chinese")
	neighborhood.queue_free()
	await process_frame


func _assert(condition: bool, message: String) -> void:
	if condition:
		return
	failures += 1
	push_error("FAIL: %s" % message)


func _count_garden_fences(house: Node) -> int:
	var count := 0
	for fence_name in ["BackFence", "LeftFence", "RightFence"]:
		if house.get_node_or_null("Garden/%s" % fence_name) != null:
			count += 1
	return count
