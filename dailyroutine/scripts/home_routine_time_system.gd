class_name HomeRoutineTimeSystem
extends Node

signal time_changed(formatted: String, minutes_since_midnight: float)
signal deadline_reached(deadline_id: String)

const START_MINUTE := 7 * 60
const TRASH_PICKUP_MINUTE := 7 * 60 + 30
const WARNING_MINUTE := 7 * 60 + 25

@export var auto_advance := true

var minutes_since_midnight := float(START_MINUTE)
var paused := false
var _fired_deadlines: Dictionary = {}

func _process(delta: float) -> void:
	if auto_advance:
		advance(delta)

func reset_clock() -> void:
	minutes_since_midnight = float(START_MINUTE)
	paused = false
	_fired_deadlines.clear()
	time_changed.emit(formatted_time(), minutes_since_midnight)

func advance(real_seconds: float) -> void:
	if paused or real_seconds <= 0.0:
		return
	var before := minutes_since_midnight
	minutes_since_midnight = minf(float(TRASH_PICKUP_MINUTE), minutes_since_midnight + real_seconds / 60.0)
	if not is_equal_approx(before, minutes_since_midnight):
		time_changed.emit(formatted_time(), minutes_since_midnight)
		_check_deadline(before, minutes_since_midnight)

func formatted_time() -> String:
	var total := clampi(roundi(minutes_since_midnight), START_MINUTE, TRASH_PICKUP_MINUTE)
	return "%02d:%02d" % [total / 60, total % 60]

func has_reached_warning() -> bool:
	return minutes_since_midnight >= float(WARNING_MINUTE)

func has_reached_deadline() -> bool:
	return minutes_since_midnight >= float(TRASH_PICKUP_MINUTE)

func _check_deadline(before: float, after: float) -> void:
	if before < float(TRASH_PICKUP_MINUTE) and after >= float(TRASH_PICKUP_MINUTE) and not _fired_deadlines.has("trash_pickup"):
		_fired_deadlines["trash_pickup"] = true
		deadline_reached.emit("trash_pickup")
