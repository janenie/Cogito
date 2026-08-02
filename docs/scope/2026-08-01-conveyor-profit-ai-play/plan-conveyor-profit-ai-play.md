# Conveyor Profit Complete AI Play Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the sixteen-plate, two-choice profit game and make its standalone scene playable by the session-AWM Codex orchestrator.

**Architecture:** Keep recipe enumeration, constrained supply generation, window scoring, and scene coordination separate. Add one scenario monitor as the trusted adapter between the generic AI Play controller and `ConveyorGameplay`, plus a fixed-camera observer that publishes only the existing HUD-level conveyor DTO. Extend protocol-v4 action allowlists symmetrically without exposing hidden supply or optimal-profit data.

**Tech Stack:** Godot 4.7/GDScript, Python 3.12, pytest, stdio/WebSocket/Streamable HTTP MCP, Codex orchestrator and session-scoped AWM.

---

### Task 1: Generate sixteen real plates with exactly two unequal-profit recipes

**Files:**
- Modify: `conveyor_profit/scripts/window_supply_generator.gd`
- Modify: `tests/conveyor_profit/test_window_supply_generator.gd`
- Modify: `tests/conveyor_profit/test_conveyor_profit_scene.gd`

- [ ] **Step 1: Tighten the generator tests**

Replace the current `1 or 2` assertions with exact constraints:

```gdscript
for window: Dictionary in first:
	var ingredients: Array = window["ingredients"]
	_check(ingredients.size() == 16, "window contains sixteen real plates")
	_check(
		ingredients.all(func(value: Variant) -> bool:
			return value is String and value in catalog.INGREDIENT_IDS
		),
		"every plate contains a catalog ingredient",
	)
	var candidates: Array[Dictionary] = catalog.attainable_single_dishes(ingredients)
	_check(candidates.size() == 2, "window has exactly two feasible recipes")
	_check(
		int(candidates[0]["profit"]) != int(candidates[1]["profit"]),
		"candidate recipe profits differ",
	)
	_check(
		window["best_profit"]
		== maxi(int(candidates[0]["profit"]), int(candidates[1]["profit"])),
		"hidden best profit is exact",
	)
```

In the scene test, require all sixteen followers to be visible and the candidate count to equal two.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
godot --headless --path . --script tests/conveyor_profit/test_window_supply_generator.gd
godot --headless --path . --script tests/conveyor_profit/test_conveyor_profit_scene.gd
```

Expected: FAIL because current windows contain only the minimum recipe ingredients and may contain one candidate.

- [ ] **Step 3: Implement deterministic viable-pair generation**

Replace candidate generation with recipe-pair enumeration, then fill duplicate real plates only from the pair's safe ingredient union:

```gdscript
const PLATE_COUNT: int = 16


static func generate(seed_value: int, window_count: int = 10) -> Array[Dictionary]:
	var random := RandomNumberGenerator.new()
	random.seed = seed_value
	var pairs: Array[Dictionary] = _viable_recipe_pairs()
	var windows: Array[Dictionary] = []
	for _index: int in window_count:
		var pair: Dictionary = pairs[random.randi_range(0, pairs.size() - 1)]
		var ingredients: Array[String] = pair["ingredients"].duplicate()
		while ingredients.size() < PLATE_COUNT:
			ingredients.append(pair["support"][random.randi_range(0, pair["support"].size() - 1)])
		_shuffle(ingredients, random)
		windows.append({
			"ingredients": ingredients,
			"best_profit": pair["best_profit"],
		})
	return windows


