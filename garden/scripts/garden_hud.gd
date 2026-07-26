class_name GardenHUD
extends CanvasLayer

@export var time_system_path: NodePath
@export var game_manager_path: NodePath
@export var watering_can_path: NodePath

var time_system: Node
var game_manager: Node
var watering_can: Node

func _ready() -> void:
	time_system = get_node_or_null(time_system_path)
	game_manager = get_node_or_null(game_manager_path)
	watering_can = get_node_or_null(watering_can_path)
	if time_system != null:
		time_system.time_changed.connect(_on_time_changed)
		_on_time_changed(time_system.formatted_time(), time_system.minutes_since_midnight)
	if game_manager != null:
		game_manager.objective_changed.connect(_on_objective_changed)
		game_manager.day_failure.connect(_on_day_failed)
		_on_objective_changed(game_manager.current_objective)
	if watering_can != null:
		watering_can.capacity_changed.connect(_on_capacity_changed)
		_on_capacity_changed(watering_can.capacity_current, watering_can.capacity_max)

func show_condition(value: String) -> void:
	%ConditionLabel.text = "Condition: %s" % value.capitalize()

func _on_time_changed(formatted: String, _minutes: float) -> void:
	%ClockLabel.text = formatted

func _on_objective_changed(text: String) -> void:
	%ObjectiveLabel.text = text

func _on_capacity_changed(current: float, maximum: float) -> void:
	%CanLabel.text = "Water: %d / %d" % [roundi(current), roundi(maximum)]

func _on_day_failed(reason: String) -> void:
	%FailurePanel.visible = true
	%FailureReason.text = reason
