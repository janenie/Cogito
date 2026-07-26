class_name GardenWateringCan
extends Node3D

signal capacity_changed(current: float, maximum: float)
signal emptied

@export var capacity_max := 100.0
@export var capacity_current := 100.0
@export var water_rate := 10.0
@export var valid_range := 2.2
@export var hint_on_empty := "The watering can is empty. Refill it at the shared tap."

var is_watering := false

func tick_watering(delta: float, target: Node) -> float:
	if delta <= 0.0 or capacity_current <= 0.0 or not _is_valid_target(target):
		return 0.0
	var delivered = minf(water_rate * delta, capacity_current)
	capacity_current = maxf(0.0, capacity_current - delivered)
	target.apply_water(delivered)
	capacity_changed.emit(capacity_current, capacity_max)
	if capacity_current <= 0.0:
		emptied.emit()
	return delivered

func refill(amount: float) -> float:
	if amount <= 0.0:
		return 0.0
	var before := capacity_current
	capacity_current = minf(capacity_max, capacity_current + amount)
	var added := capacity_current - before
	if added > 0.0:
		capacity_changed.emit(capacity_current, capacity_max)
	return added

func capacity_text() -> String:
	return "Water: %d / %d" % [roundi(capacity_current), roundi(capacity_max)]

func _is_valid_target(target: Node) -> bool:
	return target != null and target.has_method("apply_water")
