# Find Key Contract Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `find_key` with a four-pack temporal contract-elimination game, enforce one irreversible Archive password submission, and set both contract scenarios to 150 act requests.

**Architecture:** Keep the shared Lobby and isolate all new physical content in an inactive `AIPlayFindKeyContractSetup` subscene. A pure `AIPlayFindKeyRound` generator owns script-pack selection and every date/code/dialogue value; `AIPlayFindKeyMonitor` injects that data into the setup, NPCs, Archive door, Keypad, and terminal signals. The supervisor supplies deterministic sequential seeds, while MCP receives neither seeds nor answers.

**Tech Stack:** Godot 4.7, typed GDScript, `.tscn` resources, Python 3/pytest, shell validation scripts.

---

### Task 1: Lock the public request limits and terminal contract

**Files:**
- Modify: `ai_play/src/ai_play/scenarios.py`
- Modify: `ai_play/src/ai_play/find_key_briefing.py`
- Modify: `ai_play/tests/test_scenarios.py`
- Modify: `ai_play/tests/test_briefing.py`
- Modify: `ai_play/tests/test_game_session.py`
- Modify: `ai_play/tests/test_bridge_server.py`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `addons/cogito/AIPlay/ai_play_game_over_screen.gd`
- Modify: `tests/ai_play/test_ai_play_controller.gd`
- Modify: `tests/ai_play/test_ai_play_game_over_screen.gd`

- [ ] **Step 1: Write failing Python assertions for both 150 caps and the security terminal**

```python
assert scenario_act_request_limit("find_contract", 500) == 150
assert scenario_act_request_limit("find_key", 500) == 150
assert scenario_round_act_request_limit("find_key", 150) == 150
assert is_allowed_game_over("find_key", "failure", "security_lockout")
```

- [ ] **Step 2: Run the focused Python tests and verify RED**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest ai_play/tests/test_scenarios.py ai_play/tests/test_game_session.py -q`

Expected: failures report the old 300/100 caps and reject `security_lockout`.

- [ ] **Step 3: Write failing GDScript assertions for the same bridge contract**

```gdscript
fixture.terminal_monitor.act_request_limit = 150
_assert(fixture.controller.FIND_KEY_ACT_REQUEST_LIMITS.has(150), "find_key allows 150")
fixture.terminal_monitor.game_finished.emit("failure", "security_lockout")
_assert(_last_game_over(fixture.bridge) == {
	"outcome": "failure",
	"reason": "security_lockout",
}, "controller forwards the security lockout terminal")
```

- [ ] **Step 4: Run the controller test and verify RED**

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd`

Expected: 150 is not allowlisted and `security_lockout` is rejected.

- [ ] **Step 5: Implement the minimal synchronized registry changes**

```python
FIND_KEY_ROUND_ACT_REQUEST_LIMITS = frozenset({50, 100, 150})

"find_contract": ScenarioDefinition(
    briefing_loader=load_public_briefing,
    max_act_requests=150,
    terminal_results=frozenset({
        ("success", "correct_password"),
        ("failure", "wrong_password"),
        ("failure", "max_requests"),
    }),
),
"find_key": ScenarioDefinition(
    briefing_loader=load_find_key_briefing,
    max_act_requests=150,
    terminal_results=frozenset({
        ("success", "key_picked_up"),
        ("failure", "security_lockout"),
        ("failure", "max_requests"),
    }),
),
```

```gdscript
const FIND_KEY_ACT_REQUEST_LIMITS: Array[int] = [50, 100, 150]

"find_key": [
	["success", "key_picked_up"],
	["failure", "security_lockout"],
	["failure", "max_requests"],
],
```

Add `security_lockout` to both game-over text maps with “安保锁定 / 密码提交错误，仅有的一次机会已消耗” wording. Rewrite the public `find_key` briefing around the 12:00 submission rule, six identical keys, three truthful NPCs, and one irreversible password confirmation; state 150 requests without exposing names, script IDs, dates, codes, or the Archive key location.

