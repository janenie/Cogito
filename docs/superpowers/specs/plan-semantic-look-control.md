# Semantic AI Look Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace signed numeric AI camera input with a four-direction semantic look action, isolate the active AI camera from non-AI mouse motion, and prove screenshots reflect completed turns before running the AWM comparison.

**Architecture:** Python and Godot retain mirrored exact-field validation for `{"type":"look","direction":...,"degrees":...}`. Godot maps direction to the existing private yaw/pitch path, while `AIPlayController` toggles a mouse-device guard on `CogitoPlayer`; deferred observation capture waits for a rendered frame. Briefing, Codex developer instructions, README, and wiki publish one consistent contract.

**Tech Stack:** Python 3, pytest 8, Godot 4.7/GDScript, MCP over the existing protocol-v3 WebSocket bridge, Codex CLI.

## Global Constraints

- Work only in the current `feature/session-awm` worktree; do not switch branches or worktrees.
- `look.direction` is exactly `left`, `right`, `up`, or `down`; `look.degrees` is a finite non-boolean number in `[1, 45]`.
- Private mapping is `left=(-degrees,0)`, `right=(degrees,0)`, `up=(0,-degrees)`, and `down=(0,degrees)` in `(yaw,pitch)` form.
- Numeric public `yaw`/`pitch` look actions are rejected; other action schemas and limits are unchanged.
- Escape remains the physical emergency stop key. Disable, error, terminal, teardown, and disconnect paths continue releasing simulated input.
- AI control stays explicitly enabled only by `-- --ai-play`; the bridge stays bound to `127.0.0.1`.
- Runtime player input never includes repository files, trusted logs, hidden state, `game_script/`, `code_read/`, tests, specs, or plans.
- AWM and no-AWM groups receive identical camera and screenshot-comparison capabilities.

---

### Task 1: Python semantic look boundary and public briefing

**Files:**
- Modify: `ai_play/tests/test_action_schema.py`
- Modify: `ai_play/tests/test_briefing.py`
- Modify: `ai_play/src/ai_play/action_schema.py`
- Modify: `ai_play/src/ai_play/common_briefing_rules.py`

**Interfaces:**
- Consumes: `validate_action_batch(actions, available_interactions, interface_open)`.
- Produces: unchanged validated semantic action dictionaries; `LOOK_DIRECTIONS = {"left", "right", "up", "down"}` and `LOOK_MAX_DEGREES = 45`.

- [ ] **Step 1: Write failing Python action-contract tests**

```python
@pytest.mark.parametrize("direction", ["left", "right", "up", "down"])
@pytest.mark.parametrize("degrees", [1, 45])
def test_validate_action_batch_accepts_semantic_look_directions(direction, degrees):
    action = {"type": "look", "direction": direction, "degrees": degrees}
    assert validate_action_batch([action], set(), False) == [action]


@pytest.mark.parametrize(
    "action",
    [
        {"type": "look", "yaw": -15, "pitch": 0},
        {"type": "look", "direction": "north", "degrees": 10},
        {"type": "look", "direction": "left", "degrees": 0},
        {"type": "look", "direction": "left", "degrees": 45.1},
        {"type": "look", "direction": "left", "degrees": math.inf},
        {"type": "look", "direction": "left", "degrees": True},
    ],
)
def test_validate_action_batch_rejects_invalid_semantic_look(action):
    with pytest.raises(ActionValidationError):
        validate_action_batch([action], set(), False)
```

Update `test_all_scenario_briefings_teach_look_based_spatial_estimation` to require `direction`, `degrees`, all four direction names, screenshot comparison, and the absence of public `yaw`/`pitch` instructions.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
PYTHONPATH=ai_play/src /Users/jan/workspace/Phazorknight-Cogito/.venv/bin/python -m pytest \
  ai_play/tests/test_action_schema.py ai_play/tests/test_briefing.py -q
```

Expected: FAIL because Python still requires `yaw` and `pitch`, and briefing still documents signed axes.

- [ ] **Step 3: Implement the minimal Python schema and briefing**

```python
LOOK_DIRECTIONS = {"left", "right", "up", "down"}
LOOK_MAX_DEGREES = 45

ALLOWED_KEYS = {
    "look": {"type", "direction", "degrees"},
    # Keep every existing non-look entry unchanged.
}

