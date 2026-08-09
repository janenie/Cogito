extends SceneTree

const Game1Rules = preload("res://garden/scripts/garden_game1_rules.gd")

var failures := 0

func _init() -> void:
	_test_game_assigns_two_watering_houses_and_orchid_alarm()
	_test_each_watering_house_requires_two_lawns()
	_test_wrong_four_lawns_fail_after_water_is_used()
	_test_rain_always_starts_two_to_five_minutes_after_opening_and_lasts_ten_real_minutes()
	_test_rain_requires_orchid_alarm_before_rain_ends()
	_test_game_completes_after_correct_watering_and_rain_alarm()
	if failures == 0:
		print("Garden game1 tests passed")
		quit(0)
	else:
		push_error("%d Garden game1 test(s) failed" % failures)
		quit(1)

func _test_game_assigns_two_watering_houses_and_orchid_alarm() -> void:
	var rules := Game1Rules.new()
	rules.start_run(12345)
	_assert(rules.watering_house_numbers == [1, 2], "house 1 and house 2 are watering houses")
	_assert(rules.alarm_house_number == 3, "orchid house owns the rain alarm")
	_assert(not rules.watering_house_numbers.has(rules.alarm_house_number), "alarm house is not a watering house")
	for house_number in rules.watering_house_numbers:
		_assert(house_number >= 1 and house_number <= 3, "watering house is valid")

func _test_each_watering_house_requires_two_lawns() -> void:
	var rules := Game1Rules.new()
	rules.start_run(7)
	var first_house: int = rules.watering_house_numbers[0]
	var second_house: int = rules.watering_house_numbers[1]
	_assert(rules.try_water_lawn(first_house, 1), "can water first lawn in watering house")
	_assert(not rules.try_water_lawn(first_house, 1), "same lawn cannot be watered twice")
	_assert(not rules.is_watering_complete(), "one lawn does not complete watering")
	_assert(rules.try_water_lawn(first_house, 2), "can water second lawn in same garden")
	_assert(not rules.is_watering_complete(), "one complete garden is not enough")
	_assert(rules.try_water_lawn(second_house, 1), "can water first lawn in second watering house")
	_assert(rules.try_water_lawn(second_house, 2), "can water second lawn in second watering house")
	_assert(rules.is_watering_complete(), "two watering houses with two lawns each completes watering")
	_assert(not rules.is_complete(), "watering alone does not complete because rain alarm is still required")

func _test_wrong_four_lawns_fail_after_water_is_used() -> void:
	var rules := Game1Rules.new()
	rules.start_run(7)
	_assert(rules.try_water_lawn(1, 1), "can water sunflower lawn")
	_assert(rules.try_water_lawn(1, 2), "can water second sunflower lawn")
	_assert(rules.try_water_lawn(2, 1), "can water hydrangea lawn")
	_assert(rules.try_water_lawn(3, 1), "can spend water on orchid lawn")
	_assert(rules.day_failed, "using all water on the wrong lawns fails")
	_assert(rules.failure_reason.contains("浇水对象不正确"), "wrong watering failure explains the mistake")

func _test_rain_always_starts_two_to_five_minutes_after_opening_and_lasts_ten_real_minutes() -> void:
	_assert(
		is_equal_approx(Game1Rules.RAIN_DURATION_REAL_SECONDS, 10.0 * 60.0),
		"rain duration is ten real minutes",
	)
	for seed in range(1, 101):
		var rules := Game1Rules.new()
		rules.start_run(seed)
		_assert(rules.minutes_since_midnight == 8 * 60 + 29, "game starts at 08:29")
		_assert(rules.rain_scheduled, "rain is scheduled every run")
		_assert(rules.rain_start_minute >= Game1Rules.RAIN_START_MINUTE_MIN, "rain starts no earlier than 2 real minutes after opening")
		_assert(rules.rain_start_minute <= Game1Rules.RAIN_START_MINUTE_MAX, "rain starts no later than 5 real minutes after opening")
		_assert(rules.rain_end_minute == min(Game1Rules.END_MINUTE, rules.rain_start_minute + Game1Rules.RAIN_DURATION_MINUTES), "rain lasts ten real minutes")

func _test_rain_requires_orchid_alarm_before_rain_ends() -> void:
	var rules := Game1Rules.new()
	rules.start_run(99)
	_assert(not rules.has_method("next_weather"), "simplified game has no weather forecast API")
	rules.advance_to_minutes(rules.rain_start_minute)
	_assert(rules.current_weather() == "rain", "scheduled rain starts")
	rules.advance_to_minutes(rules.rain_end_minute - 1)
	_assert(not rules.day_failed, "player has the full rain window to press alarm")
	_assert(not rules.try_press_alarm(1), "non-orchid alarm does not satisfy rain")
	_assert(rules.day_failed, "wrong doorbell fails immediately")

	rules = Game1Rules.new()
	rules.start_run(99)
	_assert(not rules.try_press_alarm(3), "orchid alarm before rain does not satisfy alarm")
	_assert(rules.day_failed, "orchid alarm before rain fails immediately")

	rules = Game1Rules.new()
	rules.start_run(99)
	rules.advance_to_minutes(rules.rain_start_minute)
	_assert(rules.try_press_alarm(3), "orchid alarm can be pressed during rain")
	_assert(rules.alarm_pressed, "orchid alarm press is recorded")

	var failed_rules := Game1Rules.new()
	failed_rules.start_run(99)
	failed_rules.advance_to_minutes(failed_rules.rain_end_minute)
	_assert(failed_rules.day_failed, "rain without orchid alarm fails when rain window ends")

func _test_game_completes_after_correct_watering_and_rain_alarm() -> void:
	var rules := Game1Rules.new()
	rules.start_run(123)
	for house_number in rules.watering_house_numbers:
		_assert(rules.try_water_lawn(house_number, 1), "dry run can water lawn 1")
		_assert(rules.try_water_lawn(house_number, 2), "dry run can water lawn 2")
	_assert(rules.is_watering_complete(), "correct watering completes watering")
	_assert(not rules.is_complete(), "correct watering waits for rain alarm")
	rules.advance_to_minutes(rules.rain_start_minute)
	_assert(rules.try_press_alarm(3), "orchid alarm can be pressed")
	_assert(rules.is_complete(), "correct watering and rain alarm completes game")

func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
