# Conveyor Profit Timed Strategy Windows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a ten-minute conveyor game scored against 80% of the best single dish in each one-minute window, with an allowlisted MCP scenario that plays through English ingredient-name actions instead of simulated mouse control.

**Architecture:** Keep economics in `ProfitSession`, time-window state and the hidden threshold in a new `ProfitWindowSession`, and deterministic per-window supply in a focused generator. `ConveyorGameplay` exposes shared selection/undo/make methods to human clicks and a semantic AI adapter. The bridge remains protocol version 3; Python and Godot independently validate scenario-gated actions and results, while a conveyor observer publishes screenshots and HUD-level state but no structured available-ingredient inventory.

**Tech Stack:** Godot 4.7, typed GDScript, Godot headless script tests, Python 3, pytest, FastMCP, WebSocket bridge protocol 3.

## Global Constraints

- AI Play remains explicitly enabled only by `-- --ai-play`; the selector is `--ai-play-scenario=conveyor_profit`.
- Godot connects only to `127.0.0.1`; Escape, disconnect, invalid data, API failure, and teardown stop actions and release simulated input.
- The game lasts exactly `10 × 60` seconds and permits at most one legal dish per window.
- Success is `actual_profit >= ceil(theoretical_best_total * 0.8)`; the old `$100` target is removed.
- Runtime model input never exposes structured available supply, candidate recipes, best dish, future windows, seed, theoretical total, or passing amount.
- `game_script/`, `code_read/`, tests, specs, plans, scene paths, node paths, and internal class names never enter briefing or observation payloads.
- Python and GDScript both enforce fresh `observation_id`, exact fields, and batches of one to three actions.
- Do not run a real external MCP/model acceptance test without renewed approval for screenshots, tokens, cost, and local trajectories.
- Do not modify `addons/input_helper/` or `addons/quick_audio/`.

---

### Task 1: Deterministic one-to-two-recipe window supplies

**Files:**
- Create: `conveyor_profit/scripts/window_supply_generator.gd`
- Create through Godot import: `conveyor_profit/scripts/window_supply_generator.gd.uid`
- Create: `tests/conveyor_profit/test_window_supply_generator.gd`
- Create through Godot import: `tests/conveyor_profit/test_window_supply_generator.gd.uid`
- Modify: `conveyor_profit/scripts/recipe_catalog.gd`

**Interfaces:**
- Consumes: `RecipeCatalog.RECIPES`, `RecipeCatalog.INGREDIENT_IDS`.
- Produces: `RecipeCatalog.attainable_single_dishes(ingredient_ids: Array) -> Array[Dictionary]`.
- Produces: `WindowSupplyGenerator.generate(seed_value: int, window_count: int = 10) -> Array[Dictionary]`, each entry having exactly `ingredients: Array[String]` and `best_profit: int`.

- [ ] **Step 1: Write the failing generator test**

```gdscript
extends SceneTree

const Catalog := preload("res://conveyor_profit/scripts/recipe_catalog.gd")
const Generator := preload("res://conveyor_profit/scripts/window_supply_generator.gd")

func _initialize() -> void:
	var dishes := Catalog.attainable_single_dishes(["bread", "egg", "cheese"])
	assert(dishes.map(func(recipe: Dictionary) -> String: return recipe["id"]) == [
		"egg_toast", "cheese_toast",
	])
	var first := Generator.generate(1337, 10)
	assert(first == Generator.generate(1337, 10))
	assert(first.size() == 10)
	for window: Dictionary in first:
		var candidates := Catalog.attainable_single_dishes(window["ingredients"])
		assert(candidates.size() in [1, 2])
		var profits := candidates.map(func(recipe: Dictionary) -> int: return recipe["profit"])
		assert(window["best_profit"] == profits.max())
	quit(0)
```

- [ ] **Step 2: Run it and confirm the missing file/API failure**

```bash
godot --headless --path . --log-file /private/tmp/conveyor-window-supply-red.log --script tests/conveyor_profit/test_window_supply_generator.gd
```

Expected: non-zero because the generator and catalog method do not exist.

- [ ] **Step 3: Implement exact single-dish enumeration**

Add to `recipe_catalog.gd` and refactor `max_attainable_profit()` to reuse `_ingredient_counts()`:

