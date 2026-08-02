class_name AIPlayLoopStaircaseObserver
extends AIPlayObserver

@export var manager: Node


func capture_observation(last_results: Array) -> Dictionary:
	var observation: Dictionary = super.capture_observation(last_results)
	if manager != null and manager.has_method("ai_play_public_state"):
		observation["staircase"] = manager.ai_play_public_state()
	return observation
