class_name ConveyorGameplay
extends Node

signal game_finished(outcome: String, reason: String)

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")
const PROFIT_SESSION := preload("res://conveyor_profit/scripts/profit_session.gd")
const PROFIT_WINDOW_SESSION := preload("res://conveyor_profit/scripts/profit_window_session.gd")
const WINDOW_SUPPLY_GENERATOR := preload("res://conveyor_profit/scripts/window_supply_generator.gd")
const MARKET_CAMPAIGNS := preload("res://conveyor_profit/scripts/market_campaigns.gd")
const ROUND_SEED_PARSER := preload(
	"res://addons/cogito/AIPlay/ai_play_round_seed.gd"
)
const MAX_TRAY_INGREDIENTS: int = 5
const DRAW_INDEX_ARG_PREFIX: String = "--conveyor-draw-index="

const MODEL_PATHS := {
	"lettuce": "res://conveyor_profit/assets/kenney_food_kit/models/lettuce.glb",
	"tomato": "res://conveyor_profit/assets/kenney_food_kit/models/tomato.glb",
	"carrot": "res://conveyor_profit/assets/kenney_food_kit/models/carrot.glb",
	"avocado": "res://conveyor_profit/assets/kenney_food_kit/models/avocado.glb",
	"sausage": "res://conveyor_profit/assets/kenney_food_kit/models/sausage.glb",
	"bread": "res://conveyor_profit/assets/kenney_food_kit/models/bread.glb",
	"egg": "res://conveyor_profit/assets/kenney_food_kit/models/egg.glb",
	"mushroom": "res://conveyor_profit/assets/kenney_food_kit/models/mushroom.glb",
	"onion": "res://conveyor_profit/assets/kenney_food_kit/models/onion.glb",
	"pumpkin": "res://conveyor_profit/assets/kenney_food_kit/models/pumpkin.glb",
	"cheese": "res://conveyor_profit/assets/kenney_food_kit/models/cheese.glb",
	"bacon": "res://conveyor_profit/assets/kenney_food_kit/models/bacon.glb",
	"broccoli": "res://conveyor_profit/assets/kenney_food_kit/models/broccoli.glb",
	"corn": "res://conveyor_profit/assets/kenney_food_kit/models/corn.glb",
	"fish": "res://conveyor_profit/assets/kenney_food_kit/models/fish.glb",
	"meat": "res://conveyor_profit/assets/kenney_food_kit/models/meat.glb",
}

@export var supply_seed: int = 1337
@export_range(1, 100, 1) var window_count: int = 10
@export_range(0.01, 3600.0, 0.01) var window_seconds: float = 60.0

var session: RefCounted
var window_session: RefCounted
var window_supplies: Array[Dictionary] = []
var campaign: Dictionary = {}
var pending_supply: Array[String] = []
var _ingredient_path: Path3D
var _tray_visuals: Node3D
var _tray_label: Label3D
var _total_time_label: Label
var _window_label: Label
var _dish_label: Label
var _profit_label: Label
var _status_label: Label
var _demand_label: Label
var _signal_one_label: Label
var _signal_two_label: Label
var _contracts_label: Label
var _menu_board: RecipeMenuPager
var _make_button: StaticBody3D
var _next_selection_id: int = 1
var _semantic_random := RandomNumberGenerator.new()
var _ai_control_active: bool = false
var _window_refill_pool: Array[String] = []
var _refill_index: int = 0
var _last_receipt: Dictionary = {}


