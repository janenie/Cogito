# Unknown Lighting Circuit Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `repair_lighting_circuit` Lobby scenario with deterministic hidden wiring, one tripped circuit, a reusable entrance control panel, four distributed light groups, one-shot breaker selection, terminal verification, sanitized MCP briefing, and regression coverage.

**Architecture:** A pure trusted GDScript round model owns deterministic hidden state and is adapted to the existing Lobby by `AIPlayRepairLightingCircuitMonitor`. The existing entrance red switch becomes control A; an inert-by-default task setup scene supplies B–D, breaker/Verify buttons, labels, spawn markers, and the break-room lamp. Python and Godot keep matching scenario and terminal allowlists, while all per-round answers remain inside trusted Godot state.

**Tech Stack:** Godot 4.7, typed GDScript, Godot `.tscn` resources, Python 3, pytest, Bash static/integration checks.

## Global Constraints

- Use scenario ID exactly `repair_lighting_circuit`.
- Reuse `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`; do not duplicate the Lobby.
- Reuse existing `GenericSwitch`, `GenericButton`, floor-lamp, ceiling-lamp, task-card, and game-over assets; add no art assets.
- The scenario setup must be invisible, non-colliding, non-interactive, and state-free unless this scenario is selected.
- Only `-- --ai-play-scenario=repair_lighting_circuit` selects the gameplay; only an additional `--ai-play` enables MCP control.
- Keep mapping, fault circuit, seed, initial state, target generation, node paths, and correct breaker out of briefing, observations, bridge packets, logs, and player prompts.
- The public target is shown only on the in-world task card.
- The hard limit is exactly 300 `act` requests; `AI_PLAY_MAX_ACT_REQUESTS` may only reduce it.
- Allow exactly `success/circuit_repaired`, `failure/wrong_breaker`, `failure/incorrect_circuit_configuration`, and `failure/max_requests` for this scenario.
- Do not extend trajectory, observation, bridge, or workflow-memory schemas for reasoning metrics.
- Do not run a real external model or MCP acceptance session without separate user approval for screenshots, tokens, cost, and trajectory persistence.
- Run the most focused failing test before implementation, then focused passing tests, affected full suites, and finally `git diff --check`.

## File Structure

**Create**

- `ai_play/src/ai_play/repair_lighting_circuit_briefing.py` — sanitized public rules and bounded reused JPEG loader.
- `addons/cogito/AIPlay/ai_play_lighting_circuit_round.gd` — deterministic trusted wiring/fault/state model with no scene dependencies.
- `addons/cogito/AIPlay/ai_play_repair_lighting_circuit_monitor.gd` — adapts the round model to real switches, buttons, lamps, player, task card, and game-over screen.
- `addons/cogito/AIPlay/ai_play_repair_lighting_circuit_setup.tscn` — inert task-only panel, markers, and break-room lamp.
- `tests/ai_play/test_ai_play_lighting_circuit_round.gd` — pure model contract tests.
- `tests/ai_play/test_ai_play_repair_lighting_circuit_monitor.gd` — selected-scenario and unselected-scenario Lobby integration tests.
- `tests/check_ai_play_repair_lighting_circuit_monitor.sh` — runs both integration modes and rejects parser/UID errors.

**Modify**

- `ai_play/src/ai_play/scenarios.py` — Python scenario registry, request cap, and terminal allowlist.
- `ai_play/tests/test_scenarios.py` — registry, cap, and terminal isolation tests.
- `ai_play/tests/test_briefing.py` — public briefing and shared-rule/privacy tests.
- `addons/cogito/AIPlay/ai_play_controller.gd` — Godot terminal allowlist.
- `addons/cogito/AIPlay/ai_play_game_over_screen.gd` — result copy for the three task outcomes.
- `tests/ai_play/test_ai_play_controller.gd` — terminal packet, rejection, and idempotency coverage.
- `tests/ai_play/test_ai_play_game_over_screen.gd` — visible result copy coverage.
- `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn` — setup instance, Monitor, and explicit existing-node wiring.
- `tests/check_ai_play_lobby.sh` — static scene wiring and inert-default assertions.
- `README_AI_PLAY.md` — user-facing task list, launch commands, cap, and outcomes.
- `ai_play/README.md` — MCP-facing scenario, briefing, cap, and terminal contract.
- `docs/wiki/ai-play/system-guide.md` — architecture, hidden-state, and round rules.
- `docs/wiki/development/contributor-guide.md` — dedicated Godot verification command.

---

### Task 1: Register the Sanitized Python Scenario

**Files:**

- Create: `ai_play/src/ai_play/repair_lighting_circuit_briefing.py`
- Modify: `ai_play/src/ai_play/scenarios.py:8-79`
- Modify: `ai_play/tests/test_scenarios.py:14-135`
- Modify: `ai_play/tests/test_briefing.py:21-194`

**Interfaces:**

- Consumes: `COMMON_CONTROL_RULES`, `ScenarioDefinition`, and `ai_play/assets/find_contract/imgs/reference_atlas.jpg`.
- Produces: `load_repair_lighting_circuit_briefing() -> tuple[dict, bytes]`; registry entry `repair_lighting_circuit` with cap 300 and four legal terminal pairs.

- [ ] **Step 1: Write failing registry and briefing tests**

Extend `test_scenario_registry_exposes_only_allowlisted_scenarios()` so the ordered tuple ends with
`"repair_lighting_circuit"`, and add these exact assertions:

```python
assert is_supported_scenario("repair_lighting_circuit")
assert scenario_act_request_limit("repair_lighting_circuit", 500) == 300
assert scenario_act_request_limit("repair_lighting_circuit", 240) == 240
assert is_allowed_game_over(
    "repair_lighting_circuit", "success", "circuit_repaired"
)
assert is_allowed_game_over(
    "repair_lighting_circuit", "failure", "wrong_breaker"
)
assert is_allowed_game_over(
    "repair_lighting_circuit",
    "failure",
    "incorrect_circuit_configuration",
)
assert is_allowed_game_over(
    "repair_lighting_circuit", "failure", "max_requests"
)
assert not is_allowed_game_over(
    "find_contract", "success", "circuit_repaired"
)
```

Add a briefing test and add the new ID to every all-scenario shared-rule loop:

```python
def test_repair_lighting_circuit_briefing_is_public_and_bounded():
    briefing, image_bytes = load_scenario_briefing("repair_lighting_circuit")

    assert briefing["game_id"] == "repair_lighting_circuit"
    assert "任务卡" in briefing["objective"]
    assert "300 次 act 请求" in briefing["failure_condition"]
    assert "一次" in repr(briefing)
    assert image_bytes.startswith(b"\xff\xd8\xff")
    assert image_bytes.endswith(b"\xff\xd9")
    assert len(image_bytes) <= 2 * 1024 * 1024
    serialized = repr(briefing)
    for forbidden in [
        "round_seed",
        "LIGHTS_CEILING_WALL",
        "lampSquareCeiling8",
        "fault_circuit",
        "control_mapping",
        "NodePath",
    ]:
        assert forbidden not in serialized
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
PYTHONPATH=ai_play/src python3 -m pytest \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_briefing.py -q
```

Expected: failures report that `repair_lighting_circuit` is absent or unsupported.

- [ ] **Step 3: Create the public briefing loader**

Create `repair_lighting_circuit_briefing.py` with the same JPEG validation used by the existing Lobby briefings:

```python
"""Approved public briefing for the lighting-circuit repair scenario."""

from copy import deepcopy
from pathlib import Path

from .common_briefing_rules import COMMON_CONTROL_RULES


MAX_REFERENCE_IMAGE_BYTES = 2 * 1024 * 1024
REFERENCE_IMAGE_PATH = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "find_contract"
    / "imgs"
    / "reference_atlas.jpg"
)

PUBLIC_BRIEFING = {
    "game_id": "repair_lighting_circuit",
    "title": "未知照明电路修复",
    "background": (
        "这是一个第一人称办公室照明诊断任务。入口面板上的 A～D 与四个区域的照明线路"
        "接线未知，其中一条线路已经跳闸。"
    ),
    "objective": (
        "先读取出生点附近唯一的任务卡，记住入口、CEO OFFICE、LOBBY 和 BREAK ROOM"
        "四组灯的目标状态。通过操作 A～D 并往返观察灯光，推断接线和故障线路；"
        "选择一次正确断路器，调整全部灯光后按 Verify。"
    ),
    "success_condition": "正确线路已复位，四组灯全部符合任务卡目标，并按下 Verify。",
    "failure_condition": (
        "断路器只能选择一次，选错立即失败；错误 Verify 立即失败；最多允许 300 次 act 请求。"
    ),
    "rules": COMMON_CONTROL_RULES + [
        "第一步一定要找到并读取面板附近的任务卡；任务卡可重复阅读。",
        "A～D 与四个区域是一对一未知接线，不能从字母顺序假设对应关系。",
        "正常线路会让开关指示和对应灯光一起变化；故障线路只改变开关指示，灯光不响应。",
        "面板前不能同时观察所有区域；每次实验后前往各区域观察并记住结果。",
        "断路器按区域命名且整局只能选择一次；选择错误会立即结束任务。",
        "完成复位和灯光调整后才按 Verify；配置错误会立即结束任务。",
    ],
    "reference_image": (
        "随简报返回的图片只帮助识别常见任务卡、开关和交互物，不代表本局映射、"
        "故障线路、目标状态或任何物体位置。"
    ),
    "objects": [
        {
            "id": "readable_document",
            "meaning": "出生点附近任务卡给出四组灯的本局目标状态。",
            "actions": {
                "probe_interaction": "对准任务卡寻找阅读提示。",
                "interact": "阅读并记住四个区域的 ON/OFF 目标。",
                "close_ui": "关闭任务卡后开始面板实验。",
            },
        },
        {
            "id": "lighting_control",
            "meaning": "A～D 控制未知区域线路，开关自身指示状态始终可见。",
            "actions": {
                "probe_interaction": "对准一个控制开关寻找操作提示。",
                "interact": "切换指示状态并观察分散区域中的灯光变化。",
            },
        },
        {
            "id": "breaker_and_verify_buttons",
            "meaning": "区域断路器只能选择一次；Verify 会提交最终配置。",
            "actions": {
                "probe_interaction": "对准带区域文字或 Verify 文字的按钮。",
                "interact": "仅在推断完成后复位线路或提交配置。",
            },
        },
    ],
}


def load_repair_lighting_circuit_briefing():
    try:
        image_bytes = REFERENCE_IMAGE_PATH.read_bytes()
    except OSError as error:
        raise RuntimeError("briefing_reference_image_unavailable") from error
    if (
        len(image_bytes) > MAX_REFERENCE_IMAGE_BYTES
        or not image_bytes.startswith(b"\xff\xd8\xff")
        or not image_bytes.endswith(b"\xff\xd9")
    ):
        raise RuntimeError("briefing_reference_image_invalid")
    return deepcopy(PUBLIC_BRIEFING), image_bytes
```

