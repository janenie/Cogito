# Garden Daily Routine AI Play Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect `../garden/dailyroutine/scenes/home_daily_routine.tscn` to the current stdio MCP AI Play stack so an external MCP client can observe, act, and receive terminal success/failure for the daily routine cleanup game.

**Architecture:** Reuse the current Cogito v3 MCP/Python sidecar and Godot bridge/controller semantics, but add a home-scene-specific observer/interaction probe because `HomeRobotPlayer` is not a `CogitoPlayer` and does not expose `body`, `head`, `player_interaction_component`, attributes, or COGITO UI state. Add a small terminal monitor that converts `DailyRoutineManager.routine_completed` and `routine_failed_changed` into AI Play game-over events.

**Tech Stack:** Godot 4.7 GDScript, WebSocket bridge on `127.0.0.1:8765`, Python stdio MCP package under `ai_play/src/ai_play`, pytest, Godot headless scene tests.

## Global Constraints

- Target garden repo root: `/Users/jan/workspace/cogito_variants/garden`.
- Target scene: `dailyroutine/scenes/home_daily_routine.tscn`.
- AI Play must remain opt-in: normal scene launch must not connect AI; AI launch requires exact user arg `-- --ai-play`.
- Godot bridge must bind/connect only to numeric loopback host `127.0.0.1`.
- Use protocol version `3`; do not extend or revive the garden repo's older protocol version `1` agent-loop path.
- Do not expose scene source, hidden node paths, test files, implementation notes, or puzzle internals in MCP tool outputs.
- Daily routine scenario id: `daily_routine_cleanup`.
- Daily routine max act requests: `150` unless the product owner later chooses a different limit.
- Terminal results whitelist: `success/cleanup_complete`, `failure/cleanup_incomplete`, `failure/max_requests`.
- Do not run real external AI-client acceptance without explicit operator approval because screenshots may leave the machine and incur API cost.

---

## Current dependency map

### Runtime scene dependencies

- `dailyroutine/scenes/home_daily_routine.tscn`
  - Root node: `HomeDailyRoutine`.
  - Player: `CogitoPlayer` node name, but script class is `HomeRobotPlayer`.
  - Manager: `DailyRoutineManager`.
  - Time: `HomeRoutineTimeSystem`.
  - Randomizer: `TrashRandomizer`.
  - HUD: `HomeRoutineHUD`.
  - Core interactables:
    - `Kitchen/Fridge`, script `addon_fridge_interaction.gd`.
    - `Kitchen/FridgeMilk`, script `fridge_milk.gd`.
    - `Kitchen/PaperTrashA`, `Kitchen/PaperTrashB`, `Bedroom/PaperTrashBedroomA`, `Bedroom/PaperTrashBedroomB`, script `paper_trash.gd`.
    - `LivingRoom/LivingRoomTrashBin`, script `kitchen_trash_bin.gd`.
    - `LivingRoom/FinishButton`, script `completion_button.gd`.

### Gameplay state dependencies

- `DailyRoutineManager` is the source of truth:
  - Success is emitted through `routine_completed`.
  - Failure is emitted through `routine_failed_changed(reason)`.
  - Completion requires `milk_drunk == true` and `collected_trash_count >= required_trash_count`, then `submit_cleanup()`.
  - Random loose trash count is set by `RoutineTrashRandomizer.set_required_loose_trash_count(active_count)`.
  - Held item is reported by `held_item_label()`.
- `HomeRobotPlayer` is the action sink:
  - Movement uses InputMap actions `forward`, `back`, `left`, `right`, `sprint`, `jump`.
  - Mouse look is handled from `InputEventMouseMotion`.
  - Interaction uses `interact` and `interact2`.
  - It exposes test hooks: `resolve_interaction_target_for_test`, `get_interaction_prompt_for_test`, `interact_with_target_for_test`, `drop_held_trash_to_nearby_bin_for_test`.
  - It tracks current raycast target in private `_current_interaction_target`; AI observer/probe should not rely on private state when a stable public method can be added.

### Existing AI Play dependencies

- Current Cogito AI Play v3 pieces to copy/adapt into garden:
  - `addons/cogito/AIPlay/ai_play_controller.gd`
  - `addons/cogito/AIPlay/ai_play_bridge.gd`
  - `addons/cogito/AIPlay/ai_play_executor.gd`
  - `addons/cogito/AIPlay/ai_play_interaction_probe.gd`
  - `addons/cogito/AIPlay/ai_play_game_over_screen.gd`
  - `addons/cogito/AIPlay/ai_play_game_over_screen.tscn`
  - Python MCP package under `ai_play/src/ai_play`
- Garden currently has older AI Play files under `../garden/addons/cogito/AIPlay` and `../garden/ai_play` that use protocol version `1` and a direct model agent-loop. They should be upgraded/replaced by the v3 MCP shape, not mixed with it.

---

### Task 1: Add daily-routine scenario metadata to Python MCP

**Files:**
- Create: `/Users/jan/workspace/cogito_variants/garden/ai_play/src/ai_play/daily_routine_cleanup_briefing.py`
- Modify: `/Users/jan/workspace/cogito_variants/garden/ai_play/src/ai_play/scenarios.py`
- Test: `/Users/jan/workspace/cogito_variants/garden/ai_play/tests/test_scenarios.py`
- Test: `/Users/jan/workspace/cogito_variants/garden/ai_play/tests/test_briefing.py`
- Test: `/Users/jan/workspace/cogito_variants/garden/ai_play/tests/test_game_session.py`

**Interfaces:**
- Consumes: current v3 `Scenario` registry API from Cogito.
- Produces: scenario id `daily_routine_cleanup`; hard act limit `150`; allowed game-over pairs `success/cleanup_complete`, `failure/cleanup_incomplete`, `failure/max_requests`; public briefing loader `load_daily_routine_cleanup_briefing() -> tuple[dict, bytes | None]`.