- [ ] **Step 6: Run focused Python and Godot tests and verify GREEN**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest ai_play/tests/test_scenarios.py ai_play/tests/test_briefing.py ai_play/tests/test_game_session.py ai_play/tests/test_bridge_server.py -q`

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd`

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd`

Expected: all selected tests pass.

- [ ] **Step 7: Commit the synchronized contract**

```bash
git add ai_play/src/ai_play/scenarios.py ai_play/src/ai_play/find_key_briefing.py ai_play/tests/test_scenarios.py ai_play/tests/test_briefing.py ai_play/tests/test_game_session.py ai_play/tests/test_bridge_server.py addons/cogito/AIPlay/ai_play_controller.gd addons/cogito/AIPlay/ai_play_game_over_screen.gd tests/ai_play/test_ai_play_controller.gd tests/ai_play/test_ai_play_game_over_screen.gd
git commit -m "feat(ai-play): raise contract task limits to 150"
```

### Task 2: Generate deterministic four-pack contract rounds

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_find_key_round.gd`
- Create: `tests/ai_play/test_ai_play_find_key_round.gd`

- [ ] **Step 1: Write a failing pure round-data test**

```gdscript
func _unique_count(values: Array) -> int:
	var unique := {}
	for value: Variant in values:
		unique[value] = true
	return unique.size()

var first_cycle: Array[String] = []
for seed_value: int in range(0, 4):
	var round_data: Dictionary = round_script.build(seed_value)
	first_cycle.append(round_data.pack_id)
	_assert(round_data.stages.size() == 3, "three paper stages")
	_assert(round_data.current.status == "SUBMITTED", "v1.1 is submitted")
	_assert(round_data.current.minutes_before_noon > 0, "current submission precedes noon")
	_assert(_unique_count(round_data.all_codes) == 4, "codes are unique")
_assert(_unique_count(first_cycle) == 4, "first cycle has no replacement")
_assert(round_script.build(2) == round_script.build(2), "same seed reproduces data")
```

Also assert the exact `POLARIS`, `ATLAS`, `ORBIT`, and `NOVA` room/handler matrices from the spec.

- [ ] **Step 2: Run the new test and verify RED**

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_find_key_round.gd`

Expected: the new round script cannot be loaded.

- [ ] **Step 3: Implement `AIPlayFindKeyRound.build()` as the sole puzzle-data source**

```gdscript
class_name AIPlayFindKeyRound
extends RefCounted

const PACK_IDS: Array[String] = ["POLARIS", "ATLAS", "ORBIT", "NOVA"]
const PACKS := {
	"POLARIS": {"contract": "Polaris", "rooms": ["MEETING_ROOM", "UPPER_OFFICE_CEO", "CUBICLE_AREA"], "handlers": ["李明", "王芳", "陈宇"]},
	"ATLAS": {"contract": "Atlas", "rooms": ["UPPER_OFFICE_CEO", "MEETING_ROOM", "CUBICLE_AREA"], "handlers": ["陈宇", "李明", "王芳"]},
	"ORBIT": {"contract": "Orbit", "rooms": ["CUBICLE_AREA", "MEETING_ROOM", "UPPER_OFFICE_CEO"], "handlers": ["王芳", "陈宇", "李明"]},
	"NOVA": {"contract": "Nova", "rooms": ["CUBICLE_AREA", "UPPER_OFFICE_CEO", "MEETING_ROOM"], "handlers": ["李明", "王芳", "陈宇"]},
}
const VERSIONS := ["INITIAL DRAFT v0.1", "REVIEW REVISION v0.8", "FINAL v1.0"]
const STATUSES := ["INITIAL DRAFT", "UNDER REVIEW", "PREPARED FOR SUBMISSION"]

static func build(round_seed: int) -> Dictionary:
	assert(round_seed >= 0)
	var pack_order: Array[String] = PACK_IDS.duplicate()
	var cycle_rng := RandomNumberGenerator.new()
	cycle_rng.seed = round_seed / 4
	for index: int in range(pack_order.size() - 1, 0, -1):
		var swap_index := cycle_rng.randi_range(0, index)
		var value := pack_order[index]
		pack_order[index] = pack_order[swap_index]
		pack_order[swap_index] = value
	var pack_id := pack_order[round_seed % 4]
	return _build_pack(round_seed, pack_id, PACKS[pack_id])
