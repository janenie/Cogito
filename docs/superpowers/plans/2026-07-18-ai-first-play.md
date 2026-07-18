# AI First Play Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first autonomous player that observes the running Lobby through the player camera and a strict state whitelist, asks an OpenAI-compatible vision model for short actions, remembers runtime discoveries, and executes those actions through COGITO's normal inputs.

**Architecture:** A Python sidecar under `ai_play/` owns API calls, prompts, validation, memory, and the decision loop. A reusable Godot component under `addons/cogito/AIPlay/` owns camera/state observation and bounded input execution; the two communicate over a loopback-only WebSocket. The model never receives repository files, scene internals, hidden objectives, or developer-authored solutions.

**Tech Stack:** Godot 4.7/GDScript, Python 3.11+, `openai` Python SDK, `websockets` synchronous server, `pytest`.

## Global Constraints

- Work only on branch `ai_first_play`.
- Never commit or log a real API key; read it only from `AI_PLAY_API_KEY`.
- Default compatible endpoint: `https://api-cn.freeailab.cn/v1`.
- Default model: `gemini-3.5-flash`.
- Bind the sidecar only to `127.0.0.1` in the first version.
- The model receives only the player-camera image, approved embodied state, current visible F/E prompts, bindings, action results, and runtime-created memory.
- The model receives no `.gd`, `.tscn`, resource, repository, scene-tree, hidden objective, test fixture, `game_script/`, or `code_read/` content.
- A batch contains at most three actions; movement is at most 1000 ms and waiting is at most 2000 ms.
- Any error, disconnect, manual takeover, or emergency stop releases all simulated inputs.
- F and E are contextual interaction slots. Their visible HUD prompt defines their meaning.
- Start acceptance runs with empty memory.

---

## File Map

### Python sidecar

- `ai_play/requirements.txt`: bounded runtime/test dependencies.
- `ai_play/.env.example`: safe variable names with no secret.
- `ai_play/README.md`: install, configuration, launch, controls, and privacy boundary.
- `ai_play/src/ai_play/__init__.py`: package marker.
- `ai_play/src/ai_play/config.py`: environment parsing and loopback validation.
- `ai_play/src/ai_play/action_schema.py`: strict model-response/action validation.
- `ai_play/src/ai_play/memory.py`: bounded runtime memory and persistence.
- `ai_play/src/ai_play/prompts.py`: generic control guide and multimodal message construction.
- `ai_play/src/ai_play/api_client.py`: OpenAI-compatible Chat Completions adapter.
- `ai_play/src/ai_play/agent_loop.py`: serialized observation-to-action decision flow.
- `ai_play/src/ai_play/bridge_server.py`: loopback WebSocket message handling.
- `ai_play/src/ai_play/main.py`: executable entry point.
- `ai_play/tests/`: focused pytest coverage for each Python unit.

### Godot runtime

- `addons/cogito/AIPlay/ai_play_executor.gd`: validate again and inject bounded normal inputs.
- `addons/cogito/AIPlay/ai_play_observer.gd`: camera image, body state, bindings, and current raycast prompts.
- `addons/cogito/AIPlay/ai_play_bridge.gd`: WebSocket client and protocol framing.
- `addons/cogito/AIPlay/ai_play_controller.gd`: orchestration, AI state, manual takeover, and emergency stop.
- `addons/cogito/AIPlay/ai_play_controller.tscn`: reusable component with child nodes/timers.
- `tests/ai_play/test_ai_play.gd`: headless Godot contract tests.
- `tests/check_ai_play_lobby.sh`: static scene/privacy wiring check.
- `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`: one controller instance referencing `Player`.
- `.gitignore`: ignore local secrets, memory, logs, and Python caches.

---

### Task 1: Sidecar configuration and safe project scaffold

**Files:**
- Modify: `.gitignore`
- Create: `ai_play/requirements.txt`
- Create: `ai_play/.env.example`
- Create: `ai_play/src/ai_play/__init__.py`
- Create: `ai_play/src/ai_play/config.py`
- Create: `ai_play/tests/test_config.py`

**Interfaces:**
- Consumes: environment variables listed in Global Constraints.
- Produces: `Config.from_env() -> Config` and `Config.validate() -> None`.

- [ ] **Step 1: Write failing configuration tests**

