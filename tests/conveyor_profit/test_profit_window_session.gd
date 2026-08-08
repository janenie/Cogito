extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var campaigns_script: GDScript = load("res://conveyor_profit/scripts/market_campaigns.gd")
	var generator: GDScript = load("res://conveyor_profit/scripts/window_supply_generator.gd")
	var session_script: GDScript = load("res://conveyor_profit/scripts/profit_window_session.gd")
	_check(session_script != null, "profit window session loads")
	if campaigns_script == null or generator == null or session_script == null:
		quit(1)
		return

	var campaign: Dictionary = campaigns_script.campaign_by_id("E")
	var windows: Array[Dictionary] = generator.generate(campaign, 1337)
	var session: RefCounted = session_script.new(campaign, windows, 60.0)
	_check(session.baseline_profit == 264, "session stores contract-constrained online baseline")
	_check(session.passing_profit == 238, "threshold is ceil of ninety percent")
	_check(session.get_public_contracts().size() == 3, "three public contracts are active")
	_check(session.omniscient_profit >= session.baseline_profit, "omniscient DP remains developer comparison")
	_check(session.advance_time(59.999).is_empty(), "time before boundary stays in window one")
	_check(session.advance_time(0.001) == [1], "exact boundary enters window two")
	_check(session.record_make("", "invalid_combo", {}) == "invalid_combo", "invalid combo is recorded")
	_check(session.record_make("avocado_salad", "accepted", {}) == "window_locked", "retry is rejected")
	_check(session.completed_windows == 1, "invalid attempt consumes one window")
	_check(session.baseline_windows == 0, "invalid attempt is not a baseline decision")

	var route_session: RefCounted = session_script.new(campaign, windows, 60.0)
	for round_index: int in campaign["rounds"].size():
		var baseline_id := String(campaign["rounds"][round_index]["baseline_recipe_id"])
		_check(route_session.record_make(baseline_id, "accepted", {}) == "accepted", "round %d baseline is accepted" % (round_index + 1))
		route_session.advance_time(60.0)
	_check(route_session.completed_windows == 10, "baseline route completes all windows")
	_check(route_session.baseline_windows == 10, "baseline decisions are tracked")
	_check(route_session.is_time_expired(), "ten windows expire the game clock")
	_check(route_session.contract_adjustment == 30, "baseline route earns all contract rewards")
	for contract: Dictionary in route_session.get_public_contracts():
		_check(contract["status"] == "completed", "baseline completes %s" % contract["id"])
	_check(route_session.get_total_profit(234) == 264, "contract rewards enter net profit")
	route_session.finish(237)
	_check(route_session.terminal_status == "failure", "profit below online target fails")
	_check(route_session.terminal_reason == "efficiency_below_target", "failure reason remains stable")

	var passing: RefCounted = session_script.new(campaign, windows, 60.0)
	passing.advance_time(600.0)
	_check(passing.contract_adjustment == -37, "missed contracts apply every penalty")
	_check(passing.get_total_profit(0) == -37, "contract penalties enter net profit")
	passing.finish(238)
	_check(passing.terminal_status == "success", "profit at online target succeeds")
	_check(passing.get_efficiency_percent(238) == 90, "efficiency uses online baseline")
	var metrics: Dictionary = route_session.get_developer_metrics(237)
	_check(metrics["completed_windows"] == 10, "developer metrics include completion")
	_check(metrics["baseline_windows"] == 10, "developer metrics include baseline decisions")
	_check(metrics["efficiency_percent"] == 90, "developer metrics use online baseline")
	_check(int(metrics["omniscient_profit"]) >= 264, "developer metrics retain omniscient total")

	var guarded: RefCounted = session_script.new(campaign, windows, 60.0)
	guarded.finish(1000)
	_check(not guarded.is_terminal(), "cannot finish before time expires")
	_check(guarded.advance_time(-1.0).is_empty(), "negative delta is ignored")
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
