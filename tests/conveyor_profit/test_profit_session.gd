extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var session_script: GDScript = load("res://conveyor_profit/scripts/profit_session.gd")
	_check(session_script != null, "profit session loads")
	if session_script == null:
		quit(1)
		return

	var session: RefCounted = session_script.new()
	_check(session.select_ingredient("bread"), "selects bread")
	_check(session.select_ingredient("egg"), "selects egg")
	_check(session.undo() == "egg", "undo returns last ingredient")
	_check(session.select_ingredient("egg"), "egg can be selected again")
	var valid_result: Dictionary = session.make()
	_check(valid_result.get("recipe_id", "") == "egg_toast", "makes exact recipe")
	_check(valid_result.get("dish_profit", -1) == 4, "valid result reports dish profit")
	_check(session.spent == 4, "valid recipe costs are charged")
	_check(session.revenue == 8, "valid recipe earns revenue")
	_check(session.get_profit() == 4, "valid recipe earns net profit")

	session.select_ingredient("bread")
	session.select_ingredient("tomato")
	var invalid_result: Dictionary = session.make()
	_check(invalid_result.get("recipe_id", "") == "", "invalid combination has no recipe")
	_check(invalid_result.get("dish_profit", -1) == 0, "invalid result reports zero dish profit")
	_check(session.spent == 7, "invalid combination still costs money")
	_check(session.revenue == 8, "invalid combination earns no revenue")
	_check(session.get_profit() == 1, "invalid combination lowers profit")

	var negative_session: RefCounted = session_script.new()
	negative_session.select_ingredient("meat")
	var negative_result: Dictionary = negative_session.make()
	_check(negative_result.get("recipe_id", "") == "", "single meat is not a recipe")
	_check(negative_session.get_profit() == -5, "invalid combination can make profit negative")
	_check(not negative_session.is_terminal(), "economics do not decide the terminal state")

	session.freeze("success", "efficiency_target_reached")
	_check(session.terminal_status == "success", "explicit freeze stores status")
	_check(session.terminal_reason == "efficiency_target_reached", "explicit freeze stores reason")
	_check(not session.select_ingredient("tomato"), "frozen selection rejected")
	_check(not session.make().get("accepted", true), "frozen make rejected")
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
