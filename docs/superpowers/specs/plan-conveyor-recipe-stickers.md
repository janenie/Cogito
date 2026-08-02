# Conveyor Profit Bilingual Recipe Stickers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the abbreviated recipe paragraph with six readable, bilingual 3D recipe stickers in a three-column by two-row layout.

**Architecture:** Keep the change scene-native and visual: six stable `Node3D` sticker groups live under `Stations/MenuBoard/RecipeStickers`, each with its own geometry and labels. Extend the existing scene contract test before editing the scene; economy and gameplay scripts remain untouched.

**Tech Stack:** Godot 4.7 `.tscn`, `BoxMesh`, `StandardMaterial3D`, `Label3D`, headless SceneTree tests, Metal preview renderer.

---

## Planned File Changes

- Modify `tests/conveyor_profit/test_conveyor_profit_scene.gd`: assert sticker hierarchy and complete bilingual public text.
- Modify `conveyor_profit/scenes/conveyor_profit_environment.tscn`: replace the abbreviated recipe label with six sticker groups.
- Modify `conveyor_profit/README.md`: note the bilingual full-name menu.

## Task 1: Lock the Recipe Sticker Contract with RED

**Files:**
- Modify: `tests/conveyor_profit/test_conveyor_profit_scene.gd`

- [ ] **Step 1: Add exact hierarchy assertions**

After the existing menu assertion, add:

```gdscript
var menu := environment.get_node("Stations/MenuBoard")
var stickers := menu.get_node_or_null("RecipeStickers")
_check(stickers != null, "recipe sticker container exists")
_check(stickers != null and stickers.get_child_count() == 6, "six recipe stickers exist")
_check(not menu.has_node("Recipes"), "abbreviated recipe paragraph removed")
```

- [ ] **Step 2: Add complete-text assertions**

Build each sticker's public text by concatenating `Title`, `Ingredients`, and `Economy`, then require these complete terms:

```gdscript
var expected_terms := {
	"Salad": ["沙拉", "SALAD", "生菜", "LETTUCE", "番茄", "TOMATO", "蘑菇", "MUSHROOM", "$7", "+$3"],
	"EggToast": ["鸡蛋吐司", "EGG TOAST", "面包", "BREAD", "鸡蛋", "EGG", "$8", "+$4"],
	"CheeseToast": ["奶酪吐司", "CHEESE TOAST", "面包", "BREAD", "奶酪", "CHEESE", "$10", "+$5"],
	"Burger": ["汉堡", "BURGER", "肉", "MEAT", "生菜", "LETTUCE", "番茄", "TOMATO", "$15", "+$6"],
	"FishSandwich": ["鱼肉三明治", "FISH SANDWICH", "鱼", "FISH", "生菜", "LETTUCE", "$14", "+$7"],
	"MushroomOmelet": ["蘑菇蛋卷", "MUSHROOM OMELET", "鸡蛋", "EGG", "奶酪", "CHEESE", "蘑菇", "MUSHROOM", "$14", "+$7"],
}
```

For every named sticker, assert the five required child nodes exist and every expected term occurs in its combined label text.

- [ ] **Step 3: Verify RED**

Run:

```bash
godot --headless --log-file /private/tmp/conveyor_stickers_red.log --path . --script tests/conveyor_profit/test_conveyor_profit_scene.gd
```

Expected: exit 1 because `RecipeStickers` is absent and `Recipes` still exists.

## Task 2: Build the Six Scene-Native Stickers

**Files:**
- Modify: `conveyor_profit/scenes/conveyor_profit_environment.tscn`

- [ ] **Step 1: Add shared geometry and materials**

Create a `2.5 × 1.15 × 0.08`米白 `BoxMesh` for each background and a `2.38 × 0.3 × 0.04` title-bar mesh. Add six restrained title-bar materials: green, amber, cheese yellow, red, blue, and mushroom purple. Keep all surfaces rough and non-emissive so text contrast remains stable under the existing lights.

- [ ] **Step 2: Replace the old recipe paragraph**

Delete `Stations/MenuBoard/Recipes`. Add `RecipeStickers` and place sticker centers at:

```text
top row:    (-2.7, 0.52), (0, 0.52), (2.7, 0.52)
bottom row: (-2.7,-0.78), (0,-0.78), (2.7,-0.78)
```

Set all sticker surfaces slightly toward the camera at local `z = -0.15` to avoid depth fighting with the dark board.

- [ ] **Step 3: Add exact bilingual labels**

Each stable sticker node contains `Background`, `TitleBar`, `Title`, `Ingredients`, and `Economy`. Use these exact strings, with line breaks only at ingredient boundaries:

```text
沙拉 SALAD
生菜 LETTUCE + 番茄 TOMATO
蘑菇 MUSHROOM
售价 SALE $7  ·  净利 PROFIT +$3

鸡蛋吐司 EGG TOAST
面包 BREAD + 鸡蛋 EGG
售价 SALE $8  ·  净利 PROFIT +$4

奶酪吐司 CHEESE TOAST
面包 BREAD + 奶酪 CHEESE
售价 SALE $10  ·  净利 PROFIT +$5

汉堡 BURGER
面包 BREAD + 肉 MEAT
生菜 LETTUCE + 番茄 TOMATO
售价 SALE $15  ·  净利 PROFIT +$6

鱼肉三明治 FISH SANDWICH
面包 BREAD + 鱼 FISH
生菜 LETTUCE
售价 SALE $14  ·  净利 PROFIT +$7

蘑菇蛋卷 MUSHROOM OMELET
鸡蛋 EGG + 奶酪 CHEESE
蘑菇 MUSHROOM
售价 SALE $14  ·  净利 PROFIT +$7
```

Use title font size 23–26, ingredient size 15–18, economy size 14–16, dark text, and a small outline only where necessary. Move the existing board title upward and reduce it only if required to keep clear separation from the first row.

- [ ] **Step 4: Verify GREEN and regressions**

Run the scene contract, gameplay, recipe, session, supply, and motion tests. All must exit 0.

- [ ] **Step 5: Commit the scene change**

```bash
git add conveyor_profit/scenes/conveyor_profit_environment.tscn tests/conveyor_profit/test_conveyor_profit_scene.gd
git commit -m "style(conveyor-profit): add bilingual recipe stickers"
```

## Task 3: Render, Inspect, and Document

**Files:**
- Modify: `conveyor_profit/README.md`

- [ ] **Step 1: Render the scene**

```bash
godot --log-file /private/tmp/conveyor_stickers_render.log --path . --script tools/render_conveyor_profit_preview.gd -- --output=/private/tmp/conveyor-profit-stickers.png
```

Expected: a non-empty 1280×720 PNG.

- [ ] **Step 2: Inspect at original resolution**

Require six visually separate米白 cards, readable bilingual dish names, no collisions between cards, no clipped ingredient lines, and no overlap with the board title. If any condition fails, adjust only scene positions/font sizes and re-render.

- [ ] **Step 3: Document the menu**

Add one README bullet stating that the wall menu uses six bilingual full-name recipe stickers and does not require abbreviation memorization.

- [ ] **Step 4: Run final verification**

Run Godot editor parse, all six affected tests, `git diff --check`, `git status --short --branch`, and re-render from the final commit.

- [ ] **Step 5: Commit documentation and hand off**

```bash
git add conveyor_profit/README.md docs/superpowers/specs/plan-conveyor-recipe-stickers.md
git commit -m "docs(conveyor-profit): document bilingual menu"
```

Report the preview path, branch/worktree, test evidence, commit hashes, and that push/merge remain deferred while the broader feature continues.