```python
# ai_play/tests/test_config.py
import pytest

from ai_play.config import Config


def test_config_requires_api_key(monkeypatch):
    monkeypatch.delenv("AI_PLAY_API_KEY", raising=False)
    with pytest.raises(ValueError, match="AI_PLAY_API_KEY"):
        Config.from_env()


def test_config_uses_safe_defaults(monkeypatch):
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    config = Config.from_env()
    assert config.base_url == "https://api-cn.freeailab.cn/v1"
    assert config.model == "gemini-3.5-flash"
    assert config.ws_host == "127.0.0.1"
    assert config.ws_port == 8765
    assert config.request_timeout_seconds == 45.0


def test_config_rejects_non_loopback_host(monkeypatch):
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    monkeypatch.setenv("AI_PLAY_WS_HOST", "0.0.0.0")
    with pytest.raises(ValueError, match="loopback"):
        Config.from_env()
```

- [ ] **Step 2: Add package/dependency scaffold and verify the test fails**

```text
# ai_play/requirements.txt
openai>=1.0,<3.0
websockets>=14.0,<16.0
pytest>=8.0,<9.0
```

```bash
python3 -m venv /tmp/cogito-ai-play-venv
/tmp/cogito-ai-play-venv/bin/pip install -r ai_play/requirements.txt
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/pytest ai_play/tests/test_config.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'ai_play.config'`.

- [ ] **Step 3: Implement configuration parsing**

```python
# ai_play/src/ai_play/config.py
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str = "https://api-cn.freeailab.cn/v1"
    model: str = "gemini-3.5-flash"
    ws_host: str = "127.0.0.1"
    ws_port: int = 8765
    request_timeout_seconds: float = 45.0
    data_dir: Path | None = None

    @classmethod
    def from_env(cls) -> "Config":
        key = os.environ.get("AI_PLAY_API_KEY", "").strip()
        if not key:
            raise ValueError("AI_PLAY_API_KEY is required")
        config = cls(
            api_key=key,
            base_url=os.environ.get("AI_PLAY_BASE_URL", cls.base_url).rstrip("/"),
            model=os.environ.get("AI_PLAY_MODEL", cls.model),
            ws_host=os.environ.get("AI_PLAY_WS_HOST", cls.ws_host),
            ws_port=int(os.environ.get("AI_PLAY_WS_PORT", str(cls.ws_port))),
            request_timeout_seconds=float(os.environ.get(
                "AI_PLAY_REQUEST_TIMEOUT_SECONDS", str(cls.request_timeout_seconds)
            )),
            data_dir=Path(os.environ["AI_PLAY_DATA_DIR"]).expanduser()
            if os.environ.get("AI_PLAY_DATA_DIR") else None,
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.ws_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("AI Play WebSocket host must be loopback")
        if not 1 <= self.ws_port <= 65535:
            raise ValueError("AI_PLAY_WS_PORT must be between 1 and 65535")
        if not 1.0 <= self.request_timeout_seconds <= 120.0:
            raise ValueError("AI_PLAY_REQUEST_TIMEOUT_SECONDS must be 1..120")
```

Create an empty `ai_play/src/ai_play/__init__.py`. Add this safe example:

```dotenv
# ai_play/.env.example
AI_PLAY_API_KEY=
AI_PLAY_BASE_URL=https://api-cn.freeailab.cn/v1
AI_PLAY_MODEL=gemini-3.5-flash
AI_PLAY_WS_HOST=127.0.0.1
AI_PLAY_WS_PORT=8765
AI_PLAY_REQUEST_TIMEOUT_SECONDS=45
```

Append these ignore rules:

```gitignore
# AI Play local secrets and runtime data
ai_play/.env
ai_play/runtime/
ai_play/**/*.log
ai_play/**/__pycache__/
ai_play/.pytest_cache/
```

- [ ] **Step 4: Run configuration tests**

Run: `PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/pytest ai_play/tests/test_config.py -q`

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add .gitignore ai_play
git commit -m "feat: scaffold safe AI play sidecar"
```

---

### Task 2: Strict action schema

**Files:**
- Create: `ai_play/src/ai_play/action_schema.py`
- Create: `ai_play/tests/test_action_schema.py`

**Interfaces:**
- Consumes: decoded model JSON dictionary.
- Produces: `validate_decision(payload: object, available_interactions: set[str], interface_open: bool) -> dict`.

- [ ] **Step 1: Write failing action validation tests**

```python
# ai_play/tests/test_action_schema.py
import math
import pytest

