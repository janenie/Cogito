# Conveyor Profit Market Reasoning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixed two-recipe conveyor decks with five ten-round market scripts that combine three feasible dishes, current category multipliers, two next-round signals, recipe-history memory, and a 90% online-baseline target.

**Architecture:** Keep script truth, candidate IDs, baseline routes, safe fallback supplies, draw indices, and omniscient metrics on the trusted Godot side. Generate randomized sixteen-plate windows whose feasible recipe set is invariant, settle dynamic prices through one pure market-economy helper, and expose only current multipliers, current signal text, receipts, and existing public state to AI clients.

**Tech Stack:** Godot 4.7 / GDScript, Python 3, pytest, headless Godot SceneTree tests, existing AI First Play protocol v4.

---

### Task 1: Add category-aware market economics

**Files:**
- Create: `conveyor_profit/scripts/market_economy.gd`
- Create: `tests/conveyor_profit/test_market_economy.gd`
- Modify: `conveyor_profit/scripts/recipe_catalog.gd`
- Modify: `tests/conveyor_profit/test_recipe_catalog.gd`

- [ ] **Step 1: Write the failing category and multiplier tests**

Add assertions that all ten recipes have one of the five approved categories and that dynamic sale/profit uses half-up rounding with fixed ingredient cost:

```gdscript
var economy: GDScript = load("res://conveyor_profit/scripts/market_economy.gd")
_check(economy.adjusted_sale_price("avocado_burger", 0.75) == 23, "22.5 rounds up")
_check(economy.adjusted_profit("avocado_burger", 0.75) == 11, "ingredient cost stays 12")
_check(economy.adjusted_profit("corn_bacon_omelet", 1.50) == 30, "40.5 rounds up")
_check(economy.is_valid_multiplier(0.75), "low multiplier is valid")
_check(not economy.is_valid_multiplier(1.10), "arbitrary multiplier is rejected")
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
godot --headless --path . --script tests/conveyor_profit/test_market_economy.gd
godot --headless --path . --script tests/conveyor_profit/test_recipe_catalog.gd
```

Expected: the market helper is missing and recipe dictionaries have no `category` field.

- [ ] **Step 3: Implement the pure market helper and catalog categories**

Implement this public surface without mutable state:

```gdscript
class_name MarketEconomy
extends RefCounted

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")
const CATEGORIES: Array[String] = ["salad", "soup", "burger", "omelet", "sandwich"]
const MULTIPLIERS: Array[float] = [0.75, 1.0, 1.25, 1.5]

static func adjusted_sale_price(recipe_id: String, multiplier: float) -> int:
	var recipe: Dictionary = CATALOG.recipe_by_id(recipe_id)
	if recipe.is_empty() or not is_valid_multiplier(multiplier):
		return -1
	return floori(float(recipe["sale_price"]) * multiplier + 0.5)

static func adjusted_profit(recipe_id: String, multiplier: float) -> int:
	var recipe: Dictionary = CATALOG.recipe_by_id(recipe_id)
	if recipe.is_empty():
		return -1
	return adjusted_sale_price(recipe_id, multiplier) - int(recipe["ingredient_cost"])

static func is_valid_multiplier(value: float) -> bool:
	return value in MULTIPLIERS
```

Add immutable `category` and `ingredient_cost` fields to each recipe plus a defensive `recipe_by_id()` helper. Preserve existing IDs, ingredients, base sale prices, and base profits.

- [ ] **Step 4: Re-run focused tests and commit**

Run the two commands from Step 2. Expected: PASS.

```bash
git add conveyor_profit/scripts/market_economy.gd conveyor_profit/scripts/recipe_catalog.gd tests/conveyor_profit/test_market_economy.gd tests/conveyor_profit/test_recipe_catalog.gd
git commit -m "feat(conveyor-profit): add market category economics"
```

### Task 2: Replace fixed decks with five validated market scripts

**Files:**
- Create: `conveyor_profit/scripts/market_campaigns.gd`
- Create: `tests/conveyor_profit/test_market_campaigns.gd`
- Remove: `conveyor_profit/scripts/fixed_window_decks.gd`
- Remove: `conveyor_profit/scripts/fixed_window_decks.gd.uid`
- Remove: `tests/conveyor_profit/test_fixed_window_decks.gd`
- Remove: `tests/conveyor_profit/test_fixed_window_decks.gd.uid`