- [ ] **Step 1: Port current v3 Python package shape into garden if needed**

If garden `ai_play/src/ai_play/scenarios.py` does not contain `Scenario`, `load_scenario_briefing`, `scenario_act_request_limit`, and `is_allowed_game_over`, copy the current v3 files from Cogito:

```bash
cp -R /Users/jan/workspace/cogito_variants/Cogito/ai_play/src/ai_play \
  /Users/jan/workspace/cogito_variants/garden/ai_play/src/
cp -R /Users/jan/workspace/cogito_variants/Cogito/ai_play/tests \
  /Users/jan/workspace/cogito_variants/garden/ai_play/
```

Expected: garden Python tests now target the same stdio MCP/v3 bridge design as Cogito, not the old model-agent loop.

- [ ] **Step 2: Write failing scenario registry test**

Add to `/Users/jan/workspace/cogito_variants/garden/ai_play/tests/test_scenarios.py`:

```python
def test_daily_routine_cleanup_scenario_is_registered():
    assert scenario_act_request_limit("daily_routine_cleanup") == 150
    assert is_allowed_game_over(
        "daily_routine_cleanup",
        {"outcome": "success", "reason": "cleanup_complete"},
    )
    assert is_allowed_game_over(
        "daily_routine_cleanup",
        {"outcome": "failure", "reason": "cleanup_incomplete"},
    )
    assert is_allowed_game_over(
        "daily_routine_cleanup",
        {"outcome": "failure", "reason": "max_requests"},
    )
    assert not is_allowed_game_over(
        "daily_routine_cleanup",
        {"outcome": "success", "reason": "correct_password"},
    )
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_scenarios.py -q
```

Expected: FAIL because `daily_routine_cleanup` is not registered.

- [ ] **Step 4: Create public briefing**

Create `/Users/jan/workspace/cogito_variants/garden/ai_play/src/ai_play/daily_routine_cleanup_briefing.py`:

```python
from __future__ import annotations

from copy import deepcopy


PUBLIC_BRIEFING = {
    "game_id": "daily_routine_cleanup",
    "title": "清理日常垃圾",
    "background": (
        "这是一个第一人称家庭日常任务。玩家在一个小型室内空间中探索，"
        "根据 HUD 目标和可见交互提示完成清理。"
    ),
    "objective": (
        "把家里全部需要处理的垃圾都扔进客厅垃圾桶，然后点击客厅垃圾桶旁边的完成按钮。"
    ),
    "success_condition": "所有目标垃圾都已扔进客厅垃圾桶，并点击完成按钮。",
    "failure_condition": "在垃圾尚未全部处理时点击完成按钮，或达到最大 act 请求数。",
    "rules": [
        "先观察 HUD 的当前目标、总垃圾数、已扔数量和手上物品。",
        "可交互物体需要靠近、对准并在出现交互提示后操作。",
        "冰箱需要先打开，里面的过期牛奶也属于需要处理的物品。",
        "手上一次只能拿一个物品；拿到垃圾后先送到客厅垃圾桶。",
        "只有客厅垃圾桶用于本局目标。",
        "完成按钮在客厅垃圾桶旁边；垃圾未清理完时点击会失败。",
        "看到可疑小物体但没有交互提示时，先靠近并使用 probe_interaction 对准它。",
        "每次交互后重新 observe，依据画面、HUD 和动作结果决定下一步。",
    ],
    "objects": [
        {
            "id": "living_room_trash_bin",
            "meaning": "客厅垃圾桶是所有垃圾的投放目标。",
            "actions": {
                "probe_interaction": "对准垃圾桶寻找使用提示。",
                "interact": "手上有垃圾时，把垃圾扔进桶里。",
            },
        },
        {
            "id": "finish_button",
            "meaning": "完成按钮用于提交任务。",
            "actions": {
                "probe_interaction": "对准按钮寻找完成任务提示。",
                "interact": "只有确认所有垃圾已处理后再点击。",
            },
        },
        {
            "id": "fridge",
            "meaning": "冰箱可以打开；打开后可能出现需要处理的过期牛奶。",
            "actions": {
                "probe_interaction": "对准冰箱门寻找打开或拿取提示。",
                "interact": "打开冰箱或拿取过期牛奶。",
            },
        },
        {
            "id": "loose_trash",
            "meaning": "地上的纸团等散落物是需要捡起的垃圾。",
            "actions": {
                "probe_interaction": "对准散落垃圾寻找拾取提示。",
                "interact": "拿起垃圾。",
            },
        },
    ],
}


def load_daily_routine_cleanup_briefing():
    return deepcopy(PUBLIC_BRIEFING), None
```

- [ ] **Step 5: Register scenario**

Modify `/Users/jan/workspace/cogito_variants/garden/ai_play/src/ai_play/scenarios.py`:

```python
from .daily_routine_cleanup_briefing import load_daily_routine_cleanup_briefing

_SCENARIOS["daily_routine_cleanup"] = Scenario(
    scenario_id="daily_routine_cleanup",
    briefing_loader=load_daily_routine_cleanup_briefing,
    max_act_requests=150,
    allowed_terminal_results=frozenset({
        ("success", "cleanup_complete"),
        ("failure", "cleanup_incomplete"),
        ("failure", "max_requests"),
    }),
)
```

- [ ] **Step 6: Add briefing test**

Add to `/Users/jan/workspace/cogito_variants/garden/ai_play/tests/test_briefing.py`:

```python
def test_daily_routine_cleanup_briefing_is_public_and_bounded():
    briefing, image_bytes = load_scenario_briefing("daily_routine_cleanup")

    assert image_bytes is None
    assert briefing["game_id"] == "daily_routine_cleanup"
    assert "客厅垃圾桶" in briefing["objective"]
    assert briefing["success_condition"] == "所有目标垃圾都已扔进客厅垃圾桶，并点击完成按钮。"
    text = repr(briefing)
    forbidden = [
        "DailyRoutineManager",
        "TrashRandomizer",
        "routine_completed",
        "dailyroutine/scripts",
        "home_daily_routine.tscn",
    ]
    for value in forbidden:
        assert value not in text
```

- [ ] **Step 7: Add session terminal/cap test**

Add to `/Users/jan/workspace/cogito_variants/garden/ai_play/tests/test_game_session.py`:

```python
def test_daily_routine_cleanup_uses_150_request_cap(config):
    session = GameSession(config)
    assert scenario_act_request_limit("daily_routine_cleanup") == 150


def test_daily_routine_cleanup_rejects_other_scenario_terminal_results():
    assert not is_allowed_game_over(
        "daily_routine_cleanup",
        {"outcome": "success", "reason": "meeting_door_closed"},
    )
```

- [ ] **Step 8: Run Python tests**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_briefing.py \
  ai_play/tests/test_game_session.py \
  -q
```

Expected: all selected tests PASS.

- [ ] **Step 9: Commit**

```bash
cd /Users/jan/workspace/cogito_variants/garden
git add ai_play/src/ai_play ai_play/tests
git commit -m "feat: register daily routine AI Play scenario"
```

---

### Task 2: Make `HomeRobotPlayer` observable by AI Play

**Files:**
- Modify: `/Users/jan/workspace/cogito_variants/garden/dailyroutine/scripts/home_robot_player.gd`
- Create: `/Users/jan/workspace/cogito_variants/garden/addons/cogito/AIPlay/ai_play_home_observer.gd`
- Test: `/Users/jan/workspace/cogito_variants/garden/tests/dailyroutine/test_home_ai_play_observer.gd`
- Create shell check: `/Users/jan/workspace/cogito_variants/garden/tests/check_home_ai_play_observer.sh`

**Interfaces:**
- Consumes: `HomeRobotPlayer.camera`, `HomeRobotPlayer._target_from_ray()`, `HomeRobotPlayer.get_interaction_prompt_for_test(target)`, `DailyRoutineManager` fields.
- Produces:
  - `HomeRobotPlayer.current_interaction_target() -> Node`
  - `HomeRobotPlayer.is_readable_open() -> bool`
  - `HomeRobotPlayer.ai_play_orientation_degrees() -> Vector2`
  - `AIPlayHomeObserver.capture_observation(last_results: Array) -> Dictionary`
  - `AIPlayHomeObserver.get_available_interactions() -> Array[Dictionary]`

- [ ] **Step 1: Write failing observer test**

Create `/Users/jan/workspace/cogito_variants/garden/tests/dailyroutine/test_home_ai_play_observer.gd`:

```gdscript
extends SceneTree

var failures: Array[String] = []

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var packed: PackedScene = load("res://dailyroutine/scenes/home_daily_routine.tscn")
	_assert(packed != null, "daily routine scene loads")
	if packed == null:
		_finish()
		return
	var scene := packed.instantiate()
	root.add_child(scene)
	await process_frame

	var player := scene.get_node_or_null("CogitoPlayer")
	var manager := scene.get_node_or_null("DailyRoutineManager")
	var ObserverScript = load("res://addons/cogito/AIPlay/ai_play_home_observer.gd")
	_assert(player != null, "scene has HomeRobotPlayer")
	_assert(manager != null, "scene has manager")
	_assert(ObserverScript != null, "home observer script loads")
	if player == null or manager == null or ObserverScript == null:
		scene.queue_free()
		_finish()
		return

	var observer = ObserverScript.new()
	observer.player = player
	observer.manager = manager
	scene.add_child(observer)
	var observation: Dictionary = observer.capture_observation([])

	_assert(observation["observation_id"] == 1, "observation id starts at one")
	_assert(observation["image"]["mime_type"] == "image/jpeg", "observation includes jpeg image")
	_assert(observation["player"]["position"].size() == 3, "player position is public")
	_assert(observation["player"].has("yaw_degrees"), "player yaw is public")
	_assert(observation["player"].has("pitch_degrees"), "player pitch is public")
	_assert(observation["interface"].has("available_interactions"), "interactions are public")
	_assert(observation["interface"]["visible_object_text"] == "", "no hidden text is leaked")
	_assert(observation["routine"]["objective"] == manager.current_objective, "routine objective is exposed")
	_assert(observation["routine"]["trash_collected"] == manager.collected_trash_count, "trash count current is exposed")
	_assert(observation["routine"]["trash_required"] == manager.required_trash_count, "trash count required is exposed")
	_assert(observation["routine"]["held_item"] == manager.held_item_label(), "held item is exposed")
	_assert(not repr(observation).contains("DailyRoutineManager"), "observation does not leak class names")
	_assert(not repr(observation).contains("dailyroutine/scripts"), "observation does not leak script paths")

	scene.queue_free()
	await process_frame
	_finish()

func _finish() -> void:
	if failures.is_empty():
		print("Home AI Play observer test passed")
		quit(0)
	for failure in failures:
		push_error(failure)
	quit(1)

func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)
```

- [ ] **Step 2: Run observer test to verify it fails**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
godot --headless --path . --script tests/dailyroutine/test_home_ai_play_observer.gd
```

Expected: FAIL because `ai_play_home_observer.gd` does not exist.

- [ ] **Step 3: Add stable AI-facing methods to `HomeRobotPlayer`**

Append to `/Users/jan/workspace/cogito_variants/garden/dailyroutine/scripts/home_robot_player.gd`:

```gdscript
func current_interaction_target() -> Node:
	return _target_from_ray()

func is_readable_open() -> bool:
	return _readable_is_open()

func ai_play_orientation_degrees() -> Vector2:
	var yaw := global_rotation_degrees.y
	var pitch := 0.0
	if camera != null:
		pitch = camera.rotation_degrees.x
	return Vector2(yaw, pitch)
```

- [ ] **Step 4: Create `AIPlayHomeObserver`**

Create `/Users/jan/workspace/cogito_variants/garden/addons/cogito/AIPlay/ai_play_home_observer.gd`:

```gdscript
class_name AIPlayHomeObserver
extends Node

const APPROVED_ACTIONS: Array[String] = [
	"forward", "back", "left", "right", "jump", "sprint", "interact",
	"interact2", "menu",
]
const IMAGE_WIDTH := 768
const IMAGE_HEIGHT := 432
const MAX_JSON_DEPTH := 16

@export var player: Node3D
@export var manager: DailyRoutineManager
@export_range(0.0, 1.0, 0.01) var jpeg_quality := 0.75

var bindings: Dictionary = {}
var _observation_id := 0

func capture_observation(last_results: Array) -> Dictionary:
	_observation_id += 1
	bindings = get_bindings()
	var image := _capture_image()
	var orientation := _orientation()
	return {
		"observation_id": _observation_id,
		"captured_at_ms": Time.get_ticks_msec(),
		"image": {
			"mime_type": "image/jpeg",
			"base64": Marshalls.raw_to_base64(image.save_jpg_to_buffer(jpeg_quality)),
			"width": IMAGE_WIDTH,
			"height": IMAGE_HEIGHT,
		},
		"player": {
			"position": [player.position.x, player.position.y, player.position.z],
			"yaw_degrees": orientation.x,
			"pitch_degrees": orientation.y,
			"planar_velocity": [player.velocity.x, player.velocity.z],
			"on_floor": player.is_on_floor(),
			"health_ratio": null,
			"stamina_ratio": null,
		},
		"interface": {
			"is_open": player.has_method("is_readable_open") and player.is_readable_open(),
			"visible_object_text": "",
			"available_interactions": get_available_interactions(),
		},
		"routine": {
			"objective": manager.current_objective,
			"trash_collected": manager.collected_trash_count,
			"trash_required": manager.required_trash_count,
			"held_item": manager.held_item_label(),
			"completed": manager.routine_complete,
			"failed": manager.routine_failed,
		},
		"bindings": bindings,
		"last_action_results": _sanitize_last_results(last_results),
	}

func get_bindings() -> Dictionary:
	var result: Dictionary = {}
	for action_name: String in APPROVED_ACTIONS:
		result[action_name] = "unbound"
		for event: InputEvent in InputMap.action_get_events(action_name):
			if event is InputEventKey:
				var key_event := event as InputEventKey
				var label := OS.get_keycode_string(key_event.physical_keycode)
				if not label.is_empty():
					result[action_name] = label
				break
	bindings = result
	return result

func get_available_interactions() -> Array[Dictionary]:
	var target: Node = null
	if player != null and player.has_method("current_interaction_target"):
		target = player.current_interaction_target()
	if target == null:
		return []
	var prompt := ""
	if player != null and player.has_method("get_interaction_prompt_for_test"):
		prompt = player.get_interaction_prompt_for_test(target)
	if prompt.is_empty():
		return []
	return [{
		"action": "interact",
		"binding": bindings.get("interact", "unbound"),
		"prompt": prompt,
	}]

func _capture_image() -> Image:
	if DisplayServer.get_name() == "headless":
		return Image.create(IMAGE_WIDTH, IMAGE_HEIGHT, false, Image.FORMAT_RGB8)
	var image := get_viewport().get_texture().get_image()
	image.resize(IMAGE_WIDTH, IMAGE_HEIGHT, Image.INTERPOLATE_LANCZOS)
	return image

func _orientation() -> Vector2:
	if player != null and player.has_method("ai_play_orientation_degrees"):
		return player.ai_play_orientation_degrees()
	return Vector2.ZERO

func _sanitize_last_results(last_results: Array) -> Array:
	var safe_results: Array = []
	for result: Variant in last_results:
		var sanitized := _sanitize_json_value(result)
		if sanitized["valid"]:
			safe_results.append(sanitized["value"])
	return safe_results

func _sanitize_json_value(value: Variant, depth: int = 0) -> Dictionary:
	if depth > MAX_JSON_DEPTH:
		return {"valid": false}
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_STRING:
			return {"valid": true, "value": value}
		TYPE_FLOAT:
			return {"valid": is_finite(value), "value": value}
		TYPE_ARRAY:
			var safe_array: Array = []
			for item: Variant in value:
				var sanitized_item := _sanitize_json_value(item, depth + 1)
				if not sanitized_item["valid"]:
					return {"valid": false}
				safe_array.append(sanitized_item["value"])
			return {"valid": true, "value": safe_array}
		TYPE_DICTIONARY:
			var safe_dictionary: Dictionary = {}
			for key: Variant in value:
				if not key is String:
					return {"valid": false}
				var sanitized_value := _sanitize_json_value(value[key], depth + 1)
				if not sanitized_value["valid"]:
					return {"valid": false}
				safe_dictionary[key] = sanitized_value["value"]
			return {"valid": true, "value": safe_dictionary}
	return {"valid": false}
```

- [ ] **Step 5: Create shell wrapper**

Create `/Users/jan/workspace/cogito_variants/garden/tests/check_home_ai_play_observer.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
godot --headless --path . --script tests/dailyroutine/test_home_ai_play_observer.gd
```

Then run:

```bash
chmod +x /Users/jan/workspace/cogito_variants/garden/tests/check_home_ai_play_observer.sh
```

- [ ] **Step 6: Run observer test to verify it passes**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
bash tests/check_home_ai_play_observer.sh
```

Expected: `Home AI Play observer test passed`.

- [ ] **Step 7: Commit**

```bash
cd /Users/jan/workspace/cogito_variants/garden
git add dailyroutine/scripts/home_robot_player.gd \
  addons/cogito/AIPlay/ai_play_home_observer.gd \
  tests/dailyroutine/test_home_ai_play_observer.gd \
  tests/check_home_ai_play_observer.sh
git commit -m "feat: expose daily routine observations for AI Play"
```

---

### Task 3: Add home-compatible interaction probe and controller wiring

**Files:**
- Create: `/Users/jan/workspace/cogito_variants/garden/addons/cogito/AIPlay/ai_play_home_interaction_probe.gd`
- Modify: `/Users/jan/workspace/cogito_variants/garden/addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `/Users/jan/workspace/cogito_variants/garden/addons/cogito/AIPlay/ai_play_controller.tscn`
- Test: `/Users/jan/workspace/cogito_variants/garden/tests/ai_play/test_ai_play_home_probe.gd`

**Interfaces:**
- Consumes: `HomeRobotPlayer.camera`, `HomeRobotPlayer.mouse_sensitivity`, `HomeRobotPlayer.ai_play_orientation_degrees()`.
- Produces: `AIPlayHomeInteractionProbe.probe(target_x: float, target_y: float) -> Dictionary`, same result shape as current `AIPlayInteractionProbe`.

- [ ] **Step 1: Write failing probe test**

Create `/Users/jan/workspace/cogito_variants/garden/tests/ai_play/test_ai_play_home_probe.gd`:

```gdscript
extends SceneTree

var failures: Array[String] = []

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var ProbeScript = load("res://addons/cogito/AIPlay/ai_play_home_interaction_probe.gd")
	_assert(ProbeScript != null, "home interaction probe loads")
	if ProbeScript != null:
		var probe = ProbeScript.new()
		root.add_child(probe)
		var rotation: Vector2 = probe.target_rotation_degrees(0.5, 0.5, 75.0, 16.0 / 9.0)
		_assert(rotation.length() < 0.001, "center target has zero rotation")
		probe.queue_free()
	_finish()

func _finish() -> void:
	if failures.is_empty():
		print("Home AI Play interaction probe test passed")
		quit(0)
	for failure in failures:
		push_error(failure)
	quit(1)

func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)
```

- [ ] **Step 2: Run probe test to verify it fails**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
godot --headless --path . --script tests/ai_play/test_ai_play_home_probe.gd
```

Expected: FAIL because `ai_play_home_interaction_probe.gd` does not exist.

- [ ] **Step 3: Create home interaction probe**

Create `/Users/jan/workspace/cogito_variants/garden/addons/cogito/AIPlay/ai_play_home_interaction_probe.gd` by copying the v3 `AIPlayInteractionProbe` algorithm and replacing the Cogito-specific availability/orientation code with:

```gdscript
class_name AIPlayHomeInteractionProbe
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
var input_sender: Callable
var _generation := 0
var _cancel_reason := "cancelled"

func target_rotation_degrees(target_x: float, target_y: float, vertical_fov_degrees: float, aspect_ratio: float) -> Vector2:
	var vertical_tangent := tan(deg_to_rad(vertical_fov_degrees * 0.5))
	var ndc_x := target_x * 2.0 - 1.0
	var ndc_y := target_y * 2.0 - 1.0
	var yaw := rad_to_deg(atan(ndc_x * vertical_tangent * aspect_ratio))
	var pitch := rad_to_deg(atan(ndc_y * vertical_tangent))
	return Vector2(yaw, pitch)

func probe(target_x: float, target_y: float) -> Dictionary:
	if not _is_available():
		return {"status": "error", "error": "interaction probe is unavailable"}
	_generation += 1
	var generation := _generation
	_cancel_reason = "cancelled"
	var active_camera := _active_camera()
	var target_rotation := target_rotation_degrees(target_x, target_y, active_camera.fov, _viewport_aspect_ratio())
	var previous_rotation := Vector2.ZERO
	for scan_index in SCAN_OFFSETS_DEGREES.size():
		var scan_rotation := target_rotation + SCAN_OFFSETS_DEGREES[scan_index]
		_emit_mouse_rotation(scan_rotation - previous_rotation)
		previous_rotation = scan_rotation
		await get_tree().process_frame
		if generation != _generation:
			return {"status": "cancelled", "reason": _cancel_reason}
		var interactions: Variant = interaction_provider.call() if interaction_provider.is_valid() else []
		if interactions is Array and not interactions.is_empty():
			return {"status": "completed", "type": "probe_interaction", "outcome": "aligned", "scan_steps": scan_index + 1}
	return {"status": "completed", "type": "probe_interaction", "outcome": "not_found", "scan_steps": SCAN_OFFSETS_DEGREES.size()}

func cancel(reason: String) -> void:
	_cancel_reason = reason
	_generation += 1

func _active_camera() -> Camera3D:
	if player != null and "camera" in player:
		return player.get("camera") as Camera3D
	return get_viewport().get_camera_3d()

func _is_available() -> bool:
	return player != null \
		and is_instance_valid(player) \
		and _active_camera() != null \
		and "mouse_sensitivity" in player \
		and interaction_provider.is_valid()

func _viewport_aspect_ratio() -> float:
	var viewport_size := get_viewport().get_visible_rect().size
	return 1.0 if viewport_size.y <= 0.0 else viewport_size.x / viewport_size.y