func initialize(
	ingredient_path: Path3D,
	tray_visuals: Node3D,
	tray_label: Label3D,
	total_time_label: Label,
	window_label: Label,
	dish_label: Label,
	profit_label: Label,
	status_label: Label,
	demand_label: Label,
	signal_one_label: Label,
	signal_two_label: Label,
	contracts_label: Label,
	menu_board: RecipeMenuPager,
	make_button: StaticBody3D,
) -> void:
	_ingredient_path = ingredient_path
	_tray_visuals = tray_visuals
	_tray_label = tray_label
	_total_time_label = total_time_label
	_window_label = window_label
	_dish_label = dish_label
	_profit_label = profit_label
	_status_label = status_label
	_demand_label = demand_label
	_signal_one_label = signal_one_label
	_signal_two_label = signal_two_label
	_contracts_label = contracts_label
	_menu_board = menu_board
	_make_button = make_button
	session = PROFIT_SESSION.new()
	var requested_round_seed: Dictionary = ROUND_SEED_PARSER.parse(
		OS.get_cmdline_user_args()
	)
	if not requested_round_seed["valid"]:
		push_error("Invalid --ai-play-round-seed argument")
	elif requested_round_seed["provided"]:
		supply_seed = ROUND_SEED_PARSER.runtime_seed(
			int(requested_round_seed["value"])
		)
	_semantic_random.seed = supply_seed
	var draw_index := parse_conveyor_draw_index(OS.get_cmdline_user_args())
	if draw_index < 0:
		draw_index = MARKET_CAMPAIGNS.next_manual_draw_index()
	campaign = MARKET_CAMPAIGNS.campaign_for_draw(supply_seed, draw_index)
	window_supplies = WINDOW_SUPPLY_GENERATOR.generate(campaign, supply_seed)
	window_count = window_supplies.size()
	window_session = PROFIT_WINDOW_SESSION.new(campaign, window_supplies, window_seconds)
	_make_button.activated.connect(_on_action_requested)
	_load_window(0)
	_update_public_display("从传送带选择食材 / CHOOSE INGREDIENTS FROM THE BELT")


func _process(delta: float) -> void:
	if not _ai_control_active:
		advance_time(delta)


func set_ai_control_active(value: bool) -> void:
	_ai_control_active = value


static func parse_conveyor_draw_index(user_args: Array) -> int:
	for raw_arg: Variant in user_args:
		var argument := String(raw_arg)
		if not argument.begins_with(DRAW_INDEX_ARG_PREFIX):
			continue
		var value_text := argument.trim_prefix(DRAW_INDEX_ARG_PREFIX)
		if value_text.is_empty() or not value_text.is_valid_int():
			return -1
		var value := value_text.to_int()
		if value < 0 or str(value) != value_text:
			return -1
		return value
	return -1


static func parse_round_seed(user_args: Array) -> int:
	var parsed: Dictionary = ROUND_SEED_PARSER.parse(user_args)
	if not parsed["valid"] or not parsed["provided"]:
		return -1
	return int(parsed["value"])


func get_profit() -> int:
	if session == null:
		return 0
	if window_session == null:
		return session.get_profit()
	return window_session.get_total_profit(session.get_profit())


func get_selected_count() -> int:
	return session.selected_ingredients.size() if session != null else 0


func get_remaining_count() -> int:
	if session == null:
		return 0
	var count: int = pending_supply.size() + session.selected_ingredients.size()
	for follower: Node in _ingredient_path.get_children():
		if follower.visible and follower.get_meta("available", false):
			count += 1
	return count


func get_public_state() -> Dictionary:
	if window_session == null or session == null:
		return {}
	return {
		"total_time": _format_seconds(window_session.get_total_remaining_seconds()),
		"window": "%d / %d" % [window_session.current_window_index + 1, window_count],
		"window_time": _format_seconds(window_session.get_window_remaining_seconds()),
		"dish": "1 / 1" if window_session.dish_made else "0 / 1",
		"net_profit": get_profit(),
		"tray": session.selected_ingredients.duplicate(),
		"last_receipt": _last_receipt.duplicate(true),
		"market": _get_public_market(),
		"contracts": window_session.get_public_contracts(),
		"finished": window_session.is_terminal(),
	}


func _get_public_market() -> Dictionary:
	var window: Dictionary = window_supplies[window_session.current_window_index]
	var signal_texts: Array[String] = []
	for signal_data: Dictionary in window.get("signals", []):
		signal_texts.append(String(signal_data.get("text", "")))
	return {
		"category_multipliers": window.get("category_multipliers", {}).duplicate(),
		"signals": signal_texts,
	}


func advance_time(delta_seconds: float) -> void:
	if window_session == null or window_session.is_terminal():
		return
	var was_expired: bool = window_session.is_time_expired()
	for entered_index: int in window_session.advance_time(delta_seconds):
		_expire_current_window()
		_load_window(entered_index)
	if not was_expired and window_session.is_time_expired():
		_expire_current_window()
		_finish_game()
	else:
		_update_public_display(_status_label.text)