static func _viable_recipe_pairs() -> Array[Dictionary]:
	var pairs: Array[Dictionary] = []
	for first_index: int in CATALOG.RECIPES.size():
		for second_index: int in range(first_index + 1, CATALOG.RECIPES.size()):
			var first: Dictionary = CATALOG.RECIPES[first_index]
			var second: Dictionary = CATALOG.RECIPES[second_index]
			if int(first["profit"]) == int(second["profit"]):
				continue
			var base: Array[String] = []
			base.assign(first["ingredients"])
			for ingredient: String in second["ingredients"]:
				base.append(ingredient)
			var feasible: Array[Dictionary] = CATALOG.attainable_single_dishes(base)
			if feasible.size() != 2:
				continue
			var feasible_ids := feasible.map(
				func(recipe: Dictionary) -> String: return String(recipe["id"])
			)
			if String(first["id"]) not in feasible_ids or String(second["id"]) not in feasible_ids:
				continue
			var support: Array[String] = []
			for ingredient: String in base:
				if ingredient not in support:
					support.append(ingredient)
			pairs.append({
				"ingredients": base,
				"support": support,
				"best_profit": maxi(int(first["profit"]), int(second["profit"])),
			})
	return pairs
```

Keep `_shuffle()` unchanged and remove `_candidate_ingredients()`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the two commands from Step 2.

Expected: both exit 0, with every initial window showing sixteen plates and exactly two unequal-profit recipe types.

- [ ] **Step 5: Commit the generator change**

```bash
git add conveyor_profit/scripts/window_supply_generator.gd \
  tests/conveyor_profit/test_window_supply_generator.gd \
  tests/conveyor_profit/test_conveyor_profit_scene.gd
git commit -m "feat(conveyor-profit): fill two-choice strategy windows"
```

### Task 2: Make every MAKE consume the window and preserve a full belt

**Files:**
- Modify: `conveyor_profit/scripts/profit_session.gd`
- Modify: `conveyor_profit/scripts/profit_window_session.gd`
- Modify: `conveyor_profit/scripts/conveyor_gameplay.gd`
- Modify: `tests/conveyor_profit/test_profit_session.gd`
- Modify: `tests/conveyor_profit/test_profit_window_session.gd`
- Modify: `tests/conveyor_profit/test_conveyor_gameplay.gd`

- [ ] **Step 1: Add failing lifecycle and economic assertions**

Update the window-session test to require invalid submissions to lock:

```gdscript
_check(session.record_make("", 0) == "invalid_combo", "invalid combo is recorded")
_check(session.dish_made, "invalid combo consumes the window")
_check(session.record_make("egg_toast", 4) == "window_locked", "retry is rejected")
```

Add gameplay checks for a full belt after selection, invalid-cost loss, stable completion text, and direct advancement:

```gdscript
var before_profit: int = gameplay.get_profit()
var selected_ids := _available_ingredient_ids(path)
gameplay.request_select_ingredient(selected_ids[0], camera)
_check(_available_ingredient_ids(path).size() == 16, "belt refills after selection")
var invalid_result: Dictionary = gameplay.request_make()
_check(invalid_result["outcome"] == "invalid_combo", "invalid combo settles")
_check(gameplay.get_profit() < before_profit, "invalid combo deducts ingredient cost")
_check(gameplay.window_session.dish_made, "invalid combo locks window")
_check(gameplay.request_make()["outcome"] == "window_locked", "second make is rejected")
_check(gameplay.request_wait_next_window()["outcome"] == "window_advanced", "locked window advances")
```

- [ ] **Step 2: Run the three focused tests and verify RED**

```bash
godot --headless --path . --script tests/conveyor_profit/test_profit_session.gd
godot --headless --path . --script tests/conveyor_profit/test_profit_window_session.gd
godot --headless --path . --script tests/conveyor_profit/test_conveyor_gameplay.gd
```

Expected: FAIL on invalid locking, full-belt refill, and missing `request_wait_next_window()`.

- [ ] **Step 3: Return dish profit and track window accuracy internally**

Extend `ProfitSession.make()` without changing its cumulative `profit` field:

```gdscript
var dish_profit := int(recipe.get("profit", 0))
return {
	"accepted": true,
	"recipe_id": recipe_id,
	"dish_profit": dish_profit,
	"profit": get_profit(),
}
```

Change `ProfitWindowSession.record_make()` and add trusted metrics:

```gdscript
var completed_windows: int = 0
var optimal_windows: int = 0