func _emit_mouse_rotation(target_rotation: Vector2) -> void:
	var sensitivity := float(player.get("mouse_sensitivity"))
	var motion := InputEventMouseMotion.new()
	motion.device = SYNTHETIC_DEVICE_ID
	motion.relative = Vector2(target_rotation.x / maxf(sensitivity, 0.0001), target_rotation.y / maxf(sensitivity, 0.0001))
	motion.screen_relative = motion.relative
	if input_sender.is_valid():
		input_sender.call(motion)
	else:
		Input.parse_input_event(motion)
```

- [ ] **Step 4: Upgrade controller to accept generic player and scenario**

In `/Users/jan/workspace/cogito_variants/garden/addons/cogito/AIPlay/ai_play_controller.gd`:

```gdscript
const PROTOCOL_VERSION: int = 3
const DEFAULT_SCENARIO_ID := "daily_routine_cleanup"
const SCENARIO_ARG_PREFIX := "--ai-play-scenario="
const SCENARIO_TERMINAL_RESULTS := {
	"daily_routine_cleanup": [
		["success", "cleanup_complete"],
		["failure", "cleanup_incomplete"],
		["failure", "max_requests"],
	],
}

@export var player: Node3D
```

Also port the v3 controller methods from Cogito:

```gdscript
func get_requested_scenario_id(user_args: Array) -> String
func is_requested_scenario(scenario_id: String) -> bool
func get_active_scenario_id() -> String
func _find_scenario_monitor(scenario_id: String) -> Node
func _on_end_game_received(request: Dictionary) -> void
func _is_allowed_terminal_result(outcome: String, reason: String) -> bool
```

Expected behavior:

- `-- --ai-play-scenario=daily_routine_cleanup` selects the home scenario without connecting AI.
- `-- --ai-play --ai-play-scenario=daily_routine_cleanup` connects AI.
- Any other scenario id is invalid in this garden-only controller until explicitly added.

- [ ] **Step 5: Wire controller scene to home observer/probe**

Modify `/Users/jan/workspace/cogito_variants/garden/addons/cogito/AIPlay/ai_play_controller.tscn`:

```ini
[node name="Observer" type="Node" parent="."]
script = ExtResource("ai_play_home_observer")

[node name="InteractionProbe" type="Node" parent="."]
script = ExtResource("ai_play_home_interaction_probe")
```

Keep existing children:

```ini
Bridge
Executor
ObservationTimer
```

- [ ] **Step 6: Run AI Play controller/probe tests**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
godot --headless --path . --script tests/ai_play/test_ai_play_home_probe.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
```

Expected: all selected tests PASS. If existing controller tests are for protocol v1, update their expected protocol to `3` and remove checks for old `bindings`/`data_dir` in hello.

- [ ] **Step 7: Commit**

```bash
cd /Users/jan/workspace/cogito_variants/garden
git add addons/cogito/AIPlay tests/ai_play
git commit -m "feat: upgrade garden AI Play controller to protocol v3"
```

---

### Task 4: Add daily routine terminal monitor and game-over UI

**Files:**
- Create: `/Users/jan/workspace/cogito_variants/garden/dailyroutine/scripts/ai_play_daily_routine_monitor.gd`
- Modify: `/Users/jan/workspace/cogito_variants/garden/addons/cogito/AIPlay/ai_play_game_over_screen.gd`
- Test: `/Users/jan/workspace/cogito_variants/garden/tests/dailyroutine/test_daily_routine_ai_play_monitor.gd`
- Create shell check: `/Users/jan/workspace/cogito_variants/garden/tests/check_daily_routine_ai_play_monitor.sh`

**Interfaces:**
- Consumes: `DailyRoutineManager.routine_completed`, `DailyRoutineManager.routine_failed_changed(reason)`.
- Produces: `signal game_finished(outcome: String, reason: String)`, `show_result(outcome: String, reason: String)`.

- [ ] **Step 1: Write failing monitor test**

Create `/Users/jan/workspace/cogito_variants/garden/tests/dailyroutine/test_daily_routine_ai_play_monitor.gd`:

```gdscript
extends SceneTree

var failures: Array[String] = []

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var MonitorScript = load("res://dailyroutine/scripts/ai_play_daily_routine_monitor.gd")
	_assert(MonitorScript != null, "daily routine monitor loads")
	var ManagerScript = load("res://dailyroutine/scripts/daily_routine_manager.gd")
	_assert(ManagerScript != null, "manager script loads")
	if MonitorScript == null or ManagerScript == null:
		_finish()
		return
	var root_node := Node.new()
	root.add_child(root_node)
	var manager = ManagerScript.new()
	var monitor = MonitorScript.new()
	root_node.add_child(manager)
	root_node.add_child(monitor)
	monitor.manager = manager
	var results: Array[Dictionary] = []
	monitor.game_finished.connect(func(outcome: String, reason: String) -> void:
		results.append({"outcome": outcome, "reason": reason})
	)
	monitor._ready()
	manager.start_routine()
	manager.milk_drunk = true
	manager.collected_trash_count = manager.required_trash_count
	manager.submit_cleanup()
	_assert(results == [{"outcome": "success", "reason": "cleanup_complete"}], "routine completion emits success once")
	manager.submit_cleanup()
	_assert(results.size() == 1, "monitor emits terminal result once")
	root_node.queue_free()
	_finish()

func _finish() -> void:
	if failures.is_empty():
		print("Daily routine AI Play monitor test passed")
		quit(0)
	for failure in failures:
		push_error(failure)
	quit(1)

func _assert(condition: bool, label: String) -> void:
	if not condition:
		failures.append(label)
```