- [ ] **Step 4: Add the explicit registry entry**

Import `load_repair_lighting_circuit_briefing` and append this `ScenarioDefinition` after `garden_watering`:

```python
"repair_lighting_circuit": ScenarioDefinition(
    briefing_loader=load_repair_lighting_circuit_briefing,
    max_act_requests=300,
    terminal_results=frozenset({
        ("success", "circuit_repaired"),
        ("failure", "wrong_breaker"),
        ("failure", "incorrect_circuit_configuration"),
        ("failure", "max_requests"),
    }),
),
```

Do not add this scenario to `FIND_KEY_ROUND_ACT_REQUEST_LIMITS`; only `find_key` accepts a per-round hello override.

- [ ] **Step 5: Run focused and full Python scenario tests**

Run:

```bash
PYTHONPATH=ai_play/src python3 -m pytest \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_briefing.py \
  ai_play/tests/test_bridge_server.py \
  ai_play/tests/test_game_session.py -q
```

Expected: all selected tests pass and no briefing privacy assertion fails.

- [ ] **Step 6: Commit the Python scenario contract**

```bash
git add \
  ai_play/src/ai_play/repair_lighting_circuit_briefing.py \
  ai_play/src/ai_play/scenarios.py \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_briefing.py
git commit -m "feat(ai-play): register lighting circuit scenario"
```

---

### Task 2: Add Matching Godot Terminal Contracts

**Files:**

- Modify: `addons/cogito/AIPlay/ai_play_controller.gd:14-51`
- Modify: `addons/cogito/AIPlay/ai_play_game_over_screen.gd:3-35`
- Modify: `tests/ai_play/test_ai_play_controller.gd:750-858`
- Modify: `tests/ai_play/test_ai_play_game_over_screen.gd:10-35`

**Interfaces:**

- Consumes: scenario ID and terminal pairs produced by Task 1.
- Produces: Godot-side terminal validation and visible Chinese result copy; no bridge schema change.

- [ ] **Step 1: Add failing Controller terminal cases**

Add all three task terminal cases to `_test_terminal_outcomes()`:

```gdscript
{
	"scenario": "repair_lighting_circuit",
	"outcome": "success",
	"reason": "circuit_repaired",
},
{
	"scenario": "repair_lighting_circuit",
	"outcome": "failure",
	"reason": "wrong_breaker",
},
{
	"scenario": "repair_lighting_circuit",
	"outcome": "failure",
	"reason": "incorrect_circuit_configuration",
},
```

Add a cross-scenario rejection fixture that emits `success/circuit_repaired` while active scenario is
`find_contract` and asserts `invalid_game_outcome` is recorded in executor cancellation reasons.

- [ ] **Step 2: Add failing game-over copy cases**

Before `_finish()` in `test_ai_play_game_over_screen.gd`, call:

```gdscript
await _test_result(
	screen_scene,
	"success",
	"circuit_repaired",
	"任务成功",
	"照明电路已修复",
)
await _test_result(
	screen_scene,
	"failure",
	"wrong_breaker",
	"任务失败",
	"断路器选择错误",
)
await _test_result(
	screen_scene,
	"failure",
	"incorrect_circuit_configuration",
	"任务失败",
	"照明配置不正确",
)
```

- [ ] **Step 3: Run both Godot tests and confirm RED**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
```

Expected: Controller reports invalid game outcome for the new legal cases, and UI assertions see fallback copy.

- [ ] **Step 4: Implement matching allowlist and UI dictionaries**

Add to `SCENARIO_TERMINAL_RESULTS`:

```gdscript
"repair_lighting_circuit": [
	["success", "circuit_repaired"],
	["failure", "wrong_breaker"],
	["failure", "incorrect_circuit_configuration"],
	["failure", "max_requests"],
],
```

Add these exact key/value pairs to `OUTCOME_TEXT` and `REASON_TEXT`:

```gdscript
"circuit_repaired": "任务成功",
"wrong_breaker": "任务失败",
"incorrect_circuit_configuration": "任务失败",
```

```gdscript
"circuit_repaired": "照明电路已修复",
"wrong_breaker": "断路器选择错误",
"incorrect_circuit_configuration": "照明配置不正确",
```

- [ ] **Step 5: Re-run both Godot tests**

Run the two Step 3 commands again.

Expected: both scripts exit 0, each new terminal sends/displays exactly once, and the existing terminal cases remain green.

- [ ] **Step 6: Commit the Godot terminal contract**

```bash
git add \
  addons/cogito/AIPlay/ai_play_controller.gd \
  addons/cogito/AIPlay/ai_play_game_over_screen.gd \
  tests/ai_play/test_ai_play_controller.gd \
  tests/ai_play/test_ai_play_game_over_screen.gd
