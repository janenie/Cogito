extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var capture_script: GDScript = load(
		"res://addons/cogito/AIPlay/ai_play_depth_capture.gd"
	)
	_assert(capture_script != null, "depth capture component exists")
	if capture_script != null:
		var capture: Node = capture_script.new()
		root.add_child(capture)
		var payload: Dictionary = capture.capture(null, 1024, 576)
		_assert(payload["mime_type"] == "image/png", "depth uses PNG")
		_assert(
			payload["encoding"] == "linear_depth_normalized_8bit",
			"depth encoding is declared",
		)
		_assert(payload["near_meters"] < payload["far_meters"], "depth range is ordered")
		_assert(
			is_equal_approx(payload["near_meters"], 0.05)
			and is_equal_approx(payload["far_meters"], 20.0),
			"depth range is tuned for local navigation",
		)
		var image := Image.new()
		_assert(
			image.load_png_from_buffer(
				Marshalls.base64_to_raw(payload["base64"])
			) == OK,
			"depth base64 decodes as PNG",
		)
		_assert(image.get_size() == Vector2i(1024, 576), "depth image is 1024x576")
		capture.free()
	_finish()


func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)


func _finish() -> void:
	if failures.is_empty():
		print("AIPlay depth capture tests passed")
		quit(0)
	else:
		for failure: String in failures:
			push_error(failure)
		quit(1)
