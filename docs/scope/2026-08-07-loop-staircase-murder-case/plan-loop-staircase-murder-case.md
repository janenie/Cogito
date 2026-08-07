# Loop Staircase Murder Case Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unchanged-room puzzle with a deterministic five-round murder-room investigation whose four evidence histories identify one floor only when time-aligned.

**Architecture:** A pure trusted-side case generator owns themes, visible round states, private candidate sets, and consistency checks. `LoopStaircaseManager` coordinates play, a focused room builder renders themes/evidence, and a focused investigation board stores screenshots and manual marks without receiving hidden case data.

**Tech Stack:** Godot 4.7, typed GDScript, Godot headless SceneTree tests, Python 3 with pytest, AI Play protocol v4.

---

### Task 1: Commit the approved design contract

**Files:**
- Create: `docs/scope/2026-08-07-loop-staircase-murder-case/spec-loop-staircase-murder-case.md`
- Create: `docs/scope/2026-08-07-loop-staircase-murder-case/plan-loop-staircase-murder-case.md`
- Modify: `docs/wiki/ai-play/system-guide.md:615`

- [ ] **Step 1: Verify the durable rules**

```bash
rg -n "五轮凶案推理 spec|8 → 6 → 5 → 3 → 2 → 1|Tab 打开调查板" docs/wiki/ai-play/system-guide.md
git diff --check
```

Expected: three Wiki matches and no diff-check output.

- [ ] **Step 2: Commit the design documents**

```bash
git add docs/scope/2026-08-07-loop-staircase-murder-case docs/wiki/ai-play/system-guide.md
git commit -m "docs: specify loop staircase murder case"
```

Expected: one documentation-only commit.

### Task 2: Build the deterministic trusted-side case model

**Files:**
- Create: `addons/cogito/DemoScenes/LoopStaircase/loop_staircase_case.gd`
- Modify: `tests/ai_play/test_loop_staircase_manager.gd:1`

- [ ] **Step 1: Write the failing 300-seed model test**

```gdscript
const EXPECTED_COUNTS: Array[int] = [8, 6, 5, 3, 2, 1]

func _assert_case(seed_value: int) -> void:
	var model_script: Script = load(
		"res://addons/cogito/DemoScenes/LoopStaircase/loop_staircase_case.gd"
	)
	_assert(model_script != null, "case model script loads")
	if model_script == null:
		return
	var first: RefCounted = model_script.generate(seed_value)
	var second: RefCounted = model_script.generate(seed_value)
	var snapshot: Dictionary = first.test_snapshot()
	_assert(snapshot == second.test_snapshot(), "seed %d is deterministic" % seed_value)
	_assert(first.is_consistent(), "seed %d is internally consistent" % seed_value)
	for index: int in range(EXPECTED_COUNTS.size()):
		_assert(snapshot["candidate_sets"][index].size() == EXPECTED_COUNTS[index], "candidate count")
	_assert(snapshot["candidate_sets"][-1] == [snapshot["true_floor"]], "one answer")
	for kind: String in ["visitor", "item", "trash", "signal"]:
		_assert(first.matching_floors_without(kind).size() > 1, "final needs %s" % kind)
```

Call this for `range(1, 301)`. Test paired-but-distinct `room_type`/`theme_id`; six visitor-name matches; five item-rule matches; the three exact-minus-one, one zero-trash, one noisy-trash roles; same-current-trash ambiguity; two strict two-color ABAB sequences; same-current-color ambiguity; and one four-way time match.

- [ ] **Step 2: Confirm the test fails**

```bash
godot --headless --path . --script tests/ai_play/test_loop_staircase_manager.gd
```

Expected: the test exits 1 with `case model script loads`; the failure is caused by the missing model, not malformed test syntax.

- [ ] **Step 3: Implement the pure model interface**