- [ ] **Step 1: Write failing campaign schema and approved-route tests**

Assert exact campaign IDs, routes, baseline profits, and passing targets from the spec:

```gdscript
const EXPECTED_ROUTES := {
	"A": ["avocado_burger", "avocado_burger", "pumpkin_sausage_soup", "corn_bacon_omelet", "avocado_fish_sandwich", "avocado_fish_sandwich", "avocado_salad", "corn_bacon_omelet", "broccoli_bacon_omelet", "pumpkin_sausage_soup"],
	"B": ["corn_bacon_omelet", "avocado_salad", "pumpkin_sausage_soup", "corn_bacon_omelet", "avocado_burger", "avocado_salad", "avocado_fish_sandwich", "avocado_fish_sandwich", "classic_burger", "pumpkin_sausage_soup"],
	"C": ["avocado_burger", "avocado_burger", "pumpkin_sausage_soup", "avocado_salad", "avocado_fish_sandwich", "avocado_salad", "corn_bacon_omelet", "avocado_fish_sandwich", "corn_bacon_omelet", "classic_burger"],
	"D": ["pumpkin_sausage_soup", "avocado_fish_sandwich", "avocado_burger", "avocado_burger", "classic_burger", "avocado_fish_sandwich", "garden_fish_sandwich", "garden_fish_sandwich", "avocado_salad", "corn_bacon_omelet"],
	"E": ["avocado_burger", "avocado_salad", "avocado_salad", "pumpkin_sausage_soup", "pumpkin_sausage_soup", "avocado_fish_sandwich", "avocado_burger", "corn_bacon_omelet", "avocado_fish_sandwich", "corn_bacon_omelet"],
}
const EXPECTED_BASELINES := {"A": 194, "B": 213, "C": 184, "D": 229, "E": 234}
const EXPECTED_TARGETS := {"A": 175, "B": 192, "C": 166, "D": 207, "E": 211}
```

For every round assert three unique catalog recipe IDs, five exact category multipliers, two non-empty signals except zero in round ten, and a baseline recipe contained in the candidates. Replay counts and assert no baseline recipe exceeds two uses.

- [ ] **Step 2: Run the campaign test and verify failure**

Run:

```bash
godot --headless --path . --script tests/conveyor_profit/test_market_campaigns.gd
```

Expected: `market_campaigns.gd` does not exist.

- [ ] **Step 3: Implement the campaign data boundary**

Use this exact dictionary shape and transcribe all fifty approved rows and signal copy from `spec-conveyor-market-reasoning.md`:

```gdscript
class_name MarketCampaigns
extends RefCounted

const CAMPAIGNS: Array[Dictionary] = [
	{
		"id": "A",
		"strategy": "history_quota",
		"rounds": [
			{
				"candidate_recipe_ids": ["avocado_burger", "classic_burger", "garden_salad"],
				"category_multipliers": {"salad": 1.0, "soup": 1.0, "burger": 1.0, "omelet": 1.0, "sandwich": 1.0},
				"signals": [
					{"category": "burger", "direction": "up", "text": "中型球赛即将散场，下一轮汉堡需求可能升高。"},
					{"category": "burger", "direction": "down", "text": "末班车延误，下一轮汉堡需求可能降低。"},
				],
				"baseline_recipe_id": "avocado_burger",
			},
		],
	},
]
```

The completed constant must contain A–E and ten rounds each. Implement `campaign_by_id(id)`, `campaign_for_draw(seed, draw_index)`, `baseline_profit(campaign)`, and `passing_profit(campaign)`; all returned dictionaries must be deep copies.

- [ ] **Step 4: Delete obsolete fixed-deck resources and re-run the test**

Remove only the four fixed-deck files listed above after `rg "fixed_window_decks"` shows that remaining references are scheduled in later tasks. Run the campaign test. Expected: PASS with exact approved route totals.

- [ ] **Step 5: Commit the trusted script data**

