class_name HomeRobotPlayer
extends CharacterBody3D

@export var walk_speed := 4.0
@export var sprint_speed := 6.5
@export var jump_velocity := 4.0
@export var mouse_sensitivity := 0.0025
@export var prompt_label_path: NodePath
@export var hint_label_path: NodePath
@export var crosshair_texture_path: NodePath
@export var manager_path: NodePath
@export var readable_panel_path: NodePath
@export var readable_title_path: NodePath
@export var readable_content_path: NodePath
@export var nearby_trash_bin_range := 2.0
@export var default_crosshair: Texture2D
@export var interaction_crosshair: Texture2D

var _pitch := 0.0
var _current_interaction_target: Node
var _hint_timer := 0.0

@onready var camera: Camera3D = get_node_or_null("Camera3D")
@onready var interaction_ray: RayCast3D = get_node_or_null("Camera3D/InteractionRay")
@onready var prompt_label: Label = get_node_or_null(prompt_label_path)
@onready var hint_label: Label = get_node_or_null(hint_label_path)
@onready var crosshair_texture: TextureRect = get_node_or_null(crosshair_texture_path)
@onready var routine_manager: Node = get_node_or_null(manager_path)
@onready var readable_panel: Control = get_node_or_null(readable_panel_path)
@onready var readable_title_label: Label = get_node_or_null(readable_title_path)
@onready var readable_content_label: Label = get_node_or_null(readable_content_path)

func _ready() -> void:
	if routine_manager == null:
		routine_manager = get_node_or_null("../DailyRoutineManager")
	if camera != null:
		_pitch = camera.rotation.x
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	_update_interaction_ui(null)
	if hint_label != null:
		hint_label.visible = false
	if readable_panel != null:
		readable_panel.visible = false

