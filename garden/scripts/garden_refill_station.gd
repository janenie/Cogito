class_name GardenRefillStation
extends Node3D

@export var refill_rate := 100.0

func refill(can: Node, amount: float = -1.0) -> float:
	if can == null or not can.has_method("refill"):
		return 0.0
	var refill_amount := refill_rate if amount < 0.0 else amount
	return can.refill(refill_amount)