```gdscript
class_name LoopStaircaseCase
extends RefCounted

const ROOM_TYPES: Dictionary = {
	2: "lounge", 3: "lounge", 4: "archive", 5: "archive",
	6: "office", 7: "office", 8: "meeting", 9: "meeting",
}
const THEME_IDS: Dictionary = {
	2: "lounge_window", 3: "lounge_reading",
	4: "archive_paper", 5: "archive_digital",
	6: "office_manager", 7: "office_open",
	8: "meeting_round", 9: "meeting_boardroom",
}

var true_floor: int
var victim_name: String
var clues: Array[String] = []
var floor_states: Dictionary = {}
var candidate_sets: Array[Array] = []

static func generate(seed_value: int) -> LoopStaircaseCase:
	var result := LoopStaircaseCase.new()
	result._generate(seed_value)
	assert(result.is_consistent(), "generated staircase case is inconsistent")
	return result

func visible_state(floor_number: int, round_index: int) -> Dictionary:
	return (floor_states[floor_number][round_index] as Dictionary).duplicate(true)

func visible_clues(round_index: int) -> Array[String]:
	return clues.slice(0, clampi(round_index, 0, 4) + 1)
```

Pick the answer first with a local `RandomNumberGenerator`, construct nested sets sized 6, 5, 3, and 2, then generate evidence backward. Each visible state has `floor`, `room_type`, `theme_id`, `visitor_names`, `visitor_round_visible`, `visitor_round`, `tracked_item`, `item_count`, `trash_count`, `signal_color`, and `paired_floor`. Implement `test_snapshot()`, `is_consistent()`, and `matching_floors_without(kind)` using recomputed rules rather than stored candidate membership.

- [ ] **Step 4: Pass and commit the model test**

```bash
godot --headless --path . --script tests/ai_play/test_loop_staircase_manager.gd
git add addons/cogito/DemoScenes/LoopStaircase/loop_staircase_case.gd tests/ai_play/test_loop_staircase_manager.gd
git commit -m "feat: generate five-round staircase cases"
```

Expected: `Loop staircase manager test passed`.

### Task 3: Coordinate observations, clues, and final submission

**Files:**
- Modify: `addons/cogito/DemoScenes/LoopStaircase/loop_staircase_manager.gd:6-236`
- Modify: `tests/ai_play/test_loop_staircase_manager.gd:1`

- [ ] **Step 1: Write failing coordinator tests**

```gdscript
_assert(manager.get_visible_clue_lines().size() == 1, "one current clue")
manager.set_current_floor(9)
manager.move_up()
_assert(manager.current_loop == 0, "incomplete round is blocked")
_assert(manager.get_missing_floor_labels() == ["3F", "4F", "5F", "6F", "7F", "8F"], "neutral feedback")
for floor_number: int in range(2, 10):
	manager.mark_floor_observed(floor_number)
manager.move_up()
var lines: Array[String] = manager.get_visible_clue_lines()
_assert(lines[0].begins_with("第一轮线索："), "old clue label")
_assert(lines[1].begins_with("本轮线索："), "current clue label")
_assert(lines.size() == 2, "future clues hidden")
```

Also test that rounds 1–4 ignore submission, manual marks never finish the game, final correct/wrong reasons remain unchanged, and terminal state freezes navigation.

- [ ] **Step 2: Confirm old wrapping fails**

```bash
godot --headless --path . --script tests/ai_play/test_loop_staircase_manager.gd
```

Expected: FAIL on missing observation/clue methods.

- [ ] **Step 3: Replace anomaly arrays with coordinator state**

```gdscript
var _case: LoopStaircaseCase
var _observed_by_round: Array[Dictionary] = []
var _manual_candidates: Dictionary = {}

func configure_round(seed_value: int = 0) -> void:
	_case = LoopStaircaseCase.generate(seed_value)
	current_loop = 0
	_current_floor = FLOOR_MIN
	_round_finished = false
	_observed_by_round.clear()
	for round_index: int in range(TOTAL_LOOPS):
		_observed_by_round.append({})
	_manual_candidates.clear()

func get_floor_state(floor_number: int, loop_index: int = current_loop) -> Dictionary:
	if _case == null or floor_number < FLOOR_MIN or floor_number > FLOOR_MAX:
		return {}
	return _case.visible_state(floor_number, loop_index)
```