```gdscript
static func attainable_single_dishes(ingredient_ids: Array) -> Array[Dictionary]:
	var available_counts := _ingredient_counts(ingredient_ids)
	var result: Array[Dictionary] = []
	for recipe: Dictionary in RECIPES:
		if _can_consume(available_counts, _ingredient_counts(recipe["ingredients"])):
			result.append(recipe.duplicate(true))
	return result


static func _ingredient_counts(ingredient_ids: Array) -> Array[int]:
	var counts: Array[int] = []
	counts.resize(INGREDIENT_IDS.size())
	counts.fill(0)
	for ingredient_id: Variant in ingredient_ids:
		var index := INGREDIENT_IDS.find(String(ingredient_id))
		if index >= 0:
			counts[index] += 1
	return counts
```

- [ ] **Step 4: Implement bounded deterministic generation**

Create `window_supply_generator.gd`:

```gdscript
class_name WindowSupplyGenerator
extends RefCounted

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")

static func generate(seed_value: int, window_count: int = 10) -> Array[Dictionary]:
	var random := RandomNumberGenerator.new()
	random.seed = seed_value
	var windows: Array[Dictionary] = []
	while windows.size() < window_count:
		var ingredients := _candidate_ingredients(random)
		var recipes := CATALOG.attainable_single_dishes(ingredients)
		if recipes.size() not in [1, 2]:
			continue
		_shuffle(ingredients, random)
		var best_profit := 0
		for recipe: Dictionary in recipes:
			best_profit = maxi(best_profit, int(recipe["profit"]))
		windows.append({"ingredients": ingredients, "best_profit": best_profit})
	return windows
```

`_candidate_ingredients()` chooses one recipe and optionally a distinct second recipe, merges one required copy of each ingredient, and relies on the public enumerator to reject accidental third recipes. `_shuffle()` is Fisher–Yates using only the passed RNG.

- [ ] **Step 5: Run focused regressions**

```bash
godot --headless --path . --log-file /private/tmp/conveyor-window-supply-green.log --script tests/conveyor_profit/test_window_supply_generator.gd
godot --headless --path . --log-file /private/tmp/conveyor-recipe-regression.log --script tests/conveyor_profit/test_recipe_catalog.gd
```

Expected: both exit `0`.

- [ ] **Step 6: Commit**

```bash
git add conveyor_profit/scripts/recipe_catalog.gd conveyor_profit/scripts/window_supply_generator.gd conveyor_profit/scripts/window_supply_generator.gd.uid tests/conveyor_profit/test_window_supply_generator.gd tests/conveyor_profit/test_window_supply_generator.gd.uid
git commit -m "feat(conveyor-profit): generate strategy windows"
```

---

### Task 2: Timer, window lock, and efficiency judgment

**Files:**
- Create: `conveyor_profit/scripts/profit_window_session.gd`
- Create through Godot import: `conveyor_profit/scripts/profit_window_session.gd.uid`
- Create: `tests/conveyor_profit/test_profit_window_session.gd`
- Create through Godot import: `tests/conveyor_profit/test_profit_window_session.gd.uid`
- Modify: `conveyor_profit/scripts/profit_session.gd`
- Modify: `tests/conveyor_profit/test_profit_session.gd`

**Interfaces:**
- Produces: economics-only `ProfitSession.new()` and `freeze(status: String, reason: String)`.
- Produces: `ProfitWindowSession.new(best_profits: Array[int], window_seconds: float = 60.0)`, `advance_time(delta_seconds: float) -> Array[int]`, `record_make(recipe_id: String) -> String`, `finish(actual_profit: int)`, and remaining-time/efficiency getters.

- [ ] **Step 1: Write failing economics and boundary tests**

Replace target assertions with:

```gdscript
var session := ProfitSession.new()
session.select_ingredient("bread")
session.select_ingredient("egg")
assert(session.make() == {"accepted": true, "recipe_id": "egg_toast", "profit": 4})
session.select_ingredient("meat")
var invalid := session.make()
assert(invalid["recipe_id"] == "" and invalid["profit"] == -1)
assert(not session.is_terminal())
```

Create window assertions:

```gdscript
var windows := ProfitWindowSession.new([3, 4, 5, 6, 7, 7, 3, 4, 5, 6], 60.0)
assert(windows.advance_time(59.999).is_empty())
assert(windows.advance_time(0.001) == [1])
assert(windows.record_make("egg_toast") == "accepted")
assert(windows.record_make("egg_toast") == "window_locked")
assert(windows.advance_time(120.0) == [2, 3])
windows.advance_time(420.0)
assert(windows.is_time_expired())
assert(not windows.is_terminal())
windows.finish(39)
assert(windows.is_terminal())
assert(windows.passing_profit == 40)
```

Add separate `finish(39)` and `finish(40)` cases for `failure/efficiency_below_target` and `success/efficiency_target_reached`.

- [ ] **Step 2: Run both tests and confirm intended failures**

```bash
godot --headless --path . --log-file /private/tmp/conveyor-profit-session-red.log --script tests/conveyor_profit/test_profit_session.gd
godot --headless --path . --log-file /private/tmp/conveyor-window-session-red.log --script tests/conveyor_profit/test_profit_window_session.gd
```

- [ ] **Step 3: Make `ProfitSession` economics-only**

Remove `target_profit`, reachability evaluation, and amount-based terminal transitions. Keep settlement unchanged and add:

```gdscript
func freeze(status: String, reason: String) -> void:
	if is_terminal():
		return
	terminal_status = status
	terminal_reason = reason
```

- [ ] **Step 4: Implement `ProfitWindowSession`**

```gdscript
class_name ProfitWindowSession
extends RefCounted

const TARGET_RATIO := 0.8

var best_profits: Array[int]
var window_seconds: float
var elapsed_seconds := 0.0
var current_window_index := 0
var dish_made := false
var terminal_status := ""
var terminal_reason := ""
var passing_profit: int

func _init(values: Array[int], seconds: float = 60.0) -> void:
	best_profits = values.duplicate()
	window_seconds = seconds
	passing_profit = ceili(float(_sum(best_profits)) * TARGET_RATIO)

func record_make(recipe_id: String) -> String:
	if is_terminal() or is_time_expired(): return "game_finished"
	if dish_made: return "window_locked"
	if recipe_id.is_empty(): return "invalid_combo"
	dish_made = true
	return "accepted"

func finish(actual_profit: int) -> void:
	if is_terminal() or not is_time_expired(): return
	terminal_status = "success" if actual_profit >= passing_profit else "failure"
	terminal_reason = "efficiency_target_reached" if terminal_status == "success" else "efficiency_below_target"
```

`advance_time()` clamps negative delta to zero, returns every newly entered window index in order,
resets `dish_made` at each boundary, and marks the clock expired at total duration. It does not choose
an outcome until `finish(actual_profit)` receives the final economic result. Add
`get_total_remaining_seconds()`, `get_window_remaining_seconds()`,
`get_efficiency_percent(actual_profit)`, `is_time_expired()`, and `is_terminal()`.

- [ ] **Step 5: Run both tests and commit**

Expected: both commands from Step 2 exit `0`.

```bash
git add conveyor_profit/scripts/profit_session.gd conveyor_profit/scripts/profit_window_session.gd conveyor_profit/scripts/profit_window_session.gd.uid tests/conveyor_profit/test_profit_session.gd tests/conveyor_profit/test_profit_window_session.gd tests/conveyor_profit/test_profit_window_session.gd.uid
git commit -m "feat(conveyor-profit): score timed windows"
```

---

### Task 3: Scene window lifecycle and timed HUD

**Files:**
- Modify: `conveyor_profit/scripts/conveyor_gameplay.gd`
- Modify: `conveyor_profit/scripts/conveyor_environment.gd`
- Modify: `conveyor_profit/scenes/conveyor_profit_environment.tscn`
- Modify: `tests/conveyor_profit/test_conveyor_gameplay.gd`
- Modify: `tests/conveyor_profit/test_conveyor_profit_scene.gd`

**Interfaces:**
- Produces: `advance_time(delta_seconds: float)`, `get_public_state() -> Dictionary`, `request_undo() -> Dictionary`, `request_make() -> Dictionary`, and `game_finished(outcome: String, reason: String)`.

- [ ] **Step 1: Add failing lifecycle and HUD tests**

Require `HUD/TotalTimeLabel`, `HUD/WindowLabel`, `HUD/DishLabel`, `HUD/ProfitLabel`, and `HUD/StatusLabel`. With `window_seconds = 0.1`, assert:

```gdscript
gameplay.advance_time(0.1)
assert(gameplay.window_session.current_window_index == 1)
assert(gameplay.get_selected_count() == 0)
assert(gameplay.get_public_state().keys() == [
	"total_time", "window", "window_time", "dish", "net_profit", "tray", "finished",
])
```

Make one legal recipe, assert selection/undo/make lock, advance a boundary, and assert the next window restores actions.

- [ ] **Step 2: Run tests and confirm missing lifecycle failures**

```bash
godot --headless --path . --log-file /private/tmp/conveyor-gameplay-red.log --script tests/conveyor_profit/test_conveyor_gameplay.gd
godot --headless --path . --log-file /private/tmp/conveyor-scene-red.log --script tests/conveyor_profit/test_conveyor_profit_scene.gd
```

- [ ] **Step 3: Add the HUD and window replacement**

Runtime labels are exactly:

```text
TOTAL TIME  10:00
WINDOW  1 / 10  ·  01:00
DISH  0 / 1
NET PROFIT  $0
```

Add exports `window_count: int = 10` and `window_seconds: float = 60.0`. Generate all supplies once, load only the active window, call `advance_time(delta)` from `_process(delta)`, expire old tray/supply without charging, and fill slots from only the new window.

- [ ] **Step 4: Route buttons through public gameplay methods**

```gdscript
func request_undo() -> Dictionary:
	if window_session.is_terminal(): return {"outcome": "game_finished"}
	if window_session.dish_made: return {"outcome": "window_locked"}
	var ingredient_id: String = session.undo()
	if ingredient_id.is_empty(): return {"outcome": "tray_empty"}
	pending_supply.push_front(ingredient_id)
	_remove_last_tray_visual()
	return {"outcome": "undone"}

func request_make() -> Dictionary:
	if window_session.is_terminal(): return {"outcome": "game_finished"}
	if window_session.dish_made: return {"outcome": "window_locked"}
	var result: Dictionary = session.make()
	if not result["accepted"]: return {"outcome": "tray_empty"}
	var outcome := window_session.record_make(result["recipe_id"])
	_clear_tray_visuals()
	if outcome == "accepted": _set_input_enabled(false)
	return {"outcome": outcome, "recipe_id": result["recipe_id"]}
```

Invalid combos consume ingredients and cost, clear the tray, and leave the window unlocked.

- [ ] **Step 5: Freeze and signal at 600 seconds**

Call `window_session.finish(session.get_profit())`, then
`session.freeze(window_session.terminal_status, window_session.terminal_reason)`, disable all entry
points, show `EFFICIENCY <percent>% · SUCCESS|FAILURE`, and emit:

```gdscript
signal game_finished(outcome: String, reason: String)
```

Only `success/efficiency_target_reached` and `failure/efficiency_below_target` are legal.

- [ ] **Step 6: Run focused regressions and commit**

```bash
godot --headless --path . --log-file /private/tmp/conveyor-gameplay-green.log --script tests/conveyor_profit/test_conveyor_gameplay.gd
godot --headless --path . --log-file /private/tmp/conveyor-scene-green.log --script tests/conveyor_profit/test_conveyor_profit_scene.gd
godot --headless --path . --log-file /private/tmp/conveyor-profit-regression.log --script tests/conveyor_profit/test_profit_session.gd
git add conveyor_profit/scripts/conveyor_gameplay.gd conveyor_profit/scripts/conveyor_environment.gd conveyor_profit/scenes/conveyor_profit_environment.tscn tests/conveyor_profit/test_conveyor_gameplay.gd tests/conveyor_profit/test_conveyor_profit_scene.gd
git commit -m "feat(conveyor-profit): run ten timed windows"
```

---

### Task 4: Shared English-name ingredient selection

**Files:**
- Modify: `conveyor_profit/scripts/conveyor_gameplay.gd`
- Modify: `conveyor_profit/scripts/ingredient_interactable.gd`
- Modify: `tests/conveyor_profit/test_conveyor_gameplay.gd`

**Interfaces:**
- Produces: `request_select_ingredient(ingredient_id: String, camera: Camera3D) -> Dictionary`.
- Human click and semantic selection both call `_select_by_selection_id(selection_id: int) -> Dictionary`.

- [ ] **Step 1: Add failing semantic-selection tests**

