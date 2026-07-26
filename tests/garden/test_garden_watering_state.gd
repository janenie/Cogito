extends SceneTree

const GardenWateringState = preload("res://garden/scripts/garden_watering_state.gd")

var failures := 0

func _init() -> void:
	var state = GardenWateringState.new()
	_assert(not state.has_can, "player starts without watering can")
	_assert(not state.water(), "cannot water before picking up can")
	state.has_can = true
	_assert(state.has_water, "picked up watering can starts full")
	state.water()
	_assert(not state.has_water, "watering empties the can")
	state.water()
	_assert(not state.has_water, "watering while empty stays empty")
	state.refill()
	_assert(state.has_water, "refill makes can full")

	if failures == 0:
		print("Garden watering state tests passed")
		quit(0)
	else:
		push_error("%d Garden watering state test(s) failed" % failures)
		quit(1)

func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
