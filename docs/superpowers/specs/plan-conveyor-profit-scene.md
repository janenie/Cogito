# Conveyor Profit Scene Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable and reviewable Godot scene showing the U-shaped looping conveyor, eight distinct food ingredients, kitchen set dressing, menu board, tray, controls, and profit HUD.

**Architecture:** Keep the reusable environment in `conveyor_profit_environment.tscn` and place the preview-only camera, world environment, and render harness in separate files. A focused `ConveyorMotion` helper owns deterministic closed-loop progress math, while `ConveyorPreview` only advances `PathFollow3D` children; no economy or MCP behavior enters this visual milestone.

**Tech Stack:** Godot 4.7, typed GDScript, `.tscn` scenes, Kenney Food Kit 2.0 CC0 GLB models, existing Cogito/Kenney furniture assets.

---

## Planned File Structure

- `conveyor_profit/README.md`: launch instructions and asset provenance.
- `conveyor_profit/assets/kenney_food_kit/{LICENSE.txt,SOURCE.md}`: CC0 and exact source mapping.
- `conveyor_profit/assets/kenney_food_kit/models/*.glb`: eight ingredients and one plate.
- `conveyor_profit/scripts/conveyor_motion.gd`: pure closed-loop progress calculation.
- `conveyor_profit/scripts/conveyor_preview.gd`: preview-only `PathFollow3D` advancement.
- `conveyor_profit/scenes/ingredient_preview.tscn`: shared ingredient visual.
- `conveyor_profit/scenes/conveyor_profit_environment.tscn`: reusable environment without player/camera.
- `conveyor_profit/scenes/conveyor_profit_preview.tscn`: standalone review scene.
- `tests/conveyor_profit/test_conveyor_motion.gd`: deterministic motion tests.
- `tests/conveyor_profit/test_conveyor_profit_scene.gd`: scene contract tests.
- `tools/render_conveyor_profit_preview.gd`: deterministic review PNG renderer.

## Task 1: Acquire and Record the CC0 Food Assets

**Files:**
- Create: `conveyor_profit/assets/kenney_food_kit/LICENSE.txt`
- Create: `conveyor_profit/assets/kenney_food_kit/SOURCE.md`
- Create: `conveyor_profit/assets/kenney_food_kit/models/bread.glb`
- Create: `conveyor_profit/assets/kenney_food_kit/models/lettuce.glb`
- Create: `conveyor_profit/assets/kenney_food_kit/models/tomato.glb`
- Create: `conveyor_profit/assets/kenney_food_kit/models/cheese.glb`
- Create: `conveyor_profit/assets/kenney_food_kit/models/egg.glb`
- Create: `conveyor_profit/assets/kenney_food_kit/models/mushroom.glb`
- Create: `conveyor_profit/assets/kenney_food_kit/models/fish.glb`
- Create: `conveyor_profit/assets/kenney_food_kit/models/meat.glb`
- Create: `conveyor_profit/assets/kenney_food_kit/models/plate.glb`

- [ ] **Step 1: Download into a temporary directory**

Download Food Kit 2.0 from `https://www.kenney.nl/assets/food-kit`, keep the archive outside the repository, and extract it under `mktemp -d`.

- [ ] **Step 2: Inspect and select exact GLBs**

Run:

```bash
find "$food_kit_temp" -type f -name '*.glb' | sort
```

Choose one unambiguous model for each approved ingredient and one plate. Copy only those nine files to the stable destination names above. Record variant mappings such as steak → `meat.glb`.

- [ ] **Step 3: Record source and license**

`SOURCE.md` records the official URL, `Food Kit 2.0`, download date `2026-07-31`, original filename for every renamed GLB, and that only the selected models were copied. Copy the pack's bundled CC0 file unchanged to `LICENSE.txt`.

- [ ] **Step 4: Verify bounded scope**

```bash
find conveyor_profit/assets/kenney_food_kit -type f | sort
du -sh conveyor_profit/assets/kenney_food_kit
```

Expected: two provenance files and exactly nine GLBs; no archive, FBX, OBJ, Blend, generated `.import`, or render file is tracked.

- [ ] **Step 5: Commit**

```bash
git add conveyor_profit/assets/kenney_food_kit
git commit -m "assets(conveyor-profit): import selected CC0 food models"
```

## Task 2: Implement Deterministic Closed-Loop Motion with TDD

**Files:**
- Create: `tests/conveyor_profit/test_conveyor_motion.gd`
- Create: `conveyor_profit/scripts/conveyor_motion.gd`
- Create: `conveyor_profit/scripts/conveyor_preview.gd`

- [ ] **Step 1: Write the failing test**

