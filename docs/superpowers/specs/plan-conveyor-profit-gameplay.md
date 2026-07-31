# Conveyor Profit Playable Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the approved conveyor scene into a complete human-playable loop with deterministic finite supply, exact recipe matching, tray undo, settlement, and success/failure state.

**Architecture:** Keep economy rules in pure `RefCounted` classes so headless tests can prove them without a scene. A scene controller owns only public runtime state and visuals; every ingredient click enters through `IngredientInteractable.select()`, which is also the future pixel-hit MCP seam. This plan deliberately excludes Lobby registration and Python/MCP protocol changes.

**Tech Stack:** Godot 4.7, typed GDScript, `Area3D` input picking, existing conveyor scenes, headless SceneTree tests.

---

## Planned File Structure

- `conveyor_profit/scripts/recipe_catalog.gd`: immutable ingredient costs, recipes, exact multiset matching, and attainable-profit calculation.
- `conveyor_profit/scripts/profit_session.gd`: tray and economic state machine.
- `conveyor_profit/scripts/supply_generator.gd`: deterministic finite batch generation with a hidden solvability witness.
- `conveyor_profit/scripts/ingredient_interactable.gd`: common human/future-MCP selection seam.
- `conveyor_profit/scripts/conveyor_action_button.gd`: MAKE/UNDO input adapter.
- `conveyor_profit/scripts/conveyor_gameplay.gd`: scene inventory, replenishment, tray visuals, HUD, and terminal presentation.
- `tests/conveyor_profit/test_recipe_catalog.gd`: exact recipe and attainable-profit tests.
- `tests/conveyor_profit/test_profit_session.gd`: settlement, undo, invalid recipe, and terminal freeze tests.
- `tests/conveyor_profit/test_supply_generator.gd`: determinism, finite batch, and solvability property tests.
- `tests/conveyor_profit/test_conveyor_gameplay.gd`: real scene selection, button actions, and public HUD tests.

## Task 1: Recipe Catalog and Economic State Machine

**Files:**
- Create: `tests/conveyor_profit/test_recipe_catalog.gd`
- Create: `tests/conveyor_profit/test_profit_session.gd`
- Create: `conveyor_profit/scripts/recipe_catalog.gd`
- Create: `conveyor_profit/scripts/profit_session.gd`

- [ ] **Step 1: Write failing catalog tests**

Test that `find_recipe(["tomato", "mushroom", "lettuce"])` returns salad regardless of order, duplicates do not match, unknown ingredients do not match, costs equal the approved table, and `max_attainable_profit()` returns 7 for one fish sandwich and 14 for two.

- [ ] **Step 2: Verify catalog RED**

Run:

```bash
godot --headless --log-file /private/tmp/conveyor_catalog_red.log --path . --script tests/conveyor_profit/test_recipe_catalog.gd
```

Expected: non-zero because `recipe_catalog.gd` is absent.

- [ ] **Step 3: Implement `RecipeCatalog`**

Define the exact eight costs and six recipe dictionaries from the approved spec. Canonicalize multisets by sorting a copied `Array[String]`. `find_recipe()` returns a duplicated recipe dictionary or `{}`. Implement `max_attainable_profit()` as memoized recursive recipe packing over a cost-independent ingredient-count signature; this function is internal gameplay logic and is never exposed by MCP observations.

- [ ] **Step 4: Verify catalog GREEN**

Run the catalog test and expect exit 0.

- [ ] **Step 5: Write failing session tests**

Cover these exact state transitions:

```text
select bread, egg; undo -> egg; select egg; make -> egg_toast, spent 4, revenue 8, profit 4
select bread, tomato; make -> invalid, spent 3, revenue unchanged, profit decreases by 3
profit reaches target -> success/profit_target_reached and later select/make are rejected
current profit plus attainable remaining profit below target -> failure/profit_target_unreachable
```

- [ ] **Step 6: Verify session RED**

