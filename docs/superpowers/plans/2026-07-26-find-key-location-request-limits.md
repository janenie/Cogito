# Find Key Location Request Limits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give three `find_key` locations a 50-request MCP `act` hard cap while the other two retain 100, without exposing the selected location or current cap through MCP tools or trajectory logs.

**Architecture:** Godot computes an allowlisted 50/100 round cap after selecting the key location and sends only that number in an optional protocol-v3 `hello` field. Python validates and locks the round cap, continues counting every MCP `act` request at the existing entry point, and never includes the cap in MCP results or logs.

**Tech Stack:** Godot 4.7 GDScript, Python 3.12, pytest, WebSocket protocol version 3, Markdown.

## Global Constraints

- `desktop_desk`, `tv_coffee_table`, and `archive_sofa` use a 50-request hard cap.
- `laptop_desk` and `meeting_table` use a 100-request hard cap.
- The effective cap is `min(round cap, AI_PLAY_MAX_ACT_REQUESTS)`.
- Protocol version 3 accepts an optional `act_request_limit` only for `find_key`, with exact integer values 50 or 100.
- Legacy version-3 `find_key` hellos without the optional field default to 100.
- Selected location, current cap, candidate coordinates, and seed never enter MCP tool results or trajectory logs.
- Request counting, success-first threshold behavior, input release, and Escape emergency stop retain their existing semantics.
- Preserve unrelated working-tree changes and do not modify `addons/input_helper/` or `addons/quick_audio/`.

---

### Task 1: Compute the round cap in the Find Key monitor

**Files:**
- Modify: `tests/ai_play/test_ai_play_find_key_monitor.gd`
- Modify: `addons/cogito/AIPlay/ai_play_find_key_monitor.gd`

**Interfaces:**
- Consumes: `_selected_location: String`, chosen by `configure_round(seed_value)`.
- Produces: `get_act_request_limit() -> int`, returning exactly 50 or 100.

- [ ] **Step 1: Add a failing location-to-cap assertion**

Inside the existing seed loop, derive the literal expected cap:

```gdscript
var expected_limit: int = (
	50
	if location in [
		"desktop_desk",
		"tv_coffee_table",
		"archive_sofa",
	]
	else 100
)
_assert(
	monitor.get_act_request_limit() == expected_limit,
	"selected key location uses its allowlisted request limit",
)
```

- [ ] **Step 2: Run the monitor test and verify RED**

Run:

```bash
godot --headless --path . \
  --script tests/ai_play/test_ai_play_find_key_monitor.gd
```

Expected: failure because `get_act_request_limit()` does not exist.

- [ ] **Step 3: Implement the allowlisted mapping**

Add:

```gdscript
const SHORT_ACT_REQUEST_LIMIT: int = 50
const DEFAULT_ACT_REQUEST_LIMIT: int = 100
const SHORT_LIMIT_LOCATION_IDS: Array[String] = [
	"desktop_desk",
	"tv_coffee_table",
	"archive_sofa",
]


func get_act_request_limit() -> int:
	if _selected_location in SHORT_LIMIT_LOCATION_IDS:
		return SHORT_ACT_REQUEST_LIMIT
	return DEFAULT_ACT_REQUEST_LIMIT
```

- [ ] **Step 4: Run the monitor test and verify GREEN**

Run the Step 2 command again. Expected: exit 0 with
`AIPlay find-key monitor test passed`.

### Task 2: Normalize and lock the round cap in Python

**Files:**
- Modify: `ai_play/tests/test_scenarios.py`
- Modify: `ai_play/tests/test_game_session.py`
- Modify: `ai_play/src/ai_play/scenarios.py`
- Modify: `ai_play/src/ai_play/game_session.py`

**Interfaces:**
- Produces: `scenario_round_act_request_limit(scenario_id: str, requested_limit: object = None) -> int`.
- Extends: `scenario_act_request_limit(scenario_id: str, configured_limit: int, round_limit: object = None) -> int`.
- Extends: `GameSession.attach(send_packet, scenario_id=DEFAULT_SCENARIO_ID, act_request_limit=None)`.

- [ ] **Step 1: Add failing scenario normalization tests**

Add assertions:

```python
assert scenario_round_act_request_limit("find_key") == 100
assert scenario_round_act_request_limit("find_key", 50) == 50
assert scenario_round_act_request_limit("find_key", 100) == 100
assert scenario_act_request_limit("find_key", 500, 50) == 50
assert scenario_act_request_limit("find_key", 40, 50) == 40
```

Parameterize rejected values so booleans, floats, strings, values other than
50/100, and any explicit limit for another scenario raise
`RuntimeError("invalid_act_request_limit")`.

- [ ] **Step 2: Add failing session attach and reconnect tests**

Add tests that:

```python
session = GameSession(Config(max_act_requests=500))
session.attach(lambda packet: True, "find_key", act_request_limit=50)
assert session.act_request_limit == 50
session.detach("test")
session.attach(lambda packet: True, "find_key", act_request_limit=50)
assert session.act_request_limit == 50
```

Then verify reconnecting the same session with 100 raises
`SessionError("scenario_mismatch")`, a legacy `find_key` attach yields 100,
and `Config(max_act_requests=40)` tightens a round cap of 50 to 40.

- [ ] **Step 3: Run focused Python tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_game_session.py -q
```

Expected: failures for the missing helper and attach parameter.

- [ ] **Step 4: Implement scenario cap normalization**

In `scenarios.py`, add:

```python
FIND_KEY_ROUND_ACT_REQUEST_LIMITS = frozenset({50, 100})


def scenario_round_act_request_limit(
    scenario_id: str,
    requested_limit: object = None,
) -> int:
    try:
        default_limit = _SCENARIOS[scenario_id].max_act_requests
    except (KeyError, TypeError) as error:
        raise RuntimeError("unsupported_scenario") from error
    if requested_limit is None:
        return default_limit
    if (
        scenario_id != "find_key"
        or type(requested_limit) is not int
        or requested_limit not in FIND_KEY_ROUND_ACT_REQUEST_LIMITS
    ):
        raise RuntimeError("invalid_act_request_limit")
    return requested_limit
```

Extend `scenario_act_request_limit()` to return:

```python
return min(
    scenario_round_act_request_limit(scenario_id, round_limit),
    configured_limit,
)
```

- [ ] **Step 5: Implement session locking**

Store `_round_act_request_limit = None` initially. In `attach()`, normalize the
candidate before mutating session state, reject a different normalized value on
reconnect with `scenario_mismatch`, store and roll it back alongside
`_scenario_id` if logging fails, and pass it into
`scenario_act_request_limit()` from `_act_request_limit_locked()`.

- [ ] **Step 6: Run focused Python tests and verify GREEN**

Run the Step 3 command again. Expected: all selected tests pass.

### Task 3: Validate the optional cap in the Python bridge

**Files:**
- Modify: `ai_play/tests/test_bridge_server.py`
- Modify: `ai_play/src/ai_play/bridge_server.py`

**Interfaces:**
- Consumes: protocol-v3 hello field `act_request_limit`.
- Calls: `GameSession.attach(..., act_request_limit=hello.get("act_request_limit"))`.
- Keeps the Python hello response unchanged: type, protocol version, and scenario ID only.

- [ ] **Step 1: Add failing bridge acceptance and rejection tests**

Add a `find_key` hello helper case:

```python
hello = _hello("find_key")
hello["act_request_limit"] = 50
assert _send(connection, hello) == {
    "type": "hello",
    "protocol_version": 3,
    "scenario_id": "find_key",
}
assert session.act_request_limit == 50
```

Add rejection cases for `True`, `50.0`, `"50"`, `49`, `51`, and `101`, plus
`find_contract` carrying 50. Each must return
`invalid_act_request_limit`. Retain tests proving legacy `find_key` without the
field defaults to 100 and unrelated extra fields return `invalid_hello`.

- [ ] **Step 2: Run bridge tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_bridge_server.py -q
```

Expected: bridge rejects the new valid field as `invalid_hello`.

- [ ] **Step 3: Implement exact hello validation**

Allow only this additional exact field set:

```python
{"type", "protocol_version", "scenario_id", "act_request_limit"}
```

After validating `scenario_id`, call
`scenario_round_act_request_limit(scenario_id, packet["act_request_limit"])`
when the field is present. Convert validation failure to
`invalid_act_request_limit`, pass the value to `GameSession.attach()`, and do
not echo it in the server hello.

