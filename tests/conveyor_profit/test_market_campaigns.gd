extends SceneTree

const EXPECTED_ROUTES := {
	"A": ["avocado_burger", "avocado_burger", "pumpkin_sausage_soup", "corn_bacon_omelet", "avocado_fish_sandwich", "avocado_fish_sandwich", "avocado_salad", "corn_bacon_omelet", "broccoli_bacon_omelet", "pumpkin_sausage_soup"],
	"B": ["corn_bacon_omelet", "avocado_salad", "pumpkin_sausage_soup", "corn_bacon_omelet", "avocado_burger", "avocado_salad", "avocado_fish_sandwich", "avocado_fish_sandwich", "classic_burger", "pumpkin_sausage_soup"],
	"C": ["avocado_burger", "avocado_burger", "pumpkin_sausage_soup", "avocado_salad", "avocado_fish_sandwich", "avocado_salad", "corn_bacon_omelet", "avocado_fish_sandwich", "corn_bacon_omelet", "classic_burger"],
	"D": ["pumpkin_sausage_soup", "avocado_fish_sandwich", "avocado_burger", "avocado_burger", "classic_burger", "avocado_fish_sandwich", "garden_fish_sandwich", "garden_fish_sandwich", "avocado_salad", "corn_bacon_omelet"],
	"E": ["avocado_burger", "avocado_salad", "avocado_salad", "pumpkin_sausage_soup", "pumpkin_sausage_soup", "avocado_fish_sandwich", "avocado_burger", "corn_bacon_omelet", "avocado_fish_sandwich", "corn_bacon_omelet"],
}
const EXPECTED_BASELINES := {"A": 194, "B": 213, "C": 184, "D": 229, "E": 234}
const EXPECTED_TARGETS := {"A": 175, "B": 192, "C": 166, "D": 207, "E": 211}

var failures: Array[String] = []


func _initialize() -> void:
	var catalog: GDScript = load("res://conveyor_profit/scripts/recipe_catalog.gd")
	var economy: GDScript = load("res://conveyor_profit/scripts/market_economy.gd")
	var campaigns_script: GDScript = load("res://conveyor_profit/scripts/market_campaigns.gd")
	_check(campaigns_script != null, "market campaigns load")
	if campaigns_script == null:
		quit(1)
		return

	var campaigns: Array = campaigns_script.CAMPAIGNS
	_check(campaigns.size() == 5, "five market campaigns exist")
	var seen_ids: Dictionary = {}
	for campaign: Dictionary in campaigns:
		var campaign_id := String(campaign.get("id", ""))
		_check(campaign_id in EXPECTED_ROUTES, "campaign ID is approved")
		_check(not seen_ids.has(campaign_id), "campaign IDs are unique")
		seen_ids[campaign_id] = true
		var rounds: Array = campaign.get("rounds", [])
		_check(rounds.size() == 10, "campaign %s has ten rounds" % campaign_id)
		var actual_route: Array[String] = []
		var counts: Dictionary = {}
		for round_index: int in rounds.size():
			var round_data: Dictionary = rounds[round_index]
			var candidates: Array = round_data.get("candidate_recipe_ids", [])
			_check(candidates.size() == 3, "%s round %d has three candidates" % [campaign_id, round_index + 1])
			_check(_unique_count(candidates) == 3, "%s round %d candidates are unique" % [campaign_id, round_index + 1])
			for recipe_id: Variant in candidates:
				_check(not catalog.recipe_by_id(String(recipe_id)).is_empty(), "%s round %d candidate is public recipe" % [campaign_id, round_index + 1])
			var multipliers: Dictionary = round_data.get("category_multipliers", {})
			_check(multipliers.keys().size() == 5, "%s round %d has five market categories" % [campaign_id, round_index + 1])
			for category: String in economy.CATEGORIES:
				_check(multipliers.has(category), "%s round %d includes %s" % [campaign_id, round_index + 1, category])
				_check(economy.is_valid_multiplier(float(multipliers.get(category, -1.0))), "%s round %d multiplier is approved" % [campaign_id, round_index + 1])
			var signals: Array = round_data.get("signals", [])
			_check(signals.size() == (0 if round_index == 9 else 2), "%s round %d signal count is exact" % [campaign_id, round_index + 1])
			for signal_data: Dictionary in signals:
				_check(String(signal_data.get("category", "")) in economy.CATEGORIES, "signal category is public")
				_check(String(signal_data.get("direction", "")) in ["up", "down"], "signal direction is explicit")
				_check(not String(signal_data.get("text", "")).is_empty(), "signal has player-facing text")
			var baseline_id := String(round_data.get("baseline_recipe_id", ""))
			_check(baseline_id in candidates, "%s round %d baseline is a candidate" % [campaign_id, round_index + 1])
			_check(int(counts.get(baseline_id, 0)) < 2, "%s round %d baseline respects history quota" % [campaign_id, round_index + 1])
			counts[baseline_id] = int(counts.get(baseline_id, 0)) + 1
			actual_route.append(baseline_id)
		_check(actual_route == EXPECTED_ROUTES[campaign_id], "campaign %s route is approved" % campaign_id)
		_check(campaigns_script.baseline_profit(campaign) == EXPECTED_BASELINES[campaign_id], "campaign %s baseline profit is exact" % campaign_id)
		_check(campaigns_script.passing_profit(campaign) == EXPECTED_TARGETS[campaign_id], "campaign %s ninety-percent target is exact" % campaign_id)

	var first_draw: Dictionary = campaigns_script.campaign_for_draw(1337, 0)
	first_draw["rounds"][0]["baseline_recipe_id"] = "mutated"
	_check(campaigns_script.campaign_for_draw(1337, 0)["rounds"][0]["baseline_recipe_id"] != "mutated", "campaign draws are defensive copies")
	var drawn_ids: Array[String] = []
	for draw_index: int in 5:
		drawn_ids.append(String(campaigns_script.campaign_for_draw(1337, draw_index)["id"]))
	drawn_ids.sort()
	_check(drawn_ids == ["A", "B", "C", "D", "E"], "five draws use every campaign once")
	_check(campaigns_script.campaign_for_draw(1337, 5)["id"] == campaigns_script.campaign_for_draw(1337, 0)["id"], "sixth draw resets seeded bag")
	quit(1 if not failures.is_empty() else 0)


func _unique_count(values: Array) -> int:
	var unique: Dictionary = {}
	for value: Variant in values:
		unique[value] = true
	return unique.size()


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