func request_make() -> Dictionary:
	if window_session.is_terminal() or window_session.is_time_expired():
		return {"outcome": "game_finished"}
	if window_session.dish_made:
		return {"outcome": "window_locked"}
	var counts_before: Dictionary = session.get_recipe_counts()
	var market: Dictionary = window_supplies[window_session.current_window_index]
	var result: Dictionary = session.make(market.get("category_multipliers", {}))
	if not result.get("accepted", false):
		return {"outcome": "tray_empty"}
	_clear_tray_visuals()
	var recipe_id := String(result.get("recipe_id", ""))
	var make_outcome := String(result.get("outcome", "invalid_combo"))
	var outcome: String = window_session.record_make(
		recipe_id,
		make_outcome,
		counts_before,
	)
	if outcome in ["accepted", "invalid_combo", "recipe_limit_exceeded"]:
		_set_input_enabled(false)
		var message := "WINDOW COMPLETE · INVALID COMBO · COST CHARGED"
		if outcome == "accepted":
			message = "WINDOW COMPLETE · SOLD %s" % recipe_id.replace("_", " ").to_upper()
		elif outcome == "recipe_limit_exceeded":
			message = "WINDOW COMPLETE · RECIPE LIMIT EXCEEDED · COST CHARGED"
		_last_receipt = {
			"outcome": outcome,
			"recipe_id": recipe_id,
			"profit": get_profit(),
		}
		_update_public_display(message)
	return {"outcome": outcome, "recipe_id": recipe_id, "profit": get_profit()}


func request_wait_next_window() -> Dictionary:
	if window_session.is_terminal() or window_session.is_time_expired():
		return {"outcome": "game_finished"}
	if not window_session.dish_made:
		return {"outcome": "window_not_complete"}
	var previous_index: int = window_session.current_window_index
	advance_time(window_session.get_window_remaining_seconds())
	if window_session.is_terminal():
		return {"outcome": "game_finished"}
	return {
		"outcome": (
			"window_advanced"
			if window_session.current_window_index == previous_index + 1
			else "game_finished"
		),
	}


func request_select_ingredient(ingredient_id: String, camera: Camera3D) -> Dictionary:
	if ingredient_id not in CATALOG.INGREDIENT_IDS:
		return {"outcome": "invalid_ingredient"}
	if window_session.is_terminal() or window_session.is_time_expired():
		return {"outcome": "game_finished"}
	if window_session.dish_made:
		return {"outcome": "window_locked"}
	if session.selected_ingredients.size() >= MAX_TRAY_INGREDIENTS:
		return {"outcome": "tray_full"}
	var matches: Array[PathFollow3D] = []
	for follower_node: Node in _ingredient_path.get_children():
		var follower := follower_node as PathFollow3D
		if (
			follower.get_meta("ingredient_id", "") == ingredient_id
			and follower.get_meta("available", false)
			and _is_in_camera(follower, camera)
		):
			var interactable := follower.get_node("IngredientPreview/Interactable") as Area3D
			if interactable.enabled:
				matches.append(follower)
	if matches.is_empty():
		return {"outcome": "ingredient_not_available"}
	var chosen := matches[_semantic_random.randi_range(0, matches.size() - 1)]
	return _select_by_selection_id(int(chosen.get_meta("selection_id", -1)))


func _fill_follower(follower: PathFollow3D) -> void:
	var preview := follower.get_node("IngredientPreview") as Node3D
	var previous_model := preview.get_node_or_null("FoodModel")
	if previous_model != null:
		preview.remove_child(previous_model)
		previous_model.free()
	var interactable := preview.get_node("Interactable") as Area3D
	if pending_supply.is_empty():
		follower.visible = false
		follower.set_meta("available", false)
		interactable.enabled = false
		interactable.selection_id = -1
		return

	var ingredient_id: String = pending_supply.pop_front()
	var selection_id := _next_selection_id
	_next_selection_id += 1
	follower.visible = true
	follower.set_meta("available", true)
	follower.set_meta("ingredient_id", ingredient_id)
	follower.set_meta("selection_id", selection_id)
	var label := preview.get_node("CostLabel") as Label3D
	label.text = "$%d  %s" % [CATALOG.ingredient_cost(ingredient_id), ingredient_id.to_upper()]
	interactable.enabled = true
	interactable.selection_id = selection_id
	if not interactable.select_requested.is_connected(_on_select_requested):
		interactable.select_requested.connect(_on_select_requested)
	var food_scene := load(String(MODEL_PATHS[ingredient_id])) as PackedScene
	var food := food_scene.instantiate() as Node3D
	food.name = "FoodModel"
	food.position.y = 0.16
	food.scale = Vector3.ONE * 1.35
	preview.add_child(food)


