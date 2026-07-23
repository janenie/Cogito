# AI Interaction Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the AI identify a visible object by normalized screenshot coordinates, have Godot align and locally scan the crosshair through normal mouse input, then return a fresh observation without automatically interacting.

**Architecture:** Extend the strict Python/Godot action protocol with an exclusive `probe_interaction` action. Put camera alignment and bounded scanning in a focused `AIPlayInteractionProbe` node that consumes only the observer's approved interaction list; the existing executor delegates to it and the controller immediately re-observes after completion.

**Tech Stack:** Python 3.13, pytest, Godot 4 GDScript, OpenAI-compatible Chat Completions, loopback WebSocket protocol v1

## Global Constraints

- `probe_interaction` has exactly `type`, `target_x`, and `target_y`.
- Both coordinates are finite numbers in the inclusive range `0.0..1.0`.
- A probe must be the only action in its batch and is forbidden while an interface is open.
- A probe never moves the player and never emits `interact` or `interact2`.
- Alignment uses synthetic mouse input; it never writes player or camera transforms.
- The local scan tests at most nine positions and at most four degrees on either axis.
- A successful probe leaves the camera aligned; a failed probe restores the pre-probe orientation.
- Completed outcomes are `aligned` and `not_found`; cancellation keeps the existing cancellation shape.
- Every completed probe causes immediate re-observation.
- Normal startup uses `ai_play/start_ai.sh` and `api_key.py`; the YibuAPI launcher is outside this feature.

---

## File Structure

- Modify `ai_play/src/ai_play/action_schema.py`: validate the new model action and exclusive-batch rule.
- Modify `ai_play/src/ai_play/observation_schema.py`: validate completed probe result fields.
- Modify `ai_play/src/ai_play/prompts.py`: teach the model when and how to probe.
- Modify `ai_play/tests/test_action_schema.py`, `test_observation_schema.py`, and `test_prompts.py`: Python protocol regression coverage.
- Modify `addons/cogito/AIPlay/ai_play_observer.gd`: expose the already-filtered interaction list through a public method.
- Create `addons/cogito/AIPlay/ai_play_interaction_probe.gd`: own target-angle math, synthetic camera input, bounded scanning, restoration, and cancellation.
- Create `tests/ai_play/test_ai_play_interaction_probe.gd`: focused probe behavior and safety tests.
- Modify `addons/cogito/AIPlay/ai_play_executor.gd`: validate and delegate the new action.
- Modify `addons/cogito/AIPlay/ai_play_controller.gd` and `.tscn`: wire the probe and trigger immediate observation.
- Modify `tests/ai_play/test_ai_play_executor.gd`, `test_ai_play_controller.gd`, and `test_ai_play_observer.gd`: integration regression coverage.
- Modify `ai_play/README.md`: document the action behavior and normal `api_key.py` startup.

### Task 1: Extend the Python Action and Observation Protocol

**Files:**
- Modify: `ai_play/src/ai_play/action_schema.py`
- Modify: `ai_play/src/ai_play/observation_schema.py`
- Modify: `ai_play/src/ai_play/prompts.py`
- Test: `ai_play/tests/test_action_schema.py`
- Test: `ai_play/tests/test_observation_schema.py`
- Test: `ai_play/tests/test_prompts.py`

**Interfaces:**
- Consumes: `validate_decision(payload, available_interactions, interface_open)` and `validate_action_results(results)`.
- Produces: validated `{"type":"probe_interaction","target_x":float,"target_y":float}` actions and completed results with `outcome` plus `scan_steps`.

- [ ] **Step 1: Write failing action-schema tests**

Add tests that cover valid normalized coordinates, each invalid coordinate
class, interface rejection, and exclusive batching:

```python
def test_probe_interaction_accepts_normalized_target():
    payload = {
        "reason": "Check the visible red button.",
        "memory_updates": [],
        "actions": [
            {"type": "probe_interaction", "target_x": 0.2, "target_y": 0.3}
        ],
    }
    assert validate_decision(payload, [], False) == payload


@pytest.mark.parametrize("value", [-0.01, 1.01, float("inf"), float("nan"), True, "0.5"])
def test_probe_interaction_rejects_invalid_coordinate(value):
    payload = {
        "reason": "Probe.",
        "memory_updates": [],
        "actions": [
            {"type": "probe_interaction", "target_x": value, "target_y": 0.5}
        ],
    }
    with pytest.raises(ActionValidationError):
        validate_decision(payload, [], False)


def test_probe_interaction_must_be_only_action_and_requires_closed_interface():
    probe = {"type": "probe_interaction", "target_x": 0.5, "target_y": 0.5}
    for actions, interface_open in [
        ([{"type": "look", "yaw": 1.0, "pitch": 0.0}, probe], False),
        ([probe, {"type": "wait", "duration_ms": 50}], False),
        ([probe], True),
    ]:
        with pytest.raises(ActionValidationError):
            validate_decision(
                {"reason": "Probe.", "memory_updates": [], "actions": actions},
                [],
                interface_open,
            )
```

- [ ] **Step 2: Run the action-schema tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_action_schema.py -q
```

Expected: the new tests fail because `probe_interaction` is not allowed.

- [ ] **Step 3: Implement minimal Python action validation**

Add the exact action fields:

```python
ALLOWED_KEYS = {
    # existing actions...
    "probe_interaction": {"type", "target_x", "target_y"},
}
```

In `_validate_action`:

```python
elif action_type == "probe_interaction":
    _require_number(action["target_x"], 0, 1, "target_x")
    _require_number(action["target_y"], 0, 1, "target_y")
    if interface_open:
        raise ActionValidationError(
            "probe_interaction requires a closed interface"
        )
```

In `validate_decision`, before returning:

```python
if any(action["type"] == "probe_interaction" for action in actions) and len(actions) != 1:
    raise ActionValidationError("probe_interaction must be the only action")
```

- [ ] **Step 4: Write failing probe-result tests**

Add:

```python
@pytest.mark.parametrize("outcome", ["aligned", "not_found"])
def test_probe_result_accepts_completed_outcome(outcome):
    results = [{
        "status": "completed",
        "type": "probe_interaction",
        "outcome": outcome,
        "scan_steps": 3,
    }]
    assert validate_action_results(results) == results


@pytest.mark.parametrize(
    "patch",
    [
        {"outcome": "clicked"},
        {"scan_steps": -1},
        {"scan_steps": 10},
        {"scan_steps": 1.5},
    ],
)
def test_probe_result_rejects_invalid_fields(patch):
    result = {
        "status": "completed",
        "type": "probe_interaction",
        "outcome": "aligned",
        "scan_steps": 1,
        **patch,
    }
    with pytest.raises(ObservationValidationError):
        validate_action_results([result])
```

- [ ] **Step 5: Run the observation-schema tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_observation_schema.py -q
```

Expected: completed probe results fail the current exact-field validation.

- [ ] **Step 6: Implement minimal probe-result validation**

Add `probe_interaction` to `ACTION_TYPES`. Extend the initial allowed result
field set from `{"status", "type", "error", "reason"}` to include `outcome`
and `scan_steps`. In `validate_action_results`, branch completed probe results
before the normal completed-result exact-field check:

```python
if status == "completed" and result.get("type") == "probe_interaction":
    if set(result) != {"status", "type", "outcome", "scan_steps"}:
        raise ObservationValidationError("probe result fields are invalid")
    if result["outcome"] not in {"aligned", "not_found"}:
        raise ObservationValidationError("probe outcome is invalid")
    if type(result["scan_steps"]) is not int or not 0 <= result["scan_steps"] <= 9:
        raise ObservationValidationError("probe scan_steps is invalid")
```

Copy `outcome` and `scan_steps` into `safe_result` only in this branch.

- [ ] **Step 7: Write failing prompt tests**

Assert that the fixed prompt documents all constraints:

```python
def test_prompt_documents_interaction_probe():
    assert "`probe_interaction`" in SYSTEM_PROMPT
    assert "`target_x`" in SYSTEM_PROMPT
    assert "`target_y`" in SYSTEM_PROMPT
    assert "only action in its batch" in SYSTEM_PROMPT
    assert "does not activate" in SYSTEM_PROMPT
    assert '"type":"probe_interaction"' in SYSTEM_PROMPT
```

- [ ] **Step 8: Run prompt tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_prompts.py -q
```

Expected: the new prompt assertions fail.

- [ ] **Step 9: Document the action in the system prompt**

Add:

```text
- `probe_interaction` attempts to align the crosshair with a visible object at
  normalized image coordinates `target_x` and `target_y`, each from 0 through 1.
  It does not activate the object. Use it only for a visible, plausible
  interaction target. It must be the only action in its batch and requires a
  closed interface. After it completes, inspect the fresh observation and use
  only the newly reported `available_interactions`.
```

Add the exact shape to the allowed action list:

```text
- {"type":"probe_interaction","target_x":<finite normalized x>,"target_y":<finite normalized y>}
```

- [ ] **Step 10: Run focused and full Python tests**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_action_schema.py \
  ai_play/tests/test_observation_schema.py \
  ai_play/tests/test_prompts.py -q
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
```

Expected: all tests pass.

- [ ] **Step 11: Commit Task 1**

```bash
git add \
  ai_play/src/ai_play/action_schema.py \
  ai_play/src/ai_play/observation_schema.py \
  ai_play/src/ai_play/prompts.py \
  ai_play/tests/test_action_schema.py \
  ai_play/tests/test_observation_schema.py \
  ai_play/tests/test_prompts.py
git commit -m "feat: add interaction probe protocol"
```

### Task 2: Add the Focused Godot Interaction Probe

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_observer.gd`
- Create: `addons/cogito/AIPlay/ai_play_interaction_probe.gd`
- Modify: `tests/ai_play/test_ai_play_observer.gd`
- Create: `tests/ai_play/test_ai_play_interaction_probe.gd`

**Interfaces:**
- Consumes: `AIPlayObserver.get_available_interactions() -> Array[Dictionary]`, active `Camera3D.fov`, viewport aspect ratio, `player.MOUSE_SENS`, `player.INVERT_Y_AXIS`, and player yaw/pitch.
- Produces: `AIPlayInteractionProbe.probe(target_x: float, target_y: float) -> Dictionary` and `cancel(reason: String) -> void`.

- [ ] **Step 1: Write a failing observer public-interface test**

In `test_ai_play_observer.gd`, after the fixture creates primary and secondary
interactions:

```gdscript
_assert(
    observer.get_available_interactions() == [
        {"action": "interact", "binding": "F", "prompt": "Read"},
        {"action": "interact2", "binding": "E", "prompt": "Move"},
    ],
    "observer publicly exposes only approved visible interactions",
)
```

- [ ] **Step 2: Run the observer test and verify RED**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
```

Expected: failure because `get_available_interactions` does not exist.

- [ ] **Step 3: Expose the filtered observer method**

Change capture to call a public method and keep the existing filter:

```gdscript
"available_interactions": get_available_interactions(),
```

```gdscript
func get_available_interactions() -> Array[Dictionary]:
    return _available_interactions()
```

- [ ] **Step 4: Write the failing probe tests**

Create `test_ai_play_interaction_probe.gd` with fixtures that:

- Assert `target_rotation_degrees(0.5, 0.5, 75.0, 16.0 / 9.0)` is zero.
- Assert left/right coordinates produce opposite yaw signs.
- Assert top/bottom coordinates produce opposite pitch signs.
- Assert all `SCAN_OFFSETS_DEGREES` components are within `-4.0..4.0` and the
  list has exactly nine entries.
- Supply an interaction provider that returns `[]` twice and `[{"action":
  "interact"}]` on the third check; assert the result is:

```gdscript
{
    "status": "completed",
    "type": "probe_interaction",
    "outcome": "aligned",
    "scan_steps": 3,
}
```

