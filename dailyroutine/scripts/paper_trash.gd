extends StaticBody3D

@export var manager_path: NodePath
@export var room_id := "kitchen"
@export var breakfast_trash := false

var manager: Node
var collected := false

func _ready() -> void:
	add_to_group("interactable")
	manager = get_node_or_null(manager_path)
	if breakfast_trash:
		_set_available(false)
	if manager != null and breakfast_trash and manager.has_signal("breakfast_completed"):
		manager.breakfast_completed.connect(_on_breakfast_completed)

func interact(player_interaction_component: Node = null) -> void:
	if collected:
		return
	if manager != null and not manager.pick_up_loose_trash(room_id):
		if player_interaction_component != null and player_interaction_component.has_method("send_hint"):
			player_interaction_component.send_hint(null, manager.current_objective)
		return
	collected = true
	_set_available(false)
	if player_interaction_component != null and player_interaction_component.has_method("send_hint"):
		player_interaction_component.send_hint(null, "拿到垃圾。")

func _on_breakfast_completed() -> void:
	if not collected:
		_set_available(true)

func set_spawned(active: bool) -> void:
	collected = not active
	_set_available(active)

func _set_available(available: bool) -> void:
	visible = available
	for child in get_children():
		if child is CollisionShape3D:
			child.disabled = not available
