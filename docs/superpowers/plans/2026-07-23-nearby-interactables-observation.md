# Nearby Interactables Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded `nearby_interactables` observation containing the five nearest enabled interactables that are inside the current camera view and unobstructed.

**Architecture:** A focused Godot collector owns candidate filtering, interaction-point selection, camera projection, line-of-sight checks, player-distance sorting, and DTO construction. `AIPlayObserver` adds that DTO to every observation; Python validates the exact wire shape and the prompt teaches the model to use screen coordinates only as `probe_interaction` estimates.

**Tech Stack:** Godot 4.7/GDScript, COGITO `interactable` group and `InteractionComponent`, Python 3.9, pytest.

## Global Constraints

- Enumerate all enabled COGITO `interactable` objects, not a puzzle whitelist.
- Keep only objects inside the active camera frustum and unobstructed by another collider.
- Measure three-dimensional distance from `player.global_position` to the selected interaction point.
- Sort by that player distance and return at most five objects.
- Never expose readable content, passwords, node paths, scene filenames, scripts, or developer node names.
- Preserve the rule that only non-empty current `available_interactions` means the crosshair is aligned.
- A missing camera, world, viewport, or safe interaction point produces an empty/omitted candidate rather than blocking the observation.
- Preserve all unrelated user changes already present in `prompts.py`, its tests, and the AI Play harness.

---

### Task 1: Implement and test the Godot nearby-interactable collector

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_nearby_interactables.gd`
- Create: `tests/ai_play/test_ai_play_nearby_interactables.gd`

**Interfaces:**
- Consumes: `player: Node3D`, `camera: Camera3D`, `candidates: Array`, `viewport_size: Vector2`
- Produces: `collect(player, camera, candidates, viewport_size) -> Array[Dictionary]`
- Test seam: writable `line_of_sight_provider: Callable`; when valid, it receives `(camera_position, interaction_point, candidate)` and returns `bool`

- [ ] **Step 1: Write the failing collector test**

Create a SceneTree test with:

```gdscript
const NearbyCollector = preload(
	"res://addons/cogito/AIPlay/ai_play_nearby_interactables.gd"
)

class FakeInteractable extends Node3D:
	var interaction_nodes: Array[Node] = []
	var prompt_pos_mode: int = 0
	var prompt_marker: Marker3D

func _interaction(prompt: String, disabled: bool = false) -> InteractionComponent:
	var component := InteractionComponent.new()
	component.input_map_action = "interact"
	component.interaction_text = prompt
	component.is_disabled = disabled
	return component
```

Set a current `Camera3D` at the origin looking down Godot forward `-Z`, a player
at the origin, and visible candidates at `z = -2, -4, -6, -8, -10, -12`.
Assert:

```gdscript
var result: Array = collector.collect(
	player,
	camera,
	candidates,
	Vector2(768.0, 432.0),
)
_assert(result.size() == 5, "collector caps output at five")
_assert(result.map(func(item): return item["distance_m"]) == [2.0, 4.0, 6.0, 8.0, 10.0],
	"collector sorts by player-to-interaction-point distance")
```

Also assert:

- a candidate behind the camera is excluded;
- a candidate whose line-of-sight provider returns `false` is excluded;
- a candidate with only disabled or unapproved interaction components is
  excluded;
- marker mode uses `prompt_marker.global_position`;
- AABB mode uses the global visual center;
- normalized screen coordinates are within `[0, 1]`;
- a centered candidate has screen `(0.5, 0.5)`, yaw near `0`, right near `0`,
  and positive forward;
- the DTO contains only `tracking_id`, `category`, `distance_m`,
  `world_position`, `relative_position`, `relative_yaw_degrees`,
  `relative_pitch_degrees`, `screen_position`, and `interactions`;
- serialized output contains neither fake node names nor fake readable content.

- [ ] **Step 2: Run the collector test to verify RED**

Run:

```bash
godot --headless --rendering-method gl_compatibility \
  --log-file /private/tmp/cogito_nearby_test.log \
  --path . \
  --script tests/ai_play/test_ai_play_nearby_interactables.gd
