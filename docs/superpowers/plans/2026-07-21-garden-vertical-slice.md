# Garden Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an isolated `garden` COGITO variant with one playable sunflower-garden loop, a finite watering can, a refill tap, compressed time, failure/retry, basic HUD, and a correctly scaled neighborhood graybox.

**Architecture:** Keep upstream COGITO under `addons/` unchanged and put game content under `garden/`. Pure simulation nodes expose deterministic methods for headless tests; scene adapters connect them to COGITO input, inventory, HUD, and interactions.

**Tech Stack:** Godot 4.7 stable, GDScript, COGITO `WieldableItemPD`, COGITO interactions, shell contracts, headless SceneTree tests.

## Global Constraints

- Copy the current working tree exactly into `/Users/jan/workspace/cogito_variants/garden`; never clean or mutate the source checkout.
- Work on a new `garden` branch in the copied repository.
- Rename the Godot project to `Garden`; main scene is `res://garden/scenes/garden_vertical_slice.tscn`.
- Preserve copied uncommitted changes but stage only garden-specific files.
- Style is bright, friendly, and low-poly.
- Player walk/sprint speeds remain 4 m/s and 7 m/s.
- Target a 38-real-minute 08:00-17:00 day; tests may override the time scale.
- Plant death or a missed deadline fails the day; retry resets to 08:00.
- Resume state is only for voluntary exit and cannot survive failure.
- Follow test-first development for every behavior.

## File Map

- `project.godot`: Garden identity and main scene.
- `garden/scripts/garden_plant.gd`: moisture, health, watering, drying, and death.
- `garden/scripts/garden_plant_group.gd`: group watering-window completion.
- `garden/scripts/garden_watering_can.gd`: continuous wieldable watering and charge drain.
- `garden/scripts/garden_refill_station.gd`: tap refill validation.
- `garden/scripts/garden_time_system.gd`: deterministic compressed clock.
- `garden/scripts/garden_game_manager.gd`: objective, failure, and retry lifecycle.
- `garden/scripts/garden_hud.gd`: clock, objective, capacity, condition, and failure UI.
- `garden/scripts/garden_route_marker.gd`: route-distance checks.
- `garden/resources/garden_watering_can_item.tres`: 100-unit wieldable item.
- `garden/scenes/`: watering tool, tap, sunflower, HUD, and playable graybox scenes.
- `tests/garden/`: shell and GDScript contracts.

---

### Task 1: Create and identify the isolated Garden variant

**Files:**
- Create: `tests/garden/check_variant_setup.sh`
- Modify: `project.godot`
- Create: `garden/README.md`

**Interfaces:**
- Consumes: current `Phazorknight-Cogito` working tree.
- Produces: isolated repository on `garden`, project `Garden`, content root `garden/`.

- [ ] **Step 1: Validate targets**

Run:

```bash
test -d /Users/jan/workspace/Phazorknight-Cogito/.git
test ! -e /Users/jan/workspace/cogito_variants/garden
```

Expected: both exit 0. Stop if the destination exists.

- [ ] **Step 2: Copy and branch**

Run each command separately:

```bash
mkdir -p /Users/jan/workspace/cogito_variants
cp -a /Users/jan/workspace/Phazorknight-Cogito /Users/jan/workspace/cogito_variants/garden
git -C /Users/jan/workspace/cogito_variants/garden switch -c garden
```

Expected: the copied status matches the source status and current branch prints `garden`.

- [ ] **Step 3: Write the failing setup contract**

```bash
#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd -P)"
test "$(git -C "$repo" branch --show-current)" = "garden"
rg -q '^config/name="Garden"$' "$repo/project.godot"
rg -q '^run/main_scene="res://garden/scenes/garden_vertical_slice.tscn"$' "$repo/project.godot"
test -f "$repo/garden/README.md"
```

- [ ] **Step 4: Verify RED**

Run: `bash tests/garden/check_variant_setup.sh`

Expected: FAIL because the project is still named Cogito.

- [ ] **Step 5: Apply minimal identity**

Set:

