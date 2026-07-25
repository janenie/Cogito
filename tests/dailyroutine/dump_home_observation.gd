extends SceneTree


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var packed: PackedScene = load("res://dailyroutine/scenes/home_daily_routine.tscn")
	var scene := packed.instantiate()
	root.add_child(scene)
	await process_frame
	var observer := scene.get_node_or_null("AIPlayController/Observer")
	var player := scene.get_node_or_null("CogitoPlayer")
	var manager := scene.get_node_or_null("DailyRoutineManager")
	observer.player = player
	observer.manager = manager
	var observation: Dictionary = observer.capture_observation([])
	var file := FileAccess.open("/tmp/cogito_home_observation.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(observation))
	file.close()
	scene.queue_free()
	await process_frame
	print("dumped home observation")
	quit(0)
