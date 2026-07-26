extends SceneTree

var failures := 0

class FakeFridge extends Node:
	var is_open := false

func _init() -> void:
	_test_clock_uses_real_time_and_deadline()
	_test_routine_progression()
	if failures == 0:
		print("Daily routine time and game tests passed")
		quit(0)
	else:
		push_error("%d Daily routine time/game test(s) failed" % failures)
		quit(1)

func _test_clock_uses_real_time_and_deadline() -> void:
	var TimeSystem = load("res://dailyroutine/scripts/home_routine_time_system.gd")
	_assert(TimeSystem != null, "time system script loads")
	if TimeSystem == null:
		return
	var clock = TimeSystem.new()
	clock.reset_clock()
	_assert(clock.formatted_time() == "07:00", "routine starts at 07:00")
	clock.advance(60.0)
	_assert(clock.formatted_time() == "07:01", "one real minute advances one game minute")
	clock.advance(24.0 * 60.0)
	_assert(clock.formatted_time() == "07:25", "warning time is reachable at 07:25")
	clock.advance(5.0 * 60.0)
	_assert(clock.formatted_time() == "07:30", "clock can still display 07:30")

func _test_routine_progression() -> void:
	var TimeSystem = load("res://dailyroutine/scripts/home_routine_time_system.gd")
	var ManagerScript = load("res://dailyroutine/scripts/daily_routine_manager.gd")
	_assert(TimeSystem != null, "time script loads for manager test")
	_assert(ManagerScript != null, "manager script loads")
	if TimeSystem == null or ManagerScript == null:
		return

	var root_node := Node.new()
	root.add_child(root_node)
	var clock = TimeSystem.new()
	var fridge := FakeFridge.new()
	fridge.name = "Fridge"
	var manager = ManagerScript.new()
	root_node.add_child(clock)
	root_node.add_child(fridge)
	manager.time_system = clock
	manager.fridge_path = NodePath("../Fridge")
	root_node.add_child(manager)
	manager.required_trash_count = 5
	manager.start_routine()

	_assert(manager.current_objective == "把全部垃圾扔进客厅垃圾桶。", "routine starts without showing total trash count")
	_assert(int(manager.room_bin_counts.get("living_room", 0)) == 0, "living room bin starts empty")
	manager.set_required_loose_trash_count(4)
	_assert(manager.required_trash_count == 5, "required trash includes four loose trash items plus milk carton")
	manager.read_start_hint()
	_assert(manager.pick_up_loose_trash("kitchen"), "trash can be picked before drinking milk")
	_assert(manager.has_loose_trash, "player carries trash")
	_assert(manager.deposit_held_trash("living_room"), "trash can be placed into the living room bin")
	_assert(manager.collected_trash_count == 1, "early disposed trash count increments")

	_assert(manager.take_milk(), "player can take expired milk as trash from fridge")
	_assert(not manager.current_objective.contains("垃圾"), "HUD does not tell the player that held milk is trash")
	_assert(not manager.has_milk, "expired milk is not held as drinkable milk")
	_assert(manager.has_loose_trash, "expired milk is held as trash")
	_assert(manager.held_item_label() == "过期牛奶", "HUD shows held milk without explaining the trash-count inference")
	_assert(not manager.pick_up_loose_trash("bedroom"), "player cannot pick up trash while holding expired milk")
	_assert(manager.deposit_held_trash("living_room"), "player can place expired milk to free hands again")
	for room_id in ["bedroom", "living_room", "entry"]:
		_assert(manager.pick_up_loose_trash(room_id), "player can pick up %s trash" % room_id)
		_assert(manager.deposit_held_trash("living_room"), "player can place %s trash" % room_id)
	_assert(manager.collected_trash_count == 5, "disposed trash count increments")
	_assert(not manager.routine_complete, "cleanup does not complete until finish button is pressed")
	_assert(manager.submit_cleanup(), "finish button succeeds after all trash is in the bin")
	_assert(manager.routine_complete, "finish button completes the routine")
	_assert(not manager.routine_failed, "completion does not fail")

	var open_fridge_manager = ManagerScript.new()
	open_fridge_manager.time_system = clock
	open_fridge_manager.fridge_path = NodePath("../Fridge")
	root_node.add_child(open_fridge_manager)
	open_fridge_manager.start_routine()
	open_fridge_manager.required_trash_count = 1
	open_fridge_manager.collected_trash_count = 1
	open_fridge_manager.milk_drunk = true
	fridge.is_open = true
	_assert(not open_fridge_manager.submit_cleanup(), "finish button fails while fridge is open")
	_assert(open_fridge_manager.routine_failed, "open fridge completion attempt fails the routine")
	_assert(open_fridge_manager.failure_reason == "任务失败。", "open fridge failure does not reveal which rule failed")
	fridge.is_open = false

	var actor := Node3D.new()
	root_node.add_child(actor)
	actor.position = Vector3(10, 0, 0)
	_assert(not manager.take_room_bin("living_room", actor, Vector3.ZERO), "trash bin is no longer picked up")

	manager.retry_routine()
	manager.read_start_hint()
	_assert(not manager.submit_cleanup(), "finish button fails if trash remains")
	_assert(manager.routine_failed, "unfinished cleanup reports failure")
	root_node.queue_free()

func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