```gdscript
extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var motion: GDScript = load("res://conveyor_profit/scripts/conveyor_motion.gd")
	_check(is_equal_approx(motion.advance(2.0, 1.5, 2.0, 10.0), 5.0), "advances")
	_check(is_equal_approx(motion.advance(9.0, 2.0, 1.0, 10.0), 1.0), "wraps forward")
	_check(is_equal_approx(motion.advance(0.5, -1.0, 1.0, 10.0), 9.5), "wraps reverse")
	_check(is_equal_approx(motion.advance(4.0, 3.0, 0.0, 10.0), 4.0), "zero delta")
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
```

- [ ] **Step 2: Verify RED**

```bash
godot --headless --path . --script tests/conveyor_profit/test_conveyor_motion.gd
```

Expected: non-zero because `conveyor_motion.gd` does not exist.

- [ ] **Step 3: Implement the pure helper**

```gdscript
class_name ConveyorMotion
extends RefCounted


static func advance(progress: float, speed: float, delta: float, path_length: float) -> float:
	if path_length <= 0.0:
		return 0.0
	return wrapf(progress + speed * delta, 0.0, path_length)
```

- [ ] **Step 4: Implement the scene adapter**

Create:

```gdscript
class_name ConveyorPreview
extends Path3D

@export_range(-10.0, 10.0, 0.05) var speed_meters_per_second: float = 1.2


func _process(delta: float) -> void:
	if curve == null:
		return
	var path_length: float = curve.get_baked_length()
	if path_length <= 0.0:
		return
	for child: Node in get_children():
		if child is PathFollow3D:
			child.progress = ConveyorMotion.advance(
				child.progress,
				speed_meters_per_second,
				delta,
				path_length,
			)
```

- [ ] **Step 5: Verify GREEN**

```bash
godot --headless --path . --script tests/conveyor_profit/test_conveyor_motion.gd
```

Expected: exit 0 without pushed errors.

- [ ] **Step 6: Commit**

```bash
git add conveyor_profit/scripts tests/conveyor_profit/test_conveyor_motion.gd
git commit -m "feat(conveyor-profit): add closed-loop preview motion"
```

## Task 3: Build the Reusable U-Shaped Environment

**Files:**
- Create: `tests/conveyor_profit/test_conveyor_profit_scene.gd`
- Create: `conveyor_profit/scenes/ingredient_preview.tscn`
- Create: `conveyor_profit/scenes/conveyor_profit_environment.tscn`

- [ ] **Step 1: Write the failing scene contract test**

Load and instantiate the environment, then make these exact assertions:

```gdscript
_check(environment.has_node("Architecture/Conveyor"), "conveyor exists")
_check(environment.has_node("Architecture/Conveyor/IngredientPath"), "path exists")
_check(environment.has_node("Stations/MenuBoard"), "menu exists")
_check(environment.has_node("Stations/Tray"), "tray exists")
_check(environment.has_node("Stations/MakeButton"), "make button exists")
_check(environment.has_node("Stations/UndoButton"), "undo button exists")
_check(environment.has_node("HUD/ProfitLabel"), "profit label exists")
var path := environment.get_node("Architecture/Conveyor/IngredientPath") as Path3D
_check(path.curve.closed, "path is closed")
_check(path.get_child_count() == 16, "sixteen food slots exist")
var ingredient_ids: Dictionary = {}
for follower: Node in path.get_children():
	ingredient_ids[follower.get_meta("ingredient_id", "")] = true
_check(ingredient_ids.keys().size() == 8, "all ingredient types exist")
```

The test frees the scene and exits non-zero on failure.

- [ ] **Step 2: Verify RED**

```bash
godot --headless --path . --script tests/conveyor_profit/test_conveyor_profit_scene.gd
```

Expected: non-zero because the environment scene is absent.

- [ ] **Step 3: Create the ingredient visual**

Use a `Node3D` root, imported food scene, shallow plate/pedestal, and `Label3D` named `CostLabel`. The environment overrides model, label, and accent color per instance. This milestone adds no gameplay script.

- [ ] **Step 4: Build room and conveyor**

Build an approximately 14 m × 11 m room using static meshes and collisions. Construct the U conveyor from three dark straight belt sections, rounded corner covers, orange rails, and cylinder rollers. Add a closed `Curve3D` above the surface and attach `ConveyorPreview` to `IngredientPath`.

- [ ] **Step 5: Place sixteen slots**

Add sixteen looping `PathFollow3D` nodes distributed over the baked path. Use two instances of each ingredient ID, keep food upright, and show its cost.

- [ ] **Step 6: Add station and set dressing**

Create the menu and tray from local primitives and the imported plate. Reuse repository `kitchenBar`, `kitchenFridge`, `kitchenStove`, `kitchenSink`, and `lamp_square_ceiling`. Instance `generic_button.tscn` twice as `MAKE` and `UNDO`, without gameplay signals.

