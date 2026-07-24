# AI Play Act Request Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** End an AI Play session with `failure/max_requests` after the configurable 500th MCP `act()` invocation unless that request already produced a password terminal result.

**Architecture:** `GameSession` owns a connection-scoped request counter under its existing condition lock. The threshold request completes normal processing, then Python sends one private protocol-v3 `end_game` packet and waits for Godot's normal `game_over`; Godot validates the packet and reuses its existing terminal/UI/input-release path.

**Tech Stack:** Python 3, pytest, FastMCP, WebSockets, Godot 4.7/GDScript, shell integration checks.

## Global Constraints

- Count every invocation that reaches Python `GameSession.act()`, including stale, invalid-context, malformed-action, and concurrent in-flight requests.
- Do not count `briefing`, `observe`, or `stop`, and do not add a public MCP tool.
- Default `AI_PLAY_MAX_ACT_REQUESTS` to `500`; accept only integers from `1` through `1_000_000`.
- Reset the counter whenever Godot successfully attaches or reconnects.
- The threshold request gets normal processing; `correct_password` and `wrong_password` terminal results take priority over `max_requests`.
- Move the private Python/Godot WebSocket contract from protocol version `2` to `3`; this does not change standard MCP/JSON-RPC negotiation.
- The only new private packet is exact `end_game/failure/max_requests`; Godot must reply through its existing `game_over` path.
- Keep AI Play opt-in, bind only `127.0.0.1`, preserve Escape/stop input release, and expose no hidden game state or credentials.
- Do not modify `addons/input_helper/`, `addons/quick_audio/`, generated caches, or historical scope documents.

---

### Task 1: Configuration and connection-scoped request accounting

**Files:**
- Modify: `ai_play/src/ai_play/config.py`
- Modify: `ai_play/.env.example`
- Test: `ai_play/tests/test_config.py`
- Test: `ai_play/tests/test_game_session.py`

**Interfaces:**
- Consumes: existing `Config.from_env()`, `Config.validate()`, `GameSession.attach()`, and `GameSession.act()`.
- Produces: `Config.max_act_requests: int`, `GameSession._record_act_request_locked() -> int`, and reset-on-attach behavior used by Task 2.

- [ ] **Step 1: Add failing configuration tests**

```python
def test_config_defaults_max_act_requests_to_500():
    assert Config().max_act_requests == 500


def test_config_reads_max_act_requests(monkeypatch):
    monkeypatch.setenv("AI_PLAY_MAX_ACT_REQUESTS", "7")
    assert Config.from_env().max_act_requests == 7


@pytest.mark.parametrize("value", ["0", "-1", "1000001", "1.5", "true"])
def test_config_rejects_invalid_max_act_requests(monkeypatch, value):
    monkeypatch.setenv("AI_PLAY_MAX_ACT_REQUESTS", value)
    with pytest.raises(ValueError, match="AI_PLAY_MAX_ACT_REQUESTS"):
        Config.from_env()
```

- [ ] **Step 2: Run the configuration tests and confirm RED**

Run: `PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_config.py -q`

Expected: FAIL because `Config` does not yet expose or parse `max_act_requests`.

- [ ] **Step 3: Add the bounded integer configuration**

```python
@dataclass(frozen=True)
class Config:
    max_act_requests: int = 500

    @classmethod
    def from_env(cls) -> "Config":
        config = cls(
            # existing values...
            max_act_requests=_read_int(
                "AI_PLAY_MAX_ACT_REQUESTS",
                cls.max_act_requests,
            ),
        )

    def validate(self) -> None:
        if (
            type(self.max_act_requests) is not int
            or not 1 <= self.max_act_requests <= 1_000_000
        ):
            raise ValueError(
                "AI_PLAY_MAX_ACT_REQUESTS must be between 1 and 1000000"
            )
```

Add `AI_PLAY_MAX_ACT_REQUESTS=500` to `ai_play/.env.example`.

- [ ] **Step 4: Run configuration tests and confirm GREEN**

Run: `PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_config.py -q`

Expected: all tests pass.

- [ ] **Step 5: Add failing request-accounting tests**

Use `Config(max_act_requests=2, wait_timeout_seconds=0.2, stop_timeout_seconds=0.2)` and assert:

```python
with pytest.raises(SessionError, match="stale_observation"):
    session.act(6, valid_actions, timeout=0.1)
with pytest.raises(SessionError, match="invalid_action"):
    session.act(7, [{"type": "not_an_action"}], timeout=0.1)
assert session.act_request_count == 2
```

Also detach and attach a new sender, then assert `session.act_request_count == 0`. Add a concurrent test proving the second call records request 2 before it raises `action_in_flight`.

- [ ] **Step 6: Run the focused accounting tests and confirm RED**

Run: `PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_game_session.py -q -k 'request_count or reconnect'`

Expected: FAIL because the counter/property/reset behavior does not exist.

- [ ] **Step 7: Implement minimal lock-protected accounting**

```python
class GameSession:
    def __init__(self, config):
        self._act_request_count = 0
        self._request_limit_pending = False

    @property
    def act_request_count(self):
        with self._condition:
            return self._act_request_count

    def attach(self, send_packet):
        with self._condition:
            # existing attach validation...
            self._act_request_count = 0
            self._request_limit_pending = False

    def _record_act_request_locked(self):
        if self._state in {"stopped", "game_over"}:
            raise SessionError(self._state)
        if self._request_limit_pending:
            raise SessionError("request_limit_reached")
        self._act_request_count += 1
        if self._act_request_count >= self.config.max_act_requests:
            self._request_limit_pending = True
        return self._act_request_count
```

Call `_record_act_request_locked()` as the first operation under `act()`'s condition lock, before observation/action/state validation.

- [ ] **Step 8: Run focused and full Python unit tests**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_config.py ai_play/tests/test_game_session.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit Task 1**

```bash
git add ai_play/src/ai_play/config.py ai_play/.env.example ai_play/tests/test_config.py ai_play/tests/test_game_session.py
git commit -m "feat: count AI Play act requests"
```

---

### Task 2: Protocol-v3 Python terminal orchestration

**Files:**
- Modify: `ai_play/src/ai_play/game_session.py`
- Modify: `ai_play/src/ai_play/bridge_server.py`
- Modify: `ai_play/src/ai_play/mcp_server.py` only if structured terminal mapping needs adjustment
- Test: `ai_play/tests/test_game_session.py`
- Test: `ai_play/tests/test_bridge_server.py`
- Test: `ai_play/tests/test_mcp_server.py`

**Interfaces:**
- Consumes: Task 1's `Config.max_act_requests`, `_act_request_count`, and `_request_limit_pending`.
- Produces: protocol-v3 packets, `_request_limit_result_locked(deadline, action_results) -> SessionResult`, and acceptance of `game_over/failure/max_requests`.

- [ ] **Step 1: Add failing protocol-v3 and threshold tests**

Update expected protocol literals from `2` to `3`. Add tests that:

```python
session = make_session(max_act_requests=1)
# Start the valid threshold act in a thread.
assert sent[0]["type"] == "action_batch"
session.receive_action_results(7, wait_action_results())
session.receive_observation(observation(8))
assert sent[1] == {
    "type": "end_game",
    "protocol_version": 3,
    "observation_id": 8,
    "outcome": "failure",
    "reason": "max_requests",
}
session.receive_game_over({
    "type": "game_over",
    "protocol_version": 3,
    "observation_id": 8,
    "outcome": "failure",
    "reason": "max_requests",
})
assert result.status == "game_over"
```

Add separate tests for an invalid threshold request, password terminal priority, exactly one `end_game`, request 501 rejection while pending, disconnect, acknowledgement timeout, and invalid `success/max_requests`.

- [ ] **Step 2: Run focused Python tests and confirm RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_game_session.py ai_play/tests/test_bridge_server.py ai_play/tests/test_mcp_server.py -q
```

Expected: FAIL on protocol `2`, missing `end_game`, and rejected `max_requests`.

- [ ] **Step 3: Bump Python private protocol and validate exact terminal pairs**

```python
PROTOCOL_VERSION = 3

allowed_terminal_pairs = {
    ("success", "correct_password"),
    ("failure", "wrong_password"),
    ("failure", "max_requests"),
}
if (packet.get("outcome"), packet.get("reason")) not in allowed_terminal_pairs:
    raise SessionError("invalid_game_over")
