extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var session_script: GDScript = load("res://conveyor_profit/scripts/profit_session.gd")
	_check(session_script != null, "profit session loads")
	if session_script == null:
		quit(1)
		return

	var session: RefCounted = session_script.new()
	_check(session.select_ingredient("lettuce"), "selects lettuce")
	_check(session.select_ingredient("tomato"), "selects tomato")
	_check(session.select_ingredient("carrot"), "selects carrot")
	_check(session.undo() == "carrot", "undo returns last ingredient")
	_check(session.select_ingredient("carrot"), "carrot can be selected again")
	var first_result: Dictionary = session.make()
	_check(first_result.get("outcome", "") == "accepted", "first valid make is accepted")
	_check(first_result.get("recipe_id", "") == "garden_salad", "makes exact recipe")
	_check(first_result.get("dish_profit", -1) == 4, "valid result reports dish profit")
	_check(session.get_recipe_counts() == {"garden_salad": 1}, "first success is counted")

	for ingredient_id: String in ["lettuce", "tomato", "carrot"]:
		session.select_ingredient(ingredient_id)
	var second_result: Dictionary = session.make()
	_check(second_result.get("outcome", "") == "accepted", "second valid make is accepted")
	_check(session.get_recipe_counts() == {"garden_salad": 2}, "second success reaches quota")
	_check(session.spent == 6, "two valid recipes charge ingredient costs")
	_check(session.revenue == 14, "two valid recipes earn revenue")
	_check(session.get_profit() == 8, "two valid recipes earn net profit")

	for ingredient_id: String in ["lettuce", "tomato", "carrot"]:
		session.select_ingredient(ingredient_id)
	var quota_result: Dictionary = session.make()
	_check(quota_result.get("accepted", false), "quota failure still consumes the make request")
	_check(quota_result.get("outcome", "") == "recipe_limit_exceeded", "third recipe reports quota failure")
	_check(quota_result.get("recipe_id", "") == "garden_salad", "quota receipt names attempted recipe")
	_check(quota_result.get("dish_profit", -1) == 0, "quota failure earns zero dish profit")
	_check(session.spent == 9, "quota failure still charges ingredient costs")
	_check(session.revenue == 14, "quota failure earns no revenue")
	_check(session.get_profit() == 5, "quota failure reduces total profit")
	_check(session.get_recipe_counts() == {"garden_salad": 2}, "quota failure does not increment count")
	var count_snapshot: Dictionary = session.get_recipe_counts()
	count_snapshot["garden_salad"] = 0
	_check(session.get_recipe_counts() == {"garden_salad": 2}, "count snapshots cannot mutate trusted state")

	session.select_ingredient("bread")
	session.select_ingredient("tomato")
	var invalid_result: Dictionary = session.make()
	_check(invalid_result.get("outcome", "") == "invalid_combo", "invalid combination has stable outcome")
	_check(invalid_result.get("recipe_id", "") == "", "invalid combination has no recipe")
	_check(invalid_result.get("dish_profit", -1) == 0, "invalid result reports zero dish profit")
	_check(session.spent == 12, "invalid combination still costs money")
	_check(session.revenue == 14, "invalid combination earns no revenue")
	_check(session.get_profit() == 2, "invalid combination lowers profit")

	var negative_session: RefCounted = session_script.new()
	negative_session.select_ingredient("meat")
	var negative_result: Dictionary = negative_session.make()
	_check(negative_result.get("outcome", "") == "invalid_combo", "single ingredient is invalid")
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