```

Expected: FAIL because `ai_play_nearby_interactables.gd` does not exist.

- [ ] **Step 3: Implement the collector**

Create:

```gdscript
class_name AIPlayNearbyInteractables
extends RefCounted

const MAX_OBJECTS := 5
const APPROVED_ACTIONS := ["interact", "interact2"]
const PromptPositionMode := {
	"ORIGIN": 0,
	"MARKER": 1,
	"AABB_CENTER": 2,
}

var line_of_sight_provider: Callable

func collect(
	player: Node3D,
	camera: Camera3D,
	candidates: Array,
	viewport_size: Vector2,
) -> Array[Dictionary]:
	# Guard invalid inputs; build candidates with _describe_candidate();
	# sort by distance_m and resize to MAX_OBJECTS.
```

Implement these focused helpers:

```gdscript
func _enabled_interactions(candidate: Node) -> Array[Dictionary]
func _interaction_point(candidate: Node3D) -> Variant
func _global_aabb(node: Node) -> AABB
func _is_in_camera(camera: Camera3D, point: Vector3, viewport_size: Vector2) -> bool
func _has_line_of_sight(camera: Camera3D, point: Vector3, candidate: Node3D) -> bool
func _belongs_to_candidate(collider: Object, candidate: Node) -> bool
func _category(candidate: Node, components: Array) -> String
func _relative_fields(camera: Camera3D, delta: Vector3) -> Dictionary
```

Use:

```gdscript
var distance_m := player.global_position.distance_to(point)
var projected := camera.unproject_position(point)
var screen := Vector2(projected.x / viewport_size.x, projected.y / viewport_size.y)
var flat_forward := -camera.global_basis.z
flat_forward.y = 0.0
flat_forward = flat_forward.normalized()
var flat_right := flat_forward.cross(Vector3.UP).normalized()
var forward := delta.dot(flat_forward)
var right := delta.dot(flat_right)
var up := delta.y
var relative_yaw := rad_to_deg(atan2(right, forward))
var relative_pitch := -rad_to_deg(atan2(up, Vector2(forward, right).length()))
```

The default line-of-sight implementation uses
`PhysicsRayQueryParameters3D.create(camera.global_position, point)`, excludes
the player RID when it is a `CollisionObject3D`, and accepts an impact only when
the collider is the candidate or belongs to its hierarchy.

Map only public runtime types to bounded categories:

```text
ReadableComponent -> readable
CogitoKeypad -> keypad
CogitoDoor -> door
CogitoButton -> button
CharacterBody3D -> character
CogitoObject -> object
fallback -> interactable
```

- [ ] **Step 4: Run the collector test to verify GREEN**

Run the command from Step 2.

Expected: exit `0` and `AIPlay nearby interactables tests passed`.

- [ ] **Step 5: Commit the isolated collector**

```bash
git add addons/cogito/AIPlay/ai_play_nearby_interactables.gd \
  tests/ai_play/test_ai_play_nearby_interactables.gd
git commit -m "feat: collect nearby visible interactables"
```

---

### Task 2: Add nearby interactables to Godot observations

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_observer.gd`
- Modify: `tests/ai_play/test_ai_play_observer.gd`

**Interfaces:**
- Consumes: `AIPlayNearbyInteractables.collect(...)`
- Produces: required observation field `nearby_interactables: Array`

- [ ] **Step 1: Write the failing observer assertions**

In `test_ai_play_observer.gd`, assert:

```gdscript
_assert(
	observation.get("nearby_interactables") == [],
	"observer emits an empty bounded nearby list when no candidates are visible",
)
_assert(
	find_contract_observation.has("nearby_interactables"),
	"find_contract observer preserves nearby interactables",
)
```

- [ ] **Step 2: Run the observer test to verify RED**

Run:

```bash
godot --headless --rendering-method gl_compatibility \
  --log-file /private/tmp/cogito_observer_test.log \
  --path . \
  --script tests/ai_play/test_ai_play_observer.gd
```

Expected: FAIL because `nearby_interactables` is absent.

- [ ] **Step 3: Integrate the collector**

Preload and initialize the collector:

```gdscript
const NearbyInteractables = preload(
	"res://addons/cogito/AIPlay/ai_play_nearby_interactables.gd"
)
var nearby_interactables_collector = NearbyInteractables.new()
```

Add this required field to the observation:

```gdscript
"nearby_interactables": _nearby_interactables(),
```

Implement:

```gdscript
func _nearby_interactables() -> Array:
	if player == null or not is_instance_valid(player) or not is_inside_tree():
		return []
	var camera := get_viewport().get_camera_3d()
	if camera == null and "camera" in player:
		camera = player.get("camera") as Camera3D
	var viewport_size := get_viewport().get_visible_rect().size
	if camera == null or viewport_size.x <= 0.0 or viewport_size.y <= 0.0:
		return []
	return nearby_interactables_collector.collect(
		player,
		camera,
		get_tree().get_nodes_in_group("interactable"),
		viewport_size,
	)
```

- [ ] **Step 4: Run Godot tests to verify GREEN**

Run both collector and observer commands.

Expected: both exit `0`.

- [ ] **Step 5: Commit observer integration**

```bash
git add addons/cogito/AIPlay/ai_play_observer.gd \
  tests/ai_play/test_ai_play_observer.gd
git commit -m "feat: report nearby interactables in observations"
```

---

### Task 3: Validate the nearby-interactable wire schema

**Files:**
- Modify: `ai_play/src/ai_play/observation_schema.py`
- Modify: `ai_play/tests/test_observation_schema.py`
- Modify: `ai_play/tests/test_agent_loop.py`
- Modify: `ai_play/tests/test_prompts.py`

**Interfaces:**
- Consumes: Godot `nearby_interactables`
- Produces: a fresh validated DTO preserved in `safe_observation`

- [ ] **Step 1: Add the valid fixture field and failing schema tests**

Add `"nearby_interactables": []` to every complete observation fixture in
`test_agent_loop.py` and `test_prompts.py`. Add a helper in
`test_observation_schema.py` that returns:

```python
{
    "tracking_id": 123,
    "category": "readable",
    "distance_m": 3.4,
    "world_position": [4.2, 1.3, -12.5],
    "relative_position": {"forward": 3.1, "right": 1.2, "up": 0.4},
    "relative_yaw_degrees": 21.2,
    "relative_pitch_degrees": -5.8,
    "screen_position": {"x": 0.68, "y": 0.44},
    "interactions": [{"action": "interact", "prompt": "Read task"}],
}
```

Test valid lists of zero through five items. Parametrize rejection of:

```python
[
    [nearby_item()] * 6,
    [{**nearby_item(), "distance_m": float("nan")}],
    [{**nearby_item(), "screen_position": {"x": -0.1, "y": 0.5}}],
    [{**nearby_item(), "interactions": [{"action": "reload", "prompt": "x"}]}],
    [{**nearby_item(), "developer_node_name": "FindContract_CeoContract"}],
]
```

- [ ] **Step 2: Run Python tests to verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/pytest \
  ai_play/tests/test_observation_schema.py \
  ai_play/tests/test_agent_loop.py \
  ai_play/tests/test_prompts.py -q
```

Expected: FAIL because the schema rejects or drops the new required field.

- [ ] **Step 3: Implement exact validation**

Add `"nearby_interactables"` to `OBSERVATION_FIELDS`. Implement:

```python
NEARBY_FIELDS = {
    "tracking_id", "category", "distance_m", "world_position",
    "relative_position", "relative_yaw_degrees", "relative_pitch_degrees",
    "screen_position", "interactions",
}
NEARBY_CATEGORIES = {
    "readable", "keypad", "door", "button", "character", "object",
    "interactable",
}

def validate_nearby_interactables(value):
    if not isinstance(value, list) or len(value) > 5:
        raise ObservationValidationError("nearby_interactables is invalid")
    # Exact nested keys, safe integer tracking_id, finite bounded numbers,
    # screen x/y in [0, 1], at most two approved interaction slots,
    # prompt length <= 200, and no duplicate interaction action.