- Supply a provider that always returns `[]`; assert `not_found`, nine scan
  steps, and a final restoration mouse event.
- Record all `InputEventAction` events and assert no event action is `interact`
  or `interact2`.
- Call `cancel("escape_stop")` during a probe and assert the coroutine returns
  `{"status": "cancelled", "reason": "escape_stop"}`.

- [ ] **Step 5: Run the probe test and verify RED**

Run:

```bash
godot --headless --path . --script \
  tests/ai_play/test_ai_play_interaction_probe.gd
```

Expected: parse/load failure because `ai_play_interaction_probe.gd` does not
exist.

- [ ] **Step 6: Implement the probe component**

Create `AIPlayInteractionProbe` with this public surface:

```gdscript
class_name AIPlayInteractionProbe
extends Node

const SYNTHETIC_DEVICE_ID: int = 0x7ffffffe
const SCAN_OFFSETS_DEGREES: Array[Vector2] = [
    Vector2.ZERO,
    Vector2(2.0, 0.0),
    Vector2(-2.0, 0.0),
    Vector2(0.0, 2.0),
    Vector2(0.0, -2.0),
    Vector2(4.0, 4.0),
    Vector2(-4.0, 4.0),
    Vector2(4.0, -4.0),
    Vector2(-4.0, -4.0),
]

var player: Node
var interaction_provider: Callable
var _generation: int = 0
var _cancel_reason: String = "cancelled"

func probe(target_x: float, target_y: float) -> Dictionary
func cancel(reason: String) -> void
func target_rotation_degrees(
    target_x: float,
    target_y: float,
    vertical_fov_degrees: float,
    aspect_ratio: float
) -> Vector2
```

Use perspective projection for the target angle:

```gdscript
var vertical_tangent := tan(deg_to_rad(vertical_fov_degrees * 0.5))
var ndc_x := target_x * 2.0 - 1.0
var ndc_y := target_y * 2.0 - 1.0
var yaw := rad_to_deg(atan(ndc_x * vertical_tangent * aspect_ratio))
var pitch := rad_to_deg(atan(ndc_y * vertical_tangent))
return Vector2(yaw, pitch)
```

Convert desired yaw/pitch rotation to `InputEventMouseMotion.relative` using
`player.MOUSE_SENS` and `player.INVERT_Y_AXIS`, emit the event with
`SYNTHETIC_DEVICE_ID`, wait one process frame, then query
`interaction_provider.call()`.

For a target angle `Vector2(yaw_to_right, pitch_to_bottom)`, use the player's
actual rotation conventions:

```gdscript
var desired_yaw_delta := -yaw_to_right
var desired_pitch_delta := -pitch_to_bottom
var relative_x := -desired_yaw_delta / player.MOUSE_SENS
var relative_y := (
    desired_pitch_delta / player.MOUSE_SENS
    if player.INVERT_Y_AXIS
    else -desired_pitch_delta / player.MOUSE_SENS
)
```

Store starting yaw and pitch. On `not_found`, compute wrapped yaw and bounded
pitch differences back to the starting orientation and restore them through the
same mouse-input helper.

- [ ] **Step 7: Run focused Godot tests**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script \
  tests/ai_play/test_ai_play_interaction_probe.gd
```

Expected: both scripts exit 0 and print their pass messages.

- [ ] **Step 8: Commit Task 2**

```bash
git add \
  addons/cogito/AIPlay/ai_play_observer.gd \
  addons/cogito/AIPlay/ai_play_interaction_probe.gd \
  tests/ai_play/test_ai_play_observer.gd \
  tests/ai_play/test_ai_play_interaction_probe.gd
git commit -m "feat: add bounded interaction probe"
```

### Task 3: Integrate Probe Execution and Immediate Observation

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_executor.gd`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `addons/cogito/AIPlay/ai_play_controller.tscn`
- Modify: `tests/ai_play/test_ai_play_executor.gd`
- Modify: `tests/ai_play/test_ai_play_controller.gd`