git commit -m "feat(ai-play): allow lighting circuit outcomes"
```

---

### Task 3: Build the Deterministic Trusted Round Model

**Files:**

- Create: `addons/cogito/AIPlay/ai_play_lighting_circuit_round.gd`
- Create after Godot import: `addons/cogito/AIPlay/ai_play_lighting_circuit_round.gd.uid`
- Create: `tests/ai_play/test_ai_play_lighting_circuit_round.gd`

**Interfaces:**

- Consumes: integer `round_seed` and control/breaker actions from the future Monitor.
- Produces: `AIPlayLightingCircuitRound.configure(seed_value: int)`, `set_control_state(control_id: String, is_on: bool) -> Dictionary`, `reset_breaker(circuit_id: String) -> Dictionary`, `is_configuration_correct() -> bool`, and `snapshot() -> Dictionary`.

- [ ] **Step 1: Write the failing pure-model test**

Create a `SceneTree` test that loads the missing script, then verifies these exact contracts:

```gdscript
var first := AIPlayLightingCircuitRound.new()
var second := AIPlayLightingCircuitRound.new()
first.configure(87123)
second.configure(87123)
_assert(first.snapshot() == second.snapshot(), "same seed is deterministic")

for seed_value: int in range(1, 257):
	var round_state := AIPlayLightingCircuitRound.new()
	round_state.configure(seed_value)
	var state := round_state.snapshot()
	var mapped: Array = state.mapping.values()
	mapped.sort()
	_assert(mapped == ["break_room", "ceo", "entrance", "lobby"], "mapping is a permutation")
	_assert(_difference_count(state.initial_states, state.target_states) >= 2, "target differs twice")
	_assert(state.target_states[state.fault_circuit] == true, "fault target is on")
```

Define the comparison helper in the test:

```gdscript
func _difference_count(left: Dictionary, right: Dictionary) -> int:
	var count: int = 0
	for circuit_id: String in AIPlayLightingCircuitRound.CIRCUIT_IDS:
		if left[circuit_id] != right[circuit_id]:
			count += 1
	return count
```

For a configured round, find the control mapped to the fault and one mapped to a normal circuit. Assert:

```gdscript
var round_state := AIPlayLightingCircuitRound.new()
round_state.configure(9012)
var state: Dictionary = round_state.snapshot()
var fault_circuit: String = state.fault_circuit
var fault_control: String = round_state.control_for_circuit(fault_circuit)
var normal_circuit: String = ""
for circuit_id: String in AIPlayLightingCircuitRound.CIRCUIT_IDS:
	if circuit_id != fault_circuit:
		normal_circuit = circuit_id
		break
var normal_control: String = round_state.control_for_circuit(normal_circuit)
var fault_before: bool = state.circuit_states[fault_circuit]
var fault_result := round_state.set_control_state(
	fault_control,
	not state.control_states[fault_control],
)
_assert(fault_result.accepted and not fault_result.applied, "fault indicator changes without lamp")
_assert(round_state.snapshot().circuit_states[fault_circuit] == fault_before, "fault lamp stays unchanged")

var normal_result := round_state.set_control_state(
	normal_control,
	not state.control_states[normal_control],
)
_assert(normal_result.accepted and normal_result.applied, "normal circuit applies")
_assert(round_state.snapshot().circuit_states[normal_result.circuit] == normal_result.state, "normal lamp follows")
```

Also assert wrong reset, correct reset, repeated reset, post-reset synchronization, and final correctness:

```gdscript
var wrong := round_state.reset_breaker(normal_result.circuit)
_assert(wrong.accepted and not wrong.correct, "wrong breaker consumes the attempt")
_assert(not round_state.reset_breaker(fault_circuit).accepted, "second breaker is rejected")

round_state.configure(87123)
var correct := round_state.reset_breaker(round_state.snapshot().fault_circuit)
_assert(correct.accepted and correct.correct, "correct breaker restores the circuit")
_assert(round_state.snapshot().circuit_states[correct.circuit] == correct.state, "repair syncs current control")
_set_controls_to_targets(round_state)
_assert(round_state.is_configuration_correct(), "repaired target configuration is correct")
```

Define the target helper in the test:

```gdscript
func _set_controls_to_targets(round_state: AIPlayLightingCircuitRound) -> void:
	var state: Dictionary = round_state.snapshot()
	for control_id: String in AIPlayLightingCircuitRound.CONTROL_IDS:
		var circuit_id: String = state.mapping[control_id]
		round_state.set_control_state(control_id, state.target_states[circuit_id])
```

- [ ] **Step 2: Run the pure-model test and confirm RED**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_lighting_circuit_round.gd
```

Expected: parser/load failure because `AIPlayLightingCircuitRound` does not exist.

- [ ] **Step 3: Implement the model state and deterministic generator**

Define these constants and fields:

```gdscript
class_name AIPlayLightingCircuitRound
extends RefCounted

const CONTROL_IDS: Array[String] = ["A", "B", "C", "D"]
const CIRCUIT_IDS: Array[String] = ["entrance", "ceo", "lobby", "break_room"]

var mapping: Dictionary = {}
var fault_circuit: String = ""
var initial_states: Dictionary = {}
var target_states: Dictionary = {}
var control_states: Dictionary = {}
var circuit_states: Dictionary = {}
var breaker_attempted: bool = false
var breaker_restored: bool = false
```

Implement `_shuffle_with_rng(values: Array[String], rng: RandomNumberGenerator)` with descending
Fisher–Yates swaps using `rng.randi_range(0, index)`. `configure()` must:

1. clear all dictionaries and breaker flags;
2. seed or randomize one `RandomNumberGenerator`;
3. shuffle a duplicate circuit list and map it to A–D;
4. select `fault_circuit` from `CIRCUIT_IDS` with the same RNG;
5. generate each initial circuit boolean and copy it through the inverse mapping into control state;
6. generate four random target booleans and force `target_states[fault_circuit] = true`;
7. if fewer than two target bits differ, shuffle the three non-fault IDs with the same RNG and flip enough targets to reach two differences;
8. copy initial states into current circuit states.

