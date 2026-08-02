# Conveyor Profit Authored Strategy Decks Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use test-driven-development while executing this plan task by task.

**Goal:** Replace the procedural conveyor-profit puzzle with five validated ten-window authored campaigns, a public ten-recipe menu, per-recipe limits, and a global dynamic-programming score target.

**Architecture:** Keep authored campaign truth in private Godot-side data, expose only the current belt and fixed public recipe menu, and move economic decisions into small deterministic domain objects. `ProfitSession` owns trusted recipe counts and make outcomes; `CampaignProfitPlanner` computes the campaign optimum; gameplay coordinates them without exposing hidden deck or count state.

**Tech Stack:** Godot 4.7 / GDScript, Python 3, unittest/pytest-style repository tests, GDScript headless tests, Kenney Food Kit GLB assets.

---

## Task 1: Expand the ingredient and recipe catalog

**Files:**
- Modify: `conveyor_profit/scripts/recipe_catalog.gd`
- Modify: `tests/conveyor_profit/test_recipe_catalog.gd`
- Add: `conveyor_profit/assets/kenney_food_kit/models/avocado.glb`
- Add: `conveyor_profit/assets/kenney_food_kit/models/bacon.glb`
- Add: `conveyor_profit/assets/kenney_food_kit/models/broccoli.glb`
- Add: `conveyor_profit/assets/kenney_food_kit/models/carrot.glb`
- Add: `conveyor_profit/assets/kenney_food_kit/models/corn.glb`
- Add: `conveyor_profit/assets/kenney_food_kit/models/onion.glb`
- Add: `conveyor_profit/assets/kenney_food_kit/models/pumpkin.glb`
- Add: `conveyor_profit/assets/kenney_food_kit/models/sausage.glb`

1. Add failing catalog tests for all 16 stable ingredient IDs, exact costs, all 10 recipes, exact ingredient multisets, sale prices, and derived profits.
2. Run the focused catalog test and confirm it fails for the eight missing ingredients and four missing recipes.
3. Update `recipe_catalog.gd` with the approved immutable catalog. Preserve multiset matching and return defensive copies from public helpers.
4. Download the official CC0 Kenney Food Kit archive and copy only the eight required GLBs into the existing food-kit directory. Do not regenerate existing imports or edit `.godot/`.
5. Re-run the focused catalog test and confirm it passes.

## Task 2: Author and validate five private campaigns

**Files:**
- Add: `conveyor_profit/scripts/fixed_window_decks.gd`
- Replace: `conveyor_profit/scripts/window_supply_generator.gd`
- Add: `tests/conveyor_profit/test_fixed_window_decks.gd`
- Modify: `tests/conveyor_profit/test_window_supply_generator.gd`

1. Write failing tests requiring exactly five decks, ten windows per deck, sixteen valid ingredient IDs per window, deterministic window order, and random deck selection only at run start.
2. Add a private validation helper used by tests to enforce for every window:
   - exactly two complete recipes;
   - unequal profits between those recipes;
   - exactly one designated more-profitable recipe missing exactly one ingredient;
   - no other one-missing recipe with a higher sale price;
   - at least two quota-pressure decisions on each deck's canonical optimal route.
3. Confirm the focused tests fail because fixed decks do not exist.
4. Author all fifty literal ingredient arrays in `fixed_window_decks.gd`, with internal metadata available only to developer validation—not runtime observations or briefing.
5. Reduce `window_supply_generator.gd` to choosing one deck and producing its fixed windows; allow deterministic RNG injection for tests. Shuffle plate positions only when materializing a window.
6. Re-run both focused tests until every authored constraint passes.

## Task 3: Compute the global optimum with dynamic programming

**Files:**
- Add: `conveyor_profit/scripts/campaign_profit_planner.gd`
- Add: `tests/conveyor_profit/test_campaign_profit_planner.gd`

1. Add failing tests for a three-window fixture where the locally highest dish appears three times and has a two-use limit. Assert the globally optimal profit is `47`, not the greedy total, and assert optimal-choice evaluation respects prior counts.
2. Confirm the planner test fails because the class is absent.
3. Implement memoized DP keyed by window index plus ten recipe counts in the range `0..2`. Enumerate only recipes fully feasible from the current ingredient multiset and below quota.
4. Expose pure helpers for `max_profit(windows, start_index, counts)` and `is_optimal_choice(windows, index, counts, recipe_id)`; keep authored metadata out of this class.
5. Re-run the planner test and then validate all five authored decks return a positive optimum and a deterministic result.

## Task 4: Add trusted quota outcomes and campaign scoring

**Files:**
- Modify: `conveyor_profit/scripts/profit_session.gd`
- Modify: `conveyor_profit/scripts/profit_window_session.gd`
- Modify: `tests/conveyor_profit/test_profit_session.gd`
- Modify: `tests/conveyor_profit/test_profit_window_session.gd`

