extends SceneTree

const GardenPlant = preload("res://garden/scripts/garden_plant.gd")
const GardenPlantGroup = preload("res://garden/scripts/garden_plant_group.gd")

var failures := 0

func _init() -> void:
	_test_plant_moisture_health_and_group_completion()
	if failures == 0:
		print("Garden plant tests passed")
		quit(0)
	else:
		push_error("%d Garden plant test(s) failed" % failures)
		quit(1)

func _test_plant_moisture_health_and_group_completion() -> void:
	var plant := GardenPlant.new()
	plant.moisture = 50.0
	plant.health = 100.0
	plant.safe_min = 40.0
	plant.safe_max = 70.0
	plant.dry_rate = 1.0
	plant.damage_rate = 10.0

	plant.apply_water(10.0)
	_assert(is_equal_approx(plant.moisture, 60.0), "watering increases moisture")
	plant.simulate(10.0)
	_assert(is_equal_approx(plant.moisture, 50.0), "simulation dries soil")
	_assert(plant.condition() == "healthy", "safe moisture is healthy")

	plant.moisture = 20.0
	plant.simulate(2.0)
	_assert(plant.health < 100.0, "drought damages health")
	_assert(plant.condition() == "dry", "low moisture is dry")

	plant.moisture = 90.0
	plant.health = 15.0
	var death_events: Array[String] = []
	plant.died.connect(func() -> void: death_events.append("died"))
	plant.simulate(2.0)
	plant.simulate(2.0)
	_assert(plant.is_dead, "zero health kills plant")
	_assert(death_events.size() == 1, "death emits once")
	_assert(plant.condition() == "too_wet", "high moisture is too wet")

	var group := GardenPlantGroup.new()
	var required: Array[String] = ["sunflower_morning"]
	group.required_windows = required
	var a := GardenPlant.new()
	var b := GardenPlant.new()
	group.add_child(a)
	group.add_child(b)
	a.mark_window("sunflower_morning")
	_assert(not group.is_complete(), "group waits for every plant")
	b.mark_window("sunflower_morning")
	_assert(group.is_complete(), "group completes when every plant marks required window")

func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