At 9F, advance only when `get_missing_floor_labels()` is empty. Implement `mark_floor_observed`, `get_visible_clue_lines`, `get_missing_floor_labels`, `toggle_candidate`, and `is_candidate_marked`. Keep `ai_play_public_state()` at its existing eight fields. `get_round_snapshot()` may expose trusted test state but must never feed the observer.

- [ ] **Step 4: Pass and commit coordinator tests**

```bash
godot --headless --path . --script tests/ai_play/test_loop_staircase_manager.gd
git add addons/cogito/DemoScenes/LoopStaircase/loop_staircase_manager.gd tests/ai_play/test_loop_staircase_manager.gd
git commit -m "feat: coordinate staircase investigation rounds"
```

Expected: manager tests pass with unchanged terminal reasons.

### Task 4: Render paired room themes and neutral evidence

**Files:**
- Create: `addons/cogito/DemoScenes/LoopStaircase/loop_staircase_room_builder.gd`
- Modify: `addons/cogito/DemoScenes/LoopStaircase/loop_staircase_manager.gd:373-506`
- Modify: `addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn:40`
- Modify: `tests/ai_play/test_loop_staircase_scene.gd:1`

- [ ] **Step 1: Write failing scene hierarchy tests**

For every floor, assert:

```gdscript
var room: Node = manager.get_node("CurrentFloorRoom")
_assert(room.has_meta("theme_id"), "%dF has a theme" % floor_number)
_assert(room.get_node_or_null("StableTheme") is Node3D, "%dF has stable furniture" % floor_number)
_assert(room.get_node_or_null("Evidence/VisitorRecord") is Label3D, "%dF has visitor record" % floor_number)
_assert(room.get_node_or_null("Evidence/ItemSlot") is Node3D, "%dF has item slot" % floor_number)
_assert(room.get_node_or_null("Evidence/Trash") is Node3D, "%dF has trash" % floor_number)
_assert(room.get_node_or_null("Evidence/SignalLight") is MeshInstance3D, "%dF has signal" % floor_number)
```

Require eight unique theme IDs. Each pair shares `room_type` but has different stable child names. Rounds 1–4 hide visitor times and round 5 reveals them. Evidence nodes have no outline, crime label, answer label, or `is_solution` metadata.

- [ ] **Step 2: Confirm the new hierarchy is absent**

```bash
godot --headless --path . --script tests/ai_play/test_loop_staircase_scene.gd -- --ai-play-scenario=loop_staircase_anomaly
```

Expected: FAIL on `StableTheme` or `Evidence`.

- [ ] **Step 3: Implement the focused builder**

```gdscript
class_name LoopStaircaseRoomBuilder
extends RefCounted

func build(parent: Node3D, state: Dictionary, helpers: Dictionary) -> void:
	parent.set_meta("theme_id", state["theme_id"])
	parent.set_meta("room_type", state["room_type"])
	_build_shell(parent, state, helpers)
	_build_stable_theme(parent, state, helpers)
	_build_evidence(parent, state, helpers)
```

Build: 2F corner-sofa/window lounge; 3F two-chair reading lounge; 4F paper-shelf archive; 5F digital-workbench archive; 6F manager office; 7F two-desk open office; 8F compact round-table meeting room; 9F long-table boardroom. Use existing prefabs plus box-mesh fallbacks, distinct wall colors/layouts, and stable landmark node names.

`Evidence` renders a function-appropriate visitor record, one neutral item slot, `trash_count` small paper meshes, and one material-colored signal sphere. Correct and incorrect candidates use equal scale, material family, and prominence.

- [ ] **Step 4: Delegate room creation and update the editor preview**