- [ ] **Step 2: Run monitor test to verify it fails**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
godot --headless --path . --script tests/dailyroutine/test_daily_routine_ai_play_monitor.gd
```

Expected: FAIL because monitor script does not exist.

- [ ] **Step 3: Create monitor**

Create `/Users/jan/workspace/cogito_variants/garden/dailyroutine/scripts/ai_play_daily_routine_monitor.gd`:

```gdscript
class_name AIPlayDailyRoutineMonitor
extends Node

signal game_finished(outcome: String, reason: String)

@export var scenario_id := "daily_routine_cleanup"
@export var manager: DailyRoutineManager
@export var game_over_screen: AIPlayGameOverScreen

var _finished := false

func _ready() -> void:
	if manager == null:
		manager = get_node_or_null("../../DailyRoutineManager") as DailyRoutineManager
	if manager == null:
		push_error("AIPlayDailyRoutineMonitor is missing DailyRoutineManager")
		return
	if not manager.routine_completed.is_connected(_on_routine_completed):
		manager.routine_completed.connect(_on_routine_completed)
	if not manager.routine_failed_changed.is_connected(_on_routine_failed):
		manager.routine_failed_changed.connect(_on_routine_failed)

func _on_routine_completed() -> void:
	_emit_once("success", "cleanup_complete")

func _on_routine_failed(_reason: String) -> void:
	_emit_once("failure", "cleanup_incomplete")

func _emit_once(outcome: String, reason: String) -> void:
	if _finished:
		return
	_finished = true
	game_finished.emit(outcome, reason)

func show_result(outcome: String, reason: String) -> void:
	if game_over_screen != null:
		game_over_screen.show_result(outcome, reason)
```

- [ ] **Step 4: Extend game-over screen copy**

Modify `/Users/jan/workspace/cogito_variants/garden/addons/cogito/AIPlay/ai_play_game_over_screen.gd`:

```gdscript
const OUTCOME_TEXT := {
	"cleanup_complete": "任务成功",
	"cleanup_incomplete": "任务失败",
	"max_requests": "任务失败",
}
const REASON_TEXT := {
	"cleanup_complete": "所有垃圾已清理",
	"cleanup_incomplete": "还有垃圾没有处理",
	"max_requests": "达到最大步长",
}
```

- [ ] **Step 5: Run monitor test**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
godot --headless --path . --script tests/dailyroutine/test_daily_routine_ai_play_monitor.gd
```

Expected: `Daily routine AI Play monitor test passed`.

- [ ] **Step 6: Commit**

```bash
cd /Users/jan/workspace/cogito_variants/garden
git add dailyroutine/scripts/ai_play_daily_routine_monitor.gd \
  addons/cogito/AIPlay/ai_play_game_over_screen.gd \
  tests/dailyroutine/test_daily_routine_ai_play_monitor.gd
git commit -m "feat: report daily routine AI Play terminal results"
```

---

### Task 5: Mount AI Play nodes into `home_daily_routine.tscn`

**Files:**
- Modify: `/Users/jan/workspace/cogito_variants/garden/dailyroutine/scenes/home_daily_routine.tscn`
- Test: `/Users/jan/workspace/cogito_variants/garden/tests/dailyroutine/test_daily_routine_scene.gd`
- Test: `/Users/jan/workspace/cogito_variants/garden/tests/check_ai_play_home_daily_routine.sh`

**Interfaces:**
- Consumes: `AIPlayController` scene, `AIPlayDailyRoutineMonitor`, `AIPlayGameOverScreen`.
- Produces: scene launch commands:
  - Manual scenario mode: `godot --path . dailyroutine/scenes/home_daily_routine.tscn -- --ai-play-scenario=daily_routine_cleanup`
  - AI mode: `godot --path . dailyroutine/scenes/home_daily_routine.tscn -- --ai-play --ai-play-scenario=daily_routine_cleanup`

- [ ] **Step 1: Add failing scene assertions**

Append assertions to `/Users/jan/workspace/cogito_variants/garden/tests/dailyroutine/test_daily_routine_scene.gd` inside `_test_home_scene_structure()`:

```gdscript
_assert(scene.get_node_or_null("AIPlayController") != null, "scene has AIPlay controller")
_assert(scene.get_node_or_null("AIPlayController/DailyRoutineMonitor") != null, "scene has daily routine AI monitor")
_assert(scene.get_node_or_null("AIPlayController/DailyRoutineMonitor/GameOverScreen") != null, "scene has AI game-over screen")
var controller := scene.get_node_or_null("AIPlayController")
if controller != null:
	_assert(controller.get("auto_start") == false, "AI Play is opt-in")
	_assert(str(controller.get("host")) == "127.0.0.1", "AI Play uses loopback host")
```

- [ ] **Step 2: Run scene test to verify it fails**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
godot --headless --path . --script tests/dailyroutine/test_daily_routine_scene.gd
```

Expected: FAIL because scene does not have `AIPlayController`.

- [ ] **Step 3: Mount nodes in scene**

Edit `/Users/jan/workspace/cogito_variants/garden/dailyroutine/scenes/home_daily_routine.tscn`:

```ini
[ext_resource type="PackedScene" path="res://addons/cogito/AIPlay/ai_play_controller.tscn" id="ai_play_controller"]
[ext_resource type="Script" path="res://dailyroutine/scripts/ai_play_daily_routine_monitor.gd" id="ai_play_daily_routine_monitor"]
[ext_resource type="PackedScene" path="res://addons/cogito/AIPlay/ai_play_game_over_screen.tscn" id="ai_play_game_over_screen"]

[node name="AIPlayController" parent="." node_paths=PackedStringArray("player") instance=ExtResource("ai_play_controller")]
player = NodePath("../CogitoPlayer")
auto_start = false
host = "127.0.0.1"