```gdscript
assert(gameplay.request_select_ingredient("tomato", camera) == {
	"outcome": "selected", "ingredient": "tomato",
})
assert(gameplay.request_select_ingredient("potato", camera)["outcome"] == "invalid_ingredient")
camera.cull_mask = 0
assert(gameplay.request_select_ingredient("tomato", camera)["outcome"] == "ingredient_not_available")
```

Create two visible tomatoes and assert restarting with the same `supply_seed` chooses the same internal selection while the public result never contains its ID.

- [ ] **Step 2: Run and confirm the missing API failure**

```bash
godot --headless --path . --log-file /private/tmp/conveyor-semantic-red.log --script tests/conveyor_profit/test_conveyor_gameplay.gd
```

- [ ] **Step 3: Extract the single mutation path**

```gdscript
func _on_select_requested(selection_id: int) -> void:
	_select_by_selection_id(selection_id)

func _select_by_selection_id(selection_id: int) -> Dictionary:
	if window_session.is_terminal(): return {"outcome": "game_finished"}
	if window_session.dish_made: return {"outcome": "window_locked"}
	for follower: Node in _ingredient_path.get_children():
		if not follower.visible or not follower.get_meta("available", false):
			continue
		if follower.get_meta("selection_id", -1) != selection_id:
			continue
		var ingredient_id := String(follower.get_meta("ingredient_id", ""))
		if not session.select_ingredient(ingredient_id):
			return {"outcome": "game_finished"}
		_add_tray_visual(ingredient_id)
		_fill_follower(follower as PathFollow3D)
		_update_public_display("Selected %s" % ingredient_id.to_upper())
		return {"outcome": "selected", "ingredient": ingredient_id}
	return {"outcome": "ingredient_not_available"}
```

No AI-only code mutates `selected_ingredients` directly.

- [ ] **Step 4: Implement current-camera filtering and seeded choice**

```gdscript
func _is_in_camera(follower: Node3D, camera: Camera3D) -> bool:
	if not follower.visible or camera == null or not camera.is_position_in_frustum(follower.global_position):
		return false
	var point := camera.unproject_position(follower.global_position)
	return Rect2(Vector2.ZERO, camera.get_viewport().get_visible_rect().size).has_point(point)
```

Filter active, selectable, same-ID followers. Choose with a dedicated RNG seeded from `supply_seed`. Do not raycast for occlusion and never return coordinates or selection IDs.

- [ ] **Step 5: Run twice and commit**

Run the Step 2 command twice; both must exit `0`.

```bash
git add conveyor_profit/scripts/conveyor_gameplay.gd conveyor_profit/scripts/ingredient_interactable.gd tests/conveyor_profit/test_conveyor_gameplay.gd
git commit -m "feat(conveyor-profit): select visible food by name"
```

---

### Task 5: Scenario-gated Python MCP schema and briefing

**Files:**
- Create: `ai_play/src/ai_play/conveyor_profit_briefing.py`
- Modify: `ai_play/src/ai_play/action_schema.py`
- Modify: `ai_play/src/ai_play/game_session.py`
- Modify: `ai_play/src/ai_play/observation_schema.py`
- Modify: `ai_play/src/ai_play/scenarios.py`
- Modify: `ai_play/tests/test_action_schema.py`
- Modify: `ai_play/tests/test_game_session.py`
- Modify: `ai_play/tests/test_observation_schema.py`
- Modify: `ai_play/tests/test_briefing.py`
- Modify: `ai_play/tests/test_scenarios.py`

**Interfaces:**
- Produces scenario-gated `select_ingredient`, `undo`, and `make` validation.
- Produces optional public `conveyor` observation state and bounded semantic results.
- Registers the `conveyor_profit` briefing, request limit, and terminal outcomes.

- [ ] **Step 1: Write failing action-schema tests**

```python
def test_conveyor_actions_are_scenario_gated():
    actions = [
        {"type": "select_ingredient", "ingredient": "tomato"},
        {"type": "make"},
    ]
    assert validate_action_batch(actions, set(), False, "conveyor_profit") == actions
    with pytest.raises(ActionValidationError, match="scenario"):
        validate_action_batch(actions, set(), False, "find_contract")


@pytest.mark.parametrize("ingredient", ["potato", "Tomato", "../tomato", 7])
def test_conveyor_ingredient_ids_are_exact(ingredient):
    with pytest.raises(ActionValidationError, match="ingredient"):
        validate_action_batch(
            [{"type": "select_ingredient", "ingredient": ingredient}],
            set(), False, "conveyor_profit",
        )
```

