class_name ProfitWindowSession
extends RefCounted

const TARGET_RATIO: float = 0.8

var best_profits: Array[int] = []
var window_seconds: float
var elapsed_seconds: float = 0.0
var current_window_index: int = 0
var dish_made: bool = false
var terminal_status: String = ""
var terminal_reason: String = ""
var passing_profit: int


func _init(values: Array[int], seconds: float = 60.0) -> void:
	best_profits.assign(values)
	window_seconds = maxf(seconds, 0.001)
	passing_profit = ceili(float(_sum(best_profits)) * TARGET_RATIO)


func advance_time(delta_seconds: float) -> Array[int]:
	var entered_windows: Array[int] = []
	if is_terminal() or is_time_expired() or delta_seconds <= 0.0:
		return entered_windows

	var previous_index := current_window_index
	var total_duration := float(best_profits.size()) * window_seconds
	elapsed_seconds = minf(elapsed_seconds + delta_seconds, total_duration)
	var boundary_index := floori(elapsed_seconds / window_seconds)
	var final_index := best_profits.size() - 1
	var active_index := mini(boundary_index, final_index)
	for index: int in range(previous_index + 1, active_index + 1):
		entered_windows.append(index)
	if not entered_windows.is_empty():
		current_window_index = active_index
		dish_made = false
	if is_time_expired():
		dish_made = false
	return entered_windows


func record_make(recipe_id: String) -> String:
	if is_terminal() or is_time_expired():
		return "game_finished"
	if dish_made:
		return "window_locked"
	if recipe_id.is_empty():
		return "invalid_combo"
	dish_made = true
	return "accepted"


func finish(actual_profit: int) -> void:
	if is_terminal() or not is_time_expired():
		return
	if actual_profit >= passing_profit:
		terminal_status = "success"
		terminal_reason = "efficiency_target_reached"
	else:
		terminal_status = "failure"
		terminal_reason = "efficiency_below_target"


func get_total_remaining_seconds() -> float:
	return maxf(float(best_profits.size()) * window_seconds - elapsed_seconds, 0.0)


func get_window_remaining_seconds() -> float:
	if is_time_expired():
		return 0.0
	var elapsed_in_window := fmod(elapsed_seconds, window_seconds)
	return window_seconds - elapsed_in_window


func get_efficiency_percent(actual_profit: int) -> int:
	var theoretical_total := _sum(best_profits)
	if theoretical_total <= 0:
		return 0
	return roundi(float(actual_profit) * 100.0 / float(theoretical_total))


func is_time_expired() -> bool:
	return elapsed_seconds >= float(best_profits.size()) * window_seconds


func is_terminal() -> bool:
	return not terminal_status.is_empty()


static func _sum(values: Array[int]) -> int:
	var total := 0
	for value: int in values:
		total += value
	return total
