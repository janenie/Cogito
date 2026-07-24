# Find Key Scenario Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `find_key` Lobby mode that places the only key at one of five semantic locations, starts the player at the farthest safe spawn, and succeeds when the key is picked up.

**Architecture:** Reuse `COGITO_3_Lobby.tscn` and the existing AI Play Controller. Add a scenario-specific Godot monitor for world setup and terminal signaling, and make Godot/Python terminal validation and request limits depend on the scenario selected during the v3 hello handshake.

**Tech Stack:** Godot 4.7/GDScript, Python 3.12, MCP over stdio, internal WebSocket protocol v3, pytest, headless Godot tests, Bash static checks.

## Global Constraints

- `find_contract` remains the default scenario and retains its existing puzzle behavior.
- `find_key` has exactly one task card and one `Pickup_Key`.
- Key candidates are desktop desk, laptop desk, ARCHIVE-side sofa, meeting long table, and large-TV coffee table.
- Select the key first, then choose the farthest of Entrance, Lobby, and ARCHIVE-door spawns using world-space straight-line distance.
- The task card stays 1–2 meters from the selected spawn.
- Successful pickup emits `success/key_picked_up`; `find_key` has no wrong-answer failure.
- Hard request caps are 500 for `find_contract` and 200 for `find_key`; `AI_PLAY_MAX_ACT_REQUESTS` may only lower them.
- Keep protocol version 3 and the existing exact `game_over` packet shape.
- Do not expose candidate positions, selected location, node paths, random seed, or farthest-spawn calculation in MCP results.
- `game_script/` and `code_read/` remain developer-only and must never become runtime model input.

---

### Task 1: Add scenario metadata, briefing, terminal validation, and request caps in Python

**Files:**
- Create: `ai_play/src/ai_play/find_key_briefing.py`
- Modify: `ai_play/src/ai_play/scenarios.py`
- Modify: `ai_play/src/ai_play/game_session.py`
- Modify: `ai_play/tests/test_scenarios.py`
- Modify: `ai_play/tests/test_briefing.py`
- Modify: `ai_play/tests/test_game_session.py`

**Interfaces:**
- Produces: `scenario_act_request_limit(scenario_id: str, configured_limit: int) -> int`
- Produces: `is_allowed_game_over(scenario_id: str, outcome: str, reason: str) -> bool`
- Produces: `load_find_key_briefing() -> tuple[dict, bytes]`
- Consumes: the scenario ID accepted during the WebSocket hello handshake.

- [ ] **Step 1: Add failing scenario-registry tests**

Update `ai_play/tests/test_scenarios.py` to assert:

```python
from ai_play.scenarios import (
    DEFAULT_SCENARIO_ID,
    is_allowed_game_over,
    is_supported_scenario,
    load_scenario_briefing,
    scenario_act_request_limit,
    supported_scenario_ids,
)


def test_scenario_registry_exposes_only_allowlisted_scenarios():
    assert DEFAULT_SCENARIO_ID == "find_contract"
    assert supported_scenario_ids() == ("find_contract", "find_key")
    assert is_supported_scenario("find_contract")
    assert is_supported_scenario("find_key")
    assert not is_supported_scenario("unknown")
    assert not is_supported_scenario(True)


def test_scenario_request_limits_are_hard_caps():
    assert scenario_act_request_limit("find_contract", 500) == 500
    assert scenario_act_request_limit("find_contract", 120) == 120
    assert scenario_act_request_limit("find_key", 500) == 200
    assert scenario_act_request_limit("find_key", 80) == 80


def test_terminal_results_are_scenario_specific():
    assert is_allowed_game_over("find_contract", "success", "correct_password")
    assert is_allowed_game_over("find_contract", "failure", "wrong_password")
    assert not is_allowed_game_over("find_contract", "success", "key_picked_up")
    assert is_allowed_game_over("find_key", "success", "key_picked_up")
    assert not is_allowed_game_over("find_key", "success", "correct_password")
    assert not is_allowed_game_over("find_key", "failure", "wrong_password")
    assert is_allowed_game_over("find_contract", "failure", "max_requests")
    assert is_allowed_game_over("find_key", "failure", "max_requests")
```

Extend the briefing test:

```python
def test_find_key_registry_loads_bounded_public_briefing():
    briefing, image_bytes = load_scenario_briefing("find_key")

    assert briefing["game_id"] == "find_key"
    assert briefing["success_condition"] == "成功拾取办公室中唯一的目标钥匙。"
    assert "200" in briefing["failure_condition"]
    assert image_bytes.startswith(b"\xff\xd8\xff")
    serialized = repr(briefing)
    for forbidden in [
        "DesktopDeskAnchor",
        "LaptopDeskAnchor",
        "ArchiveSofaAnchor",
        "MeetingTableAnchor",
        "TvCoffeeTableAnchor",
        "round_seed",
    ]:
        assert forbidden not in serialized
```