1. Add failing `ProfitSession` tests for first and second successful makes, third-attempt `recipe_limit_exceeded`, ingredient-cost charging without revenue on quota failure, invalid-combination penalties, and defensive count snapshots.
2. Add failing `ProfitWindowSession` tests for campaign-wide DP optimum, `ceil(0.8 * optimum)` pass target, one locked result per window, and optimal-choice accounting using counts before the make.
3. Implement `ProfitSession.make(selected_ingredients)` returning a receipt with `accepted`, `outcome`, `recipe_id`, `dish_profit`, and cumulative `profit`. Increment counts only on accepted makes.
4. Implement `ProfitWindowSession` from complete window ingredient arrays rather than independent best-profit numbers. Store the global theoretical optimum once and derive the 80% threshold from it.
5. Record `accepted`, `invalid_combo`, or `recipe_limit_exceeded` once per window. Count an optimal decision only when an accepted recipe lies on a globally optimal continuation.
6. Re-run both focused suites.

## Task 5: Integrate authored campaigns into gameplay

**Files:**
- Modify: `conveyor_profit/scripts/conveyor_gameplay.gd`
- Modify: `conveyor_profit/scripts/conveyor_ai_play_monitor.gd`
- Modify: `tests/conveyor_profit/test_conveyor_gameplay.gd`
- Modify: `tests/conveyor_profit/test_conveyor_ai_play_monitor.gd`

1. Add failing gameplay tests for ten windows, sixteen displayed plates, tray capacity five, sixth-selection `tray_full`, one make per window, and exact accepted/quota/invalid receipts.
2. Add failing observer tests proving current receipts may expose the attempted recipe ID while cumulative recipe counts, deck identity, missing-ingredient hints, and authored optimal-route metadata never appear.
3. Replace procedural window creation with one randomly selected fixed deck. Build the entire `ProfitWindowSession` at run start, but publish only the current shuffled ingredient list.
4. Extend model paths for all sixteen ingredients and set `MAX_TRAY = 5`.
5. Route make requests through `ProfitSession.make`, lock the window for every make outcome, and ensure `wait_next` advances without changing authored order.
6. Preserve disconnect, invalid-data, node-destruction, and Escape input-release safety behavior.
7. Re-run focused gameplay and observer tests.

## Task 6: Build the readable two-page recipe menu

**Files:**
- Modify: `conveyor_profit/scenes/conveyor_profit_environment.tscn`
- Add: `conveyor_profit/scripts/recipe_menu_pager.gd`
- Add: `tests/conveyor_profit/test_recipe_menu_pager.gd`

1. Add a failing pager test requiring two pages, five recipe cards per page, stable ordering, full English names, ingredients, sale, cost, and profit.
2. Implement a small pager driven directly by `RecipeCatalog`, with explicit previous/next controls and no hidden campaign information.
3. Replace the six static abbreviated stickers in the scene with ten larger cards split over two pages. Keep the menu readable at the existing play distance.
4. Run the pager test and parse the scene headlessly to catch missing resources or invalid node connections.

## Task 7: Synchronize briefing and protocol schemas

**Files:**
- Modify: `ai_play/src/ai_play/conveyor_profit_briefing.py`
- Modify: `ai_play/src/ai_play/action_schema.py`
- Modify: `ai_play/src/ai_play/observation_schema.py`
- Modify: `ai_play/tests/test_briefing.py`
- Modify: `ai_play/tests/test_action_schema.py`
- Modify: `ai_play/tests/test_observation_schema.py`
- Add: `tests/conveyor_profit/test_protocol_parity.py`

1. Add failing Python tests for the sixteen selectable IDs, `recipe_limit_exceeded`, optional current-receipt `recipe_id`, and exact Python/Godot parity.
2. Replace the briefing test with the approved public text: ten-recipe menu, costs, one make per window, exact combinations, two-success recipe limit, tray capacity five, self-tracked accepted receipts, and 80% global objective.
3. Add negative assertions ensuring briefing and observations do not reveal deck names, fixed window contents, number of feasible recipes, missing-one decoy strategy, current quota counts, canonical route, or theoretical optimum answer.
4. Update both schema layers together and keep strict rejection of unknown IDs/outcomes/fields.
5. Run all conveyor Python protocol and briefing tests.

## Task 8: Documentation and complete local verification

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/wiki/wiki.md` only if a new page is added

1. Document the public ten-recipe contract, tray capacity, quota outcome, and global scoring semantics in `ai_play/README.md` without exposing authored puzzle answers to runtime clients.
2. Update the Wiki architecture description to match the final class ownership, fixed-deck selection, DP state, and privacy boundary.
3. Run the smallest focused tests after each task, then run the complete conveyor-profit Python and GDScript suites using the repository commands documented in the contributor guide.
4. Launch the conveyor scene locally in Godot for a bounded smoke test: verify both menu pages, sixteen visible plates, window advance, quota penalty, and clean emergency stop. This is local engine verification, not a real external MCP client run.
5. Run `git diff --check` and inspect `git status --short`; preserve unrelated `tests/__pycache__/` and `tools/__pycache__/` directories.
6. Commit implementation in coherent task-sized commits and push `feature/session-awm` only after all available verification passes. Real Codex/MCP acceptance remains a separately confirmed action because it persists screenshots, tokens, costs, and traces.