Assert `make` must be last; selections and undo may precede it.

- [ ] **Step 2: Write failing DTO/session/briefing tests**

Use this exact optional observation:

```python
"conveyor": {
    "total_time": "09:42",
    "window": "1 / 10",
    "window_time": "00:42",
    "dish": "0 / 1",
    "net_profit": 0,
    "tray": ["bread", "egg"],
    "finished": False,
}
```

Reject any `ingredients`, `candidate_recipes`, `best_profit`, `future_supply`, `seed`, or `passing_profit`. Accept only bounded semantic results:

```python
{"status": "completed", "type": "select_ingredient", "outcome": "selected", "ingredient": "tomato"}
{"status": "completed", "type": "make", "outcome": "window_locked"}
```

Assert `GameSession` passes its attached scenario into validation and never dispatches conveyor actions for another scenario. Assert briefing returns no image and no internal/hidden facts.

- [ ] **Step 3: Run focused tests and confirm failures**

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_action_schema.py ai_play/tests/test_observation_schema.py ai_play/tests/test_game_session.py ai_play/tests/test_briefing.py ai_play/tests/test_scenarios.py -q
```

- [ ] **Step 4: Implement scenario-aware action validation**

```python
CONVEYOR_INGREDIENT_IDS = frozenset({
    "lettuce", "tomato", "bread", "egg", "mushroom", "cheese", "fish", "meat",
})
CONVEYOR_ACTIONS = frozenset({"select_ingredient", "undo", "make"})


def validate_action_batch(
    actions, available_interactions, interface_open, scenario_id=None,
):
    if not isinstance(actions, list) or not 1 <= len(actions) <= 3:
        raise ActionValidationError("actions must contain 1..3 entries")
    available = set(available_interactions)
    for index, action in enumerate(actions):
        _validate_action(action, available, interface_open, scenario_id)
        action_type = action["type"]
        if action_type in CONVEYOR_ACTIONS and scenario_id != "conveyor_profit":
            raise ActionValidationError("action is not allowed for this scenario")
        if action_type in {"interact", "enter_digits", "close_ui", "make"}:
            if index != len(actions) - 1:
                raise ActionValidationError("context-changing action must be last")
    if any(action["type"] == "probe_interaction" for action in actions) and len(actions) != 1:
        raise ActionValidationError("probe_interaction must be the only action")
    return actions
```

Only `conveyor_profit` accepts these actions; exact fields are enforced and `make` is final. Pass `self._scenario_id` from `GameSession._execute_act()`.

- [ ] **Step 5: Add bounded observation and result variants**

Add optional `conveyor`, exact fields, `MM:SS` validation, signed safe `net_profit`, at most four allowlisted tray IDs, and boolean `finished`. Add only:

```python
CONVEYOR_OUTCOMES = {
    "selected", "undone", "accepted", "invalid_combo",
    "ingredient_not_available", "window_locked", "game_finished", "tray_empty",
}
```

Only `select_ingredient` results carry exact `ingredient`. Preserve every existing scenario's DTO shape.

- [ ] **Step 6: Register briefing and terminal outcomes**

`load_conveyor_profit_briefing()` returns `(briefing, None)`, explains public arithmetic and semantic controls, and contains no solution. Register request limit `300` and:

```python
frozenset({
    ("success", "efficiency_target_reached"),
    ("failure", "efficiency_below_target"),
    ("failure", "max_requests"),
})
```

- [ ] **Step 7: Run focused and full Python suites, then commit**

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_action_schema.py ai_play/tests/test_observation_schema.py ai_play/tests/test_game_session.py ai_play/tests/test_briefing.py ai_play/tests/test_scenarios.py -q
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
git add ai_play/src/ai_play/conveyor_profit_briefing.py ai_play/src/ai_play/action_schema.py ai_play/src/ai_play/game_session.py ai_play/src/ai_play/observation_schema.py ai_play/src/ai_play/scenarios.py ai_play/tests/test_action_schema.py ai_play/tests/test_game_session.py ai_play/tests/test_observation_schema.py ai_play/tests/test_briefing.py ai_play/tests/test_scenarios.py
git commit -m "feat(ai-play): validate conveyor semantic actions"
```

