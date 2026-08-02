class_name AIPlayLaboratoryObserver
extends AIPlayObserver

@export var manager: Node


func capture_observation(last_results: Array) -> Dictionary:
	var observation := super.capture_observation(last_results)
	if manager != null and manager.has_method("ai_play_public_state"):
		observation["laboratory"] = manager.ai_play_public_state()
	return observation
