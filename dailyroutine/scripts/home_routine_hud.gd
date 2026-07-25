class_name HomeRoutineHUD
extends CanvasLayer

@export var time_system_path: NodePath
@export var manager_path: NodePath

var time_system: Node
var manager: Node

func _ready() -> void:
	time_system = get_node_or_null(time_system_path)
	manager = get_node_or_null(manager_path)
	if time_system != null:
		time_system.time_changed.connect(_on_time_changed)
		_on_time_changed(time_system.formatted_time(), time_system.minutes_since_midnight)
	if manager != null:
		manager.objective_changed.connect(_on_objective_changed)
		manager.trash_count_changed.connect(_on_trash_count_changed)
		manager.held_item_changed.connect(_on_held_item_changed)
		manager.routine_failed_changed.connect(_on_routine_failed)
		manager.routine_completed.connect(_on_routine_completed)
		_on_objective_changed(manager.current_objective)
		_on_trash_count_changed(manager.collected_trash_count, manager.required_trash_count)
		_on_held_item_changed(manager.held_item_label())

func _on_time_changed(formatted: String, _minutes: float) -> void:
	%ClockLabel.text = formatted

func _on_objective_changed(text: String) -> void:
	%ObjectiveLabel.text = text

func _on_trash_count_changed(current: int, required: int) -> void:
	%TrashLabel.text = "总垃圾：%d，已扔：%d" % [required, current]

func _on_held_item_changed(label: String) -> void:
	%HoldingLabel.text = "手上：%s" % label

func _on_routine_failed(reason: String) -> void:
	%FailurePanel.visible = true
	%FailureReason.text = reason

func _on_routine_completed() -> void:
	%SuccessPanel.visible = true