```bash
git add conveyor_profit/scripts/market_campaigns.gd tests/conveyor_profit/test_market_campaigns.gd conveyor_profit/scripts/fixed_window_decks.gd conveyor_profit/scripts/fixed_window_decks.gd.uid tests/conveyor_profit/test_fixed_window_decks.gd tests/conveyor_profit/test_fixed_window_decks.gd.uid
git commit -m "feat(conveyor-profit): author market reasoning campaigns"
```

### Task 3: Generate randomized supplies with an invariant three-recipe set

**Files:**
- Modify: `conveyor_profit/scripts/window_supply_generator.gd`
- Modify: `tests/conveyor_profit/test_window_supply_generator.gd`

- [ ] **Step 1: Replace old two-recipe tests with failing invariant-set tests**

For every campaign and at least seeds `7`, `1337`, and `7331`, generate ten rounds and assert:

```gdscript
_check(window["ingredients"].size() == 16, "window has sixteen plates")
var feasible_ids := catalog.attainable_single_dishes(window["ingredients"]).map(
	func(recipe: Dictionary) -> String: return String(recipe["id"])
)
feasible_ids.sort()
var expected_ids: Array = campaign["rounds"][window_index]["candidate_recipe_ids"].duplicate()
expected_ids.sort()
_check(feasible_ids == expected_ids, "random filler preserves exactly three candidates")
```

Also assert same campaign/seed reproduces exact ingredients, different seeds change at least one window, and runtime windows expose only `ingredients`, `category_multipliers`, and `signals`—never candidate IDs, baseline IDs, script ID, or fallback metadata.

- [ ] **Step 2: Run the generator test and verify failure**

```bash
godot --headless --path . --script tests/conveyor_profit/test_window_supply_generator.gd
```

Expected: the old generator still loads fixed decks and yields two feasible recipes.

- [ ] **Step 3: Implement bounded safe-fill generation**

Change the API to `generate(campaign: Dictionary, seed_value: int)`. Build required ingredient counts as the per-ingredient maximum across the three recipes, then use seeded rejection sampling to fill to sixteen. Accept only exact candidate-set equality. Use a separate RNG stream for Fisher–Yates order shuffling. Cap fill attempts at `500`; on exhaustion copy the round's validated `fallback_ingredients`, shuffle it, and validate again before returning.

```gdscript
static func _matches_candidates(ingredients: Array, candidate_ids: Array) -> bool:
	var actual: Array[String] = []
	for recipe: Dictionary in CATALOG.attainable_single_dishes(ingredients):
		actual.append(String(recipe["id"]))
	actual.sort()
	var expected: Array = candidate_ids.duplicate()
	expected.sort()
	return actual == expected
```

- [ ] **Step 4: Re-run focused campaign and generator tests and commit**

```bash
godot --headless --path . --script tests/conveyor_profit/test_market_campaigns.gd
godot --headless --path . --script tests/conveyor_profit/test_window_supply_generator.gd
git add conveyor_profit/scripts/window_supply_generator.gd tests/conveyor_profit/test_window_supply_generator.gd conveyor_profit/scripts/market_campaigns.gd tests/conveyor_profit/test_market_campaigns.gd
git commit -m "feat(conveyor-profit): randomize safe three-recipe supplies"
```

### Task 4: Settle dynamic prices and score against the online baseline

**Files:**
- Modify: `conveyor_profit/scripts/profit_session.gd`
- Modify: `conveyor_profit/scripts/profit_window_session.gd`
- Modify: `conveyor_profit/scripts/campaign_profit_planner.gd`
- Modify: `tests/conveyor_profit/test_profit_session.gd`
- Modify: `tests/conveyor_profit/test_profit_window_session.gd`
- Modify: `tests/conveyor_profit/test_campaign_profit_planner.gd`

- [ ] **Step 1: Write failing settlement and target tests**

Add a receipt test where avocado burger at burger `1.50` charges cost 12, records sale 45, and returns dish profit 33. Add campaign-session assertions for campaign E:

```gdscript
_check(session.baseline_profit == 234, "session stores online baseline")
_check(session.passing_profit == 211, "target is ceil of ninety percent")
_check(session.omniscient_profit >= session.baseline_profit, "DP remains developer-only comparison")
```

Record the E route and assert `baseline_windows == 10`. Record a legal non-baseline recipe and assert it does not increment that metric even if the DP considers it globally optimal.

- [ ] **Step 2: Run all three focused tests and verify failure**

