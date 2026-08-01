# Garden Orders Neighborhood Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable Godot 4.7 neighborhood scene with ten numbered garden homes around a central tool plaza and a basic third-person inspection player.

**Architecture:** Three focused packed scenes provide a configurable house lot, a central tool display, and a third-person player. The entry scene explicitly places ten house instances around a ring and owns only world composition, lighting, roads, spawn, and HUD. Headless scene tests inspect the public node structure and configuration without coupling to future order logic.

**Tech Stack:** Godot 4.7, GDScript, `.tscn` packed scenes, repository-tracked Kenney Furniture GLBs, headless SceneTree tests.

## Global Constraints

- Keep `garden/scenes/garden_vertical_slice.tscn` and its existing gameplay unchanged.
- Reuse repository assets; do not download Kenney Suburban or Kenney Nature.
- Do not expose `game_script/`, future orders, optimal routes, or internal validation facts at runtime.
- The new scene does not auto-start AI play or modify the project main scene.
- New GDScript uses tabs, typed signatures, `snake_case`, and focused components.

---

### Task 1: Configurable Garden House Lot

**Files:**
- Create: `tests/garden/test_garden_orders_neighborhood.gd`
- Create: `garden/scripts/garden_order_house.gd`
- Create: `garden/scenes/components/garden_order_house.tscn`

**Interfaces:**
- Produces: `GardenOrderHouse` with exported `house_number: int`, `garden_size: String`, and `accent_color: Color`.
- Produces stable child paths: `AddressLabel`, `HouseBody/CollisionShape3D`, `Garden`, `Garden/Destination`, and `Garden/GardenWorkPoint`.
- Produces `get_garden_size() -> String` for structural tests and future order lookup.

- [ ] **Step 1: Write the failing component test**

Create a `SceneTree` test that loads `res://garden/scenes/components/garden_order_house.tscn`, instantiates it, sets `house_number = 7` and `garden_size = "large"`, adds it to the test root, waits one process frame, and asserts:

```gdscript
_assert(house.get_script() != null, "house component has a configuration script")
_assert(house.get_garden_size() == "large", "house exposes its garden size")
_assert((house.get_node("AddressLabel") as Label3D).text == "7", "house label follows its number")
_assert(house.get_node_or_null("Garden/Destination") != null, "house has a destination marker")
_assert(house.get_node_or_null("Garden/GardenWorkPoint") != null, "house has a work marker")
_assert(house.get_node_or_null("HouseBody/CollisionShape3D") != null, "house has collision")
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
godot --headless --path . --script tests/garden/test_garden_orders_neighborhood.gd
```

Expected: FAIL because the component scene does not exist.

- [ ] **Step 3: Implement the house script and packed scene**

Implement `GardenOrderHouse` so `_ready()` calls a focused `_refresh_visuals()` method. The method clamps the number to `1..10`, validates `garden_size` against `small`, `medium`, and `large`, updates `AddressLabel.text`, applies `accent_color` to a duplicated house material, scales the soil bed, and shows 3, 5, or 7 plant placements. Build the low-poly house, roof, door, number label, garden soil, fence visuals, static collision, markers, and Kenney plant instances in the packed scene.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the Task 1 command. Expected: PASS with no parser or missing-resource errors.

- [ ] **Step 5: Commit the house component**

```bash
git add tests/garden/test_garden_orders_neighborhood.gd garden/scripts/garden_order_house.gd garden/scripts/garden_order_house.gd.uid garden/scenes/components/garden_order_house.tscn
git commit -m "feat(garden): add configurable order house"
```

### Task 2: Central Tool Area and Third-Person Player

**Files:**
- Modify: `tests/garden/test_garden_orders_neighborhood.gd`
- Create: `garden/scenes/components/garden_order_tool_area.tscn`
- Create: `garden/scripts/garden_order_third_person_player.gd`
- Create: `garden/scenes/components/garden_order_third_person_player.tscn`

**Interfaces:**
- Produces tool paths: `WateringCan`, `Shovel`, `FertilizerSpreader`, `FertilizerStock`, `Destination`, and `Shelter/CollisionShape3D`.
- Produces `GardenOrderThirdPersonPlayer`, a `CharacterBody3D` using existing `left`, `right`, `forward`, `back`, `sprint`, `jump`, and `menu` actions.
- Produces player paths: `CollisionShape3D`, `Avatar`, `CameraPivot/SpringArm3D/Camera3D`.

- [ ] **Step 1: Extend the test for tools and camera**

Add tests that load both new component scenes and assert:

```gdscript
for node_name in ["WateringCan", "Shovel", "FertilizerSpreader", "FertilizerStock"]:
	_assert(tool_area.get_node_or_null(node_name) != null, "tool area displays %s" % node_name)
_assert(tool_area.get_node_or_null("Destination") != null, "tool area has a destination marker")
_assert(tool_area.get_node_or_null("Shelter/CollisionShape3D") != null, "tool shelter has collision")
_assert(player is CharacterBody3D, "inspection player is a character body")
_assert(player.get_node_or_null("CollisionShape3D") != null, "player has capsule collision")
_assert(player.get_node_or_null("CameraPivot/SpringArm3D/Camera3D") != null, "player has a third-person camera")
```

- [ ] **Step 2: Run the test and verify RED**

Run the focused test. Expected: FAIL because the tool-area and third-person-player scenes do not exist.

- [ ] **Step 3: Implement the tool-area scene**

Build a compact open shelter using primitive meshes and static collision. Model the four displays from primitive meshes with distinct colors, add readable `Label3D` captions, place two fertilizer bags under `FertilizerStock`, and put `Destination` in front of the shelter.

- [ ] **Step 4: Implement the third-person player**

Implement camera-relative walking and sprinting in `_physics_process`, gravity and jump, mouse-orbit yaw/pitch in `_unhandled_input`, pitch clamping, mouse capture on ready, and Escape/menu mouse release. Configure the scene with a capsule collision, visible capsule avatar, pivot, spring arm, and active camera.

- [ ] **Step 5: Run the focused test and verify GREEN**

Run the Task 1 command. Expected: all component assertions PASS.

- [ ] **Step 6: Commit the tool and player components**

```bash
git add tests/garden/test_garden_orders_neighborhood.gd garden/scenes/components/garden_order_tool_area.tscn garden/scripts/garden_order_third_person_player.gd garden/scripts/garden_order_third_person_player.gd.uid garden/scenes/components/garden_order_third_person_player.tscn
git commit -m "feat(garden): add neighborhood tools and player"
```

### Task 3: Compose the Ten-House Neighborhood

**Files:**
- Modify: `tests/garden/test_garden_orders_neighborhood.gd`
- Create: `garden/scenes/garden_orders_neighborhood.tscn`
- Modify: `garden/README.md`

**Interfaces:**
- Produces entry scene: `res://garden/scenes/garden_orders_neighborhood.tscn`.
- Produces root paths: `WorldEnvironment`, `Ground`, `Roads`, `CentralToolArea`, `PlayerSpawn`, `GardenOrderPlayer`, `Houses`, and `NeighborhoodUI`.
- Produces house paths: `Houses/House01` through `Houses/House10`.

- [ ] **Step 1: Extend the test for the complete neighborhood**

Load and instantiate the entry scene, then assert exactly ten children under `Houses`; collect the ten `house_number` values and compare them with `range(1, 11)`; count garden sizes and compare with `{"small": 4, "medium": 3, "large": 3}`. Assert the root paths listed above, all house markers, central tool destination, player camera, collisions, and `GardenOrderPlayer.global_position.distance_to(Vector3.ZERO) < 3.0`.

- [ ] **Step 2: Run the test and verify RED**

Run the focused test. Expected: FAIL because the entry scene does not exist.

- [ ] **Step 3: Compose world and ring layout**

Create the ground and collision, outdoor environment using the tracked HDR panorama, directional sun, circular central plaza, ring road, and four radial paths. Explicitly place House 1 through House 10 clockwise, rotate each lot inward, assign unique restrained accent colors, and apply the approved garden-size distribution.

- [ ] **Step 4: Add spawn, tool area, player, and HUD**

Place `PlayerSpawn` close to world origin, instantiate the player at the spawn, place the tool shelter on the central plaza without intersecting the player, and add a translucent HUD with the title and keyboard/mouse inspection controls. Do not include order schedules or strategy hints.

- [ ] **Step 5: Document the local run command**

Add the new scene and this command to `garden/README.md`:

```bash
godot --path . garden/scenes/garden_orders_neighborhood.tscn
```

- [ ] **Step 6: Run focused and affected test suites**

```bash
godot --headless --path . --script tests/garden/test_garden_orders_neighborhood.gd
godot --headless --path . --script tests/garden/test_garden_scene.gd
godot --headless --path . --script tests/garden/test_garden_game1.gd
godot --headless --path . --editor --quit
git diff --check
```

Expected: every command exits `0`; the editor import check has no parser or missing-resource errors.

- [ ] **Step 7: Capture a local visual verification image**

Run the scene locally, capture one screenshot from the central plaza, and inspect that all ten lots are visually separated, house numbers are readable, the tool shelter is visible from spawn, the camera does not start inside geometry, and no obvious mesh/collision placement errors appear. This is a local Godot check, not a real external MCP-client acceptance run.

- [ ] **Step 8: Commit the complete scene**

```bash
git add tests/garden/test_garden_orders_neighborhood.gd garden/scenes/garden_orders_neighborhood.tscn garden/README.md
git commit -m "feat(garden): build ten-house order neighborhood"
```