---

### Task 6: Godot semantic executor, observer, terminal adapter, and scene

**Files:**
- Create: `conveyor_profit/scripts/conveyor_ai_action_provider.gd`
- Create: `conveyor_profit/scripts/conveyor_ai_observer.gd`
- Create: `conveyor_profit/scripts/conveyor_ai_terminal.gd`
- Create corresponding `.uid` files through Godot import
- Modify: `addons/cogito/AIPlay/ai_play_executor.gd`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `conveyor_profit/scenes/conveyor_profit_preview.tscn`
- Modify: `tests/ai_play/test_ai_play_executor.gd`
- Modify: `tests/ai_play/test_ai_play_controller.gd`
- Create: `tests/conveyor_profit/test_conveyor_ai_play.gd`
- Create through Godot import: `tests/conveyor_profit/test_conveyor_ai_play.gd.uid`

**Interfaces:**
- Produces: `ConveyorAIActionProvider.execute_semantic_action(action: Dictionary) -> Dictionary`.
- Produces: `ConveyorAIObserver.capture_observation(last_results: Array) -> Dictionary`.
- Produces: `ConveyorAITerminal.game_finished(outcome: String, reason: String)`.

- [ ] **Step 1: Write failing executor and integration tests**

In executor tests:

```gdscript
executor.active_scenario_id = "conveyor_profit"
executor.semantic_action_provider = fake_provider
assert(executor.validate_batch([
	{"type": "select_ingredient", "ingredient": "tomato"},
	{"type": "make"},
], {}) == {"valid": true})
executor.active_scenario_id = "find_contract"
assert(not executor.validate_action({"type": "undo"}, {}).get("valid", false))
```

In `test_conveyor_ai_play.gd`:

```gdscript
var observation := observer.capture_observation([])
assert(observation.has("conveyor"))
assert(not observation["conveyor"].has("ingredients"))
var result := provider.execute_semantic_action({
	"type": "select_ingredient", "ingredient": "tomato",
})
assert(result.keys() == ["status", "type", "outcome", "ingredient"])
```

Also assert teardown rejects later actions, terminal signals propagate, and no `--ai-play` means disabled controller.

- [ ] **Step 2: Run and confirm missing adapter failures**

```bash
godot --headless --path . --log-file /private/tmp/conveyor-ai-executor-red.log --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --log-file /private/tmp/conveyor-ai-controller-red.log --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --log-file /private/tmp/conveyor-ai-integration-red.log --script tests/conveyor_profit/test_conveyor_ai_play.gd
```

- [ ] **Step 3: Add scenario-aware dispatch to `AIPlayExecutor`**

Add `active_scenario_id: String` and `semantic_action_provider: Node`. Mirror Python exact fields, IDs, scenario gate, and final-`make` rule. Dispatch:

```gdscript
"select_ingredient", "undo", "make":
	if semantic_action_provider == null:
		return {"status": "error", "error": "semantic action provider is unavailable"}
	return semantic_action_provider.execute_semantic_action(action)
```

`AIPlayController` assigns active scenario and an optional `SemanticActionProvider` child, allowlists conveyor terminal results, and immediately recaptures after semantic actions.

- [ ] **Step 4: Implement the provider without parallel state**

```gdscript
func execute_semantic_action(action: Dictionary) -> Dictionary:
	if not _active:
		return {"status": "completed", "type": action["type"], "outcome": "game_finished"}
	var result: Dictionary
	match action["type"]:
		"select_ingredient":
			result = gameplay.request_select_ingredient(action["ingredient"], camera)
		"undo":
			result = gameplay.request_undo()
		"make":
			result = gameplay.request_make()
	var public := {
		"status": "completed", "type": action["type"], "outcome": result["outcome"],
	}
	if action["type"] == "select_ingredient":
		public["ingredient"] = action["ingredient"]
	return public
```

Clear `_active` on teardown/stop. Never read hidden supply or theoretical profit.

- [ ] **Step 5: Implement HUD-only screenshot observation**

Follow existing JPEG encoding/sanitization. Use the fixed camera transform for required player fields, empty available interactions, existing exact bindings, and `gameplay.get_public_state()` as `conveyor`. The only ingredient IDs are already-selected tray values visible on the HUD.

