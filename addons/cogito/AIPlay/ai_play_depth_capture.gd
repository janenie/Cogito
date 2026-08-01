class_name AIPlayDepthCapture
extends Node

const DEPTH_SHADER: Shader = preload("res://addons/cogito/AIPlay/ai_play_depth_map.gdshader")
const DEPTH_CAPTURE_LAYER: int = 1 << 19
const NEAR_METERS: float = 0.05
const FAR_METERS: float = 20.0
const DEPTH_ENCODING := "linear_depth_normalized_8bit"

var _depth_viewport: SubViewport
var _depth_camera: Camera3D
var _depth_overlay: MeshInstance3D
var _depth_material: ShaderMaterial
var _depth_environment: Environment


func capture(source_camera: Camera3D, width: int, height: int) -> Dictionary:
	if (
		DisplayServer.get_name() == "headless"
		or source_camera == null
		or not is_instance_valid(source_camera)
		or not source_camera.is_inside_tree()
	):
		return _fallback_payload(width, height)
	var source_viewport := source_camera.get_viewport()
	var world := source_camera.get_world_3d()
	if source_viewport == null or world == null:
		return _fallback_payload(width, height)
	if not _ensure_capture_viewport(world):
		return _fallback_payload(width, height)

	_depth_viewport.size = Vector2i(maxi(2, width), maxi(2, height))
	_sync_camera(source_camera)

	# The quad shares the scene World3D, so hide its dedicated layer from every
	# other camera while the renderer refreshes all active viewports.
	var masked_cameras := _mask_capture_layer_from_other_cameras(world)
	_depth_overlay.visible = true
	_depth_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	RenderingServer.force_draw(false)
	var depth_image := _depth_viewport.get_texture().get_image()
	_depth_overlay.visible = false
	_restore_camera_masks(masked_cameras)
	if depth_image == null or depth_image.get_width() <= 0 or depth_image.get_height() <= 0:
		return _fallback_payload(width, height)
	depth_image.convert(Image.FORMAT_RGB8)
	var png := depth_image.save_png_to_buffer()
	if png.is_empty():
		return _fallback_payload(width, height)
	return _payload_from_png(png, width, height)


func _ensure_capture_viewport(world: World3D) -> bool:
	if _depth_viewport != null and _depth_viewport.world_3d != world:
		_depth_viewport.queue_free()
		_depth_viewport = null
		_depth_camera = null
		_depth_overlay = null
		_depth_material = null
		_depth_environment = null
	if _depth_viewport != null:
		return true

	_depth_viewport = SubViewport.new()
	_depth_viewport.name = "AIPlayDepthViewport"
	_depth_viewport.own_world_3d = false
	_depth_viewport.world_3d = world
	_depth_viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	_depth_viewport.transparent_bg = false
	add_child(_depth_viewport)

	_depth_camera = Camera3D.new()
	_depth_camera.name = "AIPlayDepthCamera"
	_depth_viewport.add_child(_depth_camera)
	_depth_environment = Environment.new()
	_depth_environment.background_mode = Environment.BG_COLOR
	_depth_environment.background_color = Color.BLACK
	_depth_environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	_depth_environment.tonemap_exposure = 1.0
	_depth_camera.environment = _depth_environment

	_depth_overlay = MeshInstance3D.new()
	_depth_overlay.name = "AIPlayDepthOverlay"
	var quad := QuadMesh.new()
	quad.size = Vector2(2.0, 2.0)
	_depth_overlay.mesh = quad
	_depth_overlay.layers = DEPTH_CAPTURE_LAYER
	_depth_overlay.extra_cull_margin = 1_000_000.0
	_depth_overlay.cast_shadow = MeshInstance3D.SHADOW_CASTING_SETTING_OFF
	_depth_overlay.visible = false
	_depth_material = ShaderMaterial.new()
	_depth_material.shader = DEPTH_SHADER
	_depth_material.render_priority = 127
	_depth_material.set_shader_parameter("near_meters", NEAR_METERS)
	_depth_material.set_shader_parameter("far_meters", FAR_METERS)
	_depth_overlay.material_override = _depth_material
	_depth_camera.add_child(_depth_overlay)
	return true


func _mask_capture_layer_from_other_cameras(world: World3D) -> Array[Dictionary]:
	var masked_cameras: Array[Dictionary] = []
	var tree := get_tree()
	if tree == null:
		return masked_cameras
	for node: Node in tree.root.find_children("*", "Camera3D", true, false):
		var camera := node as Camera3D
		if (
			camera == null
			or camera == _depth_camera
			or not camera.is_inside_tree()
			or camera.get_world_3d() != world
			or camera.cull_mask & DEPTH_CAPTURE_LAYER == 0
		):
			continue
		masked_cameras.append({"camera": camera, "cull_mask": camera.cull_mask})
		camera.cull_mask &= ~DEPTH_CAPTURE_LAYER
	return masked_cameras


func _restore_camera_masks(masked_cameras: Array[Dictionary]) -> void:
	for entry: Dictionary in masked_cameras:
		var camera: Camera3D = entry["camera"]
		if is_instance_valid(camera):
			camera.cull_mask = entry["cull_mask"]


func _sync_camera(source_camera: Camera3D) -> void:
	_depth_camera.global_transform = source_camera.global_transform
	_depth_camera.projection = source_camera.projection
	_depth_camera.fov = source_camera.fov
	_depth_camera.size = source_camera.size
	_depth_camera.keep_aspect = source_camera.keep_aspect
	_depth_camera.frustum_offset = source_camera.frustum_offset
	_depth_camera.near = source_camera.near
	_depth_camera.far = source_camera.far
	_depth_camera.h_offset = source_camera.h_offset
	_depth_camera.v_offset = source_camera.v_offset
	_depth_camera.cull_mask = source_camera.cull_mask | DEPTH_CAPTURE_LAYER
	_depth_camera.make_current()


func _fallback_payload(width: int, height: int) -> Dictionary:
	var image := Image.create(width, height, false, Image.FORMAT_RGB8)
	image.fill(Color.WHITE)
	return _payload_from_png(image.save_png_to_buffer(), width, height)


func _payload_from_png(png: PackedByteArray, width: int, height: int) -> Dictionary:
	return {
		"mime_type": "image/png",
		"base64": Marshalls.raw_to_base64(png),
		"width": width,
		"height": height,
		"encoding": DEPTH_ENCODING,
		"near_meters": NEAR_METERS,
		"far_meters": FAR_METERS,
	}
