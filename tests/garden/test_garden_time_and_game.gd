extends SceneTree

const GardenPlant = preload("res://garden/scripts/garden_plant.gd")
const GardenPlantGroup = preload("res://garden/scripts/garden_plant_group.gd")
const GardenTimeSystem = preload("res://garden/scripts/garden_time_system.gd")
const GardenGameManager = preload("res://garden/scripts/garden_game_manager.gd")

var failures := 0

func _init() -> void:
	_test_clock_and_day_lifecycle()
	if failures == 0:
		print("Garden time and game tests passed")
		quit(0)
	else:
		push_error("%d Garden time/game test(s) failed" % failures)
		quit(1)

func _test_clock_and_day_lifecycle() -> void:
	var clock = GardenTimeSystem.new()
	clock.real_day_seconds = 38.0 * 60.0
	clock.reset_clock()
	_assert(clock.formatted_time() == "08:00", "day starts at 08:00")
	clock.advance(38.0 * 60.0)
	_assert(clock.formatted_time() == "17:00", "38 minutes advances to 17:00")
	clock.reset_clock()
	clock.paused = true
	clock.advance(60.0)
	_assert(clock.formatted_time() == "08:00", "paused clock does not advance")

	var root := Node.new()
	var time = GardenTimeSystem.new()
	var group = GardenPlantGroup.new()
	var required: Array[String] = ["sunflower_morning"]
	group.required_windows = required
	var plant = GardenPlant.new()
	group.add_child(plant)
	var manager = GardenGameManager.new()
	root.add_child(time)
	root.add_child(group)
	root.add_child(manager)
	manager.time_system = time
	manager.sunflower_group = group
	manager.start_day()

	var objective_seen = manager.current_objective.contains("sunflower")
	_assert(objective_seen, "start objective mentions sunflowers")
	time.minutes_since_midnight = 10.0 * 60.0
	manager.evaluate_deadlines()
	_assert(manager.day_failed, "missed sunflower deadline fails")

	manager.retry_day()
	_assert(not manager.day_failed, "retry clears failure")
	_assert(time.formatted_time() == "08:00", "retry resets clock")

	manager.start_day()
	plant.health = 0.0
	plant.simulate(1.0)
	_assert(manager.day_failed, "plant death fails immediately")

func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