**Interfaces:**
- Consumes: `AIPlayInteractionProbe.probe(target_x, target_y)` and
  `AIPlayObserver.get_available_interactions()`.
- Produces: Godot-side validation, delegation, cancellation, and immediate
  recapture for completed probe outcomes.

- [ ] **Step 1: Write failing executor validation tests**

Add cases equivalent to Python:

```gdscript
var probe := {
    "type": "probe_interaction",
    "target_x": 0.25,
    "target_y": 0.75,
}
_assert(
    executor.validate_batch([probe], {"interface_open": false})
        == {"valid": true},
    "accepts one normalized probe with closed interface",
)
_assert_invalid(
    executor,
    {"type": "probe_interaction", "target_x": -0.1, "target_y": 0.5},
    {"interface_open": false},
    "probe coordinate outside image",
)
_assert(
    not executor.validate_batch(
        [probe, {"type": "wait", "duration_ms": 50}],
        {"interface_open": false},
    ).get("valid", false),
    "probe must be the only action",
)
_assert_invalid(
    executor,
    probe,
    {"interface_open": true},
    "probe with open interface",
)
```

- [ ] **Step 2: Run executor tests and verify RED**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
```

Expected: probe validation fails because the action is unknown.

- [ ] **Step 3: Implement executor validation and delegation**

Add:

```gdscript
"probe_interaction": ["type", "target_x", "target_y"],
```

Validate both coordinates with `_number_error(value, 0.0, 1.0, field)`, reject
an open interface, and in `validate_batch` reject any probe when
`actions.size() != 1`.

Add:

```gdscript
var interaction_probe: AIPlayInteractionProbe
```

Delegate in `_execute_action`:

```gdscript
"probe_interaction":
    if interaction_probe == null:
        return {"status": "error", "error": "interaction probe is unavailable"}
    return await interaction_probe.probe(
        float(action["target_x"]),
        float(action["target_y"]),
    )
```

Call `interaction_probe.cancel(reason)` from `cancel_all` and `_exit_tree`.

- [ ] **Step 4: Write failing controller tests**

Extend the controller fixture with a fake probe and assert:

- `_ready` gives the probe the same player as observer/executor.
- The probe interaction provider calls
  `observer.get_available_interactions`.
- A completed `aligned` probe causes deferred capture immediately.
- A completed `not_found` probe causes deferred capture immediately.
- Probe cancellation on Escape produces no delayed capture.

Use these exact completed result shapes:

```gdscript
{"status": "completed", "type": "probe_interaction", "outcome": "aligned", "scan_steps": 2}
{"status": "completed", "type": "probe_interaction", "outcome": "not_found", "scan_steps": 9}
```

- [ ] **Step 5: Run controller tests and verify RED**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: assertions fail because the controller has no probe node or immediate
recapture rule.

- [ ] **Step 6: Wire the probe scene and controller**

Add the script resource and node in `ai_play_controller.tscn`:

```text
[ext_resource type="Script" path="res://addons/cogito/AIPlay/ai_play_interaction_probe.gd" id="5_probe"]

[node name="InteractionProbe" type="Node" parent="."]
script = ExtResource("5_probe")
```

In controller `_ready`:

```gdscript
var _interaction_probe: AIPlayInteractionProbe

_interaction_probe = get_node("InteractionProbe")
_interaction_probe.player = player
_interaction_probe.interaction_provider = Callable(
    _observer,
    "get_available_interactions",
)
_executor.interaction_probe = _interaction_probe
```

Extend `_ends_with_immediate_recapture`:

```gdscript
return (
    final_result.get("status") == "completed"
    and final_result.get("type") in [
        "interact",
        "enter_digits",
        "close_ui",
        "probe_interaction",
    ]
)
```

- [ ] **Step 7: Run focused Godot tests and import validation**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --editor --quit
```

Expected: all commands exit 0 without parse or resource errors.

- [ ] **Step 8: Commit Task 3**