- [ ] **Step 4: Implement action and snapshot methods**

Use these exact result shapes:

```gdscript
func set_control_state(control_id: String, is_on: bool) -> Dictionary:
	if control_id not in mapping:
		return {"accepted": false}
	control_states[control_id] = is_on
	var circuit_id: String = mapping[control_id]
	var applied: bool = circuit_id != fault_circuit or breaker_restored
	if applied:
		circuit_states[circuit_id] = is_on
	return {
		"accepted": true,
		"applied": applied,
		"circuit": circuit_id,
		"state": is_on,
	}
```

```gdscript
func reset_breaker(circuit_id: String) -> Dictionary:
	if breaker_attempted or circuit_id not in CIRCUIT_IDS:
		return {"accepted": false}
	breaker_attempted = true
	var correct: bool = circuit_id == fault_circuit
	if not correct:
		return {"accepted": true, "correct": false, "circuit": circuit_id}
	breaker_restored = true
	var control_id: String = control_for_circuit(circuit_id)
	circuit_states[circuit_id] = control_states[control_id]
	return {
		"accepted": true,
		"correct": true,
		"circuit": circuit_id,
		"state": circuit_states[circuit_id],
	}
```

`is_configuration_correct()` returns false until `breaker_restored`, then compares all four
`circuit_states` to `target_states`. `snapshot()` returns deep duplicates under keys
`mapping`, `fault_circuit`, `initial_states`, `target_states`, `control_states`, `circuit_states`,
`breaker_attempted`, and `breaker_restored`. `control_for_circuit()` returns the matching A–D ID or an empty string.

- [ ] **Step 5: Import scripts and run the pure-model test**

Run:

```bash
godot --headless --path . --editor --quit
godot --headless --path . --script tests/ai_play/test_ai_play_lighting_circuit_round.gd
```

Expected: the import generates a stable `.gd.uid`; the test prints its pass sentinel and exits 0.

- [ ] **Step 6: Commit the trusted model**

```bash
git add \
  addons/cogito/AIPlay/ai_play_lighting_circuit_round.gd \
  addons/cogito/AIPlay/ai_play_lighting_circuit_round.gd.uid \
  tests/ai_play/test_ai_play_lighting_circuit_round.gd
git commit -m "feat(ai-play): model lighting circuit rounds"
```

---

### Task 4: Build and Wire the Playable Lobby Task

**Files:**

- Create: `addons/cogito/AIPlay/ai_play_repair_lighting_circuit_monitor.gd`
- Create after Godot import: `addons/cogito/AIPlay/ai_play_repair_lighting_circuit_monitor.gd.uid`
- Create: `addons/cogito/AIPlay/ai_play_repair_lighting_circuit_setup.tscn`
- Create: `tests/ai_play/test_ai_play_repair_lighting_circuit_monitor.gd`
- Create: `tests/check_ai_play_repair_lighting_circuit_monitor.sh`
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn:110-117,3297-3380,8079-8082`
- Modify: `tests/check_ai_play_lobby.sh:1-65`

**Interfaces:**

- Consumes: `AIPlayLightingCircuitRound` from Task 3, existing `CogitoSwitch`, `CogitoButton`, `ReadableComponent`, `AIPlayGameOverScreen`, and Controller scenario selection.
- Produces: `AIPlayRepairLightingCircuitMonitor.configure_round(seed_value: int = 0)`, `get_round_snapshot() -> Dictionary`, `show_result(outcome: String, reason: String)`, and `game_finished(outcome, reason)`.

- [ ] **Step 1: Write the failing selected/unselected Lobby integration test**

The selected branch must instantiate the Lobby, add it to the test tree, await two process frames for deferred
activation, disconnect the Controller's `_on_game_finished` callable so the test can inspect several terminal cases
without pausing the tree, connect `game_finished` to `_terminal_results`, and assert:

```gdscript
var monitor: Node = lobby.get_node("AIPlayController/RepairLightingCircuitMonitor")
_assert(monitor != null, "Lobby includes lighting circuit Monitor")
var controller: Node = lobby.get_node("AIPlayController")
var controller_terminal := Callable(controller, "_on_game_finished")
if monitor.game_finished.is_connected(controller_terminal):
	monitor.game_finished.disconnect(controller_terminal)
monitor.game_finished.connect(
	func(outcome: String, reason: String) -> void:
		_terminal_results.append({"outcome": outcome, "reason": reason})
)
_assert(lobby.get_node("RepairLightingCircuitSetup").visible, "selected setup is visible")
_assert(monitor.control_switch_a == lobby.get_node("GenericSwitch"), "existing red switch is A")
_assert(monitor.lobby_lamps.size() == 6, "Lobby circuit contains six ceiling lamps")
_assert(monitor.task_card.readable_content.contains("入口落地灯"), "task card lists entrance target")
_assert(monitor.task_card.readable_content.contains("CEO 办公室落地灯"), "task card lists CEO target")
_assert(monitor.task_card.readable_content.contains("大厅六盏顶灯"), "task card lists Lobby target")
_assert(monitor.task_card.readable_content.contains("休息室落地灯"), "task card lists break-room target")
```

Loop fixed seeds through `monitor.configure_round(seed_value)`, compare snapshots for deterministic replay,
and assert every direct lamp `BasicInteraction.is_disabled` is true. Exercise a normal control and fault control by
calling `switch_on()`/`switch_off()` on the corresponding real control nodes, then assert actual floor/ceiling lamp
`is_on` values follow the model result.

Use fresh rounds for terminal checks:

```gdscript
monitor.configure_round(4512)
var snapshot: Dictionary = monitor.get_round_snapshot()
var wrong_circuit: String = _first_non_fault_circuit(snapshot.fault_circuit)
_terminal_results.clear()
monitor._on_breaker_pressed(wrong_circuit)
_assert(_terminal_results == [{"outcome": "failure", "reason": "wrong_breaker"}], "wrong breaker fails once")
monitor._on_breaker_pressed(snapshot.fault_circuit)
_assert(_terminal_results.size() == 1, "terminal is idempotent")