[node name="DailyRoutineMonitor" type="Node" parent="AIPlayController" node_paths=PackedStringArray("manager", "game_over_screen")]
script = ExtResource("ai_play_daily_routine_monitor")
scenario_id = "daily_routine_cleanup"
manager = NodePath("../../DailyRoutineManager")
game_over_screen = NodePath("GameOverScreen")

[node name="GameOverScreen" parent="AIPlayController/DailyRoutineMonitor" instance=ExtResource("ai_play_game_over_screen")]
```

Also ensure `AIPlayController/Observer` receives manager:

```gdscript
if "manager" in _observer:
	_observer.manager = get_node_or_null("../DailyRoutineManager")
```

Add that line to controller `_ready()` after observer player assignment.

- [ ] **Step 4: Create static scene check**

Create `/Users/jan/workspace/cogito_variants/garden/tests/check_ai_play_home_daily_routine.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
scene="dailyroutine/scenes/home_daily_routine.tscn"
grep -q 'name="AIPlayController"' "$scene"
grep -q 'auto_start = false' "$scene"
grep -q 'host = "127.0.0.1"' "$scene"
grep -q 'name="DailyRoutineMonitor" type="Node" parent="AIPlayController"' "$scene"
grep -q 'scenario_id = "daily_routine_cleanup"' "$scene"
grep -q 'manager = NodePath("../../DailyRoutineManager")' "$scene"
grep -q 'name="GameOverScreen" parent="AIPlayController/DailyRoutineMonitor"' "$scene"
```

Then run:

```bash
chmod +x /Users/jan/workspace/cogito_variants/garden/tests/check_ai_play_home_daily_routine.sh
```

- [ ] **Step 5: Run scene checks**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
godot --headless --path . --script tests/dailyroutine/test_daily_routine_scene.gd
bash tests/check_ai_play_home_daily_routine.sh
```

Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/jan/workspace/cogito_variants/garden
git add dailyroutine/scenes/home_daily_routine.tscn \
  addons/cogito/AIPlay/ai_play_controller.gd \
  tests/dailyroutine/test_daily_routine_scene.gd \
  tests/check_ai_play_home_daily_routine.sh
git commit -m "feat: mount AI Play in daily routine scene"
```

---

### Task 6: Update docs and run final verification

**Files:**
- Modify: `/Users/jan/workspace/cogito_variants/garden/ai_play/README.md`
- Create or modify: `/Users/jan/workspace/cogito_variants/garden/README_AI_PLAY.md`
- Test: all checks from previous tasks

**Interfaces:**
- Produces documented launch commands and safety boundaries for `daily_routine_cleanup`.

- [ ] **Step 1: Update README with stdio MCP flow**

Add to `/Users/jan/workspace/cogito_variants/garden/ai_play/README.md`:

Add this section:

> ## Daily routine cleanup scenario
>
> Manual scenario launch, without AI control:
>
> ```bash
> godot --path . dailyroutine/scenes/home_daily_routine.tscn \
>   -- --ai-play-scenario=daily_routine_cleanup
> ```
>
> AI Play launch:
>
> ```bash
> godot --path . dailyroutine/scenes/home_daily_routine.tscn \
>   -- --ai-play --ai-play-scenario=daily_routine_cleanup
> ```
>
> The scene remains opt-in. `--ai-play-scenario=daily_routine_cleanup` selects
> the round rules but does not connect AI. Only the exact `--ai-play` user arg
> connects the local bridge.
>
> Success is `success/cleanup_complete`. Failure is `failure/cleanup_incomplete`
> when the finish button is submitted too early, or `failure/max_requests` when
> the MCP `act` request cap is reached. The hard cap is 150 act requests.


- [ ] **Step 2: Run Python verification**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
```

Expected: all Python tests PASS.

- [ ] **Step 3: Run Godot daily-routine verification**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
godot --headless --path . --script tests/dailyroutine/test_daily_routine_scene.gd
godot --headless --path . --script tests/dailyroutine/test_daily_routine_time_and_game.gd
godot --headless --path . --script tests/dailyroutine/test_home_robot_player_interaction.gd
bash tests/check_home_ai_play_observer.sh
bash tests/check_ai_play_home_daily_routine.sh
bash tests/check_daily_routine_ai_play_monitor.sh
```

Expected: all selected Godot checks PASS.

- [ ] **Step 4: Run shared safety checks**

Run:

```bash
cd /Users/jan/workspace/cogito_variants/garden
bash tests/check_ai_play_secrets.sh
bash tests/test_ai_play_secret_scan.sh
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 5: Commit docs**

```bash
cd /Users/jan/workspace/cogito_variants/garden
git add ai_play/README.md README_AI_PLAY.md
git commit -m "docs: document daily routine AI Play"
```

---

## Execution notes

- The main implementation risk is type mismatch: current Cogito observer/probe assumes `CogitoPlayer`; daily routine uses `HomeRobotPlayer`. Do not force `HomeRobotPlayer` to become a full `CogitoPlayer`. Keep a home-specific observer/probe with the same wire payload shape.
- The second risk is mixing garden's older protocol v1 AI agent-loop with current v3 stdio MCP. The plan intentionally upgrades garden to the v3 MCP pattern.
- The third risk is leaking hidden implementation details. Briefing and observation may expose HUD objective, public counts, held item, available interaction prompts, player pose, and screenshot only. They must not expose scene paths, script names, randomizer internals, exact hidden active trash list, or test facts.

## Self-review

- Spec coverage: daily routine dependencies, Python scenario metadata, Godot observation/action bridge, terminal results, scene mount, docs, and tests are all covered.
- Placeholder scan: no unfinished placeholder markers remain.
- Type consistency: the plan consistently uses scenario id `daily_routine_cleanup`, success reason `cleanup_complete`, failure reasons `cleanup_incomplete` and `max_requests`, and act cap `150`.
