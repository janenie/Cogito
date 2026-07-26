extends SceneTree

const GardenPlant = preload("res://garden/scripts/garden_plant.gd")
const GardenWateringCan = preload("res://garden/scripts/garden_watering_can.gd")
const GardenRefillStation = preload("res://garden/scripts/garden_refill_station.gd")

var failures := 0

func _init() -> void:
	_test_finite_watering_and_refill()
	if failures == 0:
		print("Garden watering tests passed")
		quit(0)
	else:
		push_error("%d Garden watering test(s) failed" % failures)
		quit(1)

func _test_finite_watering_and_refill() -> void:
	var plant := GardenPlant.new()
	plant.moisture = 40.0

	var can := GardenWateringCan.new()
	can.capacity_max = 100.0
	can.capacity_current = 100.0
	can.water_rate = 10.0

	var delivered := can.tick_watering(1.0, plant)
	_assert(is_equal_approx(delivered, 10.0), "delivers configured water")
	_assert(is_equal_approx(can.capacity_current, 90.0), "drains finite charge")
	_assert(is_equal_approx(plant.moisture, 50.0), "applies water to plant")

	can.capacity_current = 0.0
	_assert(is_equal_approx(can.tick_watering(1.0, plant), 0.0), "empty can delivers zero")
	can.capacity_current = 20.0
	_assert(is_equal_approx(can.tick_watering(1.0, Node3D.new()), 0.0), "invalid target delivers zero")

	var refill := GardenRefillStation.new()
	_assert(is_equal_approx(refill.refill(can, 200.0), 80.0), "refill clamps at max")
	_assert(is_equal_approx(can.capacity_current, 100.0), "refill restores can")

func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