```gdscript
var _room_builder := LoopStaircaseRoomBuilder.new()

func _create_current_floor_room() -> void:
	var room := Node3D.new()
	room.name = "CurrentFloorRoom"
	add_child(room)
	_room_builder.build(room, get_floor_state(_current_floor), _room_builder_helpers())
	_add_floor_sign_and_navigation(room)
```

Keep navigation, answer interaction, floor sign, and wall light in the manager. Make the `.tscn` preview match 2F's hierarchy and retain `CurrentFloorRoom/WallWashLight`.

- [ ] **Step 5: Pass and commit visual tests**

```bash
bash tests/check_loop_staircase.sh
git add addons/cogito/DemoScenes/LoopStaircase/loop_staircase_room_builder.gd addons/cogito/DemoScenes/LoopStaircase/loop_staircase_manager.gd addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn tests/ai_play/test_loop_staircase_scene.gd
git commit -m "feat: render paired staircase room themes"
```

Expected: both wrapper tests pass without script or UID errors.

### Task 5: Add the screenshot investigation board

**Files:**
- Create: `addons/cogito/DemoScenes/LoopStaircase/loop_staircase_investigation_board.gd`
- Modify: `addons/cogito/DemoScenes/LoopStaircase/loop_staircase_manager.gd:41-264`
- Modify: `tests/ai_play/test_loop_staircase_scene.gd:1`

- [ ] **Step 1: Write failing board tests with an injected image**

```gdscript
var board: Control = manager.get_node("GameUI/InvestigationBoard")
var sample := Image.create(64, 36, false, Image.FORMAT_RGB8)
sample.fill(Color("3d5068"))
board.record_snapshot(2, 0, sample)
_assert(board.has_snapshot(2, 0), "board stores a floor-round image")
_assert(board.get_snapshot_count(0) == 1, "board counts stored images")
board.toggle_candidate(2)
_assert(board.is_candidate_marked(2), "manual mark toggles")
_assert(not board.has_method("compute_difference"), "no diff API")
_assert(not board.has_method("candidate_is_correct"), "no correctness API")
```

Also require 8 floor rows × 5 image columns, only current/past clue text, and board-open Up/Down/Space changing only row selection/manual marks.

- [ ] **Step 2: Confirm the board is absent**

```bash
godot --headless --path . --script tests/ai_play/test_loop_staircase_scene.gd -- --ai-play-scenario=loop_staircase_anomaly
```

Expected: FAIL loading `GameUI/InvestigationBoard`.

- [ ] **Step 3: Implement the board's narrow interface**

```gdscript
class_name LoopStaircaseInvestigationBoard
extends Control

signal candidate_changed(floor_number: int, marked: bool)
var selected_floor: int = 2
var _snapshots: Dictionary = {}
var _candidate_marks: Dictionary = {}

func record_snapshot(floor_number: int, round_index: int, image: Image) -> void:
	var copy := image.duplicate()
	copy.resize(192, 108, Image.INTERPOLATE_LANCZOS)
	_snapshots[Vector2i(floor_number, round_index)] = ImageTexture.create_from_image(copy)
	_refresh_cells()

func has_snapshot(floor_number: int, round_index: int) -> bool:
	return _snapshots.has(Vector2i(floor_number, round_index))

func toggle_candidate(floor_number: int = selected_floor) -> void:
	_candidate_marks[floor_number] = not _candidate_marks.get(floor_number, false)
	candidate_changed.emit(floor_number, _candidate_marks[floor_number])
	_refresh_rows()
```

Use a dark `PanelContainer`, cumulative clue label, row labels, and plain `TextureRect` cells. The board receives images and visible clue strings only—never the case, answer, hidden candidates, counts, or diffs.

- [ ] **Step 4: Capture after rendering and route input**

```gdscript
func _capture_current_snapshot() -> void:
	await RenderingServer.frame_post_draw
	if _round_finished:
		return
	var board: Node = get_node_or_null("GameUI/InvestigationBoard")
	if board != null:
		board.record_snapshot(_current_floor, current_loop, get_viewport().get_texture().get_image())
		mark_floor_observed(_current_floor)
```