Run the new session test and expect non-zero because `profit_session.gd` is absent.

- [ ] **Step 7: Implement `ProfitSession`**

Expose `select_ingredient(id) -> bool`, `undo() -> String`, `make() -> Dictionary`, `evaluate_reachability(available_ids) -> String`, `get_profit() -> int`, and read-only public state fields. Validate IDs through `RecipeCatalog`, charge selected costs only on MAKE, clear the tray after every MAKE, and reject all mutations after terminal state.

- [ ] **Step 8: Verify both GREEN and commit**

Run both tests, then:

```bash
git add conveyor_profit/scripts/recipe_catalog.gd conveyor_profit/scripts/profit_session.gd tests/conveyor_profit/test_recipe_catalog.gd tests/conveyor_profit/test_profit_session.gd
git commit -m "feat(conveyor-profit): add recipe and profit rules"
```

## Task 2: Deterministic Solvable Supply

**Files:**
- Create: `tests/conveyor_profit/test_supply_generator.gd`
- Create: `conveyor_profit/scripts/supply_generator.gd`

- [ ] **Step 1: Write the failing property test**

For seeds `0, 1, 2, 7, 42, 999`, assert two calls with the same seed return equal non-empty arrays, every ID has a catalog cost, batches remain under 128 items, and `RecipeCatalog.max_attainable_profit(batch) >= 120`.

- [ ] **Step 2: Verify RED**

Run the supply test and expect non-zero because `supply_generator.gd` is absent.

- [ ] **Step 3: Implement minimal generator**

Use a locally seeded `RandomNumberGenerator`. Randomly choose approved recipes, append their ingredient IDs, and accumulate their published profit until the hidden witness reaches the requested minimum. Fisher-Yates shuffle the copied ID array with the same RNG and return only the shuffled IDs.

- [ ] **Step 4: Verify GREEN and commit**

Run catalog, session, and supply tests, then:

```bash
git add conveyor_profit/scripts/supply_generator.gd tests/conveyor_profit/test_supply_generator.gd
git commit -m "feat(conveyor-profit): generate solvable finite supply"
```

## Task 3: Shared Click Seam and Playable Scene Controller

**Files:**
- Create: `tests/conveyor_profit/test_conveyor_gameplay.gd`
- Create: `conveyor_profit/scripts/ingredient_interactable.gd`
- Create: `conveyor_profit/scripts/conveyor_action_button.gd`
- Create: `conveyor_profit/scripts/conveyor_gameplay.gd`
- Modify: `conveyor_profit/scripts/conveyor_environment.gd`
- Modify: `conveyor_profit/scenes/ingredient_preview.tscn`
- Modify: `conveyor_profit/scenes/conveyor_profit_environment.tscn`

- [ ] **Step 1: Write the failing scene test**

Instantiate the real environment, wait one frame, and assert:

```text
Gameplay exists and exposes profit 0, selected count 0, non-empty finite remaining count
each available follower owns IngredientPreview/Interactable Area3D with a collision shape
calling the first interactable.select() changes selected count to 1 and TRAY label from EMPTY
calling UndoButton.activate() returns selected count to 0
selecting exact bread+egg interactables then MakeButton.activate() produces profit 4
HUD reads NET PROFIT $4 / $100
```

Use interactable nodes rather than selecting by ingredient name; the test may search visible metadata only to arrange the recipe.

- [ ] **Step 2: Verify RED**

Run the gameplay scene test and expect non-zero because the gameplay node and scripts are absent.

- [ ] **Step 3: Implement input adapters**

`IngredientInteractable` extends `Area3D`, exports `instance_id`, emits `select_requested(instance_id)`, and routes left mouse `_input_event` to `select()`. `ConveyorActionButton` extends `StaticBody3D`, exports an `action` enum-like string, emits `activated(action)`, routes left mouse input to `activate()`, and contains no economy logic.

- [ ] **Step 4: Implement scene controller**

