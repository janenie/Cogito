class_name GardenPlantGroup
extends Node3D

const GardenPlantScript = preload("res://garden/scripts/garden_plant.gd")

@export var required_windows: Array[String] = []

func is_complete() -> bool:
	var plants := _plants()
	if plants.is_empty():
		return false
	for plant in plants:
		for window_id in required_windows:
			if not plant.completed_windows.has(window_id):
				return false
	return true

func has_dead_plant() -> bool:
	for plant in _plants():
		if plant.is_dead:
			return true
	return false

func reset_group() -> void:
	for plant in _plants():
		plant.reset_plant()

func _plants() -> Array:
	var result := []
	for child in get_children():
		if child.get_script() == GardenPlantScript:
			result.append(child)
	return result