Schedule capture after each room refresh while the board is closed. `KEY_TAB` toggles the board. Board-open Up/Down selects rows and Space toggles a mark; board-closed Up/Down navigates and Space submits only in round five.

- [ ] **Step 5: Pass and commit board tests**

```bash
bash tests/check_loop_staircase.sh
git add addons/cogito/DemoScenes/LoopStaircase/loop_staircase_investigation_board.gd addons/cogito/DemoScenes/LoopStaircase/loop_staircase_manager.gd tests/ai_play/test_loop_staircase_scene.gd
git commit -m "feat: add staircase investigation board"
```

Expected: wrapper passes; incomplete-round feedback reveals only missing floors.

### Task 6: Expose Tab through the scene-specific action

**Files:**
- Modify: `ai_play/src/ai_play/action_schema.py:40`
- Modify: `ai_play/tests/test_action_schema.py:18`
- Modify: `addons/cogito/AIPlay/ai_play_executor.gd:37`
- Modify: `tests/ai_play/test_ai_play_executor.gd:160`

- [ ] **Step 1: Write failing Tab validation tests**

```python
actions = [
    {"type": "press_key", "key": "up"},
    {"type": "press_key", "key": "tab"},
    {"type": "press_key", "key": "space"},
]
assert validate_action_batch(actions, [], False, "loop_staircase_anomaly") == actions
```

Require `find_contract` to reject Tab. In the Godot executor test, require one KEY_TAB press/release pair for the loop scenario and rejection for `find_contract`.

- [ ] **Step 2: Confirm current validators reject Tab**

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_action_schema.py -q
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
```

Expected: new acceptance assertions fail.

- [ ] **Step 3: Extend both exact whitelists**

```python
ALLOWED_PRESS_KEYS = {"up", "down", "space", "tab"}
```

```gdscript
const PRESS_KEYCODES: Dictionary = {
	"up": KEY_UP, "down": KEY_DOWN, "space": KEY_SPACE, "tab": KEY_TAB,
}
```

Retain the exact `loop_staircase_anomaly` scenario guard.

- [ ] **Step 4: Pass and commit validator tests**

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_action_schema.py -q
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
git add ai_play/src/ai_play/action_schema.py ai_play/tests/test_action_schema.py addons/cogito/AIPlay/ai_play_executor.gd tests/ai_play/test_ai_play_executor.gd
git commit -m "feat: allow staircase investigation board input"
```

Expected: both validators pass and other scenarios still reject `press_key`.

### Task 7: Rewrite public guidance and lock privacy regressions

**Files:**
- Modify: `ai_play/src/ai_play/loop_staircase_anomaly_briefing.py:6`
- Modify: `ai_play/tests/test_scenarios.py:55`
- Modify: `tests/ai_play/test_loop_staircase_scene.gd:46`
- Verify: `addons/cogito/AIPlay/ai_play_loop_staircase_observer.gd`

- [ ] **Step 1: Write failing briefing/privacy tests**

```python
briefing, image_bytes = load_scenario_briefing("loop_staircase_anomaly")
text = repr(briefing)
assert image_bytes is None
assert "tab" in text.lower()
assert "调查板" in text
for secret in (
    "受害者姓名", "清洁员", "垃圾", "ABAB", "红蓝红蓝",
    "访客时间", "8 → 6 → 5 → 3 → 2 → 1", "凶案楼层",
):
    assert secret not in text
```

In the scene test, require exactly these structured staircase keys: `objective`, `current_floor`, `current_floor_label`, `current_loop`, `total_loops`, `final_unlocked`, `completed`, `failed`. Reject clues, victim, room state, screenshots, candidates, seed, and answer fields.