func _on_select_requested(selection_id: int) -> void:
	_select_by_selection_id(selection_id)


func _select_by_selection_id(selection_id: int) -> Dictionary:
	if session == null or window_session == null:
		return {"outcome": "game_finished"}
	if session.is_terminal() or window_session.is_terminal() or window_session.is_time_expired():
		return {"outcome": "game_finished"}
	if window_session.dish_made:
		return {"outcome": "window_locked"}
	if session.selected_ingredients.size() >= MAX_TRAY_INGREDIENTS:
		return {"outcome": "tray_full"}
	for follower: Node in _ingredient_path.get_children():
		if (
			follower.get_meta("selection_id", -1) != selection_id
			or not follower.visible
			or not follower.get_meta("available", false)
		):
			continue
		var ingredient_id := String(follower.get_meta("ingredient_id", ""))
		if not session.select_ingredient(ingredient_id):
			return {"outcome": "game_finished"}
		_add_tray_visual(ingredient_id)
		_queue_replacement()
		_fill_follower(follower as PathFollow3D)
		_update_public_display("Selected %s" % ingredient_id.to_upper())
		return {"outcome": "selected", "ingredient": ingredient_id}
	return {"outcome": "ingredient_not_available"}


func _is_in_camera(follower: Node3D, camera: Camera3D) -> bool:
	if not follower.visible or camera == null or camera.cull_mask == 0:
		return false
	if not camera.is_position_in_frustum(follower.global_position):
		return false
	var screen_point := camera.unproject_position(follower.global_position)
	var viewport_size := camera.get_viewport().get_visible_rect().size
	return Rect2(Vector2.ZERO, viewport_size).has_point(screen_point)


func _on_action_requested(action: String) -> void:
	match action:
		"make":
			_make_dish()


func _make_dish() -> void:
	var result := request_make()
	if result["outcome"] == "tray_empty":
		_update_public_display("Tray is empty")
		return
	if result["outcome"] == "window_locked":
		_update_public_display("Dish already made; wait for next window")
		return
	var recipe_id := String(result.get("recipe_id", ""))
	if result["outcome"] == "accepted":
		_update_public_display(
			"WINDOW COMPLETE · SOLD %s" % recipe_id.replace("_", " ").to_upper()
		)


func _add_tray_visual(ingredient_id: String) -> void:
	var food_scene := load(String(MODEL_PATHS[ingredient_id])) as PackedScene
	var food := food_scene.instantiate() as Node3D
	food.name = "Selected%02d_%s" % [_tray_visuals.get_child_count() + 1, ingredient_id]
	food.position = Vector3((_tray_visuals.get_child_count() - 1.5) * 0.45, 0.1, 0)
	food.scale = Vector3.ONE * 0.8
	_tray_visuals.add_child(food)


func _update_public_display(message: String) -> void:
	var selected_text := " + ".join(session.selected_ingredients).to_upper()
	_tray_label.text = "TRAY  EMPTY" if selected_text.is_empty() else "TRAY  %s" % selected_text
	_total_time_label.text = "TOTAL TIME  %s" % _format_seconds(
		window_session.get_total_remaining_seconds(),
	)
	_window_label.text = "WINDOW  %d / %d  ·  %s" % [
		window_session.current_window_index + 1,
		window_count,
		_format_seconds(window_session.get_window_remaining_seconds()),
	]
	_dish_label.text = "DISH  %s" % ("1 / 1" if window_session.dish_made else "0 / 1")
	_profit_label.text = "NET PROFIT  $%d" % get_profit()
	_status_label.text = message
	_update_market_display()
	_update_contract_display()


func _set_input_enabled(value: bool) -> void:
	_make_button.enabled = value
	for follower: Node in _ingredient_path.get_children():
		var interactable := follower.get_node("IngredientPreview/Interactable") as Area3D
		interactable.enabled = value and follower.visible