func record_make(recipe_id: String, dish_profit: int) -> String:
	if is_terminal() or is_time_expired():
		return "game_finished"
	if dish_made:
		return "window_locked"
	dish_made = true
	completed_windows += 1
	if not recipe_id.is_empty() and dish_profit == best_profits[current_window_index]:
		optimal_windows += 1
	return "invalid_combo" if recipe_id.is_empty() else "accepted"


func get_developer_metrics(actual_profit: int) -> Dictionary:
	return {
		"completed_windows": completed_windows,
		"optimal_windows": optimal_windows,
		"total_windows": best_profits.size(),
		"efficiency_percent": get_efficiency_percent(actual_profit),
	}
```

Do not add these metrics to `get_public_state()`.

- [ ] **Step 4: Implement locked-window advancement, AI clock gating, and belt refill**

Add state and methods to `ConveyorGameplay`:

```gdscript
var _ai_control_active: bool = false
var _window_refill_pool: Array[String] = []
var _refill_index: int = 0


func _process(delta: float) -> void:
	if not _ai_control_active:
		advance_time(delta)


func set_ai_control_active(value: bool) -> void:
	_ai_control_active = value


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
		"outcome": "window_advanced"
		if window_session.current_window_index == previous_index + 1
		else "game_finished"
	}
```

In `request_make()`, pass `dish_profit`, disable input for both accepted and invalid outcomes, and publish completion text. In `_load_window()` copy the 16-item template into `_window_refill_pool`; after every selection append the next deterministic pool item before `_fill_follower()`. `request_undo()` removes the tray item without adding a seventeenth reserve item because the belt slot was already refilled.

At terminal, emit one trusted developer-only metric line without adding fields to bridge packets:

```gdscript
var metrics: Dictionary = window_session.get_developer_metrics(session.get_profit())
print(
	"CONVEYOR_PROFIT_RESULT optimal_windows=%d completed_windows=%d total_windows=%d efficiency=%d"
	% [
		metrics["optimal_windows"], metrics["completed_windows"],
		metrics["total_windows"], metrics["efficiency_percent"],
	]
)
```

- [ ] **Step 5: Run focused tests and commit**

Run the three commands from Step 2. Expected: all exit 0.

```bash
git add conveyor_profit/scripts/profit_session.gd \
  conveyor_profit/scripts/profit_window_session.gd \
  conveyor_profit/scripts/conveyor_gameplay.gd \
  tests/conveyor_profit/test_profit_session.gd \
  tests/conveyor_profit/test_profit_window_session.gd \
  tests/conveyor_profit/test_conveyor_gameplay.gd
git commit -m "feat(conveyor-profit): lock and advance completed windows"
```

### Task 3: Add the fourth semantic action and trusted Godot adapter

**Files:**
- Create: `conveyor_profit/scripts/conveyor_ai_play_monitor.gd`
- Modify: `addons/cogito/AIPlay/ai_play_executor.gd`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `tests/ai_play/test_ai_play_executor.gd`
- Create: `tests/conveyor_profit/test_conveyor_ai_play_monitor.gd`

- [ ] **Step 1: Write failing executor and monitor tests**

Require `wait_next_window` to be conveyor-only and the sole action in a batch:

```gdscript
executor.active_scenario_id = "conveyor_profit"
_assert(
	executor.validate_batch([{"type": "wait_next_window"}], {}) == {"valid": true},
	"conveyor wait-next-window validates",
)
_assert(
	not executor.validate_batch([
		{"type": "undo"}, {"type": "wait_next_window"},
	], {}).get("valid", false),
	"wait-next-window must be the only action",
)
```

The monitor test must assert exact sanitized results:

```gdscript
_check(
	monitor.execute_semantic_action({"type": "select_ingredient", "ingredient": "bread"})
	== {"status": "completed", "type": "select_ingredient", "outcome": "selected", "ingredient": "bread"},
	"monitor exposes only the selected public ingredient",
)
_check(
	monitor.execute_semantic_action({"type": "wait_next_window"})
	== {"status": "completed", "type": "wait_next_window", "outcome": "window_not_complete"},
	"monitor preserves public window state",
)
```

- [ ] **Step 2: Run tests and verify RED**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/conveyor_profit/test_conveyor_ai_play_monitor.gd
```