- [ ] **Step 2: Confirm board guidance is absent**

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_scenarios.py -q
```

Expected: FAIL on missing Tab/investigation-board guidance.

- [ ] **Step 3: Rewrite only whitelisted guidance**

The briefing may disclose: five rounds; 2F–9F; one new visible clue each round; old clues remain; observe every floor; Tab opens/closes the notebook; board Up/Down/Space manages manual marks; the board does no analysis; fifth-round closed-board Space submits.

It must not name the victim rule, item rule, cleaner habit, signal sequence, time relation, fixed room pairs, candidate counts, or generated values. Leave the observer as a thin call to `manager.ai_play_public_state()`.

- [ ] **Step 4: Pass and commit public-contract tests**

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_scenarios.py -q
bash tests/check_loop_staircase.sh
git add ai_play/src/ai_play/loop_staircase_anomaly_briefing.py ai_play/tests/test_scenarios.py tests/ai_play/test_loop_staircase_scene.gd
git commit -m "docs: brief staircase investigation safely"
```

Expected: tests pass without private case data in runtime inputs.

### Task 8: Update runtime documentation

**Files:**
- Modify: `ai_play/README.md:400`
- Modify: `ai_play/README.md:457`
- Modify: `docs/wiki/ai-play/system-guide.md:615`

- [ ] **Step 1: Update gameplay and key documentation**

Document the cumulative five-round investigation, full-floor capture requirement, manual board, fifth-round floor submission, and unchanged terminal reasons. Use this whitelist text:

```markdown
- `loop_staircase_anomaly` 额外允许 `press_key`，且 `key` 只能是 `up`、`down`、
  `space` 或 `tab`；其他玩法必须拒绝该动作。
```

Keep protocol 4, `127.0.0.1`, explicit `--ai-play`, 160 requests, Escape, and terminal reasons unchanged.

- [ ] **Step 2: Reconcile the Wiki with final code names**

Retain the source-spec link, candidate curve, cumulative labels, Tab semantics, no-auto-analysis rule, privacy fields, terminal reasons, and 160-request cap.

- [ ] **Step 3: Test and commit documentation parity**

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_action_schema.py ai_play/tests/test_scenarios.py -q
git diff --check
git add ai_play/README.md docs/wiki/ai-play/system-guide.md
git commit -m "docs: document staircase murder investigation"
```

Expected: tests pass and diff check has no output.

### Task 9: Run complete affected verification

**Files:**
- Verify: `addons/cogito/DemoScenes/LoopStaircase/`
- Verify: `addons/cogito/AIPlay/ai_play_executor.gd`
- Verify: `ai_play/src/ai_play/`
- Verify: `tests/ai_play/`
- Verify: `ai_play/tests/`

- [ ] **Step 1: Generate ignored Godot imports and class cache**

```bash
godot --headless --path . --editor --quit
```

Expected: exit 0 with no parse, compile, or invalid UID errors.

- [ ] **Step 2: Run all affected Godot tests**

```bash
bash tests/check_loop_staircase.sh
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: all scripts exit 0 and print their pass markers.

- [ ] **Step 3: Run the complete local Python/MCP suite**

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest ai_play/tests ai_host/tests tests/*.py tests/conveyor_profit/test_protocol_parity.py -q
```

Expected: every collected test passes without a real Codex, Claude, MCP client, or external model.

- [ ] **Step 4: Inspect repository state**

```bash
git status --short
git diff --check
git log --oneline --decorate -9
```

Expected: no unstaged implementation changes, no diff-check output, and small task commits.

- [ ] **Step 5: Perform manual visual QA without AI Play**

```bash
godot --path . addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn -- --ai-play-scenario=loop_staircase_anomaly
```

Expected: no AI bridge connection. Inspect all eight themes, visitor records, neutral evidence, clue labels, board thumbnails/marks, blocked incomplete rounds, and final submission; exit with physical Escape.

- [ ] **Step 6: Finish with focused regressions**

```bash
bash tests/check_loop_staircase.sh
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_action_schema.py ai_play/tests/test_scenarios.py -q
git diff --check
```

Expected: all checks pass. Do not run real external MCP/model acceptance without new explicit confirmation covering screenshots, tokens, cost, and local trajectory persistence.