```

`_build_pack()` uses a second RNG seeded with `round_seed + 1_000_003`, a fixed UTC base date plus a seed-derived day offset, timestamps at three-months-ago/yesterday-AM/yesterday-PM/today-before-noon, three unique random historical codes, and `HHMM` as the fourth current code. It returns `pack_id`, `contract_name`, `stages`, `current`, `npc_by_room`, `document_by_room`, and `all_codes`.

- [ ] **Step 4: Run the round test and verify GREEN**

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_find_key_round.gd`

Expected: `AIPlay find-key round tests passed`.

- [ ] **Step 5: Commit the pure generator**

```bash
git add addons/cogito/AIPlay/ai_play_find_key_round.gd addons/cogito/AIPlay/ai_play_find_key_round.gd.uid tests/ai_play/test_ai_play_find_key_round.gd tests/ai_play/test_ai_play_find_key_round.gd.uid
git commit -m "feat(ai-play): generate find-key contract rounds"
```

### Task 3: Pass non-secret sequential seeds from the trusted supervisor

**Files:**
- Modify: `tools/ai_play_supervisor.py`
- Modify: `tests/test_ai_play_supervisor.py`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `tests/ai_play/test_ai_play_controller.gd`
- Modify: `addons/cogito/AIPlay/ai_play_find_key_monitor.gd`

- [ ] **Step 1: Write failing supervisor tests for four aligned seeds and retry stability**

```python
assert supervisor.find_key_round_seed(27, 1) == 108
assert supervisor.find_key_round_seed(27, 4) == 111
assert supervisor.find_key_round_seed(27, 5) == 112
command = supervisor.build_godot_command(
    "godot", "scene.tscn", "find_key", find_key_round_seed=108,
)
assert command[-1] == "--ai-play-round-seed=108"
assert "108" not in supervisor.redact_command(command)
```

- [ ] **Step 2: Write failing controller parser tests**

```gdscript
_assert(controller.get_requested_round_seed([
	"--ai-play", "--ai-play-scenario=find_key", "--ai-play-round-seed=0",
]) == {"valid": true, "provided": true, "value": 0}, "zero is deterministic")
_assert(not controller.get_requested_round_seed([
	"--ai-play", "--ai-play-scenario=find_key", "--ai-play-round-seed=-1",
]).valid, "negative seed is rejected")
```

Cover duplicates, non-digits, overflow, use without `--ai-play`, and use with another scenario. Assert the hello packet contains no seed.

- [ ] **Step 3: Run both test files and verify RED**

Run: `.venv/bin/python -m pytest tests/test_ai_play_supervisor.py -q`

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd`

Expected: seed helpers and parser do not exist.

- [ ] **Step 4: Implement aligned seed generation, validation, and redaction**

```python
def find_key_round_seed(cycle_seed: int, attempt_number: int) -> int:
    if cycle_seed < 0 or attempt_number < 1:
        raise ValueError("find-key seed inputs must be nonnegative")
    return cycle_seed * 4 + attempt_number - 1

def redact_command(command: Sequence[str]) -> list[str]:
    return [
        "--ai-play-round-seed=REDACTED"
        if value.startswith("--ai-play-round-seed=") else value
        for value in command
    ]