from ai_play.action_schema import ActionValidationError, validate_decision


def valid(payload, interactions={"interact"}, interface_open=False):
    return validate_decision(payload, interactions, interface_open)


def test_accepts_bounded_actions():
    result = valid({"reason": "explore", "memory_updates": [], "actions": [
        {"type": "look", "yaw": 10, "pitch": -2},
        {"type": "move", "forward": 1, "right": 0, "duration_ms": 600},
        {"type": "interact", "action": "interact"},
    ]})
    assert len(result["actions"]) == 3


@pytest.mark.parametrize("action", [
    {"type": "press_key", "key": "F"},
    {"type": "move", "forward": 1, "right": 0, "duration_ms": 1001},
    {"type": "look", "yaw": math.inf, "pitch": 0},
    {"type": "enter_digits", "digits": "12A"},
])
def test_rejects_unsafe_actions(action):
    with pytest.raises(ActionValidationError):
        valid({"reason": "x", "memory_updates": [], "actions": [action]})


def test_rejects_interaction_not_currently_visible():
    with pytest.raises(ActionValidationError, match="available"):
        valid({"reason": "x", "memory_updates": [], "actions": [
            {"type": "interact", "action": "interact2"}
        ]})


def test_digits_require_open_interface():
    with pytest.raises(ActionValidationError, match="interface"):
        valid({"reason": "x", "memory_updates": [], "actions": [
            {"type": "enter_digits", "digits": "123"}
        ]})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/pytest ai_play/tests/test_action_schema.py -q`

Expected: import failure for `ai_play.action_schema`.

- [ ] **Step 3: Implement exact-key and range validation**

Implement `ActionValidationError(ValueError)` and `validate_decision`. Use these hard limits and exact action shapes:

```python
ALLOWED_KEYS = {
    "look": {"type", "yaw", "pitch"},
    "move": {"type", "forward", "right", "duration_ms"},
    "sprint": {"type", "forward", "right", "duration_ms"},
    "jump": {"type"},
    "crouch": {"type"},
    "interact": {"type", "action"},
    "enter_digits": {"type", "digits"},
    "close_ui": {"type"},
    "wait": {"type", "duration_ms"},
    "stop": {"type"},
}
```

Validation behavior:

```python
def validate_decision(payload, available_interactions, interface_open):
    if not isinstance(payload, dict) or set(payload) != {"reason", "memory_updates", "actions"}:
        raise ActionValidationError("decision has invalid fields")
    if not isinstance(payload["reason"], str) or len(payload["reason"]) > 500:
        raise ActionValidationError("reason must be a short string")
    if not isinstance(payload["memory_updates"], list):
        raise ActionValidationError("memory_updates must be a list")
    actions = payload["actions"]
    if not isinstance(actions, list) or not 1 <= len(actions) <= 3:
        raise ActionValidationError("actions must contain 1..3 entries")
    for action in actions:
        _validate_action(action, set(available_interactions), interface_open)
    return payload
```

`_validate_action` must reject unknown fields; require finite yaw/pitch in
`[-45, 45]`/`[-30, 30]`; require finite movement axes in `[-1, 1]`; require
movement duration `50..1000`; require wait duration `50..2000`; require
`interact.action` to be `interact` or `interact2` and present in
`available_interactions`; require one to six decimal digits and an open
interface; require `close_ui` only while an interface is open.

- [ ] **Step 4: Run schema tests**

Run: `PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/pytest ai_play/tests/test_action_schema.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add ai_play/src/ai_play/action_schema.py ai_play/tests/test_action_schema.py
git commit -m "feat: validate bounded AI player actions"
```

---

### Task 3: Runtime memory without seeded knowledge

**Files:**
- Create: `ai_play/src/ai_play/memory.py`
- Create: `ai_play/tests/test_memory.py`

**Interfaces:**
- Produces: `MemoryStore.empty()`, `apply_updates(updates, observation_id)`, `record_step(summary)`, `to_prompt_dict()`, `save(path)`, and `load(path)`.

- [ ] **Step 1: Write failing memory tests**

```python
# ai_play/tests/test_memory.py
from ai_play.memory import MemoryStore


