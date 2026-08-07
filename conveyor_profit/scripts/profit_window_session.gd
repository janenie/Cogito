class_name ProfitWindowSession
extends RefCounted

const CAMPAIGNS := preload("res://conveyor_profit/scripts/market_campaigns.gd")
const PLANNER := preload("res://conveyor_profit/scripts/campaign_profit_planner.gd")

var campaign: Dictionary = {}
var windows: Array[Dictionary] = []
var window_seconds: float
var elapsed_seconds: float = 0.0
var current_window_index: int = 0
var dish_made: bool = false
var terminal_status: String = ""
var terminal_reason: String = ""
var passing_profit: int
var baseline_profit: int
var omniscient_profit: int
var completed_windows: int = 0
var baseline_windows: int = 0


func _init(campaign_value: Dictionary, values: Array[Dictionary], seconds: float = 60.0) -> void:
	campaign = campaign_value.duplicate(true)
	for window: Dictionary in values:
		windows.append(window.duplicate(true))
	window_seconds = maxf(seconds, 0.001)
	baseline_profit = CAMPAIGNS.baseline_profit(campaign)
	passing_profit = CAMPAIGNS.passing_profit(campaign)
	omniscient_profit = PLANNER.max_profit(windows)


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


func record_make(recipe_id: String, outcome: String, _counts_before: Dictionary) -> String:
	if is_terminal() or is_time_expired():
		return "game_finished"
	if dish_made:
		return "window_locked"
	dish_made = true
	completed_windows += 1
	if outcome == "accepted":
		var round_data: Dictionary = campaign.get("rounds", [])[current_window_index]
		if recipe_id == String(round_data.get("baseline_recipe_id", "")):
			baseline_windows += 1
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
	if baseline_profit <= 0:
		return 0
	return roundi(float(actual_profit) * 100.0 / float(baseline_profit))


func get_developer_metrics(actual_profit: int) -> Dictionary:
	return {
		"completed_windows": completed_windows,
		"baseline_windows": baseline_windows,
		"total_windows": windows.size(),
		"efficiency_percent": get_efficiency_percent(actual_profit),
		"omniscient_profit": omniscient_profit,
	}


func is_time_expired() -> bool:
	return elapsed_seconds >= float(windows.size()) * window_seconds


func is_terminal() -> bool:
	return not terminal_status.is_empty()