```

Add `--find-key-cycle-seed` to the supervisor. If absent, generate one with `secrets.randbelow(1_000_000_000)` once per supervisor invocation. Pass the same command into infrastructure retries. Log only `redact_command(command)`.

In `AIPlayController`, add `ROUND_SEED_ARG_PREFIX`, a strict parser returning `{valid, provided, value}`, and reject invalid or misplaced seed arguments before enabling AI. Remove raw `user_args` from the ready log. In `AIPlayFindKeyMonitor._ready()`, read the validated seed before `configure_round`; use random nonnegative seed only when no launch seed was provided.

- [ ] **Step 5: Run supervisor/controller tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_ai_play_supervisor.py -q`

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd`

Expected: both pass, and neither stdout nor hello serializes the seed.

- [ ] **Step 6: Commit trusted seed plumbing**

```bash
git add tools/ai_play_supervisor.py tests/test_ai_play_supervisor.py addons/cogito/AIPlay/ai_play_controller.gd tests/ai_play/test_ai_play_controller.gd addons/cogito/AIPlay/ai_play_find_key_monitor.gd
git commit -m "feat(ai-play): rotate find-key scripts without replacement"
```

### Task 4: Add opt-in irreversible Keypad confirmation

**Files:**
- Modify: `addons/cogito/CogitoObjects/cogito_keypad.gd`
- Modify: `addons/cogito/PackedScenes/keypad_prefab.tscn`
- Modify: `tests/ai_play/test_cogito_keypad_result.gd`

- [ ] **Step 1: Write failing tests for request, cancel, confirm, and one-shot behavior**

```gdscript
keypad.require_submit_confirmation = true
keypad.passcode = "0937"
keypad.entered_code = "1111"
keypad.check_entered_code()
_assert(results.is_empty(), "typing a full code does not submit")
_assert(keypad.is_submission_pending(), "warning waits for confirmation")
keypad.cancel_submission()
_assert(not keypad.has_consumed_submission(), "cancel preserves the chance")
keypad.entered_code = "1111"
keypad.check_entered_code()
keypad.confirm_submission()
keypad.confirm_submission()
_assert(results == [false], "confirmed code is evaluated exactly once")
```

Keep the existing default-mode correct/wrong tests to prove other Keypads retain their behavior.

- [ ] **Step 2: Run the Keypad test and verify RED**

Run: `godot --headless --path . --script tests/ai_play/test_cogito_keypad_result.gd`

Expected: confirmation API is missing.

- [ ] **Step 3: Implement the opt-in state machine and UI**

```gdscript
@export var require_submit_confirmation: bool = false
@export_multiline var submission_warning_text := "提交后不可修改。密码错误将立即触发安保锁定。"
var _submission_pending := false
var _submission_consumed := false

func check_entered_code() -> void:
	if _submission_consumed:
		return
	if require_submit_confirmation:
		_submission_pending = true
		confirmation_label.text = submission_warning_text
		confirmation_panel.show()
		digit_grid.hide()
		return
	_evaluate_entered_code()

func cancel_submission() -> void:
	if not _submission_pending or _submission_consumed:
		return
	_submission_pending = false
	confirmation_panel.hide()
	digit_grid.show()
	clear_entered_code()

func confirm_submission() -> void:
	if not _submission_pending or _submission_consumed:
		return
	_submission_pending = false
	_submission_consumed = true
	confirmation_panel.hide()
	_evaluate_entered_code()
```

Move the existing correctness body into `_evaluate_entered_code()`. Add a hidden `ConfirmationPanel` beneath the current VBox with a wrapped warning label and `取消 / CANCEL` and `确认提交 / SUBMIT ONCE` buttons connected to the two public methods. Reset pending/consumed state in `set_state()` only when a new round explicitly calls `reset_submission()`.

- [ ] **Step 4: Run the Keypad test and verify GREEN**

Run: `godot --headless --path . --script tests/ai_play/test_cogito_keypad_result.gd`

Expected: default and confirmation modes pass.

- [ ] **Step 5: Commit the opt-in Keypad behavior**

```bash
git add addons/cogito/CogitoObjects/cogito_keypad.gd addons/cogito/PackedScenes/keypad_prefab.tscn tests/ai_play/test_cogito_keypad_result.gd
git commit -m "feat(cogito): confirm irreversible keypad submissions"
```

### Task 5: Add the isolated physical setup and stable NPC behaviors

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_find_key_contract_setup.tscn`
- Create: `addons/cogito/AIPlay/ai_play_find_key_setup.gd`
- Modify: `addons/cogito/DemoScenes/friendly_human_npc.gd`
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`
- Modify: `tests/ai_play/test_ai_play_find_key_monitor.gd`
- Modify: `tests/ai_play/test_ai_play_greet_npc_meeting_monitor.gd`
- Modify: `tests/check_ai_play_lobby.sh`

- [ ] **Step 1: Replace the old scene assertions with failing setup assertions**

Assert one setup instance, six `Pickup_Key` nodes while active, one key in each named region, exactly three `storage` and three `surface` metadata values, three readable contract records, two setup NPCs plus the existing meeting NPC, and an initially locked Archive door. Assert the setup remains invisible, non-processing, and non-colliding for another scenario.

```gdscript
func _unique_count(values: Array) -> int:
	var unique := {}
	for value: Variant in values:
		unique[value] = true
	return unique.size()