if action_type == "look":
    if action["direction"] not in LOOK_DIRECTIONS:
        raise ActionValidationError("look direction is not allowed")
    _require_number(action["degrees"], 1, LOOK_MAX_DEGREES, "degrees")
```

Replace signed-axis briefing rules with:

```python
"look 使用 direction 和 degrees；direction 只能是 left、right、up、down，degrees 是 1 到 45 度。",
"例如向左转 30 度使用 {\"type\":\"look\",\"direction\":\"left\",\"degrees\":30}；不要填写 yaw、pitch 或正负号。",
"每次 look 后重新 observe，并比较当前截图与上一张截图中地标的位置、大小和遮挡变化，确认实际转向符合预期。",
```

- [ ] **Step 4: Run focused and full Python AI Play tests and verify GREEN**

```bash
PYTHONPATH=ai_play/src /Users/jan/workspace/Phazorknight-Cogito/.venv/bin/python -m pytest \
  ai_play/tests/test_action_schema.py ai_play/tests/test_briefing.py -q
PYTHONPATH=ai_play/src /Users/jan/workspace/Phazorknight-Cogito/.venv/bin/python -m pytest ai_play/tests -q
```

Expected: both commands PASS with zero failures.

- [ ] **Step 5: Commit the Python boundary**

```bash
git add ai_play/src/ai_play/action_schema.py ai_play/src/ai_play/common_briefing_rules.py \
  ai_play/tests/test_action_schema.py ai_play/tests/test_briefing.py
git commit -m "feat(ai-play): validate semantic look actions"
```

### Task 2: Godot semantic direction mapping

**Files:**
- Modify: `tests/ai_play/test_ai_play_executor.gd`
- Modify: `addons/cogito/AIPlay/ai_play_executor.gd`

**Interfaces:**
- Consumes: the protocol-v3 semantic look dictionary validated by Python.
- Produces: `func _semantic_look_delta(direction: String, degrees: float) -> Vector2`, returning private `(yaw, pitch)` deltas; the existing completed look result shape is unchanged.

- [ ] **Step 1: Write failing Godot mapping and validation tests**

```gdscript
var cases: Array[Dictionary] = [
	{"action": {"type": "look", "direction": "left", "degrees": 30}, "delta": Vector2(-30, 0)},
	{"action": {"type": "look", "direction": "right", "degrees": 30}, "delta": Vector2(30, 0)},
	{"action": {"type": "look", "direction": "up", "degrees": 15}, "delta": Vector2(0, -15)},
	{"action": {"type": "look", "direction": "down", "degrees": 15}, "delta": Vector2(0, 15)},
]
for case: Dictionary in cases:
	_assert(executor.validate_action(case.action, {}).get("valid", false), "accepts semantic look")
	_assert(executor._semantic_look_delta(case.action.direction, case.action.degrees) == case.delta, "maps semantic look")
_assert_invalid(executor, {"type": "look", "yaw": 15, "pitch": 0}, {}, "numeric look")
_assert_invalid(executor, {"type": "look", "direction": "left", "degrees": 0}, {}, "zero look")
_assert_invalid(executor, {"type": "look", "direction": "left", "degrees": 45.1}, {}, "oversized look")
```

- [ ] **Step 2: Run the executor test and verify RED**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
```

Expected: FAIL because the executor still expects `yaw`/`pitch` and has no mapping helper.

- [ ] **Step 3: Implement mirrored validation and mapping**

```gdscript
const ACTION_FIELDS: Dictionary = {
	"look": ["type", "direction", "degrees"],
	# Keep every existing non-look entry unchanged.
}
const LOOK_DIRECTIONS: Array[String] = ["left", "right", "up", "down"]
const LOOK_MAX_DEGREES: float = 45.0

func _semantic_look_delta(direction: String, degrees: float) -> Vector2:
	match direction:
		"left": return Vector2(-degrees, 0.0)
		"right": return Vector2(degrees, 0.0)
		"up": return Vector2(0.0, -degrees)
		"down": return Vector2(0.0, degrees)
	return Vector2.ZERO
```

Validate direction membership and `_number_error(degrees, 1.0, 45.0, "degrees")`. In `_execute_action`, derive `look_delta` and pass its `x/y` to either `ai_play_look_degrees` or `_look_degrees_to_mouse_relative`.

- [ ] **Step 4: Run executor and controller tests and verify GREEN**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: both scripts print their pass marker and exit 0.