- [ ] **Step 2: Add failing session tests for scenario-specific terminals and limits**

Add helpers/tests to `ai_play/tests/test_game_session.py`:

```python
def make_scenario_session(scenario_id, configured_limit=500):
    sent = []
    session = GameSession(
        Config(
            wait_timeout_seconds=0.2,
            stop_timeout_seconds=0.2,
            max_act_requests=configured_limit,
        )
    )
    session.attach(
        lambda packet: sent.append(packet) or True,
        scenario_id=scenario_id,
    )
    return session, sent


def test_find_key_uses_200_request_hard_cap():
    session, _ = make_scenario_session("find_key", configured_limit=500)
    assert session.act_request_limit == 200


def test_global_limit_can_tighten_find_key_cap():
    session, _ = make_scenario_session("find_key", configured_limit=75)
    assert session.act_request_limit == 75


def test_find_key_accepts_only_key_success_terminal():
    session, _ = make_scenario_session("find_key")
    session.receive_observation(observation(7))
    terminal = {
        "type": "game_over",
        "protocol_version": 3,
        "observation_id": 7,
        "outcome": "success",
        "reason": "key_picked_up",
    }
    session.receive_game_over(terminal)
    assert session.observe(timeout=0.1).game_over == terminal


def test_terminal_success_cannot_cross_scenarios():
    contract, _ = make_scenario_session("find_contract")
    contract.receive_observation(observation(7))
    with pytest.raises(SessionError, match="invalid_game_over"):
        contract.receive_game_over({
            "type": "game_over",
            "protocol_version": 3,
            "observation_id": 7,
            "outcome": "success",
            "reason": "key_picked_up",
        })

    find_key, _ = make_scenario_session("find_key")
    find_key.receive_observation(observation(7))
    with pytest.raises(SessionError, match="invalid_game_over"):
        find_key.receive_game_over({
            "type": "game_over",
            "protocol_version": 3,
            "observation_id": 7,
            "outcome": "success",
            "reason": "correct_password",
        })
```

- [ ] **Step 3: Run the focused Python tests and confirm RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_briefing.py \
  ai_play/tests/test_game_session.py -q
