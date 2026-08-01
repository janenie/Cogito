class_name ProfitWindowSession
extends RefCounted

const TARGET_RATIO: float = 0.8
const PLANNER := preload("res://conveyor_profit/scripts/campaign_profit_planner.gd")

var windows: Array[Dictionary] = []
var window_seconds: float
var elapsed_seconds: float = 0.0
var current_window_index: int = 0
var dish_made: bool = false
var terminal_status: String = ""
var terminal_reason: String = ""
var passing_profit: int
var theoretical_profit: int
var completed_windows: int = 0
var optimal_windows: int = 0


func _init(values: Array[Dictionary], seconds: float = 60.0) -> void:
	for window: Dictionary in values:
		windows.append(window.duplicate(true))
	window_seconds = maxf(seconds, 0.001)
	theoretical_profit = PLANNER.max_profit(windows)
	passing_profit = ceili(float(theoretical_profit) * TARGET_RATIO)


func advance_time(delta_seconds: float) -> Array[int]:
	var entered_windows: Array[int] = []
	if is_terminal() or is_time_expired() or delta_seconds <= 0.0:
		return entered_windows

	var previous_index := current_window_index
	var total_duration := float(windows.size()) * window_seconds
	elapsed_seconds = minf(elapsed_seconds + delta_seconds, total_duration)
	var boundary_index := floori(elapsed_seconds / window_seconds)
	var final_index := windows.size() - 1
	var active_index := mini(boundary_index, final_index)
	for index: int in range(previous_index + 1, active_index + 1):
		entered_windows.append(index)
	if not entered_windows.is_empty():
		current_window_index = active_index
		dish_made = false
	if is_time_expired():
		dish_made = false
	return entered_windows


func record_make(recipe_id: String, outcome: String, counts_before: Dictionary) -> String:
	if is_terminal() or is_time_expired():
		return "game_finished"
	if dish_made:
		return "window_locked"
	dish_made = true
	completed_windows += 1
	if outcome == "accepted" and PLANNER.is_optimal_choice(
		windows,
		current_window_index,
		counts_before,
		recipe_id,
	):
		optimal_windows += 1
	return outcome


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
	return maxf(float(windows.size()) * window_seconds - elapsed_seconds, 0.0)


func get_window_remaining_seconds() -> float:
	if is_time_expired():
		return 0.0
	var elapsed_in_window := fmod(elapsed_seconds, window_seconds)
	return window_seconds - elapsed_in_window


func get_efficiency_percent(actual_profit: int) -> int:
	if theoretical_profit <= 0:
		return 0
	return roundi(float(actual_profit) * 100.0 / float(theoretical_profit))


func get_developer_metrics(actual_profit: int) -> Dictionary:
	return {
		"completed_windows": completed_windows,
		"optimal_windows": optimal_windows,
		"total_windows": windows.size(),
		"efficiency_percent": get_efficiency_percent(actual_profit),
	}


func is_time_expired() -> bool:
	return elapsed_seconds >= float(windows.size()) * window_seconds


func is_terminal() -> bool:
	return not terminal_status.is_empty()