```bash
godot --headless --path . --script tests/conveyor_profit/test_profit_session.gd
godot --headless --path . --script tests/conveyor_profit/test_profit_window_session.gd
godot --headless --path . --script tests/conveyor_profit/test_campaign_profit_planner.gd
```

Expected: settlement uses base price, target ratio remains 0.8, and the session has no baseline fields.

- [ ] **Step 3: Route accepted makes through MarketEconomy**

Change `ProfitSession.make()` to `make(category_multipliers: Dictionary)`. For a valid, under-quota recipe, look up its category, pass that category's multiplier to `MarketEconomy`, add adjusted sale to revenue, and return adjusted `dish_profit`. Invalid and quota-exceeded attempts still charge selected ingredient costs without revenue.

- [ ] **Step 4: Replace DP scoring with the approved baseline target**

Initialize `ProfitWindowSession` from one campaign plus generated public windows. Set `TARGET_RATIO = 0.90`, compute baseline and passing values from `MarketCampaigns`, and rename `optimal_windows` to `baseline_windows`. Compare accepted recipe ID with the current round's `baseline_recipe_id`; do not call DP for pass/fail.

Extend `CampaignProfitPlanner` so its developer-only DP uses each window's category multiplier and `MarketEconomy.adjusted_profit()`. Rename exposed session state to `omniscient_profit` so no caller can confuse it with the target basis.

- [ ] **Step 5: Re-run focused tests and commit**

```bash
godot --headless --path . --script tests/conveyor_profit/test_profit_session.gd
godot --headless --path . --script tests/conveyor_profit/test_profit_window_session.gd
godot --headless --path . --script tests/conveyor_profit/test_campaign_profit_planner.gd
git add conveyor_profit/scripts/profit_session.gd conveyor_profit/scripts/profit_window_session.gd conveyor_profit/scripts/campaign_profit_planner.gd tests/conveyor_profit/test_profit_session.gd tests/conveyor_profit/test_profit_window_session.gd tests/conveyor_profit/test_campaign_profit_planner.gd
git commit -m "feat(conveyor-profit): score online market baselines"
```

### Task 5: Integrate market scripts, public signals, and dynamic menu prices

**Files:**
- Modify: `conveyor_profit/scripts/conveyor_gameplay.gd`
- Modify: `conveyor_profit/scripts/conveyor_environment.gd`
- Modify: `conveyor_profit/scripts/recipe_menu_pager.gd`
- Modify: `conveyor_profit/scenes/conveyor_profit_environment.tscn`
- Modify: `tests/conveyor_profit/test_conveyor_gameplay.gd`
- Modify: `tests/conveyor_profit/test_recipe_menu_pager.gd`
- Modify: `tests/conveyor_profit/test_conveyor_profit_scene.gd`

- [ ] **Step 1: Add failing gameplay, menu, and scene assertions**

Require `get_public_state()` to return current `market` with five numeric multipliers and exactly two signal strings in rounds 1–9, then zero in round 10. Assert candidate IDs, campaign ID, baseline route/profit, passing amount, draw index, and omniscient profit are absent.

Require recipe-menu economy labels to change when calling:

```gdscript
pager.set_category_multipliers({
	"salad": 1.0, "soup": 1.0, "burger": 1.5, "omelet": 1.0, "sandwich": 1.0,
})
_check(pager.get_displayed_economy("avocado_burger") == {"sale": 45, "profit": 33}, "menu reflects current burger demand")
```

Scene tests must require `HUD/MarketPanel/DemandLabel`, `SignalOneLabel`, and `SignalTwoLabel` with readable font size at least 22.

- [ ] **Step 2: Run focused UI/gameplay tests and verify failure**

```bash
godot --headless --path . --script tests/conveyor_profit/test_conveyor_gameplay.gd
godot --headless --path . --script tests/conveyor_profit/test_recipe_menu_pager.gd
godot --headless --path . --script tests/conveyor_profit/test_conveyor_profit_scene.gd
```

- [ ] **Step 3: Integrate campaign selection and dynamic settlement**

At initialization choose one private campaign, generate its ten public windows, create the session from both, and call `session.make(current_round["category_multipliers"])`. On every `_load_window`, update the menu pager and public market labels before enabling input. Keep all existing semantic selection, undo, make, wait, timer pause, disconnect, and Escape behavior.