```

Expected: failures for missing `find_key`, scenario helpers, `act_request_limit`, and `key_picked_up`.

- [ ] **Step 4: Implement the scenario registry**

Replace the registry structure in `ai_play/src/ai_play/scenarios.py` with:

```python
"""Allowlisted AI Play scenario metadata and public briefing registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .briefing import load_public_briefing
from .find_key_briefing import load_find_key_briefing


DEFAULT_SCENARIO_ID = "find_contract"


@dataclass(frozen=True)
class ScenarioDefinition:
    briefing_loader: Callable
    max_act_requests: int
    terminal_results: frozenset[tuple[str, str]]


_SCENARIOS = {
    "find_contract": ScenarioDefinition(
        briefing_loader=load_public_briefing,
        max_act_requests=500,
        terminal_results=frozenset({
            ("success", "correct_password"),
            ("failure", "wrong_password"),
            ("failure", "max_requests"),
        }),
    ),
    "find_key": ScenarioDefinition(
        briefing_loader=load_find_key_briefing,
        max_act_requests=200,
        terminal_results=frozenset({
            ("success", "key_picked_up"),
            ("failure", "max_requests"),
        }),
    ),
}


def is_supported_scenario(scenario_id: object) -> bool:
    return type(scenario_id) is str and scenario_id in _SCENARIOS


def load_scenario_briefing(scenario_id: str):
    try:
        definition = _SCENARIOS[scenario_id]
    except (KeyError, TypeError) as error:
        raise RuntimeError("unsupported_scenario") from error
    return definition.briefing_loader()


def scenario_act_request_limit(
    scenario_id: str,
    configured_limit: int,
) -> int:
    try:
        scenario_limit = _SCENARIOS[scenario_id].max_act_requests
    except (KeyError, TypeError) as error:
        raise RuntimeError("unsupported_scenario") from error
    return min(scenario_limit, configured_limit)


def is_allowed_game_over(
    scenario_id: str,
    outcome: str,
    reason: str,
) -> bool:
    try:
        definition = _SCENARIOS[scenario_id]
    except (KeyError, TypeError):
        return False
    return (outcome, reason) in definition.terminal_results


def supported_scenario_ids() -> tuple[str, ...]:
    return tuple(_SCENARIOS)
```

- [ ] **Step 5: Add the public find-key briefing**

Create `ai_play/src/ai_play/find_key_briefing.py`:

```python
"""Approved public briefing for the find_key black-box play session."""

from copy import deepcopy
from pathlib import Path


MAX_REFERENCE_IMAGE_BYTES = 2 * 1024 * 1024
REFERENCE_IMAGE_PATH = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "find_contract"
    / "imgs"
    / "reference_atlas.jpg"
)

PUBLIC_BRIEFING = {
    "game_id": "find_key",
    "title": "寻找办公室钥匙",
    "background": (
        "这是一个第一人称办公室空间探索任务。玩家需要观察房间标识、家具和"
        "可交互物体，根据游戏内任务卡寻找目标。"
    ),
    "objective": (
        "先读取出生点附近唯一的任务卡，根据卡片中的环境描述主动探索办公室，"
        "找到并拾取场景中唯一的目标钥匙。"
    ),
    "success_condition": "成功拾取办公室中唯一的目标钥匙。",
    "failure_condition": "最多允许 200 次 act 请求；达到上限仍未拾取钥匙则失败。",
    "rules": [
        "只能依据当前画面、房间文字标识、任务卡内容和动作结果寻找钥匙。",
        "任务卡位于出生点附近并可重复读取。",
        "任务卡描述的是环境特征；需要主动探索并理解家具与房间的空间关系。",
        "看到疑似钥匙但没有交互提示时，靠近后使用 probe_interaction 调整对准。",
        "只有成功执行 Pickup 才算完成；仅看到钥匙不算成功。",
        "错误区域和其他拾取物不会直接导致失败，应调整搜索策略。",
    ],
    "reference_image": (
        "随简报返回的图片只用于识别常见交互物类别，不代表本局钥匙位置、"
        "出生点、任务卡内容或正确路线。"
    ),
    "objects": [
        {
            "id": "readable_document",
            "meaning": "纸张或任务卡可以包含本局目标描述。",
            "actions": {
                "probe_interaction": "对准任务卡寻找阅读提示。",
                "interact": "打开并阅读任务内容。",
                "close_ui": "记住目标描述后关闭阅读界面。",
            },
        },
        {
            "id": "pickup_key",
            "meaning": "金色钥匙是可拾取物；本局目标是成功拾取唯一钥匙。",
            "actions": {
                "probe_interaction": "靠近并对准钥匙确认拾取提示。",
                "interact": "出现拾取提示后拿起钥匙。",
            },
        },
        {
            "id": "operable_door",
            "meaning": "普通门可以尝试打开，以进入任务卡描述的办公区域。",
            "actions": {
                "probe_interaction": "对准门或把手寻找提示。",
                "interact": "按当前提示尝试打开或关闭门。",
            },
        },
    ],
}


def load_find_key_briefing():
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

- [ ] **Step 6: Make `GameSession` scenario-aware**

In `ai_play/src/ai_play/game_session.py` import:

```python
from .scenarios import (
    DEFAULT_SCENARIO_ID,
    is_allowed_game_over,
    scenario_act_request_limit,
)
```

Add:

```python
    @property
    def act_request_limit(self):
        with self._condition:
            if self._scenario_id is None:
                return self.config.max_act_requests
            return scenario_act_request_limit(
                self._scenario_id,
                self.config.max_act_requests,
            )

    def _act_request_limit_locked(self):
        if self._scenario_id is None:
            return self.config.max_act_requests
        return scenario_act_request_limit(
            self._scenario_id,
            self.config.max_act_requests,
        )
```

Replace all three comparisons to `self.config.max_act_requests` in `act()` and `_record_act_request_locked()` with `self._act_request_limit_locked()`.

Change:

```python
safe = _validate_game_over(packet)
```

to:

```python
safe = _validate_game_over(packet, self._scenario_id)
```

Change the validator to:

```python
def _validate_game_over(packet, scenario_id):
    fields = {"type", "protocol_version", "observation_id", "outcome", "reason"}
    if not isinstance(packet, dict) or set(packet) != fields:
        raise SessionError("invalid_game_over")
    if packet["type"] != "game_over" or packet["protocol_version"] != PROTOCOL_VERSION:
        raise SessionError("invalid_game_over")
    if not is_allowed_game_over(
        scenario_id,
        packet["outcome"],
        packet["reason"],
    ):
        raise SessionError("invalid_game_over")
    observation_id = _require_observation_id(
        packet["observation_id"],
        optional=packet["reason"] == "max_requests",
    )
    return {
        "type": "game_over",
        "protocol_version": PROTOCOL_VERSION,
        "observation_id": observation_id,
        "outcome": packet["outcome"],
        "reason": packet["reason"],
    }
```

- [ ] **Step 7: Run focused tests and confirm GREEN**

Run the Step 3 command. Expected: all selected Python tests pass.

- [ ] **Step 8: Commit Task 1**

```bash
git add \
  ai_play/src/ai_play/find_key_briefing.py \
  ai_play/src/ai_play/scenarios.py \
  ai_play/src/ai_play/game_session.py \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_briefing.py \
  ai_play/tests/test_game_session.py
git commit -m "feat: add find-key scenario metadata"
```

---

### Task 2: Make Godot terminal validation scenario-specific

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `addons/cogito/AIPlay/ai_play_find_contract_terminal.gd`
- Modify: `addons/cogito/AIPlay/ai_play_game_over_screen.gd`
- Modify: `tests/ai_play/test_ai_play_controller.gd`
- Modify: `tests/ai_play/test_ai_play_game_over_screen.gd`

**Interfaces:**
- Consumes: `scenario_id` selected from `--ai-play-scenario=...`.
- Produces: scenario-specific validation of `(outcome, reason)`.
- Produces: UI text for `success/key_picked_up`.

- [ ] **Step 1: Add failing Godot tests**

Extend the fake monitor in `test_ai_play_controller.gd` so fixtures can set:

```gdscript
var scenario_id: String = "find_contract"
```

Add a find-key fixture case that sets both:

```gdscript
fixture.controller._active_scenario_id = "find_key"
fixture.terminal_monitor.scenario_id = "find_key"
fixture.terminal_monitor.game_finished.emit("success", "key_picked_up")
```

Assert exactly one v3 `game_over` packet with `success/key_picked_up`, input cancellation, and one displayed result. Add cross-scenario rejection assertions:

```gdscript
contract_fixture.terminal_monitor.game_finished.emit("success", "key_picked_up")
_assert(
    "invalid_game_outcome" in contract_fixture.executor.cancel_reasons,
    "find_contract rejects find-key success",
)

find_key_fixture.terminal_monitor.game_finished.emit("success", "correct_password")
_assert(
    "invalid_game_outcome" in find_key_fixture.executor.cancel_reasons,
    "find_key rejects password success",
)
```

Add to `test_ai_play_game_over_screen.gd`:

```gdscript
await _test_result(
    screen_scene,
    "success",
    "key_picked_up",
    "任务成功",
    "已找到办公室钥匙",
)
```

- [ ] **Step 2: Run focused Godot tests and confirm RED**

Run:

```bash
godot --headless --log-file /tmp/cogito_find_key_controller_red.log \
  --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --log-file /tmp/cogito_find_key_screen_red.log \
  --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
```

Expected: `key_picked_up` is rejected and its UI text is absent.

- [ ] **Step 3: Add scenario-specific terminal pairs**

In `ai_play_controller.gd`, add:

```gdscript
const SCENARIO_TERMINAL_RESULTS := {
    "find_contract": [
        ["success", "correct_password"],
        ["failure", "wrong_password"],
        ["failure", "max_requests"],
    ],
    "find_key": [
        ["success", "key_picked_up"],
        ["failure", "max_requests"],
    ],
}
```

Replace `_finish_game()`’s fixed boolean with:

```gdscript
var valid_outcome: bool = (
    [outcome, reason]
    in SCENARIO_TERMINAL_RESULTS.get(_active_scenario_id, [])
)
```

- [ ] **Step 4: Prevent the contract monitor from initializing in find-key mode**

At the start of `AIPlayFindContractTerminal._ready()` add:

```gdscript
var controller := get_parent() as AIPlayController
if controller != null and not controller.is_requested_scenario(scenario_id):
    return
```

This check uses command-line scenario selection directly and is safe during child `_ready()` ordering.

- [ ] **Step 5: Add key-success UI text**

Replace the dictionaries in `ai_play_game_over_screen.gd` with:

```gdscript
const OUTCOME_TEXT := {
    "correct_password": "解谜成功",
    "wrong_password": "解谜失败",
    "max_requests": "解谜失败",
    "key_picked_up": "任务成功",
}
const REASON_TEXT := {
    "correct_password": "密码正确",
    "wrong_password": "密码错误",
    "max_requests": "达到最大步长",
    "key_picked_up": "已找到办公室钥匙",
}
```

Set:

```gdscript
outcome_label.text = OUTCOME_TEXT.get(reason, "游戏结束")
reason_label.text = REASON_TEXT.get(reason, "游戏已终止")
```

Keep color selection based on `outcome`.

- [ ] **Step 6: Run focused Godot tests and confirm GREEN**

Run the Step 2 commands. Expected: both scripts exit 0.

- [ ] **Step 7: Commit Task 2**

```bash
git add \
  addons/cogito/AIPlay/ai_play_controller.gd \
  addons/cogito/AIPlay/ai_play_find_contract_terminal.gd \
  addons/cogito/AIPlay/ai_play_game_over_screen.gd \
  tests/ai_play/test_ai_play_controller.gd \
  tests/ai_play/test_ai_play_game_over_screen.gd
git commit -m "feat: validate scenario-specific game outcomes"
```

---

### Task 3: Implement the FindKeyMonitor behavior

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_find_key_monitor.gd`
- Create: `tests/ai_play/test_ai_play_find_key_monitor.gd`

**Interfaces:**
- Produces: `signal game_finished(outcome: String, reason: String)`
- Produces: `configure_round(seed_value: int = 0) -> void`
- Produces: `get_round_snapshot() -> Dictionary`
- Consumes: one key, one task card, five key anchors, three spawns, and three task-card anchors.

- [ ] **Step 1: Write a failing monitor test**

Create `tests/ai_play/test_ai_play_find_key_monitor.gd` that loads the Lobby, obtains:

```gdscript
var monitor: Node = lobby.get_node("AIPlayController/FindKeyMonitor")
```

For seeds `1..128`, call `monitor.configure_round(seed_value)` and assert:

```gdscript
var snapshot: Dictionary = monitor.get_round_snapshot()
_assert(snapshot["location"] in monitor.LOCATION_IDS, "location is allowlisted")
_assert(
    snapshot["task_text"] == monitor.LOCATION_TASK_TEXT[snapshot["location"]],
    "task card matches the selected key location",
)
_assert(
    lobby.find_children("Pickup_Key", "", true, false).size() == 1,
    "the scene contains exactly one key",
)
for distance: float in snapshot["spawn_distances"]:
    _assert(
        snapshot["selected_spawn_distance"] + 0.001 >= distance,
        "the selected spawn is farthest from the key",
    )
var task_distance: float = monitor.player.global_position.distance_to(
    monitor.task_card.get_parent_node_3d().global_position
)
_assert(
    task_distance >= 1.0 and task_distance <= 2.0,
    "the task card remains one to two meters from spawn",
)
```

Collect selected locations and assert all five occur within the seed sample.

Connect to `game_finished`, emit the target key pickup signal twice, and assert:

```gdscript
_assert(
    terminal_results == [{
        "outcome": "success",
        "reason": "key_picked_up",
    }],
    "successful pickup ends the round exactly once",
)
```

- [ ] **Step 2: Run the monitor test and confirm RED**

Run:

```bash
godot --headless --log-file /tmp/cogito_find_key_monitor_red.log \
  --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd
```

Expected: failure because `FindKeyMonitor` and its script do not exist.

- [ ] **Step 3: Implement the monitor**

Create `addons/cogito/AIPlay/ai_play_find_key_monitor.gd` with:

```gdscript
class_name AIPlayFindKeyMonitor
extends Node

signal game_finished(outcome: String, reason: String)

const LOCATION_IDS: Array[String] = [
    "desktop_desk",
    "laptop_desk",
    "archive_sofa",
    "meeting_table",
    "tv_coffee_table",
]
const LOCATION_TASK_TEXT := {
    "desktop_desk": "钥匙在有台式电脑的办公桌上。",
    "laptop_desk": "钥匙在有笔记本电脑的办公桌上。",
    "archive_sofa": "钥匙在档案室旁边的沙发上。",
    "meeting_table": "钥匙在会议室的长桌上。",
    "tv_coffee_table": "钥匙在有大电视的茶几上。",
}

@export var scenario_id: String = "find_key"
@export var game_over_screen: AIPlayGameOverScreen
@export var player: Node3D
@export var task_card: ReadableComponent
@export var key: RigidBody3D
@export var desktop_desk_anchor: Marker3D
@export var laptop_desk_anchor: Marker3D
@export var archive_sofa_anchor: Marker3D
@export var meeting_table_anchor: Marker3D
@export var tv_coffee_table_anchor: Marker3D
@export var entrance_spawn: Marker3D
@export var entrance_task_card_anchor: Marker3D
@export var lobby_spawn: Marker3D
@export var lobby_task_card_anchor: Marker3D
@export var archive_spawn: Marker3D
@export var archive_task_card_anchor: Marker3D
@export var round_seed: int = 0

var _round_finished: bool = false
var _pickup_connected: bool = false
var _selected_location: String = ""
var _selected_spawn: String = ""
var _spawn_distances: Array[float] = []


func _ready() -> void:
    var controller := get_parent() as AIPlayController
    if controller != null and not controller.is_requested_scenario(scenario_id):
        return
    configure_round(round_seed)


func configure_round(seed_value: int = 0) -> void:
    if not _has_required_nodes():
        return
    var rng := RandomNumberGenerator.new()
    if seed_value == 0:
        rng.randomize()
    else:
        rng.seed = seed_value
    _round_finished = false
    var location_index: int = rng.randi_range(0, LOCATION_IDS.size() - 1)
    _selected_location = LOCATION_IDS[location_index]
    var key_anchors := _key_anchors()
    _place_key(key_anchors[_selected_location])
    var selected_spawn: Dictionary = _select_farthest_spawn(rng)
    _selected_spawn = selected_spawn["id"]
    player.global_transform = selected_spawn["spawn"].global_transform
    _reparent_to_anchor(
        task_card.get_parent_node_3d(),
        selected_spawn["card"],
    )
    _write_task_card()
    _connect_pickup()


func _key_anchors() -> Dictionary:
    return {
        "desktop_desk": desktop_desk_anchor,
        "laptop_desk": laptop_desk_anchor,
        "archive_sofa": archive_sofa_anchor,
        "meeting_table": meeting_table_anchor,
        "tv_coffee_table": tv_coffee_table_anchor,
    }


func _spawn_options() -> Array[Dictionary]:
    return [
        {"id": "ENTRANCE", "spawn": entrance_spawn, "card": entrance_task_card_anchor},
        {"id": "LOBBY", "spawn": lobby_spawn, "card": lobby_task_card_anchor},
        {"id": "ARCHIVE ENTRANCE", "spawn": archive_spawn, "card": archive_task_card_anchor},
    ]


func _place_key(anchor: Marker3D) -> void:
    key.freeze = true
    key.linear_velocity = Vector3.ZERO
    key.angular_velocity = Vector3.ZERO
    _reparent_to_anchor(key, anchor)


func _select_farthest_spawn(rng: RandomNumberGenerator) -> Dictionary:
    var options: Array[Dictionary] = _spawn_options()
    var farthest: Array[Dictionary] = []
    var max_distance: float = -1.0
    _spawn_distances.clear()
    for option: Dictionary in options:
        var distance: float = option["spawn"].global_position.distance_to(
            key.global_position
        )
        _spawn_distances.append(distance)
        if distance > max_distance and not is_equal_approx(distance, max_distance):
            max_distance = distance
            farthest = [option]
        elif is_equal_approx(distance, max_distance):
            farthest.append(option)
    return farthest[rng.randi_range(0, farthest.size() - 1)]


func _write_task_card() -> void:
    var content := (
        "办公室里只有一把钥匙。\n\n"
        + LOCATION_TASK_TEXT[_selected_location]
        + "\n\n找到并拾取它。"
    )
    task_card.readable_title = "寻找办公室钥匙"
    task_card.readable_content = content
    task_card.interaction_text = "Read task card"
    task_card.is_disabled = false
    var card_object := task_card.get_parent() as CollisionObject3D
    if card_object != null:
        card_object.collision_layer = 2
    if task_card.is_node_ready():
        task_card.label_title.text = task_card.readable_title
        task_card.label_content.text = content


func _connect_pickup() -> void:
    var pickup: PickupComponent = key.get_node("PickupComponent")
    if _pickup_connected:
        return
    pickup.was_interacted_with.connect(_on_key_picked_up)
    _pickup_connected = true


func _on_key_picked_up(
    _interaction_text: String,
    _input_map_action: String,
) -> void:
    if _round_finished:
        return
    _round_finished = true
    game_finished.emit("success", "key_picked_up")


func _reparent_to_anchor(object: Node3D, anchor: Node3D) -> void:
    object.reparent(anchor, false)
    object.transform = Transform3D.IDENTITY


func get_round_snapshot() -> Dictionary:
    var selected_distance: float = 0.0
    var options: Array[Dictionary] = _spawn_options()
    for index: int in options.size():
        if options[index]["id"] == _selected_spawn:
            selected_distance = _spawn_distances[index]
            break
    return {
        "location": _selected_location,
        "spawn": _selected_spawn,
        "spawn_distances": _spawn_distances.duplicate(),
        "selected_spawn_distance": selected_distance,
        "task_text": LOCATION_TASK_TEXT.get(_selected_location, ""),
    }


func _has_required_nodes() -> bool:
    var required: Array[Node] = [
        game_over_screen,
        player,
        task_card,
        key,
        desktop_desk_anchor,
        laptop_desk_anchor,
        archive_sofa_anchor,
        meeting_table_anchor,
        tv_coffee_table_anchor,
        entrance_spawn,
        entrance_task_card_anchor,
        lobby_spawn,
        lobby_task_card_anchor,
        archive_spawn,
        archive_task_card_anchor,
    ]
    for node: Node in required:
        if node == null:
            push_error("AIPlayFindKeyMonitor is missing a required scene node")
            return false
    return true


func show_result(outcome: String, reason: String) -> void:
    game_over_screen.show_result(outcome, reason)
```

- [ ] **Step 4: Run a parse check**

Run:

```bash
godot --headless --path . --editor --quit
```

Expected: exit 0 with no parse error for `AIPlayFindKeyMonitor`.

- [ ] **Step 5: Commit the script and test scaffold**

```bash
git add \
  addons/cogito/AIPlay/ai_play_find_key_monitor.gd \
  tests/ai_play/test_ai_play_find_key_monitor.gd
git commit -m "feat: add find-key round monitor"
```

---

### Task 4: Wire the Lobby scene and five physical key anchors

**Files:**
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`
- Modify: `tests/check_ai_play_lobby.sh`
- Modify: `tests/ai_play/test_ai_play_find_key_monitor.gd`

**Interfaces:**
- Consumes: existing `Pickup_Key`, task card, `AIPlayRoundMarkers`, and shared game-over screen.
- Produces: `AIPlayController/FindKeyMonitor` with `scenario_id = "find_key"`.
- Produces: five root-level Marker3D key anchors.

- [ ] **Step 1: Add failing static scene assertions**

Extend `tests/check_ai_play_lobby.sh`:

```bash
grep -q 'path="res://addons/cogito/AIPlay/ai_play_find_key_monitor.gd"' "$scene"
grep -q 'name="FindKeyMonitor" type="Node" parent="AIPlayController"' "$scene"
grep -q '^scenario_id = "find_key"$' "$scene"
test "$(grep -c 'name="Pickup_Key"' "$scene")" -eq 1
for marker in \
  DesktopDeskAnchor \
  LaptopDeskAnchor \
  ArchiveSofaAnchor \
  MeetingTableAnchor \
  TvCoffeeTableAnchor
do
  grep -q "name=\"$marker\" type=\"Marker3D\" parent=\"FindKeyMarkers\"" "$scene"
done
```

- [ ] **Step 2: Run static check and confirm RED**

Run:

```bash
bash tests/check_ai_play_lobby.sh
```

Expected: exit 1 because the monitor and markers are absent.

- [ ] **Step 3: Add the scene resource and monitor node**

Add an ext_resource for `ai_play_find_key_monitor.gd`, then add:

```text
[node name="FindKeyMonitor" type="Node" parent="AIPlayController" node_paths=PackedStringArray("game_over_screen", "player", "task_card", "key", "desktop_desk_anchor", "laptop_desk_anchor", "archive_sofa_anchor", "meeting_table_anchor", "tv_coffee_table_anchor", "entrance_spawn", "entrance_task_card_anchor", "lobby_spawn", "lobby_task_card_anchor", "archive_spawn", "archive_task_card_anchor")]
script = ExtResource("ai_play_find_key_monitor")
scenario_id = "find_key"
game_over_screen = NodePath("../TerminalMonitor/GameOverScreen")
player = NodePath("../../Player")
task_card = NodePath("../../DEMO_HINTS/Hint_01_Welcome/ReadableComponent")
key = NodePath("../../UPPER_OFFICE_CEO/Pickup_Key")
desktop_desk_anchor = NodePath("../../FindKeyMarkers/DesktopDeskAnchor")
laptop_desk_anchor = NodePath("../../FindKeyMarkers/LaptopDeskAnchor")
archive_sofa_anchor = NodePath("../../FindKeyMarkers/ArchiveSofaAnchor")
meeting_table_anchor = NodePath("../../FindKeyMarkers/MeetingTableAnchor")
tv_coffee_table_anchor = NodePath("../../FindKeyMarkers/TvCoffeeTableAnchor")
entrance_spawn = NodePath("../../AIPlayRoundMarkers/EntranceSpawn")
entrance_task_card_anchor = NodePath("../../AIPlayRoundMarkers/EntranceTaskCard")
lobby_spawn = NodePath("../../AIPlayRoundMarkers/LobbySpawn")
lobby_task_card_anchor = NodePath("../../AIPlayRoundMarkers/LobbyTaskCard")
archive_spawn = NodePath("../../AIPlayRoundMarkers/ArchiveSpawn")
archive_task_card_anchor = NodePath("../../AIPlayRoundMarkers/ArchiveTaskCard")
```

- [ ] **Step 4: Add the five root-level markers**

Add:

```text
[node name="FindKeyMarkers" type="Node3D" parent="."]

[node name="DesktopDeskAnchor" type="Marker3D" parent="FindKeyMarkers"]
transform = Transform3D(0, 1, 0, -1, 0, 0, 0, 0, 1, 7.45, 1.5, -0.55)

[node name="LaptopDeskAnchor" type="Marker3D" parent="FindKeyMarkers"]
transform = Transform3D(0.258819, 0, -0.965926, 0, 1, 0, 0.965926, 0, 0.258819, -6.0986724, 3.49246, -10.639568)

[node name="ArchiveSofaAnchor" type="Marker3D" parent="FindKeyMarkers"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 6.394, 0.55, 8.164)

[node name="MeetingTableAnchor" type="Marker3D" parent="FindKeyMarkers"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 3.9914124, 0.85, 14.54716)

[node name="TvCoffeeTableAnchor" type="Marker3D" parent="FindKeyMarkers"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, -6.93267, 3.15, -6.2181)
```

These transforms are explicit initial placements. During manual verification, adjust only a marker transform if the key intersects or floats above its named surface; do not change scenario logic or descriptions.

- [ ] **Step 5: Run monitor and static tests and confirm GREEN**

Run:

```bash
bash tests/check_ai_play_lobby.sh
godot --headless --log-file /tmp/cogito_find_key_monitor_green.log \
  --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd
```

Expected: both exit 0; the monitor test reports all five locations and farthest-spawn assertions passing.

- [ ] **Step 6: Manually inspect ordinary find-key mode**

Run:

```bash
godot --path . --log-file /tmp/cogito_find_key_manual.log \
  addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=find_key
```

Verify:

- the task card is 1–2 meters from the player;
- the displayed description matches the visible target surface;
- the key is visible, stable, reachable, and offers Pickup;
- there is no second key;
- pickup shows `任务成功 / 已找到办公室钥匙`;
- AI Play remains disabled without `--ai-play`.

- [ ] **Step 7: Commit Task 4**

```bash
git add \
  addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  tests/check_ai_play_lobby.sh \
  tests/ai_play/test_ai_play_find_key_monitor.gd
git commit -m "feat: add randomized key-search round"
```

---

### Task 5: Synchronize runtime documentation and run full affected verification

**Files:**
- Modify: `ai_play/README.md`
- Modify: `README_AI_PLAY.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `ai_play/tests/test_mcp_server.py`
- Modify: `ai_play/tests/test_bridge_server.py`

**Interfaces:**
- Documents: scenario launch arguments, scenario-specific terminal reasons, and hard request caps.
- Verifies: MCP returns `find_key` briefing and `key_picked_up` terminal state without exposing hidden placement data.

- [ ] **Step 1: Add MCP/bridge assertions**

Add a fake `find_key` session case to `test_mcp_server.py` whose `wait_for_scenario()` returns `"find_key"` and whose terminal result is:

```python
{
    "type": "game_over",
    "protocol_version": 3,
    "observation_id": 7,
    "outcome": "success",
    "reason": "key_picked_up",
}
```

Assert `briefing` returns `game_id == "find_key"` and terminal `observe` preserves `key_picked_up`.

Extend `test_bridge_server.py` to send the same packet after a `find_key` hello and assert the session reaches `game_over`.

- [ ] **Step 2: Run focused MCP tests**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_mcp_server.py \
  ai_play/tests/test_bridge_server.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Update public runtime documentation**

Document these exact rules in all three runtime guides:

```text
find_contract: default scenario, success/correct_password, wrong-password failure, 500-act hard cap.
find_key: select with --ai-play-scenario=find_key, success/key_picked_up, no wrong-answer failure, 200-act hard cap.
AI_PLAY_MAX_ACT_REQUESTS can only tighten the selected scenario hard cap.
The Nth act is processed normally; a legitimate terminal result takes priority over max_requests.
```

Document ordinary and AI launch commands:

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=find_key

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=find_key
```

Do not copy candidate positions or initialization internals into the public briefing.

- [ ] **Step 4: Run the full affected Python suite**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
```

Expected: all tests pass with no real credentials or external model calls.

- [ ] **Step 5: Run the full affected Godot and static suite**

Run:

```bash
godot --headless --log-file /tmp/cogito_find_key_controller.log \
  --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --log-file /tmp/cogito_find_key_screen.log \
  --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
godot --headless --log-file /tmp/cogito_find_key_monitor.log \
  --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd
godot --headless --log-file /tmp/cogito_find_contract_regression.log \
  --path . --script tests/ai_play/test_ai_play_lobby_game_over.gd
godot --headless --path . --editor --quit
bash tests/check_ai_play_lobby.sh
bash tests/check_ai_play_start_script.sh
bash tests/test_ai_play_secret_scan.sh
git diff --check
```

Expected: every command exits 0. Known restricted `user://` warnings in headless mode do not count as failures when the integration test exits 0 and prints its pass message.

- [ ] **Step 6: Commit Task 5**

```bash
git add \
  ai_play/README.md \
  README_AI_PLAY.md \
  docs/wiki/ai-play/system-guide.md \
  ai_play/tests/test_mcp_server.py \
  ai_play/tests/test_bridge_server.py
git commit -m "docs: document find-key AI Play mode"
```

