extends SceneTree

const HOUSE_SCENE_PATH := "res://garden/scenes/components/garden_order_house.tscn"

var failures := 0


func _init() -> void:
	_run.call_deferred()


func _run() -> void:
	await _test_house_component()
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
	_assert(house.get_node_or_null("Garden/Destination") != null, "house has a destination marker")
	_assert(house.get_node_or_null("Garden/GardenWorkPoint") != null, "house has a work marker")
	_assert(house.get_node_or_null("HouseBody/CollisionShape3D") != null, "house has collision")
	house.queue_free()
	await process_frame


func _assert(condition: bool, message: String) -> void:
	if condition:
		return
	failures += 1
	push_error("FAIL: %s" % message)