- [ ] **Step 4: Run bridge tests and verify GREEN**

Run the Step 2 command again. Expected: all bridge tests pass.

### Task 4: Send the cap from the Godot Controller

**Files:**
- Modify: `tests/ai_play/test_ai_play_controller.gd`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`

**Interfaces:**
- Consumes: active `find_key` monitor method `get_act_request_limit() -> int`.
- Produces: optional protocol-v3 hello field `act_request_limit`.

- [ ] **Step 1: Extend the fake monitor and add failing hello tests**

Extend `FakeTerminalMonitor`:

```gdscript
var act_request_limit: int = 100


func get_act_request_limit() -> int:
	return act_request_limit
```

Keep the existing `find_contract` hello assertion exact and add a `find_key`
fixture whose monitor limit is 50. Assert its first packet is exactly:

```gdscript
{
	"type": "hello",
	"protocol_version": 3,
	"scenario_id": "find_key",
	"act_request_limit": 50,
}
```

Also test that a `find_key` monitor returning a value outside 50/100 disables
the controller without sending a hello.

- [ ] **Step 2: Run the Controller test and verify RED**

Run:

```bash
godot --headless --path . \
  --script tests/ai_play/test_ai_play_controller.gd
```

Expected: the `find_key` hello lacks `act_request_limit`.

- [ ] **Step 3: Implement validated hello construction**

In `_on_bridge_connected()`, only for `find_key`:

```gdscript
var request_limit: Variant = _terminal_monitor.get_act_request_limit()
if (
	not request_limit is int
	or request_limit not in [50, 100]
):
	_pause_for_error("invalid_act_request_limit")
	return
hello["act_request_limit"] = request_limit
```

Guard the monitor and method before calling them. Other scenarios keep their
existing exact hello.

- [ ] **Step 4: Run the Controller test and verify GREEN**

Run the Step 2 command again. Expected: exit 0 with
`AIPlay controller tests passed`.

### Task 5: Synchronize documentation and run full verification

**Files:**
- Modify: `README_AI_PLAY.md`
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

**Interfaces:**
- Documents: internal 50/100 mapping, optional protocol field, legacy default,
  effective-cap formula, reconnect consistency, and privacy boundary.

- [ ] **Step 1: Update current documentation**

State that the three mapped locations use 50, the remaining two use 100, the
briefing only reports the public maximum of 100, and the internal
`act_request_limit` field never enters MCP results or logs. Correct remaining
stale `find_key` 200 references in current documentation. Do not rewrite
historical specs or plans.

- [ ] **Step 2: Run the full Python suite**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
```

Expected: all tests pass. Bridge tests bind only `127.0.0.1` on temporary
ports.

- [ ] **Step 3: Run affected Godot tests**

Run:

```bash
godot --headless --path . \
  --script tests/ai_play/test_ai_play_find_key_monitor.gd
godot --headless --path . \
  --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --editor --quit
```

Expected: both scripts exit 0 and the editor import/parse check exits 0.

- [ ] **Step 4: Run static integration and privacy checks**

Run:

```bash
bash tests/check_ai_play_lobby.sh
bash tests/check_ai_play_start_script.sh
bash tests/test_ai_play_secret_scan.sh
```

Expected: all commands exit 0.

- [ ] **Step 5: Inspect the exact diff and whitespace**

Run:

```bash
git diff -- \
  addons/cogito/AIPlay/ai_play_find_key_monitor.gd \
  addons/cogito/AIPlay/ai_play_controller.gd \
  ai_play/src/ai_play/scenarios.py \
  ai_play/src/ai_play/game_session.py \
  ai_play/src/ai_play/bridge_server.py \
  tests/ai_play/test_ai_play_find_key_monitor.gd \
  tests/ai_play/test_ai_play_controller.gd \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_game_session.py \
  ai_play/tests/test_bridge_server.py \
  README_AI_PLAY.md \
  ai_play/README.md \
  docs/wiki/ai-play/system-guide.md
git diff --check
```

Expected: only the intended cross-layer cap behavior and current documentation
change; `git diff --check` exits successfully.