_assert(_unique_count(setup.key_by_region().keys()) == 6, "six regions")
_assert(setup.keys().filter(func(key: Node) -> bool:
	return key.get_meta("placement_kind") == "storage"
).size() == 3, "three storage keys")
_assert(setup.documents().size() == 3, "three contract records")
```

- [ ] **Step 2: Run the Lobby monitor test and verify RED**

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd -- --ai-play --ai-play-scenario=find_key --ai-play-round-seed=0`

Expected: setup node and six-key API are missing.

- [ ] **Step 3: Add a focused setup controller**

```gdscript
class_name AIPlayFindKeySetup
extends Node3D

@export var spawned_keys: Array[RigidBody3D]
@export var contract_documents: Array[ReadableComponent]
@export var ceo_npc: FriendlyHumanNPC
@export var cubicle_npc: FriendlyHumanNPC

func set_scenario_active(active: bool) -> void:
	visible = active
	process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED
	for key: RigidBody3D in spawned_keys:
		key.collision_layer = 3 if active else 0
		key.process_mode = Node.PROCESS_MODE_INHERIT if active else Node.PROCESS_MODE_DISABLED
	for document: ReadableComponent in contract_documents:
		document.is_disabled = not active
		var body := document.get_parent() as CollisionObject3D
		if body != null:
			body.collision_layer = 2 if active else 0
```

Expose `keys()`, `documents()`, `key_by_region()`, and `npc_by_region()` for the monitor and tests.

- [ ] **Step 4: Add permanent seating without changing existing NPC defaults**

```gdscript
func configure_stationary_seat(anchor: Node3D, chair_parent_name: String) -> void:
	global_transform = anchor.global_transform
	sit_chair_parent_name = chair_parent_name
	allow_sitting = true
	_route_points.clear()
	_has_arrived = true
	_is_waiting = false
	velocity = Vector3.ZERO
	_try_sit_nearby_chair()

func is_sitting() -> bool:
	return _is_sitting
```

Add a regression assertion that the existing greeting scenario route configuration still works.

- [ ] **Step 5: Build and wire the setup scene**

The setup subscene must instantiate only existing resources: five additional `pickup_key.tscn` instances (the existing CEO key becomes the sixth), three `ripped_page_a_readable.tscn` records, two `friendly_human_npc.tscn` NPCs, and existing storage furniture where a room lacks usable storage. Place keys as follows and attach `region_id`/`placement_kind` metadata:

```text
MAIN_LOBBY       storage  existing/reused lobby cabinet
UPPER_OFFICE_CEO storage  existing deskCorner/Drawer
ARCHIVE          storage  reused archive cabinet, behind locked ArchiveDoor
MEETING_ROOM     surface  meeting table
BREAK_ROOM       surface  round coffee table
CUBICLE_AREA     surface  cubicle desk
```

Add two CEO pacing markers wholly inside `UPPER_OFFICE_CEO`, one cubicle seat anchor beside an existing `CUBICLE_AREA` chair, and readable records on the CEO desk, meeting table, and cubicle desk. Wire setup, existing CEO key, existing meeting NPC, Archive Keypad/door, task card, and spawn anchors into `FindKeyMonitor` NodePaths. Disable unrelated `find_contract` clue readables only when this setup activates.

- [ ] **Step 6: Run scene tests, import, and verify GREEN**

Run: `godot --headless --path . --editor --quit`

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd -- --ai-play --ai-play-scenario=find_key --ai-play-round-seed=0`

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_greet_npc_meeting_monitor.gd -- --ai-play-scenario=greet_npc_meeting`

Run: `bash tests/check_ai_play_lobby.sh`