```

Use version `3` in `game_session.py`, `bridge_server.py`, and their hello/action/stop/game-over tests.

- [ ] **Step 4: Implement threshold completion and one private end-game request**

Refactor normal action execution into a helper so `act()` can always apply the threshold policy:

```python
def act(self, observation_id, actions, timeout=None):
    deadline = _deadline(timeout or self.config.wait_timeout_seconds)
    with self._condition:
        request_number = self._record_act_request_locked()
    try:
        result = self._execute_act(observation_id, actions, deadline)
    except SessionError:
        if request_number < self.config.max_act_requests:
            raise
        return self._request_limit_result(deadline, [])
    if request_number < self.config.max_act_requests or result.status == "game_over":
        return result
    return self._request_limit_result(deadline, result.action_results or [])
```

`_request_limit_result()` must:

- return an already-received password terminal without sending `end_game`;
- select the current pending/executing/latest observation ID under the condition lock;
- send exactly one protocol-v3 `end_game/failure/max_requests`;
- set state `ending`, making `observe()` wait rather than return stale data;
- wait only until the original `act()` deadline for `receive_game_over()`;
- return `SessionResult(status="game_over", action_results=..., game_over=...)`;
- on disconnect raise `SessionError("disconnected")`;
- on timeout raise `SessionError("action_timeout")` without clearing `_request_limit_pending`.

- [ ] **Step 5: Run focused tests and refactor while GREEN**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_game_session.py ai_play/tests/test_bridge_server.py ai_play/tests/test_mcp_server.py -q
```

Expected: all tests pass, including invalid threshold requests and password priority.

- [ ] **Step 6: Run the complete Python suite**

Run: `PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q`

Expected: all Python tests pass.

- [ ] **Step 7: Commit Task 2**

```bash
git add ai_play/src/ai_play/game_session.py ai_play/src/ai_play/bridge_server.py ai_play/src/ai_play/mcp_server.py ai_play/tests/test_game_session.py ai_play/tests/test_bridge_server.py ai_play/tests/test_mcp_server.py
git commit -m "feat: end AI Play at act request limit"
```

---