Expected: executor rejects the unknown action and the monitor script/test does not yet exist.

- [ ] **Step 3: Extend the Godot action allowlist symmetrically**

Add `"wait_next_window": ["type"]` to `ACTION_FIELDS`, include it in `CONVEYOR_ACTIONS`, require it to be the only batch action, and dispatch it through `semantic_action_provider`:

```gdscript
if action_type == "wait_next_window" and actions.size() != 1:
	return _invalid("wait_next_window must be the only action")
```

Also set `executor.active_scenario_id` and its provider during controller setup:

```gdscript
if "active_scenario_id" in _executor:
	_executor.active_scenario_id = _active_scenario_id
if (
	_terminal_monitor != null
	and "semantic_action_provider" in _executor
	and _terminal_monitor.has_method("execute_semantic_action")
):
	_executor.semantic_action_provider = _terminal_monitor
```

Add conveyor terminal pairs to `SCENARIO_TERMINAL_RESULTS`.

- [ ] **Step 4: Implement the monitor adapter**

Create the focused adapter:

```gdscript
class_name ConveyorAIPlayMonitor
extends Node

signal game_finished(outcome: String, reason: String)

@export var scenario_id: String = "conveyor_profit"
@export var gameplay: ConveyorGameplay
@export var camera: Camera3D


func _ready() -> void:
	if gameplay != null and not gameplay.game_finished.is_connected(_on_game_finished):
		gameplay.game_finished.connect(_on_game_finished)


func set_ai_control_active(value: bool) -> void:
	if gameplay != null:
		gameplay.set_ai_control_active(value)


func execute_semantic_action(action: Dictionary) -> Dictionary:
	var action_type := String(action["type"])
	var result: Dictionary
	match action_type:
		"select_ingredient":
			result = gameplay.request_select_ingredient(String(action["ingredient"]), camera)
		"undo":
			result = gameplay.request_undo()
		"make":
			result = gameplay.request_make()
		"wait_next_window":
			result = gameplay.request_wait_next_window()
		_:
			return {"status": "error", "error": "semantic action is unavailable"}
	var public_result := {
		"status": "completed", "type": action_type,
		"outcome": String(result.get("outcome", "game_finished")),
	}
	if action_type == "select_ingredient" and result.has("ingredient"):
		public_result["ingredient"] = String(result["ingredient"])
	return public_result


func _on_game_finished(outcome: String, reason: String) -> void:
	game_finished.emit(outcome, reason)
```

Have `AIPlayController.enable_ai()` call `set_ai_control_active(true)` on the selected monitor and `disable_ai()`/`_exit_tree()` call `false`, so human launches retain wall-clock behavior.

- [ ] **Step 5: Run tests and commit**

Run the commands from Step 2. Expected: both exit 0.

```bash
git add addons/cogito/AIPlay/ai_play_executor.gd \
  addons/cogito/AIPlay/ai_play_controller.gd \
  conveyor_profit/scripts/conveyor_ai_play_monitor.gd \
  tests/ai_play/test_ai_play_executor.gd \
  tests/conveyor_profit/test_conveyor_ai_play_monitor.gd
git commit -m "feat(ai-play): adapt conveyor profit semantic actions"
```

### Task 4: Wire a fixed-camera observer and controller into the standalone scene