monitor.configure_round(4513)
_terminal_results.clear()
monitor._on_verify_pressed()
_assert(_terminal_results == [{"outcome": "failure", "reason": "incorrect_circuit_configuration"}], "early Verify fails")

monitor.configure_round(4514)
_terminal_results.clear()
_set_real_controls_to_targets(monitor)
monitor._on_breaker_pressed(monitor.get_round_snapshot().fault_circuit)
_set_real_controls_to_targets(monitor)
monitor._on_verify_pressed()
_assert(_terminal_results == [{"outcome": "success", "reason": "circuit_repaired"}], "repaired target succeeds")
```

Define both integration helpers explicitly:

```gdscript
func _first_non_fault_circuit(fault_circuit: String) -> String:
	for circuit_id: String in AIPlayLightingCircuitRound.CIRCUIT_IDS:
		if circuit_id != fault_circuit:
			return circuit_id
	return ""


func _set_real_controls_to_targets(monitor: Node) -> void:
	var snapshot: Dictionary = monitor.get_round_snapshot()
	var switches: Dictionary = {
		"A": monitor.control_switch_a,
		"B": monitor.control_switch_b,
		"C": monitor.control_switch_c,
		"D": monitor.control_switch_d,
	}
	for control_id: String in AIPlayLightingCircuitRound.CONTROL_IDS:
		var circuit_id: String = snapshot.mapping[control_id]
		var desired: bool = snapshot.target_states[circuit_id]
		var control: CogitoSwitch = switches[control_id]
		if control.is_on != desired:
			if desired:
				control.switch_on()
			else:
				control.switch_off()
```

When the script is launched without the scenario argument, assert Setup is invisible and processing-disabled,
B–D/buttons have collision layer 0 and disabled `BasicInteraction`, the existing A retains six
`objects_call_interact`, entrance/CEO direct interactions remain enabled, and `get_round_snapshot()` is empty.

- [ ] **Step 2: Add the shell wrapper and confirm RED**

The wrapper must run both modes into temporary logs:

```bash
godot --headless --path . \
  --script tests/ai_play/test_ai_play_repair_lighting_circuit_monitor.gd \
  -- --ai-play-scenario=repair_lighting_circuit
godot --headless --path . \
  --script tests/ai_play/test_ai_play_repair_lighting_circuit_monitor.gd