def test_memory_starts_empty():
    assert MemoryStore.empty().to_prompt_dict() == {
        "working_memory": [], "facts": [], "spatial_memory": [],
        "task_state": {"goal": "", "questions": [], "hypotheses": [], "failures": []},
    }


def test_fact_requires_runtime_source():
    store = MemoryStore.empty()
    store.apply_updates([{"kind": "fact", "text": "A visible clue", "source": "observation:4", "confidence": 0.8}], 4)
    assert store.facts[0]["text"] == "A visible clue"
    store.apply_updates([{"kind": "fact", "text": "Hidden answer", "source": "developer file", "confidence": 1}], 5)
    assert len(store.facts) == 1


def test_working_memory_is_bounded():
    store = MemoryStore.empty()
    for index in range(12):
        store.record_step({"observation_id": index, "result": "moved"})
    assert len(store.working_memory) == 8
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/pytest ai_play/tests/test_memory.py -q`

Expected: import failure for `ai_play.memory`.

- [ ] **Step 3: Implement bounded memory**

Use a `@dataclass` with list/dict defaults. Accept only update kinds `fact`,
`landmark`, `goal`, `question`, `hypothesis`, and `failure`. A fact/landmark source
must equal `observation:<current observation id>`. Cap text at 300 characters,
facts at 64, landmarks at 48, each task-state list at 24, and working memory at
8. Deduplicate entries by normalized `(kind, text)` and keep the higher
confidence. Persist JSON using a temporary sibling file followed by
`Path.replace()`; `load()` returns empty memory if the file is absent but raises
`ValueError` for malformed data.

Core source check:

```python
expected_source = f"observation:{observation_id}"
if kind in {"fact", "landmark"} and update.get("source") != expected_source:
    continue
```

- [ ] **Step 4: Run memory tests**

Run: `PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/pytest ai_play/tests/test_memory.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add ai_play/src/ai_play/memory.py ai_play/tests/test_memory.py
git commit -m "feat: add bounded runtime AI memory"
```

---

### Task 4: Generic natural-language prompt and vision request

**Files:**
- Create: `ai_play/src/ai_play/prompts.py`
- Create: `ai_play/src/ai_play/api_client.py`
- Create: `ai_play/tests/test_prompts.py`
- Create: `ai_play/tests/test_api_client.py`

**Interfaces:**
- Consumes: observation dictionary, runtime bindings, `MemoryStore.to_prompt_dict()`.
- Produces: `build_messages(observation, memory) -> list[dict]`; `ApiClient.decide(messages) -> dict`.

- [ ] **Step 1: Write prompt privacy and control-map tests**

```python
# ai_play/tests/test_prompts.py
import json
from ai_play.prompts import SYSTEM_PROMPT, build_messages


FORBIDDEN = ["game_script/", "code_read/", ".gd", ".tscn", "passcode", "walkthrough"]


def observation():
    return {
        "observation_id": 7,
        "image": {"mime_type": "image/jpeg", "base64": "aW1hZ2U="},
        "player": {"position": [0, 0, 0], "yaw_degrees": 0, "pitch_degrees": 0,
                   "planar_velocity": [0, 0], "on_floor": True,
                   "health_ratio": 1, "stamina_ratio": 1},
        "interface": {"is_open": False, "visible_object_text": "",
                      "available_interactions": [
                          {"action": "interact", "binding": "F", "prompt": "Read"},
                          {"action": "interact2", "binding": "E", "prompt": "Move"},
                      ]},
        "bindings": {"forward": "W", "back": "S", "left": "A", "right": "D",
                     "jump": "Space", "sprint": "Shift", "crouch": "C",
                     "interact": "F", "interact2": "E", "menu": "Escape"},
        "last_action_results": [],
    }


def test_prompt_maps_f_and_e_to_visible_meaning():
    rendered = json.dumps(build_messages(observation(), {}), ensure_ascii=False)
    assert "F" in rendered and "interact" in rendered and "Read" in rendered
    assert "E" in rendered and "interact2" in rendered and "Move" in rendered


def test_default_prompt_has_no_repository_or_solution_content():
    lower = SYSTEM_PROMPT.lower()
    for forbidden in FORBIDDEN:
        assert forbidden.lower() not in lower
```

Use a fake OpenAI client in `test_api_client.py` whose
`chat.completions.create()` records arguments and returns a message containing
`{"reason":"observe","memory_updates":[],"actions":[{"type":"wait","duration_ms":100}]}`.
Assert that `model`, `messages`, and `timeout` are forwarded and JSON is decoded.

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/pytest ai_play/tests/test_prompts.py ai_play/tests/test_api_client.py -q`