- [ ] **Step 6: Implement terminal adapter and scene wiring**

`ConveyorAITerminal` exports `scenario_id = "conveyor_profit"` and forwards `gameplay.game_finished`. Add an `AIPlayController` subtree to `conveyor_profit_preview.tscn` with `auto_start = false`, exact host `127.0.0.1`, custom observer, generic executor, provider, bridge, timer, and terminal. References point to `Environment/Gameplay` and `Camera`. Normal preview remains unchanged without AI flags.

- [ ] **Step 7: Run focused tests/import and commit**

```bash
godot --headless --path . --log-file /private/tmp/conveyor-ai-executor-green.log --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --log-file /private/tmp/conveyor-ai-controller-green.log --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --log-file /private/tmp/conveyor-ai-integration-green.log --script tests/conveyor_profit/test_conveyor_ai_play.gd
godot --headless --path . --log-file /private/tmp/conveyor-import.log --editor --quit
git add addons/cogito/AIPlay/ai_play_executor.gd addons/cogito/AIPlay/ai_play_controller.gd conveyor_profit/scripts/conveyor_ai_action_provider.gd conveyor_profit/scripts/conveyor_ai_action_provider.gd.uid conveyor_profit/scripts/conveyor_ai_observer.gd conveyor_profit/scripts/conveyor_ai_observer.gd.uid conveyor_profit/scripts/conveyor_ai_terminal.gd conveyor_profit/scripts/conveyor_ai_terminal.gd.uid conveyor_profit/scenes/conveyor_profit_preview.tscn tests/ai_play/test_ai_play_executor.gd tests/ai_play/test_ai_play_controller.gd tests/conveyor_profit/test_conveyor_ai_play.gd tests/conveyor_profit/test_conveyor_ai_play.gd.uid
git commit -m "feat(conveyor-profit): add MCP semantic play"
```

---

### Task 7: Documentation and complete regression

**Files:**
- Modify: `conveyor_profit/README.md`
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `game_script/conveyor_profit.md`

**Interfaces:**
- Documents exact launch commands, public DTOs, timer/score rules, and privacy boundary.
- `game_script/` remains developer-only and has no runtime loader/import.

- [ ] **Step 1: Document normal and AI launches**

```bash
godot --path . conveyor_profit/scenes/conveyor_profit_preview.tscn
godot --path . conveyor_profit/scenes/conveyor_profit_preview.tscn -- --ai-play --ai-play-scenario=conveyor_profit
```

Document all eight English IDs, three action shapes, one-to-three batches, final `make`, public outcomes, ten windows, one legal dish per window, and 80% judgment. State that `observe` does not return the available ingredient inventory.

- [ ] **Step 2: Reconcile Wiki and developer notes**

Make `docs/wiki/ai-play/system-guide.md` match implemented field/outcome names. Update `game_script/conveyor_profit.md` as non-runtime notes only; add no runtime imports from it.

- [ ] **Step 3: Run every conveyor test**

```bash
for test_file in tests/conveyor_profit/test_*.gd; do
  godot --headless --path . --log-file "/private/tmp/$(basename "$test_file" .gd).log" --script "$test_file" || exit 1
done
```

- [ ] **Step 4: Run affected AI Play regression**

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
godot --headless --path . --log-file /private/tmp/ai-play-executor-final.log --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --log-file /private/tmp/ai-play-observer-final.log --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --log-file /private/tmp/ai-play-controller-final.log --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --log-file /private/tmp/ai-play-probe-final.log --script tests/ai_play/test_ai_play_interaction_probe.gd
bash tests/test_ai_play_secret_scan.sh
```

- [ ] **Step 5: Run final import and whitespace checks**

```bash
godot --headless --path . --log-file /private/tmp/conveyor-final-import.log --editor --quit
git diff --check
git status --short
```

Expected: tests/import exit `0`, `git diff --check` is silent, and status lists only Task 7 docs.

- [ ] **Step 6: Commit and verify clean state**

```bash
git add conveyor_profit/README.md ai_play/README.md docs/wiki/ai-play/system-guide.md game_script/conveyor_profit.md
git commit -m "docs(conveyor-profit): document timed MCP play"
git status --short --branch
git log -7 --oneline
```

Expected: clean branch with the seven implementation commits after the design commit.