- [ ] **Step 5: Commit semantic execution**

```bash
git add addons/cogito/AIPlay/ai_play_executor.gd tests/ai_play/test_ai_play_executor.gd
git commit -m "feat(ai-play): map semantic look directions"
```

### Task 3: AI-only mouse guard and rendered observation synchronization

**Files:**
- Create: `tests/ai_play/test_cogito_player_ai_mouse_guard.gd`
- Modify: `tests/ai_play/test_ai_play_controller.gd`
- Modify: `addons/cogito/CogitoObjects/cogito_player.gd`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`

**Interfaces:**
- Produces on `CogitoPlayer`: `func set_ai_play_mouse_motion_device(device_id: int) -> void`; `-1` disables the guard.
- Consumes in `AIPlayController`: the setter with `EXECUTOR_DEVICE_ID` during AI control and `-1` on disable/teardown.

- [ ] **Step 1: Write failing real-player and controller lifecycle tests**

The new real-player test loads `res://addons/cogito/PackedScenes/cogito_player.tscn`, records initial `body`/`head` rotation, and exercises literal device IDs:

```gdscript
player.set_ai_play_mouse_motion_device(AIPlayExecutor.SYNTHETIC_DEVICE_ID)
var physical := InputEventMouseMotion.new()
physical.device = 0
physical.relative = Vector2(40, 20)
player._input(physical)
_assert(player.body.rotation == starting_body, "guard blocks physical yaw")
_assert(player.head.rotation == starting_head, "guard blocks physical pitch")

var synthetic := InputEventMouseMotion.new()
synthetic.device = AIPlayExecutor.SYNTHETIC_DEVICE_ID
synthetic.relative = Vector2(40, 20)
player._input(synthetic)
_assert(not player.body.rotation.is_equal_approx(starting_body), "guard accepts AI yaw")

player.set_ai_play_mouse_motion_device(-1)
var restored_body := player.body.rotation
player._input(physical)
_assert(not player.body.rotation.is_equal_approx(restored_body), "disable restores human yaw")
```

In controller tests, assert the fixture player guard equals the executor device after `enable_ai`, remains set across reconnect, becomes `-1` after `disable_ai`, and becomes `-1` before teardown completes. Retain existing Escape assertions. Change immediate-recapture tests to assert no capture before `RenderingServer.frame_post_draw` and one capture afterward.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
godot --headless --path . --script tests/ai_play/test_cogito_player_ai_mouse_guard.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: FAIL because the guard method and lifecycle toggles do not exist, and deferred recapture does not wait for post-draw.

- [ ] **Step 3: Implement the minimal player guard**

```gdscript
var _ai_play_mouse_motion_device: int = -1

func set_ai_play_mouse_motion_device(device_id: int) -> void:
	_ai_play_mouse_motion_device = device_id

func _accepts_mouse_motion(event: InputEventMouseMotion) -> bool:
	return _ai_play_mouse_motion_device < 0 or event.device == _ai_play_mouse_motion_device
```

Gate only the existing mouse-motion branch with `_accepts_mouse_motion(event)`. Do not gate Escape, keys, buttons, joypad input, or post-AI human mouse motion.

- [ ] **Step 4: Toggle the guard across controller lifecycle**

```gdscript
func _set_ai_mouse_guard(enabled: bool) -> void:
	if player != null and player.has_method("set_ai_play_mouse_motion_device"):
		player.set_ai_play_mouse_motion_device(EXECUTOR_DEVICE_ID if enabled else -1)
```

Call it with `true` at the start of `enable_ai`, with `false` in `disable_ai`, and with `false` in `_exit_tree`. Do not clear it on transient reconnect because autonomous control remains active and Escape remains available.

- [ ] **Step 5: Capture only after a rendered frame**

```gdscript
func _capture_observation_if_current(generation: int, results: Array) -> void:
	await RenderingServer.frame_post_draw
	if generation != _capture_generation or _state != State.READY or is_queued_for_deletion() or not is_inside_tree():
		return
	_capture_observation(results)
```

Keep the generation check after the await so teardown, stop, disconnect, and newer captures cancel stale work.

- [ ] **Step 6: Run affected Godot suites and verify GREEN**

```bash
godot --headless --path . --script tests/ai_play/test_cogito_player_ai_mouse_guard.gd
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_interaction_probe.gd
```

