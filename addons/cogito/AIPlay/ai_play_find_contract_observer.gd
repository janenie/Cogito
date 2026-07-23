class_name AIPlayFindContractObserver
extends AIPlayObserver


func capture_observation(last_results: Array) -> Dictionary:
	var observation: Dictionary = super(last_results)
	var player_state: Dictionary = observation.get("player", {})
	player_state.erase("health_ratio")
	player_state.erase("stamina_ratio")
	return observation
