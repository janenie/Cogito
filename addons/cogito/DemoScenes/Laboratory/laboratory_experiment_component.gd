class_name LaboratoryExperimentComponent
extends CogitoObject

@export_enum("battery", "sample", "treatment", "connector") var component_kind := "sample"
@export var component_id := "a"
@export var label_zh := "样本 A"
@export var component_color := Color(0.3, 0.8, 0.65)

var home_transform := Transform3D.IDENTITY

@onready var component_mesh: MeshInstance3D = $Mesh
@onready var component_collision: CollisionShape3D = $CollisionShape3D
@onready var component_label: Label3D = $Label


func _ready() -> void:
	cogito_name = "Laboratory%s" % component_kind.capitalize()
	display_name = label_zh
	super._ready()
	_apply_visual()
	var carryable := $CarryableComponent
	carryable.interaction_text = "按一下 E 拿取 %s" % label_zh
	carryable.carry_state_changed.connect(_on_carry_state_changed)


func configure(kind: String, id_value: String, display_label: String, color: Color) -> void:
	component_kind = kind
	component_id = id_value
	label_zh = display_label
	component_color = color
	if is_node_ready():
		_apply_visual()


func remember_home() -> void:
	home_transform = global_transform


func return_home() -> void:
	set("freeze", true)
	global_transform = home_transform


func _on_carry_state_changed(is_carried: bool) -> void:
	var carryable: Node = $CarryableComponent
	var interaction: Node = carryable.player_interaction_component
	if interaction == null or interaction.player == null:
		return
	var player: Node = interaction.player
	if is_carried:
		call("add_collision_exception_with", player)
	else:
		call("remove_collision_exception_with", player)


func _apply_visual() -> void:
	var material := StandardMaterial3D.new()
	material.albedo_color = component_color
	material.metallic = 0.35
	material.roughness = 0.32
	match component_kind:
		"battery":
			var mesh := CylinderMesh.new()
			mesh.top_radius = 0.13
			mesh.bottom_radius = 0.13
			mesh.height = 0.42
			component_mesh.mesh = mesh
			var shape := CylinderShape3D.new()
			shape.radius = 0.13
			shape.height = 0.42
			component_collision.shape = shape
		"sample":
			var mesh := BoxMesh.new()
			mesh.size = Vector3(0.5, 0.16, 0.36)
			component_mesh.mesh = mesh
			var shape := BoxShape3D.new()
			shape.size = mesh.size
			component_collision.shape = shape
		"treatment":
			var mesh := CapsuleMesh.new()
			mesh.radius = 0.13
			mesh.height = 0.42
			component_mesh.mesh = mesh
			var shape := CapsuleShape3D.new()
			shape.radius = 0.13
			shape.height = 0.42
			component_collision.shape = shape
		"connector":
			var mesh := BoxMesh.new()
			mesh.size = Vector3(1.1, 0.12, 0.12)
			component_mesh.mesh = mesh
			var shape := BoxShape3D.new()
			shape.size = mesh.size
			component_collision.shape = shape
	component_mesh.material_override = material
	component_label.text = label_zh