Expected: every script prints its pass marker and exits 0; Escape and cleanup tests remain green.

- [ ] **Step 7: Commit isolation and synchronization**

```bash
git add addons/cogito/CogitoObjects/cogito_player.gd addons/cogito/AIPlay/ai_play_controller.gd \
  tests/ai_play/test_cogito_player_ai_mouse_guard.gd tests/ai_play/test_ai_play_controller.gd
git commit -m "fix(ai-play): isolate semantic camera turns"
```

### Task 4: Codex guidance, stable documentation, and real comparison

**Files:**
- Modify: `tests/test_ai_play_codex_orchestrator.py`
- Modify: `tools/ai_play_codex_orchestrator.py`
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

**Interfaces:**
- Consumes: semantic look public contract from Tasks 1–3.
- Produces: identical AWM/no-AWM high-priority visual instructions and documented operator contract.

- [ ] **Step 1: Write failing player-guidance tests**

```python
instructions = orchestrator.build_player_developer_instructions()
assert '{"direction":"left","degrees":30}' in instructions
assert "不要填写 yaw、pitch 或正负号" in instructions
assert "比较当前截图与本会话之前由 observe 返回的截图" in instructions
assert "地标" in instructions

for enabled in (False, True):
    prompt = orchestrator.build_player_prompt(3, workflow_memory_enabled=enabled)
    assert "direction、degrees" in prompt
    assert "不要填写 yaw、pitch" in prompt
```

- [ ] **Step 2: Run orchestrator tests and verify RED**

```bash
/Users/jan/workspace/Phazorknight-Cogito/.venv/bin/python -m pytest \
  tests/test_ai_play_codex_orchestrator.py -q
```

Expected: FAIL because generated instructions do not yet show the semantic action contract.

- [ ] **Step 3: Update generated instructions and stable docs**

Add this common text to `build_player_developer_instructions()` and the common prompt section:

```text
look 只使用 direction 和 degrees，例如向左转 30 度是
{"type":"look","direction":"left","degrees":30}。direction 只能是
left、right、up、down；不要填写 yaw、pitch 或正负号。每次转向后比较当前与上一张
observe 截图中地标的位置、大小与遮挡变化，确认方向正确后再移动。
```

Replace numeric look documentation in `ai_play/README.md`. Update the wiki cross-layer contract with semantic fields, `[1,45]`, mirrored validation, AI-only mouse-motion guard, render-complete capture, and unchanged Escape behavior.

- [ ] **Step 4: Run full affected verification**

```bash
PYTHONPATH=ai_play/src /Users/jan/workspace/Phazorknight-Cogito/.venv/bin/python -m pytest ai_play/tests -q
/Users/jan/workspace/Phazorknight-Cogito/.venv/bin/python -m pytest \
  tests/test_ai_play_codex_orchestrator.py tests/test_find_contract_awm_comparison.py \
  tests/test_ai_play_supervisor.py -q
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_cogito_player_ai_mouse_guard.gd
git diff --check
```

Expected: all pytest and Godot commands exit 0; `git diff --check` has no output.

- [ ] **Step 5: Commit documentation and player guidance**

```bash
git add tools/ai_play_codex_orchestrator.py tests/test_ai_play_codex_orchestrator.py \
  ai_play/README.md docs/wiki/ai-play/system-guide.md
git commit -m "docs(ai-play): teach semantic visual exploration"
```

- [ ] **Step 6: Run controlled real acceptance and unattended comparison**

Run one no-AWM attempt and inspect its first look trajectory for requested direction, public orientation delta, and before/after screenshots. If they agree, run:

```bash
/opt/homebrew/bin/python3 tools/run_find_contract_awm_comparison.py \
  --runs 3 --model gpt-5.6-sol --reasoning-effort high \
  --codex-auth-home ~/.codex-cogito-player
```

Expected: `without_awm` then `with_awm` execute without prompts; both console logs and `comparison_summary.json` are preserved under `/tmp/cogito_ai_player_comparisons/<timestamp>/` even if a group exits non-zero.

- [ ] **Step 7: Report evidence and Git state**

Report the comparison directory, per-group success/failure counts and reasons, elapsed times, trajectory locations, verification commands, current `feature/session-awm` commits, and push state. Do not attribute a score difference solely to AWM; game randomness and model sampling remain uncontrolled.