```

It must fail on nonzero exit, `SCRIPT ERROR`, or `invalid UID`, and require the sentinels
`AIPlay lighting-circuit selected test passed` and `AIPlay lighting-circuit isolation test passed` respectively.

Run:

```bash
bash tests/check_ai_play_repair_lighting_circuit_monitor.sh
```

Expected: failure because the setup and Monitor do not exist.

- [ ] **Step 3: Create the inert setup scene**

Build `ai_play_repair_lighting_circuit_setup.tscn` with root
`RepairLightingCircuitSetup` using `visible = false` and `process_mode = 4`. Reuse these exact resources:

```text
res://addons/cogito/DemoScenes/DemoPrefabs/generic_switch.tscn
res://addons/cogito/DemoScenes/DemoPrefabs/generic_button.tscn
res://addons/cogito/DemoScenes/DemoPrefabs/lamp_round_floor.tscn
res://addons/cogito/Assets/Fonts/Montserrat/Montserrat-Bold.ttf
```

Create these stable node names:

```text
PanelBacking
TitleLabel
SwitchLabelA
SwitchLabelB
SwitchLabelC
SwitchLabelD
ControlSwitchB
ControlSwitchC
ControlSwitchD
BreakerHeadingLabel
BreakerEntrance
BreakerEntranceLabel
BreakerCEO
BreakerCEOLabel
BreakerLobby
BreakerLobbyLabel
BreakerBreakRoom
BreakerBreakRoomLabel
VerifyButton
VerifyLabel
PanelSpawn
TaskCardAnchor
BreakRoomLamp
```

Use a simple `BoxMesh` plus material for the backing and `Label3D` for all text. Place the panel around the existing
A switch at world position `(5.72934, 1.10623, -15.8447)`, with B upper-right, C lower-left, D lower-right,
breakers in one row below, and Verify centered below them. Put `PanelSpawn` about 2.5 metres in front of the panel,
`TaskCardAnchor` within 2 metres of the spawn, and `BreakRoomLamp` in open floor near global
`(-5.1, 0.0, -13.0)`.

All B–D/buttons must start with `collision_layer = 0` and child `BasicInteraction.is_disabled = true`.
`BreakRoomLamp` must start hidden through its parent, with direct `BasicInteraction.is_disabled = true`.

- [ ] **Step 4: Implement the Monitor adapter**

Define typed exports for setup, player, task card, shared screen, A–D, five buttons, three existing circuit groups,
break-room lamp, panel markers, and `round_seed`. Use these exact state members:

```gdscript
var _round := AIPlayLightingCircuitRound.new()
var _round_finished: bool = false
var _task_active: bool = false
var _configuring_round: bool = false
var _signals_connected: bool = false
var _original_a_targets: Array[NodePath] = []
var _original_lamp_interaction_states: Dictionary = {}
var _original_existing_lamp_states: Dictionary = {}
```

In `_ready()`, return before any mutation when the parent Controller rejects the scenario. For the selected scenario,
call deferred `_activate_task()` so the reused switch has completed its own `_ready()` first. `_activate_task()` must:

1. validate every export and exactly six Lobby lamps;
2. show/process Setup;
3. enable collision and BasicInteraction only for A–D, breakers, and Verify;
4. keep all four controlled lamps' own BasicInteractions disabled;
5. save and clear A's six original `objects_call_interact` targets;
6. connect A–D `switched`, four breaker `pressed`, and Verify `pressed` exactly once;
7. move player/task card to the setup markers;
8. call `configure_round(round_seed)`.

Use signal binds with these signatures:

```gdscript
func _on_control_switch_changed(is_on: bool, control_id: String) -> void
func _on_breaker_pressed(circuit_id: String) -> void
func _on_verify_pressed() -> void
```

`configure_round()` sets `_round_finished = false`, re-enables A–D, all breakers, and Verify, resets button usage
state, calls
`_round.configure(seed_value)`, applies all four
control indicators and physical initial states while `_configuring_round` is true, then writes task-card lines in
fixed order using `ON`/`OFF`. `_on_control_switch_changed()` calls `set_control_state()` and only applies physical
lamps when `result.applied` is true. `_on_breaker_pressed()` disables all breaker interactions after an accepted
attempt, synchronizes a correct repaired circuit, or finishes with `wrong_breaker`. `_on_verify_pressed()` checks
`_round.breaker_restored` plus actual `is_on` on all controlled lamps; success uses `circuit_repaired`, every other
case uses `incorrect_circuit_configuration`.

`_finish_round()` sets `_round_finished` before disabling panel interactions and emitting. `show_result()` forwards
to `game_over_screen.show_result()`. `_exit_tree()` disconnects task signals, restores A's target list, original
existing-lamp direct-interaction flags and original existing-lamp states. `get_round_snapshot()` returns `{}` before
activation and `_round.snapshot()` afterward, augmented only for trusted tests with current task-card text.

- [ ] **Step 5: Wire the setup and Monitor into the Lobby**

Add explicit ext resources for the setup scene and Monitor script. Instance `RepairLightingCircuitSetup` once at the
Lobby root. Add `RepairLightingCircuitMonitor` as a direct `AIPlayController` child with
`scenario_id = "repair_lighting_circuit"` and explicit NodePaths to:

```text
../../RepairLightingCircuitSetup
../../Player
../../DEMO_HINTS/Hint_01_Welcome/ReadableComponent
../TerminalMonitor/GameOverScreen
../../GenericSwitch
../../RepairLightingCircuitSetup/ControlSwitchB
../../RepairLightingCircuitSetup/ControlSwitchC
../../RepairLightingCircuitSetup/ControlSwitchD
../../RepairLightingCircuitSetup/BreakerEntrance
../../RepairLightingCircuitSetup/BreakerCEO
../../RepairLightingCircuitSetup/BreakerLobby
../../RepairLightingCircuitSetup/BreakerBreakRoom
../../RepairLightingCircuitSetup/VerifyButton
../../RepairLightingCircuitSetup/PanelSpawn
../../RepairLightingCircuitSetup/TaskCardAnchor
../../ENTRANCE_AREA/lampRoundFloor
../../UPPER_OFFICE_CEO/lampRoundFloor
../../LIGHTS_CEILING_WALL/lampSquareCeiling8
../../LIGHTS_CEILING_WALL/lampSquareCeiling9
../../LIGHTS_CEILING_WALL/lampSquareCeiling10
../../LIGHTS_CEILING_WALL/lampSquareCeiling11
../../LIGHTS_CEILING_WALL/lampSquareCeiling12
../../LIGHTS_CEILING_WALL/lampSquareCeiling13
../../RepairLightingCircuitSetup/BreakRoomLamp
```

Do not alter the existing `GenericSwitch` block; its ordinary six-lamp targets remain the default and are only
temporarily replaced by the selected Monitor.

- [ ] **Step 6: Extend the static Lobby contract**

Add exact checks to `tests/check_ai_play_lobby.sh` for the new ext resources, direct Controller child,
`scenario_id`, setup instance, all stable setup node names, six explicit Lobby lamp paths, existing A path, and
shared task-card/game-over paths. At minimum include:

```bash
grep -q 'path="res://addons/cogito/AIPlay/ai_play_repair_lighting_circuit_monitor.gd"' "$scene"
grep -q 'path="res://addons/cogito/AIPlay/ai_play_repair_lighting_circuit_setup.tscn"' "$scene"
grep -q 'name="RepairLightingCircuitMonitor" type="Node" parent="AIPlayController"' "$scene"
grep -q '^scenario_id = "repair_lighting_circuit"$' "$scene"
grep -q 'control_switch_a = NodePath("../../GenericSwitch")' "$scene"
test "$(grep -o 'lampSquareCeiling\(8\|9\|10\|11\|12\|13\)' "$scene" | sort -u | wc -l | tr -d ' ')" -eq 6

