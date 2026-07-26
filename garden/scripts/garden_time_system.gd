class_name GardenTimeSystem
extends Node

signal time_changed(formatted: String, minutes_since_midnight: float)
signal deadline_reached(deadline_id: String)

const START_MINUTE := 8 * 60
const END_MINUTE := 17 * 60

@export var real_day_seconds := 38.0 * 60.0
@export var auto_advance := true

var minutes_since_midnight := float(START_MINUTE)
var paused := false

var _deadlines := {
	"sunflower_morning": 10 * 60,
	"day_end": END_MINUTE,
}
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
	var scale := float(END_MINUTE - START_MINUTE) / real_day_seconds
	minutes_since_midnight = minf(float(END_MINUTE), minutes_since_midnight + real_seconds * scale)
	if not is_equal_approx(before, minutes_since_midnight):
		time_changed.emit(formatted_time(), minutes_since_midnight)
		_check_deadlines(before, minutes_since_midnight)

func formatted_time() -> String:
	var total := clampi(roundi(minutes_since_midnight), START_MINUTE, END_MINUTE)
	return "%02d:%02d" % [total / 60, total % 60]

func _check_deadlines(before: float, after: float) -> void:
	for deadline_id in _deadlines:
		var minute := float(_deadlines[deadline_id])
		if before < minute and after >= minute and not _fired_deadlines.has(deadline_id):
			_fired_deadlines[deadline_id] = true
			deadline_reached.emit(deadline_id)