### Task 3: Godot protocol-v3 terminal reception and game-over UI

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_bridge.gd`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `addons/cogito/AIPlay/ai_play_game_over_screen.gd`
- Test: `tests/ai_play/test_ai_play_controller.gd`
- Test: `tests/ai_play/test_ai_play_game_over_screen.gd`
- Test: other `tests/ai_play/*.gd` files containing protocol literals

**Interfaces:**
- Consumes: Task 2's exact protocol-v3 `end_game` packet.
- Produces: `AIPlayBridge.end_game_received(request: Dictionary)` and `AIPlayController._on_end_game_received(request: Dictionary)`, both restricted to `failure/max_requests`.

- [ ] **Step 1: Add failing bridge/controller/UI tests**

Update FakeBridge with:

```gdscript
signal end_game_received(request: Dictionary)
```

Add tests that send exact protocol-v3 `end_game` and assert one `game_over` response with `failure/max_requests`, controller disablement, executor cancellation/input release, and UI text `达到最大步长`. Add rejection cases for extra fields, protocol 2, `success/max_requests`, the wrong reason, and a mismatched observation ID. Assert a repeated end-game/keypad callback cannot replace the first terminal result.

- [ ] **Step 2: Run focused Godot tests and confirm RED**

Run:

```text
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
```

Expected: FAIL because protocol 3/end-game signal and the new text are not implemented.

- [ ] **Step 3: Add strict protocol-v3 bridge parsing**

Set `PROTOCOL_VERSION := 3`, replace the version-2 helper/message with current-version validation, and accept only:

```gdscript
[
    "type",
    "protocol_version",
    "observation_id",
    "outcome",
    "reason",
]
```

for `type == "end_game"`, `outcome == "failure"`, and `reason == "max_requests"`. Normalize a safe integer or `null` observation ID before emitting `end_game_received`.

- [ ] **Step 4: Reuse the controller terminal path**

Connect `end_game_received` in `_ready()`. In `_on_end_game_received()`, repeat exact field/version/pair validation, require the ID to match the executing ID or pending ID (allow `null` only when neither exists), then call:

```gdscript
_finish_game("failure", "max_requests", expected_observation_id)
```

Change `_finish_game()` validation to exact allowed pairs:

```gdscript
var allowed := (
    outcome == "success" and reason == "correct_password"
) or (
    outcome == "failure"
    and reason in ["wrong_password", "max_requests"]
)
```

Keep `_game_finished` as the idempotency gate and use the existing `disable_ai()`/executor-cancellation/UI path.

- [ ] **Step 5: Update the terminal copy**

Map `max_requests` to exact Chinese text:

```gdscript
"max_requests":
    reason_label.text = "达到最大步长"
```

- [ ] **Step 6: Run focused and affected Godot tests**

Run:

```text
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_cogito_keypad_result.gd
```

Expected: every script exits successfully.

- [ ] **Step 7: Commit Task 3**

```bash
git add addons/cogito/AIPlay/ai_play_bridge.gd addons/cogito/AIPlay/ai_play_controller.gd addons/cogito/AIPlay/ai_play_game_over_screen.gd tests/ai_play
git commit -m "feat: handle AI Play request-limit terminal"
```

---

### Task 4: Documentation, cross-layer checks, and final verification

**Files:**
- Modify: `AGENTS.md`
- Modify: `README_AI_PLAY.md`
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/wiki/development/contributor-guide.md`
- Modify: `docs/wiki/wiki.md` only if its index description needs updating
- Modify: `tutorial/mcp_server.md`
- Modify: `tests/check_ai_play_mcp_only.sh` only if a static contract assertion is useful

**Interfaces:**
- Consumes: completed configuration, protocol, terminal behavior, and UI wording from Tasks 1–3.
- Produces: one consistent operator/tutorial description of MCP stdio versus the private WebSocket bridge, protocol v3, counter/reset semantics, and the 500th-request terminal sequence.

- [ ] **Step 1: Update operator and architecture documentation**

Document:

```text
AI_PLAY_MAX_ACT_REQUESTS=500
```

and state that every dispatched Python `act()` call counts, invalid calls count, `observe` does not, reconnect resets to zero, request 500 is processed normally, password outcomes win, and otherwise Godot shows `failure/max_requests` (“达到最大步长”).

Replace current private bridge protocol-v2 prose/examples with v3 in `AGENTS.md`, both READMEs, Wiki pages, contributor verification wording, and `tutorial/mcp_server.md`. Explicitly preserve the distinction that MCP stdio/JSON-RPC protocol negotiation is separate from the internal WebSocket `protocol_version: 3`.

- [ ] **Step 2: Scan for stale active protocol references**

Run:

```bash
rg -n 'protocol_version.?[:=].?2|协议版本为 2|must be 2|protocol two|version_two' AGENTS.md README_AI_PLAY.md ai_play addons/cogito/AIPlay tests/ai_play docs/wiki tutorial/mcp_server.md
```

Expected: no active runtime, test, or current-document matches. Historical `docs/scope/` and old specs/plans are intentionally excluded.

- [ ] **Step 3: Run all affected verification**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_interaction_probe.gd
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
godot --headless --path . --script tests/ai_play/test_cogito_keypad_result.gd
godot --headless --path . --editor --quit
bash tests/check_ai_play_lobby.sh
bash tests/check_ai_play_start_script.sh
bash tests/check_ai_play_mcp_only.sh
bash tests/test_ai_play_secret_scan.sh
git diff --check
```

Expected: every command exits zero. If Godot is unavailable, record exactly which engine commands were not run while still running all Python, shell, scan, and diff checks.

- [ ] **Step 4: Review the final diff for scope and safety**

Run:

```bash
git status --short
git diff --stat HEAD
git diff HEAD -- ai_play/src addons/cogito/AIPlay tests/ai_play ai_play/tests
```

Expected: only planned code/tests/docs plus the pre-existing untracked `tutorial/__pycache__/`; no generated files, credentials, hidden game data, `addons/input_helper/`, or `addons/quick_audio/`.

- [ ] **Step 5: Commit Task 4**

```bash
git add AGENTS.md README_AI_PLAY.md ai_play/README.md docs/wiki/ai-play/system-guide.md docs/wiki/development/contributor-guide.md docs/wiki/wiki.md tutorial/mcp_server.md tests/check_ai_play_mcp_only.sh
git commit -m "docs: explain AI Play request limit"
```

- [ ] **Step 6: Final branch verification**

Run:

```bash
git status --short --branch
git log --oneline -6
```

Expected: the feature branch contains the design, implementation-plan, implementation, Godot, and documentation commits; the only unrelated worktree entry remains `tutorial/__pycache__/`.