Expected: import failures for `prompts` and `api_client`.

- [ ] **Step 3: Implement the generic system prompt**

`SYSTEM_PROMPT` must describe an unknown first-person environment, short
observe/act loops, visible-evidence discipline, memory update sources, F/E as
contextual slots, and the exact JSON contract. Include the natural-language
meanings of movement, look, jump, sprint, crouch, interaction, digit entry,
close, wait, and stop. Do not include room, character, object, puzzle, number,
or destination examples.

`build_messages` must strip `image.base64` from the textual state, then build one
user message containing a text part and an image URL part:

```python
return [{"role": "system", "content": SYSTEM_PROMPT}, {
    "role": "user",
    "content": [
        {"type": "text", "text": json.dumps({"observation": safe_observation, "memory": memory}, ensure_ascii=False)},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
    ],
}]
```

- [ ] **Step 4: Implement the compatible API adapter**

```python
class ApiClient:
    def __init__(self, config, client=None):
        self.config = config
        self.client = client or OpenAI(base_url=config.base_url, api_key=config.api_key)

    def decide(self, messages):
        completion = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            timeout=self.config.request_timeout_seconds,
        )
        content = completion.choices[0].message.content
        if not isinstance(content, str):
            raise ValueError("model response content must be text JSON")
        return json.loads(_strip_json_fence(content))
```

`_strip_json_fence` may remove one surrounding ```json fence but must not search
arbitrary prose for a JSON substring. Never log `messages`, the API key, or image
data in this module.

- [ ] **Step 5: Run prompt/API tests**

Run: `PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/pytest ai_play/tests/test_prompts.py ai_play/tests/test_api_client.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add ai_play/src/ai_play/prompts.py ai_play/src/ai_play/api_client.py ai_play/tests
git commit -m "feat: add private vision decision prompt"
```

---

### Task 5: Agent loop and loopback WebSocket server

**Files:**
- Create: `ai_play/src/ai_play/agent_loop.py`
- Create: `ai_play/src/ai_play/bridge_server.py`
- Create: `ai_play/src/ai_play/main.py`
- Create: `ai_play/tests/test_agent_loop.py`
- Create: `ai_play/tests/test_bridge_server.py`

**Interfaces:**
- Produces: `AgentLoop.handle_observation(observation) -> action_batch` and `serve(config, agent_loop) -> None`.
- Protocol: `hello`, `observation`, `action_batch`, `error`, `stop` JSON objects with `protocol_version: 1`.

- [ ] **Step 1: Write failing agent-loop tests**

Test with fake API and in-memory memory that:

1. `available_interactions` is passed to `validate_decision`.
2. The returned batch copies `observation_id`.
3. Valid memory proposals are applied only after validation.
4. Invalid model output returns a safe `error` and no actions.
5. A second observation is rejected while one is already being decided.

Expected success shape:

```python
assert result == {
    "type": "action_batch", "protocol_version": 1, "observation_id": 9,
    "reason": "observe", "actions": [{"type": "wait", "duration_ms": 100}],
}
```

- [ ] **Step 2: Implement serialized `AgentLoop`**

Use `threading.Lock` around `handle_observation`. Build messages, call the API,
derive the visible interaction action set, validate the decision, apply memory
updates with the current observation ID, save memory, and return the batch. On
exceptions, return:

```python
{"type": "error", "protocol_version": 1,
 "observation_id": observation.get("observation_id"),
 "code": "decision_failed", "message": type(exc).__name__}
