extends SceneTree

const ENVIRONMENT_PATH := "res://conveyor_profit/scenes/conveyor_profit_environment.tscn"
const OBSERVER_PATH := "res://conveyor_profit/scripts/conveyor_ai_play_observer.gd"

var failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	var observer_script := load(OBSERVER_PATH) as GDScript
	_check(observer_script != null, "conveyor AI Play observer loads")
	if observer_script == null:
		quit(1)
		return
	var environment := (load(ENVIRONMENT_PATH) as PackedScene).instantiate()
	root.add_child(environment)
	var observer: Node = observer_script.new()
	observer.gameplay = environment.get_node("Gameplay")
	root.add_child(observer)
	await process_frame
	var observation: Dictionary = observer.capture_observation([])
	_check(
		observation.keys().size() == 8
		and observation.has("conveyor")
		and observation.has("image")
		and observation.has("last_action_results"),
		"observer emits the bounded observation shape",
	)
	var public_state: Dictionary = observation.get("conveyor", {})
	var public_keys: Array = public_state.keys()
	public_keys.sort()
	_check(
		public_keys == [
			"dish", "finished", "last_receipt", "net_profit", "total_time", "tray", "window", "window_time",
		],
		"observer exposes only HUD-level conveyor fields",
	)
	for hidden_field: String in [
		"ingredients", "candidate_recipes", "best_profit", "future_supply", "seed", "passing_profit",
		"deck_id", "recipe_counts", "missing_ingredient", "theoretical_profit", "optimal_route",
	]:
		_check(not public_state.has(hidden_field), "observer hides %s" % hidden_field)

	observer.queue_free()
	environment.queue_free()
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