```ini
config/name="Garden"
run/main_scene="res://garden/scenes/garden_vertical_slice.tscn"
```

Document launch as `godot --path /Users/jan/workspace/cogito_variants/garden`.

- [ ] **Step 6: Verify GREEN and commit**

Run: `bash tests/garden/check_variant_setup.sh`

Expected: PASS.

```bash
git add project.godot garden/README.md tests/garden/check_variant_setup.sh
git commit -m "chore: create garden game variant"
```

---

### Task 2: Implement deterministic plant simulation

**Files:**
- Create: `garden/scripts/garden_plant.gd`
- Create: `garden/scripts/garden_plant_group.gd`
- Create: `tests/garden/test_garden_plant.gd`

**Interfaces:**
- Produces: `GardenPlant.apply_water(amount)`, `simulate(seconds)`, `condition()`, `mark_window(id)`, `reset_plant()`, signals `condition_changed`, `died`.
- Produces: `GardenPlantGroup.is_complete()`, `has_dead_plant()`, `reset_group()`.

- [ ] **Step 1: Write failing tests**

Configure a plant with moisture 50, safe range 40-70, dry rate 1, and health 100. Assert watering raises moisture, simulation dries it, saturation and drought damage health, zero health emits death once, conditions are `dry`/`healthy`/`too_wet`, and a group completes only when every plant marks `sunflower_morning`.

```gdscript
plant.apply_water(10.0)
_assert(is_equal_approx(plant.moisture, 60.0), "watering increases moisture")
plant.simulate(10.0)
_assert(is_equal_approx(plant.moisture, 50.0), "simulation dries soil")
```

- [ ] **Step 2: Verify RED**

Run: `godot --headless --path . --script tests/garden/test_garden_plant.gd`

Expected: missing `GardenPlant` script.

- [ ] **Step 3: Implement minimal simulation**

```gdscript
class_name GardenPlant
extends Node3D

signal condition_changed(value: String)
signal died

@export var moisture := 35.0
@export var health := 100.0
@export var safe_min := 40.0
@export var safe_max := 70.0
@export var dry_rate := 0.02
@export var damage_rate := 2.0
var is_dead := false
var completed_windows: Dictionary = {}

func apply_water(amount: float) -> void:
	if not is_dead and amount > 0.0:
		moisture = clampf(moisture + amount, 0.0, 100.0)

func simulate(seconds: float) -> void:
	if is_dead or seconds <= 0.0: return
	moisture = maxf(0.0, moisture - dry_rate * seconds)
	if moisture < safe_min or moisture > safe_max:
		health = maxf(0.0, health - damage_rate * seconds)
	if health <= 0.0:
		is_dead = true
		died.emit()

func condition() -> String:
	if moisture < safe_min: return "dry"
	if moisture > safe_max: return "too_wet"
	return "healthy"
```

The group owns `required_windows: Array[String]` and checks each child plant's `completed_windows`.

- [ ] **Step 4: Verify GREEN and commit**

Run: `godot --headless --path . --script tests/garden/test_garden_plant.gd`

Expected: `Garden plant tests passed`.

```bash
git add garden/scripts/garden_plant.gd garden/scripts/garden_plant_group.gd tests/garden/test_garden_plant.gd
git commit -m "feat: simulate garden plant health"
```

---

### Task 3: Add finite watering and refill

**Files:**
- Create: `garden/scripts/garden_watering_can.gd`
- Create: `garden/scripts/garden_refill_station.gd`
- Create: `garden/resources/garden_watering_can_item.tres`
- Create: `garden/scenes/garden_watering_can_wieldable.tscn`
- Create: `garden/scenes/garden_watering_can_pickup.tscn`
- Create: `garden/scenes/garden_refill_station.tscn`
- Create: `tests/garden/test_garden_watering.gd`

**Interfaces:**
- Consumes: `GardenPlant.apply_water` and `WieldableItemPD.subtract/add`.
- Produces: `tick_watering(delta, target) -> float` and `refill(item, amount) -> float`.

- [ ] **Step 1: Write failing tests**