```

Return the validated list under:

```python
"nearby_interactables": safe_nearby_interactables,
```

- [ ] **Step 4: Run focused Python tests to verify GREEN**

Run the command from Step 2.

Expected: all focused tests pass.

- [ ] **Step 5: Commit schema integration**

```bash
git add ai_play/src/ai_play/observation_schema.py \
  ai_play/tests/test_observation_schema.py \
  ai_play/tests/test_agent_loop.py \
  ai_play/tests/test_prompts.py
git commit -m "feat: validate nearby interactable observations"
```

---

### Task 4: Teach the model how to use the new field

**Files:**
- Modify: `ai_play/src/ai_play/prompts.py`
- Modify: `ai_play/tests/test_prompts.py`

**Interfaces:**
- Consumes: validated `observation.nearby_interactables`
- Produces: bounded system guidance without duplicating the DTO

- [ ] **Step 1: Write failing prompt assertions**

Add assertions that the system prompt says:

```text
nearby_interactables
screen_position
probe_interaction
available_interactions
```

Also assert the prompt explains that screen coordinates are estimates and that
current non-empty `available_interactions` remains the only alignment success
condition.

- [ ] **Step 2: Run prompt tests to verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/pytest ai_play/tests/test_prompts.py -q
```

Expected: FAIL because nearby-interactable guidance is absent.

- [ ] **Step 3: Add concise system guidance**

Add one paragraph to `SYSTEM_PROMPT`:

```text
每回合的 observation.nearby_interactables 最多列出当前画面内且无遮挡的五个
可交互物，并按玩家到交互点的三维距离排序。使用 relative_position 和
distance_m 判断是否需要靠近，使用 screen_position 作为
probe_interaction 的估计目标。该坐标不代表已经对准；只有当前
available_interactions 非空才算成功。移动、转向或探测后必须使用下一回合的
新坐标，不要复用旧坐标。
```

Do not add a second copy of the nearby DTO to `build_messages`; it already
travels inside `observation`.

- [ ] **Step 4: Run prompt and agent-loop tests to verify GREEN**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/pytest \
  ai_play/tests/test_prompts.py ai_play/tests/test_agent_loop.py -q
```

Expected: all focused tests pass.

- [ ] **Step 5: Commit prompt guidance**

```bash
git add ai_play/src/ai_play/prompts.py ai_play/tests/test_prompts.py
git commit -m "feat: guide nearby interactable targeting"
```

---

### Task 5: Full verification

**Files:**
- Verify all files changed by Tasks 1–4

**Interfaces:**
- Consumes: complete Godot-to-Python observation pipeline
- Produces: verified feature ready for a manual non-AI Lobby check and later AI run

- [ ] **Step 1: Run all Python AI Play tests**

```bash
PYTHONPATH=ai_play/src .venv/bin/pytest ai_play/tests -q
```

Expected: all tests pass. If the existing secret fixture causes only the known
repository shell scanner failure, report it separately; pytest itself must
pass.

- [ ] **Step 2: Run all relevant Godot tests**

```bash
godot --headless --rendering-method gl_compatibility \
  --log-file /private/tmp/cogito_nearby_test.log \
  --path . \
  --script tests/ai_play/test_ai_play_nearby_interactables.gd

godot --headless --rendering-method gl_compatibility \
  --log-file /private/tmp/cogito_observer_test.log \
  --path . \
  --script tests/ai_play/test_ai_play_observer.gd

godot --headless --rendering-method gl_compatibility \
  --log-file /private/tmp/cogito_lobby_nearby_test.log \
  --path . \
  --script tests/ai_play/test_ai_play_lobby_game_over.gd
```

Expected: each exits `0` with its test-specific passed message.

- [ ] **Step 3: Verify formatting and scope**

```bash
git diff --check
git status --short
git diff -- addons/cogito/AIPlay ai_play/src/ai_play \
  tests/ai_play ai_play/tests
```

Expected: no whitespace errors; no unrelated user files are staged or changed
by this implementation.

- [ ] **Step 4: Run a non-AI observation smoke test**

Load the Lobby without `--ai-play` only if manual visual confirmation is
requested. Do not start the sidecar or make a model API call as part of
automated verification.