**Files:**
- Create: `conveyor_profit/scripts/conveyor_ai_play_observer.gd`
- Create: `conveyor_profit/scenes/conveyor_ai_play_controller.tscn`
- Modify: `conveyor_profit/scenes/conveyor_profit_preview.tscn`
- Modify: `tests/conveyor_profit/test_conveyor_profit_scene.gd`
- Create: `tests/conveyor_profit/test_conveyor_ai_play_observer.gd`
- Modify: `tests/ai_play/test_ai_play_controller.gd`

- [ ] **Step 1: Add failing scene, observer, and terminal tests**

Assert the preview scene has a disabled-by-default controller, conveyor monitor, fixed-camera observer, and exact terminal allowlist:

```gdscript
var controller := preview.get_node_or_null("AIPlayController")
_check(controller != null, "preview embeds AI Play controller")
_check(controller != null and not controller.auto_start, "AI Play remains explicit")
_check(controller.has_node("ConveyorProfitMonitor"), "conveyor monitor is wired")
_check(controller.get_node("Observer").gameplay == preview.get_node("Environment/Gameplay"), "observer uses public gameplay state")
```

Observer tests must verify `conveyor` contains exactly the seven existing HUD fields and lacks `ingredients`, `best_profit`, `future_supply`, `seed`, and `passing_profit`.

- [ ] **Step 2: Run tests and verify RED**

```bash
godot --headless --path . --script tests/conveyor_profit/test_conveyor_profit_scene.gd
godot --headless --path . --script tests/conveyor_profit/test_conveyor_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: FAIL because the standalone scene has no AI Play nodes and no conveyor observer.

- [ ] **Step 3: Implement the fixed-camera observer**

Follow the existing garden observer's image capture and recursive result sanitizer, but publish a neutral fixed-camera player DTO and the existing public conveyor state:

```gdscript
class_name ConveyorAIPlayObserver
extends Node

const IMAGE_WIDTH: int = 1024
const IMAGE_HEIGHT: int = 576
const APPROVED_ACTIONS: Array[String] = [
	"forward", "back", "left", "right", "jump", "sprint", "crouch",
	"interact", "interact2", "menu",
]

@export var gameplay: ConveyorGameplay
@export_range(0.0, 1.0, 0.01) var jpeg_quality: float = 0.75
var _observation_id: int = 0


func capture_observation(last_results: Array) -> Dictionary:
	_observation_id += 1
	var image := _capture_image()
	return {
		"observation_id": _observation_id,
		"captured_at_ms": Time.get_ticks_msec(),
		"image": {
			"mime_type": "image/jpeg",
			"base64": Marshalls.raw_to_base64(image.save_jpg_to_buffer(jpeg_quality)),
			"width": IMAGE_WIDTH, "height": IMAGE_HEIGHT,
		},
		"player": {
			"position": [0.0, 0.0, 0.0], "yaw_degrees": 0.0,
			"pitch_degrees": 0.0, "planar_velocity": [0.0, 0.0],
			"on_floor": true, "health_ratio": null, "stamina_ratio": null,
		},
		"interface": {
			"is_open": false, "visible_object_text": "",
			"available_interactions": [],
		},
		"bindings": _unbound_bindings(),
		"last_action_results": _sanitize_last_results(last_results),
		"conveyor": gameplay.get_public_state(),
	}
