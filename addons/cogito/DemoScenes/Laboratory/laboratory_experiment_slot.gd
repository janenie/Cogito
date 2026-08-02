class_name LaboratoryExperimentSlot
extends Area3D

signal component_changed(kind: String, component_id: String)

@export_enum("battery", "sample", "treatment", "connector") var accepted_kind := "sample"

var current_component: Node3D = null

@onready var snap_position: Marker3D = $SnapPosition


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)


func _on_body_entered(body: Node3D) -> void:
	if current_component != null or body.get("component_kind") == null:
		return
	var component: Node3D = body
	if component.component_kind != accepted_kind:
		return
	var carryable: Node = component.get_node_or_null("CarryableComponent")
	if carryable == null or not carryable.is_being_carried:
		return
	carryable.leave()
	current_component = component
	component.set("freeze", true)
	component.global_transform = snap_position.global_transform
	component_changed.emit(accepted_kind, component.component_id)


func _on_body_exited(body: Node3D) -> void:
	if body != current_component:
		return
	current_component = null
	component_changed.emit(accepted_kind, "none")


func eject_component() -> void:
	if current_component == null:
		return
	var component: Node3D = current_component
	current_component = null
	component.return_home()
	component_changed.emit(accepted_kind, "none")