func _unhandled_input(event: InputEvent) -> void:
	if _readable_is_open():
		if event.is_action_pressed("menu") or event.is_action_pressed("interact") or event.is_action_pressed("interact2"):
			_close_readable()
		return
	if event is InputEventMouseMotion and camera != null:
		rotate_y(-event.relative.x * mouse_sensitivity)
		_pitch = clampf(_pitch - event.relative.y * mouse_sensitivity, -1.35, 1.35)
		camera.rotation.x = _pitch
	elif event.is_action_pressed("menu"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event.is_action_pressed("interact") or event.is_action_pressed("interact2"):
		_try_interact()
	elif event.is_action_pressed("inventory_use_item"):
		_try_use_held_item()
	elif event.is_action_pressed("inventory_drop_item"):
		_try_drop_held_item()

func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity += get_gravity() * delta
	if Input.is_action_just_pressed("jump") and is_on_floor():
		velocity.y = jump_velocity

	var input_dir := Input.get_vector("left", "right", "forward", "back")
	var direction := (transform.basis * Vector3(input_dir.x, 0.0, input_dir.y)).normalized()
	var speed := sprint_speed if Input.is_action_pressed("sprint") else walk_speed
	if direction:
		velocity.x = direction.x * speed
		velocity.z = direction.z * speed
	else:
		velocity.x = move_toward(velocity.x, 0.0, speed)
		velocity.z = move_toward(velocity.z, 0.0, speed)
	move_and_slide()
	_update_interaction_target()
	_update_hint(delta)

func _try_interact() -> void:
	var target := _target_from_ray()
	if target != null:
		_interact_with_target(target)
		_update_interaction_ui(target)
		return
	_drop_held_trash_to_nearby_bin()

func _try_use_held_item() -> void:
	var target := _target_from_ray()
	if target != null:
		_interact_with_target(target)
		_update_interaction_ui(target)
		return
	if _drop_held_trash_to_nearby_bin():
		return
	if routine_manager == null:
		return
	if routine_manager.get("has_milk") == true and routine_manager.has_method("drink_milk"):
		var drank: bool = routine_manager.drink_milk()
		send_hint(null, "Used." if drank else routine_manager.current_objective)

func _try_drop_held_item() -> void:
	if routine_manager == null:
		return
	if routine_manager.get("has_milk") == true and routine_manager.has_method("place_milk_down"):
		var placed: bool = routine_manager.place_milk_down()
		send_hint(null, "Placed." if placed else routine_manager.current_objective)

func send_hint(_icon: Texture2D, message: String) -> void:
	print(message)
	if hint_label != null:
		hint_label.text = message
		hint_label.visible = true
		if hint_label.get_parent() is CanvasItem:
			hint_label.get_parent().visible = true
		_hint_timer = 2.4

func resolve_interaction_target_for_test(collider: Node) -> Node:
	return _resolve_interaction_target(collider)

func get_interaction_prompt_for_test(target: Node) -> String:
	return _interaction_prompt_for(target)

func interact_with_target_for_test(target: Node) -> void:
	_interact_with_target(target)

func drop_held_trash_to_nearby_bin_for_test() -> bool:
	return _drop_held_trash_to_nearby_bin()


func current_interaction_target() -> Node:
	return _target_from_ray()


func is_readable_open() -> bool:
	return _readable_is_open()


func ai_play_orientation_degrees() -> Vector2:
	var yaw := global_rotation_degrees.y
	var pitch := 0.0
	if camera != null:
		pitch = camera.rotation_degrees.x
	return Vector2(yaw, pitch)


func ai_play_look_degrees(yaw_degrees: float, pitch_degrees: float) -> void:
	rotate_y(-deg_to_rad(yaw_degrees))
	_pitch = clampf(_pitch - deg_to_rad(pitch_degrees), -1.35, 1.35)
	if camera != null:
		camera.rotation.x = _pitch
	_update_interaction_target()

func _update_interaction_target() -> void:
	if interaction_ray == null:
		_update_interaction_ui(null)
		return
	interaction_ray.force_raycast_update()
	var target := _resolve_interaction_target(interaction_ray.get_collider())
	if target != _current_interaction_target:
		_current_interaction_target = target
	_update_interaction_ui(target)

func _target_from_ray() -> Node:
	if interaction_ray == null:
		return null
	interaction_ray.force_raycast_update()
	return _resolve_interaction_target(interaction_ray.get_collider())

func _resolve_interaction_target(collider: Object) -> Node:
	var node := collider as Node
	while node != null:
		if node.has_method("interact"):
			return node
		if _readable_component_for(node) != null:
			return node
		node = node.get_parent()
	return null

func _interaction_prompt_for(target: Node) -> String:
	if target == null:
		return ""
	var interaction_text = target.get("interaction_text")
	if interaction_text is String and not interaction_text.is_empty():
		if interaction_text == "DOOR_Open":
			return "Open"
		if interaction_text == "DOOR_Close":
			return "Close"
		return tr(interaction_text)
	if target.get("is_open") is bool:
		return "Close" if target.get("is_open") else "Open"
	var readable := _readable_component_for(target)
	if readable != null:
		var readable_interaction_text = readable.get("interaction_text")
		if readable_interaction_text is String and not readable_interaction_text.is_empty():
			return readable_interaction_text
		return "Read"
	var node_name := str(target.name)
	if node_name.contains("StartHint"):
		return "Read note"
	if node_name.contains("FridgeMilk"):
		return "Take"
	if node_name.contains("BreakfastSpot"):
		return "Check"
	if node_name.contains("TrashBin"):
		return "Use"
	if node_name.contains("PaperTrash"):
		return "Pick up"
	return "Interact"

func _interact_with_target(target: Node) -> void:
	if _is_cogito_door_like(target):
		if target.get("is_open"):
			target.close_door(self)
		else:
			target.open_door(self)
		return
	if _is_external_container_like(target):
		_toggle_external_container(target)
		return
	var readable := _readable_component_for(target)
	if readable != null:
		_show_readable(readable)
		return
	target.interact(self)

func _is_cogito_door_like(target: Node) -> bool:
	return target.has_method("open_door") \
		and target.has_method("close_door") \
		and target.get("is_open") is bool

func _is_external_container_like(target: Node) -> bool:
	if not target.has_method("open") or not target.has_method("close"):
		return false
	return target.is_in_group("external_inventory") or str(target.name).contains("Fridge")

func _toggle_external_container(target: Node) -> void:
	if str(target.get_script()).contains("addon_fridge_interaction.gd") and target.has_method("interact"):
		target.interact(self)
		return
	if target.get("is_open") == true:
		target.close(self)
	else:
		target.open(self)

func _update_interaction_ui(target: Node) -> void:
	var prompt := _interaction_prompt_for(target)
	if prompt_label != null:
		prompt_label.text = "F/E: " + prompt if not prompt.is_empty() else ""
		prompt_label.visible = not prompt.is_empty()
		if prompt_label.get_parent() is CanvasItem:
			prompt_label.get_parent().visible = not prompt.is_empty()
	if crosshair_texture != null:
		crosshair_texture.texture = interaction_crosshair if target != null and interaction_crosshair != null else default_crosshair

func _update_hint(delta: float) -> void:
	if hint_label == null or not hint_label.visible:
		return
	_hint_timer -= delta
	if _hint_timer <= 0.0:
		hint_label.visible = false
		if hint_label.get_parent() is CanvasItem:
			hint_label.get_parent().visible = false

func _readable_component_for(target: Node) -> Node:
	if target == null:
		return null
	if target.name == "ReadableComponent" or target.get_script() != null and str(target.get_script()).contains("ReadableComponent"):
		return target
	for child in target.get_children():
		if child.name == "ReadableComponent":
			return child
	return null

func _show_readable(readable: Node) -> void:
	var title := str(readable.get("readable_title"))
	var content := str(readable.get("readable_content"))
	if readable_title_label != null:
		readable_title_label.text = title
	if readable_content_label != null:
		readable_content_label.text = content
	if readable_panel != null:
		readable_panel.visible = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _close_readable() -> void:
	if readable_panel != null:
		readable_panel.visible = false
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _readable_is_open() -> bool:
	return readable_panel != null and readable_panel.visible

func _drop_held_trash_to_nearby_bin() -> bool:
	if routine_manager == null or routine_manager.get("has_loose_trash") != true:
		return false
	var bin := _nearest_trash_bin()
	if bin == null:
		return false
	_interact_with_target(bin)
	return routine_manager.get("has_loose_trash") != true

func _nearest_trash_bin() -> Node:
	var search_root := get_parent()
	if is_inside_tree() and get_tree().current_scene != null:
		search_root = get_tree().current_scene
	if search_root == null:
		return null
	var best: Node = null
	var best_distance := INF
	var origin := global_position if is_inside_tree() else position
	for node in _collect_trash_bins(search_root):
		var bin_node := node as Node3D
		if bin_node == null:
			continue
		var bin_position := bin_node.global_position if bin_node.is_inside_tree() else bin_node.position
		var distance := origin.distance_to(bin_position)
		if distance <= nearby_trash_bin_range and distance < best_distance:
			best = bin_node
			best_distance = distance
	return best

func _collect_trash_bins(root_node: Node) -> Array[Node]:
	var bins: Array[Node] = []
	if str(root_node.name).contains("TrashBin") and root_node.has_method("interact"):
		bins.append(root_node)
	for child in root_node.get_children():
		bins.append_array(_collect_trash_bins(child))
	return bins