```

Implement `_capture_image()`, `_sanitize_last_results()`, and `_sanitize_json_value()` with the same bounded behavior as `AIPlayGardenObserver`; `_unbound_bindings()` must return every `APPROVED_ACTIONS` key with value `"unbound"`.

- [ ] **Step 4: Build the dedicated controller scene and wire node paths**

Create a controller scene containing the standard Controller, Executor, InteractionProbe, Bridge and Timer, but use `ConveyorAIPlayObserver` and add `ConveyorAIPlayMonitor`. Point observer/monitor exports to `../../Environment/Gameplay` and the monitor camera to `../../Camera`. Instantiate it as `AIPlayController` in `conveyor_profit_preview.tscn`; keep `auto_start = false`, `host = "127.0.0.1"`, and `port = 8765`.

Run the editor import once so Godot generates valid script resource UIDs:

```bash
godot --headless --path . --editor --quit
```

Stage only UIDs belonging to newly created tracked scripts; leave unrelated generated files untracked.

- [ ] **Step 5: Run tests and commit**

Run the commands from Step 2. Expected: all exit 0.

```bash
git add conveyor_profit/scripts/conveyor_ai_play_observer.gd \
  conveyor_profit/scripts/conveyor_ai_play_observer.gd.uid \
  conveyor_profit/scripts/conveyor_ai_play_monitor.gd.uid \
  conveyor_profit/scenes/conveyor_ai_play_controller.tscn \
  conveyor_profit/scenes/conveyor_profit_preview.tscn \
  tests/conveyor_profit/test_conveyor_profit_scene.gd \
  tests/conveyor_profit/test_conveyor_ai_play_observer.gd \
  tests/ai_play/test_ai_play_controller.gd
git commit -m "feat(ai-play): wire standalone conveyor profit scene"
```

### Task 5: Extend Python validation and public briefing without leaking strategy answers

**Files:**
- Modify: `ai_play/src/ai_play/action_schema.py`
- Modify: `ai_play/src/ai_play/observation_schema.py`
- Modify: `ai_play/src/ai_play/conveyor_profit_briefing.py`
- Modify: `ai_play/tests/test_action_schema.py`
- Modify: `ai_play/tests/test_observation_schema.py`
- Modify: `ai_play/tests/test_briefing.py`

- [ ] **Step 1: Write failing Python contract tests**

```python
def test_wait_next_window_is_conveyor_only_and_solo():
    action = {"type": "wait_next_window"}
    assert validate_action_batch([action], set(), False, "conveyor_profit") == [action]
    with pytest.raises(ActionValidationError, match="only action"):
        validate_action_batch(
            [{"type": "undo"}, action], set(), False, "conveyor_profit"
        )
    with pytest.raises(ActionValidationError, match="scenario"):
        validate_action_batch([action], set(), False, "find_key")
```

Add action-result cases for `window_not_complete`, `window_advanced`, and `game_finished`, and assert briefing text says every MAKE locks the window, there are sixteen visible plates and exactly two unequal-profit choices, and `wait_next_window` is only valid after locking.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
PYTHONPATH=ai_play/src ../../.venv/bin/python -m pytest \
  ai_play/tests/test_action_schema.py \
  ai_play/tests/test_observation_schema.py \
  ai_play/tests/test_briefing.py -q
```

Expected: FAIL because `wait_next_window` is not allowlisted and the old briefing says invalid MAKE does not lock.

- [ ] **Step 3: Update strict Python DTO validation**

Add the exact action key and scenario gate:

```python
ALLOWED_KEYS["wait_next_window"] = {"type"}
CONVEYOR_ACTIONS = frozenset({
    "select_ingredient", "undo", "make", "wait_next_window"
})
```

Require `wait_next_window` to be the only action, add it to `ACTION_TYPES`, and accept only these exact public outcomes:

```python
CONVEYOR_OUTCOMES = {
    "selected", "undone", "accepted", "invalid_combo",
    "ingredient_not_available", "window_locked", "window_not_complete",
    "window_advanced", "game_finished", "tray_empty",
}
```

Treat `wait_next_window` as a conveyor completed result with exact fields `status`, `type`, and `outcome`.

- [ ] **Step 4: Rewrite the public briefing rules**

Expose rules, not generated answers:

```python
"rules": [
    "每个窗口画面中有十六盘真实可选食材，整批恰好能完成两种净利润不同的菜。",
    "从公开菜单计算售价减食材成本；每个窗口只允许一次 make。",
    "合法或非法 make 都会消耗当前窗口机会；非法组合收入为零并扣除托盘成本。",
    "完成后调用 wait_next_window；未完成窗口不能跳过。",
    "select_ingredient 使用画面上的固定英文食材名，同名盘由游戏随机选择。",
]
```

