class_name GardenPlant
extends Node3D

signal condition_changed(value: String)
signal died

@export var moisture := 35.0
@export var health := 100.0
@export var safe_min := 40.0
@export var safe_max := 70.0
@export var dry_rate := 0.02
@export var damage_rate := 2.0

var is_dead := false
var completed_windows: Dictionary = {}

var _initial_moisture := 35.0
var _initial_health := 100.0
var _last_condition := ""

func _ready() -> void:
	_initial_moisture = moisture
	_initial_health = health
	_last_condition = condition()
	add_to_group("garden_plants")

func apply_water(amount: float) -> void:
	if is_dead or amount <= 0.0:
		return
	moisture = clampf(moisture + amount, 0.0, 100.0)
	_emit_condition_if_changed()

func simulate(seconds: float) -> void:
	if is_dead or seconds <= 0.0:
		return
	if health <= 0.0:
		_die()
		return
	moisture = maxf(0.0, moisture - dry_rate * seconds)
	if moisture < safe_min or moisture > safe_max:
		health = maxf(0.0, health - damage_rate * seconds)
	if health <= 0.0:
		_die()
	_emit_condition_if_changed()

func condition() -> String:
	if moisture < safe_min:
		return "dry"
	if moisture > safe_max:
		return "too_wet"
	return "healthy"

func mark_window(window_id: String) -> void:
	if window_id != "":
		completed_windows[window_id] = true

func reset_plant() -> void:
	moisture = _initial_moisture
	health = _initial_health
	is_dead = false
	completed_windows.clear()
	_last_condition = condition()
	condition_changed.emit(_last_condition)

func _die() -> void:
	if is_dead:
		return
	is_dead = true
	health = 0.0
	died.emit()

func _emit_condition_if_changed() -> void:
	var current := condition()
	if current != _last_condition:
		_last_condition = current
		condition_changed.emit(current)
