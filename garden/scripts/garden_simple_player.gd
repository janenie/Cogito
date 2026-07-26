class_name GardenSimplePlayer
extends CharacterBody3D

@export var walk_speed := 4.0
@export var sprint_speed := 7.0
@export var jump_velocity := 4.5
@export var mouse_sensitivity := 0.0025

var _pitch := 0.0

@onready var camera: Camera3D = $Camera3D

func _ready() -> void:
	_pitch = camera.rotation.x
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func ai_play_orientation_degrees() -> Vector2:
	return Vector2(global_rotation_degrees.y, camera.rotation_degrees.x)


func ai_play_look_degrees(yaw_degrees: float, pitch_degrees: float) -> void:
	rotate_y(-deg_to_rad(yaw_degrees))
	_pitch = clampf(
		_pitch - deg_to_rad(pitch_degrees),
		-1.35,
		1.35,
	)
	camera.rotation.x = _pitch

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		rotate_y(-event.relative.x * mouse_sensitivity)
		_pitch = clampf(_pitch - event.relative.y * mouse_sensitivity, -1.35, 1.35)
		camera.rotation.x = _pitch
	elif event.is_action_pressed("menu"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

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