```bash
git add \
  addons/cogito/AIPlay/ai_play_executor.gd \
  addons/cogito/AIPlay/ai_play_controller.gd \
  addons/cogito/AIPlay/ai_play_controller.tscn \
  tests/ai_play/test_ai_play_executor.gd \
  tests/ai_play/test_ai_play_controller.gd
git commit -m "feat: integrate AI interaction probing"
```

### Task 4: Document and Verify the Complete Exploration Loop

**Files:**
- Modify: `ai_play/README.md`
- Verify: `api_key.py` through static configuration loading only
- Verify: all Python and Godot AI Play tests
- Verify: one intentional Lobby run

**Interfaces:**
- Consumes: normal `ai_play/start_ai.sh` startup and the complete probe protocol.
- Produces: operator documentation and evidence that the model can probe,
  receive interactions, and separately choose an interaction.

- [ ] **Step 1: Update operator documentation**

Add a controls subsection:

```markdown
`probe_interaction` accepts normalized coordinates from the current 768x432
camera image. It aligns and scans the crosshair through normal camera input but
never activates the target. A completed probe immediately produces a fresh
observation. Only the model's next action may choose an interaction from the
new `available_interactions` list.

The bounded scan checks at most nine positions within four degrees on either
axis. `not_found` means the model should approach, change angle, or abandon the
target. It does not mean the object is globally non-interactive.
```

Keep the existing setup statement that `api_key.py` is statically parsed and
environment variables override it.

- [ ] **Step 2: Run secret-safe configuration checks**

Run:

```bash
tests/check_ai_play_secrets.sh
tests/check_ai_play_start_script.sh
env -u AI_PLAY_API_KEY -u AI_PLAY_BASE_URL \
  PYTHONPATH=ai_play/src .venv/bin/python -c \
  'from ai_play.config import Config; c=Config.from_env(); print(bool(c.api_key), c.base_url.startswith("http"), c.model)'
```

Expected: secret scans pass; the final command prints `True True` and the model
name without printing the key or full URL.

- [ ] **Step 3: Run the complete automated verification suite**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_interaction_probe.gd
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --editor --quit
```

Expected: all Python tests pass, every GDScript reports its pass message, and
Godot exits without import or parse failures.

- [ ] **Step 4: Start a real sidecar with `api_key.py`**

With no `AI_PLAY_API_KEY` or `AI_PLAY_BASE_URL` override:

```bash
env -u AI_PLAY_API_KEY -u AI_PLAY_BASE_URL ./ai_play/start_ai.sh
```

Expected startup output includes `127.0.0.1:8765`, the configured model, and a
new log directory. It must not print the key or full base URL.

- [ ] **Step 5: Start the Lobby and observe one black-box run**

In a second process:

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn -- --ai-play
```

Allow the model to explore until the run log contains either the full success
chain or enough bounded failures to diagnose:

```text
probe_interaction -> aligned -> fresh available_interactions -> interact
```

Stop with Escape. Do not seed scene-specific solutions or hidden object data.

- [ ] **Step 6: Inspect the run log without exposing image bytes or secrets**

Resolve the newest run log under the configured default root, then inspect it:

```bash
probe_log_path="$(
  find /Users/jan/workspace/cogito_logs \
    -type f -name gemini_godot.jsonl -print \
  | sort \
  | tail -n 1
)"
jq -c '
  select(
    .event == "decision_validated"
    or .event == "godot_result"
    or .event == "model_input"
  )
  | {
      event,
      round_idx,
      actions: .decision.actions,
      results,
      interactions: .observation.interface.available_interactions
    }
' "$probe_log_path"
```

Expected: at least one probe result is visible. For acceptance, an `aligned`
result is followed by a fresh nonempty interaction list, and any later
`interact` appears in a separate model decision.

- [ ] **Step 7: Commit Task 4**

```bash
git add ai_play/README.md
git commit -m "docs: explain AI interaction probing"
```

- [ ] **Step 8: Review final scope**

Run:

```bash
git status --short
git diff HEAD~4 --stat
git log --oneline -6
```

Expected: only the planned interaction-probe files are committed. Existing
unrelated YibuAPI experiment files remain untouched and uncommitted.