- [ ] **Step 4: Build the market panel and refresh both menu pages**

Add one compact HUD panel listing all five current states/multipliers and two wrapped signal labels. Round ten displays `最终轮：没有后续市场信号。` in the first label and an empty second label. Refactor `RecipeMenuPager` to retain card label references and update sale/profit from `MarketEconomy` without rebuilding nodes.

- [ ] **Step 5: Re-run focused tests and commit**

```bash
godot --headless --path . --script tests/conveyor_profit/test_conveyor_gameplay.gd
godot --headless --path . --script tests/conveyor_profit/test_recipe_menu_pager.gd
godot --headless --path . --script tests/conveyor_profit/test_conveyor_profit_scene.gd
git add conveyor_profit/scripts/conveyor_gameplay.gd conveyor_profit/scripts/conveyor_environment.gd conveyor_profit/scripts/recipe_menu_pager.gd conveyor_profit/scenes/conveyor_profit_environment.tscn tests/conveyor_profit/test_conveyor_gameplay.gd tests/conveyor_profit/test_recipe_menu_pager.gd tests/conveyor_profit/test_conveyor_profit_scene.gd
git commit -m "feat(conveyor-profit): present market signals and prices"
```

### Task 6: Synchronize the AI observation and briefing contract

**Files:**
- Modify: `conveyor_profit/scripts/conveyor_ai_play_observer.gd`
- Modify: `tests/conveyor_profit/test_conveyor_ai_play_observer.gd`
- Modify: `ai_play/src/ai_play/observation_schema.py`
- Modify: `ai_play/src/ai_play/conveyor_profit_briefing.py`
- Modify: `ai_play/tests/test_observation_schema.py`
- Modify: `ai_play/tests/test_briefing.py`
- Modify: `tests/conveyor_profit/test_protocol_parity.py`
- Modify: `ai_play/README.md`

- [ ] **Step 1: Write failing public-market and privacy tests**

Require this exact additional observation shape:

```python
"market": {
    "category_multipliers": {
        "salad": 1.0,
        "soup": 1.25,
        "burger": 0.75,
        "omelet": 1.0,
        "sandwich": 1.5,
    },
    "signals": [
        "强冷空气抵达，下一轮汤类需求可能升高。",
        "部分办公楼恢复供暖，下一轮汤类需求可能降低。",
    ],
}
```

Validate only `0.75`, `1.0`, `1.25`, and `1.5`; require five exact category keys; allow zero signals only for window `10 / 10`; cap each signal at 240 characters. Add negative assertions for `campaign_id`, `candidate_recipe_ids`, `baseline_recipe_id`, `baseline_profit`, `passing_profit`, `draw_index`, `omniscient_profit`, `future_multipliers`, and `recipe_counts`.

- [ ] **Step 2: Run Python and Godot contract tests and verify failure**

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest ai_play/tests/test_observation_schema.py ai_play/tests/test_briefing.py tests/conveyor_profit/test_protocol_parity.py -q
godot --headless --path . --script tests/conveyor_profit/test_conveyor_ai_play_observer.gd
```

- [ ] **Step 3: Extend the strict allowlist and public briefing**

Add `market` to the exact conveyor schema on both sides. The briefing must state: current multipliers are exact, each of the first nine rounds includes two explicit next-round directional signals, signals can reinforce or conflict, every recipe may succeed twice, accepted receipts must be self-recorded, and success requires 90% of the hidden online benchmark. Do not mention five scripts, exact candidates, route totals, or absolute targets.

- [ ] **Step 4: Update the AI README and re-run contract tests**

Document the new public fields, the online-baseline scoring distinction, and the unchanged credential/privacy boundary. Run the commands from Step 2. Expected: PASS.

- [ ] **Step 5: Commit protocol parity changes**

```bash
git add conveyor_profit/scripts/conveyor_ai_play_observer.gd tests/conveyor_profit/test_conveyor_ai_play_observer.gd ai_play/src/ai_play/observation_schema.py ai_play/src/ai_play/conveyor_profit_briefing.py ai_play/tests/test_observation_schema.py ai_play/tests/test_briefing.py tests/conveyor_profit/test_protocol_parity.py ai_play/README.md
git commit -m "feat(ai-play): expose conveyor market evidence"
```

### Task 7: Guarantee non-repeating scripts across logical attempts

**Files:**
- Modify: `tools/ai_play_supervisor.py`
- Modify: `tests/test_ai_play_supervisor.py`
- Modify: `conveyor_profit/scripts/conveyor_gameplay.gd`
- Modify: `tests/conveyor_profit/test_conveyor_gameplay.gd`

- [ ] **Step 1: Add failing command and draw-bag tests**

Change the command-builder test to require `--conveyor-draw-index=0` for logical attempt one and indexes `0..4` across five completed runs. Assert every infrastructure retry receives the same command/index. Add Godot assertions that the same seed with draw indexes `0..4` yields all five campaign IDs exactly once and index `5` begins the same seeded permutation again.

- [ ] **Step 2: Run supervisor and gameplay tests and verify failure**

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest tests/test_ai_play_supervisor.py -q
godot --headless --path . --script tests/conveyor_profit/test_conveyor_gameplay.gd
```

