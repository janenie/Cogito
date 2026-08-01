extends SceneTree


func _initialize() -> void:
	call_deferred("_capture")


func _capture() -> void:
	DisplayServer.window_set_size(Vector2i(1600, 900))
	var packed: PackedScene = load(
		"res://addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn"
	)
	var scene := packed.instantiate()
	root.add_child(scene)
	for frame: int in range(180):
		await process_frame
	RenderingServer.force_draw(false)
	var image := root.get_texture().get_image()
	image.save_png("/private/tmp/cogito_loop_staircase_viewport.png")
	scene.queue_free()
	await process_frame
	quit(0)