Add `"wait_next_window": {"type": "wait_next_window"}` to `actions`. Do not include recipe candidates, current supply, best profit, threshold, seed, source names or paths.

- [ ] **Step 5: Run tests and commit**

Run the command from Step 2. Expected: all pass.

```bash
git add ai_play/src/ai_play/action_schema.py \
  ai_play/src/ai_play/observation_schema.py \
  ai_play/src/ai_play/conveyor_profit_briefing.py \
  ai_play/tests/test_action_schema.py \
  ai_play/tests/test_observation_schema.py \
  ai_play/tests/test_briefing.py
git commit -m "feat(ai-play): publish conveyor window progression"
```

### Task 6: Make orchestrator launch the correct scene and recognize Godot terminal output

**Files:**
- Create: `tools/ai_play_scene_registry.py`
- Modify: `tools/ai_play_codex_orchestrator.py`
- Modify: `tools/ai_play_supervisor.py`
- Modify: `tests/test_ai_play_codex_orchestrator.py`
- Modify: `tests/test_ai_play_supervisor.py`

- [ ] **Step 1: Add failing launch-resolution and terminal-parser tests**

```python
def test_conveyor_scenario_uses_standalone_scene_by_default():
    assert resolve_scene("conveyor_profit", None) == (
        "conveyor_profit/scenes/conveyor_profit_preview.tscn"
    )
    assert resolve_scene("find_key", None) == DEFAULT_SCENE


def test_game_over_disable_line_waits_for_exact_terminal_marker():
    assert parse_game_over_marker(
        "AI_PLAY disabled; reason=game_over:efficiency_target_reached"
    ) is None
    assert parse_game_over_marker(
        "AI_PLAY_GAME_OVER outcome=success reason=efficiency_target_reached"
    ) == ("success", "efficiency_target_reached")
```

Also assert an explicit `--scene` still overrides scenario defaults.

- [ ] **Step 2: Run tests and verify RED**

```bash
../../.venv/bin/python -m pytest \
  tests/test_ai_play_codex_orchestrator.py \
  tests/test_ai_play_supervisor.py -q
```

Expected: FAIL because scene resolution is absent and `game_over:*` disabled lines are currently classified as abnormal.

- [ ] **Step 3: Resolve scenario-specific default scenes**

Create one shared pure helper and import it from both launch paths:

```python
DEFAULT_SCENE = "addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
SCENARIO_SCENES = {
    "conveyor_profit": "conveyor_profit/scenes/conveyor_profit_preview.tscn",
}


def resolve_scene(scenario: str, explicit_scene: str | None) -> str:
    if explicit_scene:
        return explicit_scene
    return SCENARIO_SCENES.get(scenario, DEFAULT_SCENE)
```

Change `--scene` to default to `None`, resolve it after parsing, and pass the resolved path to the supervisor command. Preserve default Lobby behavior for every other scenario.

- [ ] **Step 4: Ignore the pre-terminal disable line**

In `parse_game_over_marker()`:

```python
if match is not None:
    reason = match.group(1)
    if reason.startswith("game_over:"):
        return None
    if reason in STOPPED_REASONS:
        return "failure", reason if reason != "mcp_stop" else "stopped"
    return "abnormal", reason
```

This makes the subsequent exact `AI_PLAY_GAME_OVER` line authoritative and prevents a valid game from being retried.

- [ ] **Step 5: Run tests and commit**

Run the command from Step 2. Expected: all pass.

```bash
git add tools/ai_play_scene_registry.py \
  tools/ai_play_codex_orchestrator.py tools/ai_play_supervisor.py \
  tests/test_ai_play_codex_orchestrator.py tests/test_ai_play_supervisor.py
git commit -m "fix(ai-play): supervise standalone conveyor rounds"
```

### Task 7: Synchronize runtime documentation and run complete local verification