- [ ] **Step 3: Pass the trusted logical-attempt index without exposing it**

Extend `build_godot_command(godot_bin: str, scene: str, scenario: str, conveyor_draw_index: int | None = None)` and append the user argument only for `scenario == "conveyor_profit"`. Build a fresh command inside the supervisor's logical-attempt loop using `attempt - 1`; pass that unchanged command into `run_supervised_attempt` so retries reuse it.

Parse only an exact non-negative integer `--conveyor-draw-index=N` in trusted Godot startup. Manual scene starts use a process-local counter in `MarketCampaigns.next_manual_draw_index()`. Never add the index to observation, logs visible to the player, briefing, or action results.

- [ ] **Step 4: Re-run tests and commit**

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest tests/test_ai_play_supervisor.py -q
godot --headless --path . --script tests/conveyor_profit/test_conveyor_gameplay.gd
git add tools/ai_play_supervisor.py tests/test_ai_play_supervisor.py conveyor_profit/scripts/conveyor_gameplay.gd tests/conveyor_profit/test_conveyor_gameplay.gd
git commit -m "feat(conveyor-profit): rotate market scripts per attempt"
```

### Task 8: Update project knowledge and complete verification

**Files:**
- Modify: `conveyor_profit/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/wiki/development/contributor-guide.md`

- [ ] **Step 1: Replace obsolete fixed-deck documentation**

Document three-candidate safe supply generation, category multipliers, two public signals, recipe-history memory, 90% online-baseline scoring, developer-only omniscient DP, and trusted draw-index rotation. Preserve the explicit AI opt-in, `127.0.0.1` bind, credential isolation, and real-client authorization boundaries.

- [ ] **Step 2: Run every focused conveyor test**

```bash
for test_file in tests/conveyor_profit/*.gd; do godot --headless --path . --script "$test_file" || exit 1; done
```

Expected: every conveyor GDScript test exits 0 without parse, UID, or runtime errors.

- [ ] **Step 3: Run affected Python and static suites**

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest ai_play/tests ai_host/tests tests/*.py tests/conveyor_profit/test_protocol_parity.py -q
bash tests/test_ai_play_secret_scan.sh
```

Expected: all tests pass; no real model, MCP client, credential, screenshot persistence, or network request is used.

- [ ] **Step 4: Parse the project and perform a bounded local smoke test**

```bash
godot --headless --path . --editor --quit
godot --path . conveyor_profit/scenes/conveyor_profit_preview.tscn
```

Manually verify current multipliers and both signals are readable, menu prices refresh, three feasible dishes can be inferred from the belt, recipe-limit receipts remain correct, and Escape stops AI control. This is local engine verification only.

- [ ] **Step 5: Run final hygiene checks and commit documentation**

```bash
git diff --check
git status --short
git add conveyor_profit/README.md docs/wiki/ai-play/system-guide.md docs/wiki/development/contributor-guide.md
git commit -m "docs(conveyor-profit): document market reasoning campaigns"
```

Inspect the final diff for runtime leaks of campaign IDs, candidates, route answers, baseline totals, draw indexes, and omniscient metrics. Do not run a real external Codex or Claude acceptance session without a new explicit user confirmation covering screenshots, tokens, costs, and local trajectories.