Expected: all pass with no missing-node/resource errors.

- [ ] **Step 7: Commit the scene assembly**

```bash
git add addons/cogito/AIPlay/ai_play_find_key_contract_setup.tscn addons/cogito/AIPlay/ai_play_find_key_setup.gd addons/cogito/AIPlay/ai_play_find_key_setup.gd.uid addons/cogito/DemoScenes/friendly_human_npc.gd addons/cogito/DemoScenes/COGITO_3_Lobby.tscn tests/ai_play/test_ai_play_find_key_monitor.gd tests/ai_play/test_ai_play_greet_npc_meeting_monitor.gd tests/check_ai_play_lobby.sh
git commit -m "feat(ai-play): stage contract key investigation"
```

### Task 6: Orchestrate evidence, NPC dialogue, password risk, and key success

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_find_key_monitor.gd`
- Modify: `tests/ai_play/test_ai_play_find_key_monitor.gd`
- Create: `tests/check_ai_play_find_key.sh`
- Modify: `docs/wiki/development/contributor-guide.md`

- [ ] **Step 1: Add failing behavioral tests for one complete round**

For each script pack, assert that document room, visible handler name, historical password, and NPC room agree. For one seed, emit pickup on all five decoys and assert no terminal; request/cancel a wrong Keypad submission and assert no terminal; confirm it and assert exactly `failure/security_lockout`. Reconfigure, confirm the correct code, assert the Archive door unlocks without terminal, then emit the Archive key pickup and assert exactly `success/key_picked_up`.

```gdscript
for decoy: RigidBody3D in monitor.get_decoy_keys():
	decoy.get_node("PickupComponent").was_interacted_with.emit("Pick up", "interact")
_assert(results.is_empty(), "decoy pickups are nonterminal")
monitor.keypad.entered_code = "9999"
monitor.keypad.check_entered_code()
monitor.keypad.cancel_submission()
_assert(results.is_empty(), "cancel keeps the round alive")
```

- [ ] **Step 2: Run the monitor test and verify RED**

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd -- --ai-play --ai-play-scenario=find_key --ai-play-round-seed=0`

Expected: document/NPC/password orchestration APIs are missing.

- [ ] **Step 3: Replace location randomization with round orchestration**

`configure_round(seed)` must call `AIPlayFindKeyRound.build(seed)`, activate the setup, reset/lock the Archive door and Keypad, configure the task card, fill all three readable records from `document_by_room`, configure each NPC identity and dialogue from `npc_by_room`, configure meeting patrol/CEO loop/cubicle seat, connect only the Archive key pickup to success, and connect `code_checked` to one terminal path.

```gdscript
func _on_code_checked(is_correct: bool) -> void:
	if _round_finished:
		return
	if not is_correct:
		_finish_round("failure", "security_lockout")

func _on_archive_key_picked_up(_text: String, _action: String) -> void:
	_finish_round("success", "key_picked_up")

func _finish_round(outcome: String, reason: String) -> void:
	if _round_finished:
		return
	_round_finished = true
	game_finished.emit(outcome, reason)
```

Task-card text must include the board deadline, “Printed/FINAL 不等于 Submitted”, three truthful historical passwords, freedom to investigate in any order, and the one-shot warning, while omitting the answer.

- [ ] **Step 4: Add a focused shell runner and verify GREEN**

```bash
#!/usr/bin/env bash
set -euo pipefail
godot --headless --path . --script tests/ai_play/test_ai_play_find_key_round.gd
godot --headless --path . --script tests/ai_play/test_cogito_keypad_result.gd
godot --headless --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd -- --ai-play --ai-play-scenario=find_key --ai-play-round-seed=0
```

Run: `bash tests/check_ai_play_find_key.sh`

Expected: all three suites pass.

- [ ] **Step 5: Commit the integrated game loop**

```bash
git add addons/cogito/AIPlay/ai_play_find_key_monitor.gd tests/ai_play/test_ai_play_find_key_monitor.gd tests/check_ai_play_find_key.sh docs/wiki/development/contributor-guide.md
git commit -m "feat(ai-play): enforce contract timeline key deduction"
```