**Files:**
- Modify: `ai_play/README.md`
- Modify: `conveyor_profit/README.md`
- Modify: `game_script/conveyor_profit.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

- [ ] **Step 1: Update operator and developer documentation**

Document the four exact semantic actions, sixteen-plate/two-choice rule, invalid MAKE lock, AI-paused clock, standalone scene mapping, and launch command:

```bash
python3 tools/ai_play_codex_orchestrator.py \
  --runs 3 \
  --scenario conveyor_profit \
  --model gpt-5.6-sol \
  --reasoning-effort high \
  --workflow-memory enabled
```

State that `game_script/` remains developer-only and is never loaded into runtime model input. Keep the already approved Wiki wording aligned with final method/action names.

- [ ] **Step 2: Run every conveyor Godot test**

```bash
godot --headless --path . --editor --quit
for test_script in tests/conveyor_profit/*.gd; do
  godot --headless --path . --script "$test_script"
done
```

Expected: every test process exits 0.

- [ ] **Step 3: Run affected Godot AI Play suites**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_rendered_recovery.gd
```

Expected: every suite exits 0.

- [ ] **Step 4: Run complete Python and static validation**

```bash
PYTHONPATH=ai_play/src ../../.venv/bin/python -m pytest ai_play/tests -q
../../.venv/bin/python -m pytest \
  tests/test_ai_play_codex_orchestrator.py tests/test_ai_play_supervisor.py -q
bash tests/check_ai_play_lobby.sh
bash tests/check_ai_play_start_script.sh
bash tests/test_ai_play_secret_scan.sh
git diff --check
```

Expected: zero failures, secret scan exit 0, and no whitespace errors.

- [ ] **Step 5: Commit the documented, locally verified integration**

```bash
git add ai_play/README.md conveyor_profit/README.md game_script/conveyor_profit.md \
  docs/wiki/ai-play/system-guide.md
git commit -m "docs(conveyor-profit): document complete AI play loop"
```

### Task 8: Run the authorized three-round AWM acceptance and publish the branch

**Files:**
- No tracked runtime files; logs remain under the orchestrator's trusted session root.

- [ ] **Step 1: Confirm a clean runtime environment**

```bash
pgrep -af 'ai_play|godot.*ai-play|codex exec' || true
lsof -nP -iTCP:8765 -sTCP:LISTEN || true
lsof -nP -iTCP:8766 -sTCP:LISTEN || true
```

Expected: no prior AI Play process or listener. Stop only verified stale processes from this repository; do not terminate unrelated Godot sessions.

- [ ] **Step 2: Start the user-authorized real run without intervention**

```bash
../../.venv/bin/python tools/ai_play_codex_orchestrator.py \
  --runs 3 \
  --scenario conveyor_profit \
  --model gpt-5.6-sol \
  --reasoning-effort high \
  --workflow-memory enabled
```

Expected: the orchestrator prints one isolated `run_dir`, Codex calls briefing/memory/observe/actions, and the supervisor completes three normal Godot terminals without manual window activation.

- [ ] **Step 3: Audit trusted results without feeding them back to the player**

For each attempt, read the operator-side terminal output and trusted `run.json`/`trajectory.json` only after the run. Record:

```text
attempt, terminal outcome/reason, optimal_windows/10, efficiency_percent,
act total_steps, abnormal retries, AWM completed_runs/update decision
```

Verify screenshots change after semantic actions, no hidden fields appear in MCP structured results, invalid/stopped attempts do not update AWM, and later rounds use only the language workflow exposed by `workflow_memory_read`.

- [ ] **Step 4: Re-run final diff and repository checks**

```bash
git diff --check
git status --short --branch
git log --oneline --decorate -8
```

Expected: only the intentionally ignored cache directories remain untracked; runtime logs are outside the repository.

- [ ] **Step 5: Push the current feature branch**

```bash
git push origin feature/session-awm
```

Expected: `origin/feature/session-awm` points at the final verified commit. Do not switch branches, merge into `ai_first_play`, create a PR, or clean this worktree because the user explicitly required all work to remain on the current branch.