`ConveyorGameplay` owns a `ProfitSession`, generates supply with exported seed `1337`, fills sixteen existing followers, and connects only opaque instance IDs from interactables. Selection records the ingredient, updates the tray with small ingredient visuals, and immediately replenishes that follower from pending supply. Undo returns the last ID to the pending supply. MAKE settles, clears tray visuals, updates public labels, evaluates reachability from pending plus visible ingredients, and freezes input on terminal state.

- [ ] **Step 5: Adapt environment construction**

Move ingredient definition/model helpers into the gameplay controller. Keep `ConveyorEnvironment` responsible for path construction and initial follower placement only. Add `Gameplay` under the scene root, a `SelectedVisuals` node under `Stations/Tray`, collision-backed interactables to the ingredient preview, collision shapes to both action buttons, and connect all signals in code to avoid brittle dynamic scene connections.

- [ ] **Step 6: Verify GREEN and commit**

Run all four gameplay-domain tests plus existing motion and scene contract tests. Expect exit 0, then:

```bash
git add conveyor_profit/scripts conveyor_profit/scenes tests/conveyor_profit/test_conveyor_gameplay.gd
git commit -m "feat(conveyor-profit): add playable cooking loop"
```

## Task 4: Runtime Review and Documentation

**Files:**
- Modify: `conveyor_profit/README.md`
- Modify: `tools/render_conveyor_profit_preview.gd` only if deterministic visual settling requires it.

- [ ] **Step 1: Document controls and scope**

Document left-click ingredient selection, left-click MAKE/UNDO, exact recipe matching, invalid-combo consumption, deterministic default seed, and terminal conditions. State that Lobby/MCP integration remains the next milestone and that no semantic choose-by-name action exists.

- [ ] **Step 2: Parse and run full affected tests**

Run:

```bash
godot --headless --log-file /private/tmp/conveyor_import_gameplay.log --path . --editor --quit
godot --headless --log-file /private/tmp/conveyor_motion_gameplay.log --path . --script tests/conveyor_profit/test_conveyor_motion.gd
godot --headless --log-file /private/tmp/conveyor_scene_gameplay.log --path . --script tests/conveyor_profit/test_conveyor_profit_scene.gd
godot --headless --log-file /private/tmp/conveyor_catalog_gameplay.log --path . --script tests/conveyor_profit/test_recipe_catalog.gd
godot --headless --log-file /private/tmp/conveyor_session_gameplay.log --path . --script tests/conveyor_profit/test_profit_session.gd
godot --headless --log-file /private/tmp/conveyor_supply_gameplay.log --path . --script tests/conveyor_profit/test_supply_generator.gd
godot --headless --log-file /private/tmp/conveyor_controller_gameplay.log --path . --script tests/conveyor_profit/test_conveyor_gameplay.gd
git diff --check
```

- [ ] **Step 3: Run human interaction review**

Launch `conveyor_profit_preview.tscn`, select bread and egg through visible 3D hit areas, press MAKE, and confirm the tray and HUD show a +4 result. This is local human review only; do not run a real external MCP client.

- [ ] **Step 4: Commit documentation**

```bash
git add conveyor_profit/README.md docs/superpowers/specs/plan-conveyor-profit-gameplay.md
git commit -m "docs(conveyor-profit): document playable loop"
```

## Task 5: Final Verification and Handoff

- [ ] **Step 1: Re-run the complete command list from Task 4**

Expected: all commands exit 0. Existing macOS certificate/Jolt warnings may remain, but no new parse, script, scene, or assertion errors are allowed.

- [ ] **Step 2: Verify repository state**

Run `git diff --check`, `git status --short --branch`, and `git log -8 --oneline`. No runtime screenshot, log, memory, or `.godot/` cache may be tracked.

- [ ] **Step 3: Present for review**

Report branch/worktree, commit hashes, test evidence, local human-review status, and that MCP/Lobby integration is intentionally the next independent milestone.
