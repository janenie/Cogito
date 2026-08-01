# Garden Orders Chinese Tool Signage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the central garden-order HUD and tool shelter readable in Chinese, with clear silhouettes and ordering for all four tool/material displays.

**Architecture:** Keep all developer-facing node names stable and change only player-facing label text and visual sizing in the existing packed scenes. Extend the real-scene headless test to validate the approved Chinese label sequence and both fertilizer bags.

**Tech Stack:** Godot 4.7, `.tscn` packed scenes, GDScript SceneTree tests.

---

### Task 1: Chinese Central HUD and Tool Display

**Files:**
- Modify: `tests/garden/test_garden_orders_neighborhood.gd`
- Modify: `garden/scenes/components/garden_order_tool_area.tscn`
- Modify: `garden/scenes/garden_orders_neighborhood.tscn`

- [ ] **Step 1: Write the failing player-facing label test**

Extend `_test_tool_area_component()` to collect the real `Label3D.text` values in visual left-to-right order and compare them to literal approved copy:

```gdscript
var labels := [
	(tool_area.get_node("FertilizerStock/Label") as Label3D).text,
	(tool_area.get_node("FertilizerSpreader/Label") as Label3D).text,
	(tool_area.get_node("Shovel/Label") as Label3D).text,
	(tool_area.get_node("WateringCan/Label") as Label3D).text,
]
_assert(labels == ["肥料 ×2", "施肥器", "松土铲", "浇水壶"], "tool labels explain each central display in Chinese")
_assert(tool_area.get_node_or_null("FertilizerStock/Bag01") != null, "first fertilizer bag remains visible")
_assert(tool_area.get_node_or_null("FertilizerStock/Bag02") != null, "second fertilizer bag remains visible")
```

Also assert the real neighborhood HUD title and controls equal `园艺订单社区` and `WASD 移动 · Shift 加速 · 鼠标旋转视角 · Esc 释放鼠标`.

- [ ] **Step 2: Run the focused test and verify RED**

```bash
godot --headless --path . --script tests/garden/test_garden_orders_neighborhood.gd
```

Expected: FAIL because the current runtime labels are English.

- [ ] **Step 3: Implement the Chinese labels and clearer displays**

Set the four tool label texts to the approved Chinese copy. Increase each `Label3D.font_size` to `72`, `outline_size` to `16`, and set `no_depth_test = true`. Scale the shovel and spreader display roots to `Vector3(1.2, 1.2, 1.2)` while preserving their positions and stable node names. Replace the neighborhood HUD title and controls with the approved Chinese copy.

- [ ] **Step 4: Run focused and full validation**

```bash
godot --headless --path . --script tests/garden/test_garden_orders_neighborhood.gd
for test_file in tests/garden/test_*.gd; do godot --headless --path . --script "$test_file" || exit 1; done
godot --headless --path . --editor --quit
git diff --check
```

Expected: all commands exit `0`. Existing engine shutdown warnings may remain, but there must be no scene parser or missing-resource failure.

- [ ] **Step 5: Verify the spawn view and restart gameplay**

Render the existing local spawn screenshot, inspect that all four Chinese labels are readable and their tools are visible, then stop and restart `garden/scenes/garden_orders_neighborhood.tscn` so the user sees the updated resources.

- [ ] **Step 6: Commit and push the focused change**

```bash
git add tests/garden/test_garden_orders_neighborhood.gd garden/scenes/components/garden_order_tool_area.tscn garden/scenes/garden_orders_neighborhood.tscn
git commit -m "feat(garden): localize central tool display"
git push origin feature/garden_new
```
