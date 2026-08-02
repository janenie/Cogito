extends SceneTree

const PREVIEW_SCENE := "res://conveyor_profit/scenes/conveyor_profit_preview.tscn"
const OUTPUT_PREFIX := "--output="


func _initialize() -> void:
	call_deferred("_render_preview")


func _render_preview() -> void:
	var output_path: String = ""
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with(OUTPUT_PREFIX):
			output_path = argument.trim_prefix(OUTPUT_PREFIX)
	if output_path.is_empty() or not output_path.is_absolute_path():
		push_error("--output must be an absolute path")
		quit(2)
		return

	root.size = Vector2i(1280, 720)
	var change_error: Error = change_scene_to_file(PREVIEW_SCENE)
	if change_error != OK:
		push_error("could not load preview scene")
		quit(3)
		return
	await scene_changed
	for _index: int in range(12):
		await process_frame
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	var save_error: Error = image.save_png(output_path)
	if save_error != OK:
		push_error("could not save preview image")
		quit(4)
		return
	quit(0)
