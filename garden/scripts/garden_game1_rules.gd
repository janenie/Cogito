class_name GardenGame1Rules
extends Node

const START_MINUTE := 8 * 60 + 29
const END_MINUTE := 17 * 60
const RAIN_RESPONSE_GRACE_MINUTES := 0
const LAWN_COUNT_PER_GARDEN := 2
const REAL_DAY_SECONDS := 30.0 * 60.0
const RAIN_START_REAL_SECONDS_MIN := 2.0 * 60.0
const RAIN_START_REAL_SECONDS_MAX := 5.0 * 60.0
const RAIN_DURATION_REAL_SECONDS := 10.0 * 60.0
const RAIN_START_MINUTE_MIN := START_MINUTE + ceili(RAIN_START_REAL_SECONDS_MIN * float(END_MINUTE - START_MINUTE) / REAL_DAY_SECONDS)
const RAIN_START_MINUTE_MAX := START_MINUTE + floori(RAIN_START_REAL_SECONDS_MAX * float(END_MINUTE - START_MINUTE) / REAL_DAY_SECONDS)
const RAIN_DURATION_MINUTES := ceili(RAIN_DURATION_REAL_SECONDS * float(END_MINUTE - START_MINUTE) / REAL_DAY_SECONDS)

var run_seed := 0
var minutes_since_midnight := START_MINUTE
var watering_house_numbers: Array[int] = []
var alarm_house_number := 3
var rain_scheduled := false
var rain_start_minute := START_MINUTE
var rain_end_minute := START_MINUTE
var rain_active := false
var alarm_pressed := false
var day_failed := false
var failure_reason := ""

var _watered_lawns: Dictionary = {}

func start_run(seed: int = 0) -> void:
	run_seed = seed if seed != 0 else randi()
	minutes_since_midnight = START_MINUTE
	rain_scheduled = false
	rain_active = false
	alarm_pressed = false
	day_failed = false
	failure_reason = ""
	_watered_lawns.clear()
	_assign_tasks()

func set_time_minutes(value: int) -> void:
	minutes_since_midnight = clampi(value, START_MINUTE, END_MINUTE)

func advance_to_minutes(value: int) -> void:
	if day_failed:
		return
	var target := clampi(value, START_MINUTE, END_MINUTE)
	var before := minutes_since_midnight
	minutes_since_midnight = target
	if rain_scheduled and before < rain_start_minute and minutes_since_midnight >= rain_start_minute:
		start_rain()
	if rain_scheduled and before < rain_end_minute and minutes_since_midnight >= rain_end_minute:
		end_rain()

func current_weather() -> String:
	return "rain" if rain_active else "sunny"

func start_rain() -> void:
	rain_scheduled = true
	if rain_end_minute <= rain_start_minute:
		rain_end_minute = min(END_MINUTE, rain_start_minute + RAIN_DURATION_MINUTES)
	rain_active = true

func end_rain() -> void:
	rain_active = false
	if not alarm_pressed:
		fail_day("下雨期间没有按下兰花房警报。")

func try_water_lawn(house_number: int, lawn_number: int) -> bool:
	if day_failed:
		return false
	if house_number < 1 or house_number > 3:
		return false
	if lawn_number < 1 or lawn_number > LAWN_COUNT_PER_GARDEN:
		return false
	var key := _lawn_key(house_number, lawn_number)
	if _watered_lawns.has(key):
		return false
	_watered_lawns[key] = true
	if is_watering_finished() and not is_watering_correct():
		fail_day("浇水对象不正确。")
	return true

func try_press_alarm(house_number: int) -> bool:
	if day_failed:
		return false
	if house_number != alarm_house_number:
		fail_day("按错门铃。")
		return false
	if not rain_active:
		fail_day("没有下雨时按了兰花房门铃。")
		return false
	alarm_pressed = true
	return true

func watered_lawn_count() -> int:
	return _watered_lawns.size()

func required_lawn_count() -> int:
	return watering_house_numbers.size() * LAWN_COUNT_PER_GARDEN

func is_watering_complete() -> bool:
	return is_watering_finished() and is_watering_correct()

func is_watering_finished() -> bool:
	return watered_lawn_count() >= required_lawn_count()

func is_watering_correct() -> bool:
	if watered_lawn_count() != required_lawn_count():
		return false
	for house_number in watering_house_numbers:
		for lawn_number in range(1, LAWN_COUNT_PER_GARDEN + 1):
			if not _watered_lawns.has(_lawn_key(house_number, lawn_number)):
				return false
	for key in _watered_lawns.keys():
		var parts := str(key).split(":")
		if parts.size() != 2:
			return false
		if not watering_house_numbers.has(parts[0].to_int()):
			return false
	return true

func is_complete() -> bool:
	return is_watering_complete() and alarm_pressed

func fail_day(reason: String) -> void:
	if day_failed:
		return
	day_failed = true
	failure_reason = reason

func _assign_tasks() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = run_seed
	alarm_house_number = 3
	watering_house_numbers = [1, 2]
	rain_scheduled = true
	rain_start_minute = rng.randi_range(RAIN_START_MINUTE_MIN, RAIN_START_MINUTE_MAX)
	rain_end_minute = min(END_MINUTE, rain_start_minute + RAIN_DURATION_MINUTES)

func _lawn_key(house_number: int, lawn_number: int) -> String:
	return "%d:%d" % [house_number, lawn_number]