setup="addons/cogito/AIPlay/ai_play_repair_lighting_circuit_setup.tscn"
for node_name in \
  ControlSwitchB ControlSwitchC ControlSwitchD \
  BreakerEntrance BreakerCEO BreakerLobby BreakerBreakRoom \
  VerifyButton PanelSpawn TaskCardAnchor BreakRoomLamp
do
  grep -q "name=\"$node_name\"" "$setup"
done
grep -A4 '^\[node name="RepairLightingCircuitSetup"' "$setup" | grep -q '^process_mode = 4$'
grep -A4 '^\[node name="RepairLightingCircuitSetup"' "$setup" | grep -q '^visible = false$'
```

Parse each B–D/button node block to assert `collision_layer = 0`, and each corresponding
`BasicInteraction` override block to assert `is_disabled = true`.

- [ ] **Step 7: Import and run selected, isolation, and static tests**

Run:

```bash
godot --headless --path . --editor --quit
godot --headless --path . --script tests/ai_play/test_ai_play_lighting_circuit_round.gd
bash tests/check_ai_play_repair_lighting_circuit_monitor.sh
bash tests/check_ai_play_lobby.sh
```

Expected: all commands exit 0; selected mode exercises all three task terminals; isolation mode preserves ordinary
A/lamp behavior; no `SCRIPT ERROR`, parser error, or invalid UID appears.

- [ ] **Step 8: Commit the playable Lobby task**

```bash
git add \
  addons/cogito/AIPlay/ai_play_repair_lighting_circuit_monitor.gd \
  addons/cogito/AIPlay/ai_play_repair_lighting_circuit_monitor.gd.uid \
  addons/cogito/AIPlay/ai_play_repair_lighting_circuit_setup.tscn \
  addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  tests/ai_play/test_ai_play_repair_lighting_circuit_monitor.gd \
  tests/check_ai_play_repair_lighting_circuit_monitor.sh \
  tests/check_ai_play_lobby.sh
git commit -m "feat(ai-play): add lighting circuit repair task"
```

---

### Task 5: Synchronize Documentation and Run Full Verification

**Files:**

- Modify: `README_AI_PLAY.md:1-260`
- Modify: `ai_play/README.md:1-360`
- Modify: `docs/wiki/ai-play/system-guide.md:1-380`
- Modify: `docs/wiki/development/contributor-guide.md:57-141`

**Interfaces:**

- Consumes: final user-visible rules, cap, launch command, outcomes, and privacy behavior from Tasks 1–4.
- Produces: one consistent user/operator/developer description; no runtime interface.

- [ ] **Step 1: Update the root and MCP READMEs**

Change the supported-task count from 6 to 7 and add both launch commands:

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=repair_lighting_circuit

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=repair_lighting_circuit
```

Document the 300-request cap, the task-card target, unknown A–D mapping, one tripped circuit, one breaker choice,
Verify behavior, and exact terminal pairs. State that mapping/fault/seed remain trusted and never enter briefing or
MCP results.

- [ ] **Step 2: Update Wiki contracts and verification commands**

In `system-guide.md`, add the new scenario to the cross-layer cap/outcome list and add a dedicated round-rules section
covering ordinary vs AI launch, four device groups, deterministic seed behavior, hidden state, one-shot failures,
and unselected-Lobby isolation. In `contributor-guide.md`, add:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_lighting_circuit_round.gd
bash tests/check_ai_play_repair_lighting_circuit_monitor.sh
```

- [ ] **Step 3: Run focused Python and Godot verification**

Run:

```bash
PYTHONPATH=ai_play/src python3 -m pytest \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_briefing.py \
  ai_play/tests/test_bridge_server.py \
  ai_play/tests/test_game_session.py -q
godot --headless --path . --script tests/ai_play/test_ai_play_lighting_circuit_round.gd
bash tests/check_ai_play_repair_lighting_circuit_monitor.sh
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
bash tests/check_ai_play_lobby.sh
```

Expected: every command exits 0 with the dedicated pass sentinel and no parser/UID errors.

- [ ] **Step 4: Run affected full regression suites**

Run:

```bash
PYTHONPATH=ai_play/src python3 -m pytest ai_play/tests -q
bash tests/check_ai_play_put_book_monitor.sh
bash tests/check_ai_play_garden.sh
bash tests/check_ai_play_start_script.sh
bash tests/test_ai_play_secret_scan.sh
```

Expected: all Python tests and shell checks pass; existing Lobby/Garden scenarios retain their behavior and the
secret scan finds no credential or hidden-answer leak.

- [ ] **Step 5: Inspect the complete diff and whitespace**

Run:

```bash
git status --short
git diff --stat cd39a636
git diff --check
git diff -- \
  addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  addons/cogito/AIPlay \
  ai_play/src/ai_play \
  tests \
  README_AI_PLAY.md \
  ai_play/README.md \
  docs/wiki
```

Confirm only intended tracked source, scene, tests, UIDs, and docs are present; do not add `.godot/`, caches,
runtime memory, logs, screenshots, or generated docs.

- [ ] **Step 6: Commit documentation**

```bash
git add \
  README_AI_PLAY.md \
  ai_play/README.md \
  docs/wiki/ai-play/system-guide.md \
  docs/wiki/development/contributor-guide.md
git commit -m "docs(ai-play): document lighting circuit task"
```

- [ ] **Step 7: Run the final clean-tree verification**

Run:

```bash
git diff --check HEAD^
git status --short --branch
```

Expected: no whitespace errors and no uncommitted files. Report every executed test command and its result; state
explicitly that no real external model acceptance run was performed.