```

Do not include exception text because compatible SDK exceptions may contain
request details.

- [ ] **Step 3: Write and run failing bridge tests**

Use a temporary port and `websockets.sync.client.connect`. Assert that the server
rejects an observation before a valid hello, accepts exactly protocol version 1,
uses the hello `data_dir` only when `Config.data_dir` is absent, and returns the
fake agent result for a valid observation.

Run: `PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/pytest ai_play/tests/test_agent_loop.py ai_play/tests/test_bridge_server.py -q`

Expected: bridge tests fail until server implementation exists.

- [ ] **Step 4: Implement bridge and entry point**

Use `websockets.sync.server.serve(handler, config.ws_host, config.ws_port)`. The
handler must parse each packet as one JSON object, enforce a 4 MiB maximum packet
size, require hello first, and send only compact JSON. It must never accept a
path from the model. Resolve the Godot-provided `data_dir` only from the hello,
create an `ai_play` child directory there, and store `memory.json` inside it.

`main.py` must load `Config`, create `MemoryStore.empty()` unless `--resume` is
explicitly passed, construct `ApiClient` and `AgentLoop`, print only host/port and
model name, then serve forever. Support `python -m ai_play.main --resume`.

- [ ] **Step 5: Run all Python tests**

Run: `PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/pytest ai_play/tests -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add ai_play/src/ai_play ai_play/tests
git commit -m "feat: serve validated AI decisions over loopback"
```

---

### Task 6: Godot bounded input executor

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_executor.gd`
- Create: `tests/ai_play/test_ai_play_executor.gd`

**Interfaces:**
- Consumes: validated action dictionaries plus current interface/interaction state.
- Produces: `execute_batch(actions, context)`, `cancel_all(reason)`, `batch_finished(results)`.

- [ ] **Step 1: Write a failing headless executor test**

Create a SceneTree test that instantiates the executor, calls its pure
`validate_action` method, and asserts rejection of an unknown action, movement
over 1000 ms, non-visible interaction, and digit entry with a closed interface.
Also assert `cancel_all()` releases `forward`, `back`, `left`, `right`, and
`sprint` using `Input.is_action_pressed`.

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd`

Expected: script load fails because the executor does not exist.

- [ ] **Step 2: Implement duplicate Godot-side validation**

`AIPlayExecutor` extends `Node` and emits `batch_finished(results: Array)`. Keep a
`held_actions: Dictionary`. `validate_action` mirrors Python hard limits and
requires the action's interaction slot to appear in `context.available_interactions`.

Use `Input.action_press`/`Input.action_release` for movement and sprint. Use an
`InputEventMouseMotion` passed through `Input.parse_input_event` for look. Use
`InputEventAction` press/release pairs for jump, crouch, F/E action names, and
menu. Use `InputEventKey` with matching `keycode` and `unicode` for digits.
Every duration wait must use a SceneTree timer, and every exit path must call a
`defer`-equivalent helper that releases held actions before emitting completion.

Core release function:

```gdscript
func cancel_all(reason: String) -> void:
    for action_name: String in held_actions.keys():
        Input.action_release(action_name)
    held_actions.clear()
    _cancel_generation += 1
    batch_finished.emit([{"status": "cancelled", "reason": reason}])
```

- [ ] **Step 3: Run the executor test**

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd`

Expected: exit code 0 with `AIPlay executor tests passed`.

- [ ] **Step 4: Commit**

```bash
git add addons/cogito/AIPlay/ai_play_executor.gd tests/ai_play/test_ai_play_executor.gd
git commit -m "feat: execute bounded AI inputs in Godot"
```

---

### Task 7: Godot observer and natural-language binding map

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_observer.gd`
- Create: `tests/ai_play/test_ai_play_observer.gd`

**Interfaces:**
- Consumes: exported `CogitoPlayer`, its camera, attributes, and current raycast interactable.
- Produces: `capture_observation(last_results) -> Dictionary`, `get_bindings() -> Dictionary`.

- [ ] **Step 1: Write failing observer contract tests**

Build small fake player/interactable nodes in the test. Assert:

- bindings include only `forward`, `back`, `left`, `right`, `jump`, `sprint`,
  `crouch`, `interact`, `interact2`, and `menu`;
- default `interact` and `interact2` bindings render as F and E;
- only enabled `interact`/`interact2` children on the current interactable appear;
- the output contains no `NodePath`, scene-tree dump, script, filename, or object
  node name;
- a missing health/stamina attribute produces ratio `null`, not an exception.

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd`

Expected: script load failure until observer exists.

- [ ] **Step 2: Implement bindings and visible interactions**

Use `InputMap.action_get_events(action_name)` and choose the first
`InputEventKey`. Render `physical_keycode` via `OS.get_keycode_string`; never send
raw arbitrary events.

Visible interaction extraction:

```gdscript
func _available_interactions() -> Array[Dictionary]:
    var result: Array[Dictionary] = []
    var target = player.player_interaction_component.interactable
    if target == null:
        return result
    for component in target.interaction_nodes:
        if component.is_disabled or component.input_map_action not in ["interact", "interact2"]:
            continue
        result.append({
            "action": component.input_map_action,
            "binding": bindings.get(component.input_map_action, "unbound"),
            "prompt": tr(component.interaction_text),
        })
    return result
```

Capture `get_viewport().get_texture().get_image()`, resize to 768x432, and call
`Marshalls.raw_to_base64(image.save_jpg_to_buffer(jpeg_quality))`. Derive yaw
from `player.body.global_rotation_degrees.y`, pitch from
`player.head.rotation_degrees.x`, planar velocity from player velocity, and
attribute ratios from `value_current / value_max`. Never serialize a Node or
NodePath.

- [ ] **Step 3: Run observer and import checks**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --editor --quit
```

Expected: observer tests pass and Godot exits without script parse errors.

- [ ] **Step 4: Commit**

```bash
git add addons/cogito/AIPlay/ai_play_observer.gd tests/ai_play/test_ai_play_observer.gd
git commit -m "feat: observe whitelisted first-person game state"
```

---

### Task 8: Godot bridge, controller, and fail-safe takeover

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_bridge.gd`
- Create: `addons/cogito/AIPlay/ai_play_controller.gd`
- Create: `addons/cogito/AIPlay/ai_play_controller.tscn`
- Create: `tests/ai_play/test_ai_play_controller.gd`

**Interfaces:**
- Bridge emits `connected`, `disconnected`, `action_batch_received`, and `remote_error`.
- Controller exports `player: CogitoPlayer`, `auto_start: bool = false`, host, port, observation interval, and emergency-stop key.

- [ ] **Step 1: Write failing controller tests**

With fake observer/bridge/executor nodes, assert:

- enabling connects and sends hello containing protocol version, bindings, and
  `OS.get_user_data_dir()` but no repository path;
- a matching observation ID executes, while a stale ID cancels;
- disconnect and remote error call `executor.cancel_all`;
- a physical human movement or mouse event pauses AI;
- emergency stop disables reconnection until explicitly enabled again.

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd`

Expected: failure until controller exists.

- [ ] **Step 2: Implement WebSocket client**

Use `WebSocketPeer.connect_to_url("ws://%s:%d" % [host, port])`, call `poll()` in
`_process`, enforce protocol version 1 and maximum packet size before JSON parse,
and emit typed signals. The bridge never executes actions itself.

- [ ] **Step 3: Implement controller state machine**

States are `DISABLED`, `CONNECTING`, `READY`, `WAITING_FOR_DECISION`, and
`EXECUTING`. After hello, capture one observation. Accept a batch only when its
ID equals `_pending_observation_id`. After execution, request the next
observation with results. On any state/protocol error, call `cancel_all` and
pause.

Human takeover should inspect physical input events in `_input` while ignoring
events marked with a dedicated executor device ID. Emergency stop defaults to
`KEY_F12`; it calls `disable_ai("emergency_stop")` and prevents automatic
reconnect.

- [ ] **Step 4: Create reusable scene**

```text
AIPlayController (Node, ai_play_controller.gd)
├── Observer (Node, ai_play_observer.gd)
├── Executor (Node, ai_play_executor.gd)
├── Bridge (Node, ai_play_bridge.gd)
└── ObservationTimer (Timer, one_shot=true)
```

Set `auto_start = false`, host `127.0.0.1`, port `8765`, and exported player path
empty so each host scene must wire it explicitly.

- [ ] **Step 5: Run controller and Godot import tests**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --editor --quit
```

Expected: all tests pass; no parser errors.

- [ ] **Step 6: Commit**

```bash
git add addons/cogito/AIPlay tests/ai_play
git commit -m "feat: connect Godot to autonomous AI sidecar"
```

---

### Task 9: Lobby wiring, documentation, and full verification

**Files:**
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`
- Create: `tests/check_ai_play_lobby.sh`
- Create: `ai_play/README.md`

**Interfaces:**
- Lobby owns one `AIPlayController` instance whose `player` points to `../Player`.
- Operator starts the sidecar, starts the Lobby, then explicitly enables AI.

- [ ] **Step 1: Write failing static Lobby/privacy check**

```bash
#!/usr/bin/env bash
set -euo pipefail

scene="addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
controller="addons/cogito/AIPlay/ai_play_controller.tscn"

