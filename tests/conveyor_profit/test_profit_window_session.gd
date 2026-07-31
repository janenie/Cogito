extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var session_script: GDScript = load(
		"res://conveyor_profit/scripts/profit_window_session.gd",
	)
	_check(session_script != null, "profit window session loads")
	if session_script == null:
		quit(1)
		return

	var best_profits: Array[int] = [3, 4, 5, 6, 7, 7, 3, 4, 5, 6]
	var session: RefCounted = session_script.new(best_profits, 60.0)
	_check(session.passing_profit == 40, "threshold is ceil of eighty percent")
	_check(session.advance_time(59.999).is_empty(), "time before boundary stays in window one")
	_check(session.current_window_index == 0, "first window remains active")
	_check(session.advance_time(0.001) == [1], "exact boundary enters window two")
	_check(session.current_window_index == 1, "second window becomes active")
	_check(session.record_make("") == "invalid_combo", "invalid combo does not lock")
	_check(not session.dish_made, "invalid combo leaves the window unlocked")
	_check(session.record_make("egg_toast") == "accepted", "first legal dish is accepted")
	_check(session.record_make("egg_toast") == "window_locked", "second legal dish is rejected")
	_check(session.advance_time(120.0) == [2, 3], "large delta crosses boundaries in order")
	_check(not session.dish_made, "new window resets the dish lock")
	_check(session.advance_time(420.0) == [4, 5, 6, 7, 8, 9], "final delta visits remaining windows")
	_check(session.is_time_expired(), "six hundred seconds expires the game clock")
	_check(not session.is_terminal(), "actual profit is required before terminal judgment")
	session.finish(39)
	_check(session.terminal_status == "failure", "profit below threshold fails")
	_check(session.terminal_reason == "efficiency_below_target", "failure reason is stable")

	var passing: RefCounted = session_script.new(best_profits, 60.0)
	passing.advance_time(600.0)
	passing.finish(40)
	_check(passing.terminal_status == "success", "profit at threshold succeeds")
	_check(passing.terminal_reason == "efficiency_target_reached", "success reason is stable")
	_check(passing.get_efficiency_percent(40) == 80, "final efficiency uses theoretical total")

	var guarded_values: Array[int] = [3]
	var guarded: RefCounted = session_script.new(guarded_values, 60.0)
	guarded.finish(100)
	_check(not guarded.is_terminal(), "cannot finish before time expires")
	_check(guarded.advance_time(-1.0).is_empty(), "negative delta is ignored")
	_check(guarded.elapsed_seconds == 0.0, "negative delta does not move the clock")
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