With a 100-unit item and rate 10, assert one second delivers 10 and leaves 90, empty and invalid targets deliver zero, and refill clamps at 100.

```gdscript
var delivered := can.tick_watering(1.0, plant)
_assert(is_equal_approx(delivered, 10.0), "delivers configured water")
_assert(is_equal_approx(item.charge_current, 90.0), "drains finite charge")
```

- [ ] **Step 2: Verify RED**

Run: `godot --headless --path . --script tests/garden/test_garden_watering.gd`

Expected: missing watering scripts.

- [ ] **Step 3: Implement drain, delivery, and refill**

`tick_watering` computes `minf(water_rate * delta, charge_current)`, subtracts exactly that amount, and applies it to a valid plant. `action_primary(item, is_released)` tracks held state; `_physics_process` waters only a `GardenPlant` hit within 2.2 meters. Refill rejects other items and returns the exact added charge.

- [ ] **Step 4: Create resources/scenes**

Set item values:

```text
name = "Watering Can"
charge_max = 100.0
charge_current = 100.0
no_reload = true
hint_on_empty = "The watering can is empty. Refill it at the shared tap."
wieldable_range = 2.2
```

The wieldable contains `AnimationPlayer`, `AudioStreamPlayer3D`, placeholder can mesh, water particles, and `RayCast3D`. The tap uses `CogitoStaticInteractable` and `BasicInteraction` labelled `Refill watering can`.

- [ ] **Step 5: Verify GREEN and commit**

Run: `godot --headless --path . --script tests/garden/test_garden_watering.gd`

Expected: `Garden watering tests passed`.

```bash
git add garden/scripts/garden_watering_can.gd garden/scripts/garden_refill_station.gd garden/resources garden/scenes/garden_watering_can_wieldable.tscn garden/scenes/garden_watering_can_pickup.tscn garden/scenes/garden_refill_station.tscn tests/garden/test_garden_watering.gd
git commit -m "feat: add finite watering and refill"
```

---

### Task 4: Add clock and day lifecycle

**Files:**
- Create: `garden/scripts/garden_time_system.gd`
- Create: `garden/scripts/garden_game_manager.gd`
- Create: `tests/garden/test_garden_time_and_game.gd`

**Interfaces:**
- Produces: `advance(real_seconds)`, `minutes_since_midnight`, `formatted_time()`, signals `time_changed`, `deadline_reached`.
- Produces: `start_day()`, `fail_day(reason)`, `retry_day()`, signals `objective_changed`, `day_failed`.

- [ ] **Step 1: Write failing tests**

Assert 38 real minutes advances 540 game minutes, start formats `08:00`, pause prevents advance, 10:00 fires once, death fails immediately, missed sunflower completion fails at 10:00, and retry resets time/plants.

- [ ] **Step 2: Verify RED**

Run: `godot --headless --path . --script tests/garden/test_garden_time_and_game.gd`

Expected: missing time scripts.

- [ ] **Step 3: Implement clock and manager**

```gdscript
const START_MINUTE := 8 * 60
const END_MINUTE := 17 * 60
@export var real_day_seconds := 38.0 * 60.0
var minutes_since_midnight := float(START_MINUTE)

func advance(real_seconds: float) -> void:
	if paused or real_seconds <= 0.0: return
	minutes_since_midnight = minf(END_MINUTE,
		minutes_since_midnight + real_seconds * float(END_MINUTE - START_MINUTE) / real_day_seconds)
```

The manager starts with `Collect the watering can and water every sunflower before 10:00.`, connects plant death to failure, evaluates the group at 10:00, pauses simulation on failure, and resets all owned systems on retry.

- [ ] **Step 4: Verify GREEN and commit**

Run: `godot --headless --path . --script tests/garden/test_garden_time_and_game.gd`

Expected: `Garden time and game tests passed`.

```bash
git add garden/scripts/garden_time_system.gd garden/scripts/garden_game_manager.gd tests/garden/test_garden_time_and_game.gd
git commit -m "feat: add compressed garden day"
```

---

### Task 5: Build playable graybox and HUD