- [ ] **Step 7: Add review text**

Show all six approved recipes, ingredient costs, sale price, and profit. HUD text is `NET PROFIT  $0 / $100`; tray text is `TRAY  EMPTY`. Use off-white text on dark panels with orange highlights.

- [ ] **Step 8: Verify GREEN**

```bash
godot --headless --path . --script tests/conveyor_profit/test_conveyor_profit_scene.gd
```

Expected: exit 0 with all nodes, a closed path, sixteen slots, and eight ingredient IDs.

- [ ] **Step 9: Commit**

```bash
git add conveyor_profit/scenes tests/conveyor_profit/test_conveyor_profit_scene.gd
git commit -m "feat(conveyor-profit): build U-shaped kitchen environment"
```

## Task 4: Create the Standalone Review Scene and Renderer

**Files:**
- Create: `conveyor_profit/scenes/conveyor_profit_preview.tscn`
- Create: `tools/render_conveyor_profit_preview.gd`
- Create: `conveyor_profit/README.md`

- [ ] **Step 1: Add the preview wrapper**

Instance the reusable environment; add a current `Camera3D` at the human standing position, a neutral `WorldEnvironment`, a warm key light, and cool fill light. Frame both conveyor arms, front belt, menu, tray, controls, and profit HUD in one 16:9 view.

- [ ] **Step 2: Add the renderer**

Create:

```gdscript
extends SceneTree

const PREVIEW_SCENE := "res://conveyor_profit/scenes/conveyor_profit_preview.tscn"
const OUTPUT_PREFIX := "--output="


func _initialize() -> void:
	call_deferred("_render_preview")


func _render_preview() -> void:
	var output_path: String = ""
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with(OUTPUT_PREFIX):
			output_path = argument.trim_prefix(OUTPUT_PREFIX)
	if output_path.is_empty() or not output_path.is_absolute_path():
		push_error("--output must be an absolute path")
		quit(2)
		return
	root.size = Vector2i(1280, 720)
	var change_error: Error = change_scene_to_file(PREVIEW_SCENE)
	if change_error != OK:
		push_error("could not load preview scene")
		quit(3)
		return
	await scene_changed
	for _index: int in range(4):
		await process_frame
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	var save_error: Error = image.save_png(output_path)
	if save_error != OK:
		push_error("could not save preview image")
		quit(4)
		return
	quit(0)
```

- [ ] **Step 3: Document the vertical slice**

Document:

```text
godot --path . conveyor_profit/scenes/conveyor_profit_preview.tscn
```

State that economy and MCP are the next milestone, and link local `SOURCE.md` and `LICENSE.txt`.

- [ ] **Step 4: Validate import and parsing**

```bash
godot --headless --path . --editor --quit
godot --headless --path . --script tests/conveyor_profit/test_conveyor_motion.gd
godot --headless --path . --script tests/conveyor_profit/test_conveyor_profit_scene.gd
```

Expected: all exit 0 without parse errors.

- [ ] **Step 5: Render the review image**

```bash
godot --path . --script tools/render_conveyor_profit_preview.gd -- --output=/tmp/conveyor-profit-preview.png
```

Expected: exit 0 and a non-empty 16:9 PNG.

- [ ] **Step 6: Inspect and iterate**

Inspect the PNG at original resolution. Require an immediately readable U shape, eight distinct foods, non-overlapping labels, readable menu, reachable controls, and no unlit or magenta meshes. Correct and re-render until all conditions hold.

- [ ] **Step 7: Commit**

```bash
git add conveyor_profit/README.md conveyor_profit/scenes/conveyor_profit_preview.tscn tools/render_conveyor_profit_preview.gd
git commit -m "feat(conveyor-profit): add standalone scene preview"
```

## Task 5: Final Verification and Review Handoff

- [ ] **Step 1: Run the full milestone verification**

```bash
godot --headless --path . --script tests/conveyor_profit/test_conveyor_motion.gd
godot --headless --path . --script tests/conveyor_profit/test_conveyor_profit_scene.gd
godot --headless --path . --editor --quit
git diff --check
git status --short
```

Expected: tests and import exit 0, diff check is empty, and status has no generated cache, archive, screenshot, or extraction file.

- [ ] **Step 2: Re-render from the verified commit**

```bash
godot --path . --script tools/render_conveyor_profit_preview.gd -- --output=/tmp/conveyor-profit-preview-final.png
```

Expected: a non-empty final PNG matching the inspected layout.

- [ ] **Step 3: Present for user review**

Provide the PNG and links to both scenes and README. State that calculation, selection, terminal monitor, and MCP are intentionally deferred until visual approval.