test -f "$controller"
grep -q 'path="res://addons/cogito/AIPlay/ai_play_controller.tscn"' "$scene"
grep -q 'name="AIPlayController"' "$scene"
grep -q 'player = NodePath("../Player")' "$scene"
grep -q 'auto_start = false' "$scene"

if rg -n 'AI_PLAY_API_KEY=[^[:space:]]+' ai_play addons/cogito/AIPlay \
  -g '!*.example' -g '!test_*.py'; then
    echo "AI Play source must not contain a credential" >&2
    exit 1
fi

if rg -n "api_key[[:space:]]*=[[:space:]]*['\"]" ai_play/src addons/cogito/AIPlay; then
    echo "AI Play source must not contain a credential" >&2
    exit 1
fi
```

Run: `bash tests/check_ai_play_lobby.sh`

Expected: failure because the Lobby is not wired.

- [ ] **Step 2: Instance the controller in the Lobby**

Add one PackedScene ext resource for
`res://addons/cogito/AIPlay/ai_play_controller.tscn`. Instance it immediately
after the `Player` node:

```text
[node name="AIPlayController" parent="." node_paths=PackedStringArray("player") instance=ExtResource("ai_play_controller")]
player = NodePath("../Player")
auto_start = false
```

Use a collision-free ext-resource ID chosen after inspecting the current scene.
Do not alter puzzle objects, prompts, or success conditions.

- [ ] **Step 3: Write operator documentation**

README must include:

```bash
python3 -m venv .venv
.venv/bin/pip install -r ai_play/requirements.txt
read -rs AI_PLAY_API_KEY
export AI_PLAY_API_KEY
PYTHONPATH=ai_play/src .venv/bin/python -m ai_play.main
```

Document that the real key must be rotated if exposed, is never placed in
`.env.example`, and should be loaded through a local shell or ignored `.env`.
Explain F/E contextual behavior, F12 emergency stop, human takeover, empty versus
`--resume` memory, loopback networking, image/API cost, and the fact that the
custom compatible endpoint must support multimodal Chat Completions content.

- [ ] **Step 4: Run the complete automated verification suite**

```bash
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/pytest ai_play/tests -q
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
bash tests/check_ai_play_lobby.sh
bash tests/check_friendly_human_npc.sh
bash tests/check_lobby_friendly_npc.sh
godot --headless --path . --editor --quit
git diff --check
```

Expected: every command exits 0; pytest reports all tests passed; each Godot test
prints its success line; Godot reports no parse errors; Git reports no whitespace
errors.

- [ ] **Step 5: Perform a credential-free local smoke test**

Start the sidecar with a deliberately absent key:

```bash
env -u AI_PLAY_API_KEY PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/python -m ai_play.main
```

Expected: exits immediately with a concise `AI_PLAY_API_KEY is required` error
and prints no environment values.

Then start with a fake key and a fake local API test double supplied by the test
suite; connect the Lobby and verify hello, one observation, one `wait` action,
and clean disconnect without contacting the external provider.

- [ ] **Step 6: Perform the opt-in live black-box run**

Only when the operator has supplied a newly rotated real key, start the sidecar
and Lobby, enable AI manually, and observe:

- images and visible prompts reach the compatible API;
- the character moves through normal COGITO physics;
- F/E actions match the visible prompt;
- runtime facts originate only from observations;
- F12 and physical human input stop execution immediately;
- stopping Python releases all held movement.

Do not inspect or inject the scenario solution during this run. Record only
transport/action failures needed for debugging; leave camera-image logging off.

- [ ] **Step 7: Commit**

```bash
git add addons/cogito/DemoScenes/COGITO_3_Lobby.tscn tests/check_ai_play_lobby.sh ai_play/README.md
git commit -m "feat: enable autonomous AI play in Lobby"
```

---

## Final Review Checklist

- Confirm every spec requirement maps to a task above.
- Search source, tests, documentation, and Git history for the exposed credential before any push; the literal credential must have zero matches.
- Search `prompts.py` and default memory fixtures for scenario names, routes, codes, dates, object locations, and repository paths.
- Confirm the Python and Godot validators use identical action names and numeric limits.
- Confirm `interact`/`interact2` are selected only from the current visible interaction list.
- Confirm all cancellation paths release `forward`, `back`, `left`, `right`, and `sprint`.
- Confirm the live API run remains opt-in because it consumes an external service and sends screenshots.