### Task 7: Update durable documentation and privacy regressions

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/wiki/wiki.md`
- Modify: `ai_play/tests/test_briefing.py`
- Modify: `ai_play/tests/test_mcp_server.py`
- Modify: `tests/check_ai_play_secrets.sh`

- [ ] **Step 1: Add failing privacy assertions**

```python
serialized = repr(load_scenario_briefing("find_key")[0])
for forbidden in [
    "POLARIS", "ATLAS", "ORBIT", "NOVA", "round_seed",
    "security_lockout", "0937", "ArchiveKey", "ai_play_find_key_round.gd",
]:
    assert forbidden not in serialized
```

Assert MCP initialization/briefing results do not serialize launch arguments, handler mappings, or the selected pack.

- [ ] **Step 2: Run the privacy tests and verify RED where obsolete briefing text remains**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest ai_play/tests/test_briefing.py ai_play/tests/test_mcp_server.py -q`

Expected: old single-key wording and old request counts violate the new assertions.

- [ ] **Step 3: Document the final public and internal contracts**

Update README launch syntax with trusted `--ai-play-round-seed=N` where `N` is a non-negative integer, state that supervisors use aligned sequential seeds and redact them, list both contract caps as 150, and document `security_lockout`. Replace the Wiki’s old `find_key` section with the six-room timeline puzzle, four-pack no-replacement rule, NPC movement rules, Keypad confirmation, terminal results, and privacy boundary. Keep script IDs/passwords in the internal design description only; explicitly state they never enter MCP results.

- [ ] **Step 4: Run privacy/docs checks and verify GREEN**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest ai_play/tests/test_briefing.py ai_play/tests/test_mcp_server.py -q`

Run: `bash tests/check_ai_play_secrets.sh`

Expected: all pass.

- [ ] **Step 5: Commit documentation and privacy coverage**

```bash
git add ai_play/README.md docs/wiki/ai-play/system-guide.md docs/wiki/wiki.md ai_play/tests/test_briefing.py ai_play/tests/test_mcp_server.py tests/check_ai_play_secrets.sh
git commit -m "docs(ai-play): explain contract timeline key task"
```

### Task 8: Run full affected validation and hand off

**Files:**
- Verify only; fix failures in the owning task’s files and tests.

- [ ] **Step 1: Run all Python AI Play tests**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest ai_play/tests -q`

Expected: all tests pass.

- [ ] **Step 2: Run supervisor/orchestrator tests affected by launch arguments**

Run: `.venv/bin/python -m pytest tests/test_ai_play_supervisor.py tests/test_ai_play_claude_orchestrator.py tests/test_ai_play_codex_orchestrator.py tests/test_ai_play_kimi_orchestrator.py -q`

Expected: all tests pass.

- [ ] **Step 3: Run Godot import and affected suites**

Run: `godot --headless --path . --editor --quit`

Run: `bash tests/check_ai_play_find_key.sh`

Run: `bash tests/check_ai_play_controller.sh`

Run: `bash tests/check_ai_play_game_over_screen.sh`

Run: `bash tests/check_ai_play_greet_npc_meeting_monitor.sh`

Run: `bash tests/check_ai_play_lobby.sh`

Expected: every command exits 0 without parser, orphan-node, leaked-input, or missing-resource errors.

- [ ] **Step 4: Perform local visual QA without an external MCP client**

Launch four local rounds with seeds 0–3, inspect screenshots or the running game, and verify that each contract record is readable, every key can be targeted, storage keys are revealed by opening their container, NPCs remain reachable, the confirmation UI fits at the configured viewport, and the Archive key cannot be reached through the locked door. Do not persist screenshots or trajectories unless the user separately authorizes it.

- [ ] **Step 5: Run final repository checks**

Run: `git diff --check`

Run: `git status -sb`

Expected: no whitespace errors; status contains only intended task files.

- [ ] **Step 6: Finish Git delivery**

If verification required corrections, commit them together with the owning task rather than creating a generic catch-all commit. If no corrections were required, do not create an empty commit. Then follow `docs/user/git-preferences.md` for push, baseline merge, and worktree cleanup.
