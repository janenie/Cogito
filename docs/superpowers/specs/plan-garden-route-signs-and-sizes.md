# Garden Route Signs and Sizes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display the complete neighborhood travel-cost rules and make the approved five small, three medium, and two large gardens visually unmistakable.

**Architecture:** Extend the reusable house component so one `garden_size` value drives its Chinese label, soil footprint, label color, and plant count. Keep map-wide route information in the neighborhood scene as one central rules board and ten adjacent-road signs; do not add clock mutation or order logic.

**Tech Stack:** Godot 4.7, GDScript, `.tscn` packed scenes, headless SceneTree tests.

---

### Task 1: Distinct Reusable Garden Sizes

**Files:**
- Modify: `tests/garden/test_garden_orders_neighborhood.gd`
- Modify: `garden/scripts/garden_order_house.gd`
- Modify: `garden/scenes/components/garden_order_house.tscn`

- [ ] **Step 1: Write the failing size-presentation test**

After adding the real house component to the test tree, set each size and assert literal player-visible results:

```gdscript
var expected_sizes := {
	"small": {"label": "7号 · 小型花园", "scale": 0.5},
	"medium": {"label": "7号 · 中型花园", "scale": 0.875},
	"large": {"label": "7号 · 大型花园", "scale": 1.25},
}
for size in ["small", "medium", "large"]:
	house.set("garden_size", size)
	_assert((house.get_node("Garden/SizeLabel") as Label3D).text == expected_sizes[size].label, "%s garden has a Chinese size label" % size)
	_assert(is_equal_approx((house.get_node("Garden/SoilBed") as MeshInstance3D).scale.x, expected_sizes[size].scale), "%s garden has the approved footprint" % size)
```

- [ ] **Step 2: Run the focused test and verify RED**

```bash
godot --headless --path . --script tests/garden/test_garden_orders_neighborhood.gd
```

Expected: FAIL because `Garden/SizeLabel` does not exist.

- [ ] **Step 3: Implement size-driven visuals**

Add `Garden/SizeLabel` to the packed scene. In `GardenOrderHouse._refresh_visuals()`, set the label to `%d号 · %s型花园`, map `small`, `medium`, and `large` to `小`, `中`, and `大`, and apply green, amber, and orange-red label colors. Return footprint scales `0.5`, `0.875`, and `1.25` from `_garden_width_scale()` while retaining visible plant counts `3`, `5`, and `7`.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the Task 1 test command. Expected: PASS.

- [ ] **Step 5: Commit the reusable house change**

```bash
git add tests/garden/test_garden_orders_neighborhood.gd garden/scripts/garden_order_house.gd garden/scenes/components/garden_order_house.tscn
git commit -m "feat(garden): distinguish garden sizes"
```

### Task 2: Route Rules and Approved Neighborhood Distribution

**Files:**
- Modify: `tests/garden/test_garden_orders_neighborhood.gd`
- Modify: `garden/scenes/garden_orders_neighborhood.tscn`

- [ ] **Step 1: Write the failing map-information test**

Update the expected distribution to `{"small": 5, "medium": 3, "large": 2}` and assert addresses by size:

```gdscript
_assert(houses.get_node("House03").get("garden_size") == "large", "House 3 is large")
_assert(houses.get_node("House06").get("garden_size") == "large", "House 6 is large")
_assert(houses.get_node("House09").get("garden_size") == "small", "House 9 is small")
```

Assert the central label text equals:

```text
路程规则
工具区 → 任意住宅：10 分钟
相隔 1 栋：5 分钟
相隔 2 栋：10 分钟
相隔 3 栋：15 分钟
相隔 4–5 栋：20 分钟
```

Assert `Roads/TravelTimeSigns` has exactly ten children and each child is a `Label3D` with text `步行 5 分钟`.

- [ ] **Step 2: Run the focused test and verify RED**

Run the focused test. Expected: FAIL because House 9 is currently large and no route-information nodes exist.

- [ ] **Step 3: Compose route signs and update House 9**

Set House 9 to `garden_size = "small"`. Add `RouteInformation` near the central plaza with a low-poly board, two posts, and the exact Chinese rules label. Add `Roads/TravelTimeSigns/Sign01` through `Sign10` at the ten ring segment midpoints, each with outlined, billboarded, depth-test-disabled `Label3D` text `步行 5 分钟`.

- [ ] **Step 4: Run complete verification and visual inspection**

```bash
godot --headless --path . --script tests/garden/test_garden_orders_neighborhood.gd
for test_file in tests/garden/test_*.gd; do godot --headless --path . --script "$test_file" || exit 1; done
godot --headless --path . --editor --quit
git diff --check
```

Render and inspect spawn and overview screenshots. Confirm the rules board is readable, ten road labels do not cover house labels, the 2/3/5 footprint differences are obvious, and perimeter fences remain absent.

- [ ] **Step 5: Commit, push, and restart gameplay**

```bash
git add tests/garden/test_garden_orders_neighborhood.gd garden/scenes/garden_orders_neighborhood.tscn
git commit -m "feat(garden): display neighborhood travel costs"
git push origin feature/garden_new
```

Stop the existing Godot neighborhood process and restart `garden/scenes/garden_orders_neighborhood.tscn`.