func _load_window(index: int) -> void:
	_last_receipt = {}
	_window_refill_pool.assign(window_supplies[index]["ingredients"])
	pending_supply.assign(_window_refill_pool)
	_refill_index = 0
	for follower: Node in _ingredient_path.get_children():
		_fill_follower(follower as PathFollow3D)
	_menu_board.set_category_multipliers(window_supplies[index]["category_multipliers"])
	_update_market_display()
	_set_input_enabled(true)


func _update_market_display() -> void:
	if window_session == null or window_supplies.is_empty():
		return
	var market := _get_public_market()
	var multipliers: Dictionary = market["category_multipliers"]
	_demand_label.text = (
		"当前需求 / CURRENT DEMAND\n"
		+ "沙拉 ×%.2f  汤类 ×%.2f  汉堡 ×%.2f\n煎蛋卷 ×%.2f  三明治 ×%.2f"
		% [
			float(multipliers.get("salad", 1.0)),
			float(multipliers.get("soup", 1.0)),
			float(multipliers.get("burger", 1.0)),
			float(multipliers.get("omelet", 1.0)),
			float(multipliers.get("sandwich", 1.0)),
		]
	)
	var signals: Array = market["signals"]
	_signal_one_label.text = "下一轮线索 1：%s" % (signals[0] if signals.size() > 0 else "无")
	_signal_two_label.text = "下一轮线索 2：%s" % (signals[1] if signals.size() > 1 else "无")


func _update_contract_display() -> void:
	if _contracts_label == null or window_session == null:
		return
	var lines: Array[String] = ["分类合同 / CATEGORY CONTRACTS"]
	for contract: Dictionary in window_session.get_public_contracts():
		var deadline := int(contract["deadline_window"])
		var requirement := String(contract["requirement"]).split(" / ")[0]
		requirement = requirement.trim_prefix("第 %d 窗结束前" % deadline)
		lines.append(
			"[%s] W%d · %s · +$%d / -$%d"
			% [
				String(contract["status"]).to_upper(),
				deadline,
				requirement,
				int(contract["reward"]),
				int(contract["penalty"]),
			]
		)
	_contracts_label.text = "\n".join(lines)


func _expire_current_window() -> void:
	pending_supply.clear()
	_window_refill_pool.clear()
	session.discard_selected_ingredients()
	_clear_tray_visuals()
	for follower: Node in _ingredient_path.get_children():
		_clear_follower(follower as PathFollow3D)


func _clear_follower(follower: PathFollow3D) -> void:
	var interactable := follower.get_node("IngredientPreview/Interactable") as Area3D
	follower.visible = false
	follower.set_meta("available", false)
	follower.set_meta("ingredient_id", "")
	follower.set_meta("selection_id", -1)
	interactable.enabled = false
	interactable.selection_id = -1


func _queue_replacement() -> void:
	if _window_refill_pool.is_empty():
		return
	pending_supply.append(_window_refill_pool[_refill_index % _window_refill_pool.size()])
	_refill_index += 1


func _clear_tray_visuals() -> void:
	for child: Node in _tray_visuals.get_children():
		child.queue_free()


func _finish_game() -> void:
	var final_profit := get_profit()
	window_session.finish(final_profit)
	session.freeze(window_session.terminal_status, window_session.terminal_reason)
	_set_input_enabled(false)
	var metrics: Dictionary = window_session.get_developer_metrics(final_profit)
	print(
		"CONVEYOR_PROFIT_RESULT baseline_windows=%d completed_windows=%d total_windows=%d efficiency=%d"
		% [
			metrics["baseline_windows"],
			metrics["completed_windows"],
			metrics["total_windows"],
			metrics["efficiency_percent"],
		]
	)
	_update_public_display(
		"EFFICIENCY  %d%%  ·  %s" % [
			window_session.get_efficiency_percent(final_profit),
			window_session.terminal_status.to_upper(),
		],
	)
	game_finished.emit(window_session.terminal_status, window_session.terminal_reason)


static func _format_seconds(seconds: float) -> String:
	var whole_seconds := maxi(ceili(seconds), 0)
	return "%02d:%02d" % [whole_seconds / 60, whole_seconds % 60]
