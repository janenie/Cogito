extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var session_script: GDScript = load("res://conveyor_profit/scripts/profit_session.gd")
	_check(session_script != null, "profit session loads")
	if session_script == null:
		quit(1)
		return

	var session: RefCounted = session_script.new(100)
	_check(session.select_ingredient("bread"), "selects bread")
	_check(session.select_ingredient("egg"), "selects egg")
	_check(session.undo() == "egg", "undo returns last ingredient")
	_check(session.select_ingredient("egg"), "egg can be selected again")
	var valid_result: Dictionary = session.make()
	_check(valid_result.get("recipe_id", "") == "egg_toast", "makes exact recipe")
	_check(session.spent == 4, "valid recipe costs are charged")
	_check(session.revenue == 8, "valid recipe earns revenue")
	_check(session.get_profit() == 4, "valid recipe earns net profit")

	session.select_ingredient("bread")
	session.select_ingredient("tomato")
	var invalid_result: Dictionary = session.make()
	_check(invalid_result.get("recipe_id", "") == "", "invalid combination has no recipe")
	_check(session.spent == 7, "invalid combination still costs money")
	_check(session.revenue == 8, "invalid combination earns no revenue")
	_check(session.get_profit() == 1, "invalid combination lowers profit")

	var winning_session: RefCounted = session_script.new(4)
	winning_session.select_ingredient("bread")
	winning_session.select_ingredient("egg")
	winning_session.make()
	_check(winning_session.terminal_status == "success", "target freezes as success")
	_check(winning_session.terminal_reason == "profit_target_reached", "success reason")
	_check(not winning_session.select_ingredient("tomato"), "terminal selection rejected")
	_check(not winning_session.make().get("accepted", true), "terminal make rejected")

	var losing_session: RefCounted = session_script.new(10)
	_check(
		losing_session.evaluate_reachability(["bread", "egg"]) == "failure",
		"unreachable target freezes as failure",
	)
	_check(losing_session.terminal_reason == "profit_target_unreachable", "failure reason")
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
