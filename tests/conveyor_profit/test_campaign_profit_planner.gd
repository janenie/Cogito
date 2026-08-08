extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var campaigns_script: GDScript = load("res://conveyor_profit/scripts/market_campaigns.gd")
	var generator: GDScript = load("res://conveyor_profit/scripts/window_supply_generator.gd")
	var planner: GDScript = load("res://conveyor_profit/scripts/campaign_profit_planner.gd")
	_check(planner != null, "campaign profit planner loads")
	if campaigns_script == null or generator == null or planner == null:
		quit(1)
		return

	var normal_market := {"salad": 1.0, "soup": 1.0, "burger": 1.0, "omelet": 1.0, "sandwich": 1.0}
	var fixture: Array[Dictionary] = [
		{"ingredients": ["egg", "cheese", "bacon", "corn", "lettuce", "tomato", "carrot"], "category_multipliers": normal_market},
		{"ingredients": ["egg", "cheese", "bacon", "corn", "sausage", "mushroom", "onion", "carrot"], "category_multipliers": normal_market},
		{"ingredients": ["egg", "cheese", "bacon", "corn", "sausage", "mushroom", "onion", "pumpkin"], "category_multipliers": normal_market},
	]
	_check(planner.max_profit(fixture) == 47, "normal-market fixture preserves hand-checked optimum")
	_check(planner.is_optimal_choice(fixture, 2, {"corn_bacon_omelet": 2}, "pumpkin_sausage_soup"), "quota-aware optimal choice remains valid")

	for campaign: Dictionary in campaigns_script.CAMPAIGNS:
		var windows: Array[Dictionary] = generator.generate(campaign, 1337)
		var omniscient_profit: int = planner.max_profit(windows)
		var contract_reward := 0
		for contract: Dictionary in campaign.get("contracts", []):
			contract_reward += int(contract.get("reward", 0))
		_check(
			omniscient_profit + contract_reward >= campaigns_script.baseline_profit(campaign),
			"campaign %s omniscient result bounds contract baseline" % campaign["id"],
		)
		_check(omniscient_profit == planner.max_profit(windows), "campaign %s DP result is deterministic" % campaign["id"])
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