**Files:**
- Create: `garden/scripts/garden_hud.gd`
- Create: `garden/scripts/garden_route_marker.gd`
- Create: `garden/scenes/garden_hud.tscn`
- Create: `garden/scenes/sunflower_plant.tscn`
- Create: `garden/scenes/garden_vertical_slice.tscn`
- Create: `tests/garden/test_garden_scene.gd`

**Interfaces:**
- Consumes: all prior components and COGITO player.
- Produces: launchable main scene and route metrics.

- [ ] **Step 1: Write failing scene tests**

Load the packed scene and assert one player, manager, clock, tap, can pickup and HUD; six nodes in `garden_sunflowers`; collision for walkable surfaces; start-to-garden distance 35-45 meters; garden-to-tap distance 12-20 meters.

- [ ] **Step 2: Verify RED**

Run: `godot --headless --path . --script tests/garden/test_garden_scene.gd`

Expected: packed scene missing.

- [ ] **Step 3: Build sunflower and HUD scenes**

Use low-poly stem/head meshes, soil dry/healthy/wet material variants, collision, and `GardenPlant`. HUD labels are `ClockLabel`, `ObjectiveLabel`, `CanLabel`, `ConditionLabel`, plus hidden `FailurePanel/RetryButton`. Capacity displays `Water: 73 / 100`; moisture/health numbers remain hidden.

- [ ] **Step 4: Build the graybox**

Build a 75-by-55-meter ground, main road, start room, one 12-by-10-meter house, one 14-by-12-meter fenced garden, six sunflowers, tap, pickup, COGITO player, managers, environment, sun, route markers, and HUD. Use distinct path/grass colors and visible landmarks.

- [ ] **Step 5: Verify GREEN and import**

Run separately:

```bash
godot --headless --path . --script tests/garden/test_garden_scene.gd
godot --headless --path . --editor --quit
```

Expected: scene tests pass and import has no parse errors.

- [ ] **Step 6: Commit**

```bash
git add garden/scripts/garden_hud.gd garden/scripts/garden_route_marker.gd garden/scenes/garden_hud.tscn garden/scenes/sunflower_plant.tscn garden/scenes/garden_vertical_slice.tscn tests/garden/test_garden_scene.gd
git commit -m "feat: build sunflower garden slice"
```

---

### Task 6: Aggregate verification and guide

**Files:**
- Create: `tests/garden/run_all.sh`
- Modify: `garden/README.md`

**Interfaces:**
- Produces: one verification command and manual playtest procedure.

- [ ] **Step 1: Write aggregate runner**

```bash
#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd -P)"
cd "$repo"
bash tests/garden/check_variant_setup.sh
for script in test_garden_plant.gd test_garden_watering.gd test_garden_time_and_game.gd test_garden_scene.gd; do
	godot --headless --path . --script "tests/garden/$script"
done
godot --headless --path . --editor --quit
```

- [ ] **Step 2: Run aggregate verification**

Run: `bash tests/garden/run_all.sh`

Expected: all suites pass and editor import exits 0.

- [ ] **Step 3: Document and manually accept**

Document launch, pickup/equip, hold-to-water, refill, HUD, retry, test time scale, and route timing. Run `godot --path . garden/scenes/garden_vertical_slice.tscn` and verify actual COGITO input, capacity, refill, plant feedback, deadline failure, retry, and 9-12/3-5-second walking targets.

- [ ] **Step 4: Commit**

```bash
git add tests/garden/run_all.sh garden/README.md
git commit -m "docs: add garden slice verification"
```

## Phase 1 Completion Gate

- `bash tests/garden/run_all.sh` passes.
- Main scene launches without parser/runtime errors.
- Finite drain/refill works through real COGITO input.
- Sunflowers succeed and fail through the HUD lifecycle.
- Walking route targets pass without sprinting.
- Original checkout remains untouched except for the already approved design/plan documents.

After this gate, create follow-up plans for: full three-house graybox and hydrangeas; orchids and rain; voluntary-exit persistence and 17:00 evaluation; final low-poly art/audio/balance.
