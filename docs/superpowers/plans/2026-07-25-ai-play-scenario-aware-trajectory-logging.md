# AI Play Scenario-Aware Trajectory Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Partition MCP gameplay runs by validated `scenario_id` and preserve each attempt's terminal reason in `run.json` without changing `trajectory.json`.

**Architecture:** `TrajectoryLogger` owns generic scenario-directory validation, run allocation, and summary persistence. `GameSession` passes the bridge-validated scenario into attempt creation and translates existing terminal lifecycle paths into a coarse status plus stable reason. The bridge and MCP tool surfaces keep their current scenario-aware behavior and public schemas.

**Tech Stack:** Python 3.11+, pytest, Godot/Python protocol version 3, JSON filesystem persistence.

## Global Constraints

- Work only in the isolated `feature/mcp-trajectory-logging` worktree.
- Keep AI Play explicitly enabled and the bridge bound to exact `127.0.0.1`.
- Do not add credentials, hidden state, repository content, briefing data, or image Base64 to logs.
- Keep `trajectory.json` with exactly `trajectory` and `result`; keep `result` with exactly `total_steps` and `status`.
- Record only `observe`, `act`, and `stop`; do not record `briefing`.
- One run contains at most three attempts of exactly one scenario.
- Preserve the first terminal status and reason.
- Update `ai_play/README.md`, the AI Play Wiki, and tests when changing log layout.
- Do not run a real external MCP/model acceptance session.

---

### Task 1: Scenario-partitioned logger and run metadata

**Files:**
- Modify: `ai_play/tests/test_trajectory_logger.py`
- Modify: `ai_play/src/ai_play/trajectory_logger.py`

**Interfaces:**
- Consumes: a bridge-validated `scenario_id: str`.
- Produces: `TrajectoryLogger.start_attempt(scenario_id: str) -> pathlib.Path`.
- Produces: `TrajectoryLogger.finish_attempt(status: str, terminal_reason: str) -> None`.
- Produces: `run.json` with top-level `scenario_id` and per-attempt `terminal_reason`.

- [ ] **Step 1: Write failing layout and metadata tests**

Change existing `start_attempt()` calls to supply a scenario and assert the
scenario directory plus stable summary schema:

```python
attempt_dir = logger.start_attempt("find_key")

assert attempt_dir == (
    tmp_path / "find_key" / "20260724-14-35" / "attempt-01"
)
assert load_json(attempt_dir.parent / "run.json") == {
    "scenario_id": "find_key",
    "started_at": "2026-07-24T14:35:00+00:00",
    "max_attempts": 3,
    "completed_attempts": 0,
    "status": "in_progress",
    "successful_attempt": None,
    "attempts": [{
        "attempt": 1,
        "status": "in_progress",
        "total_steps": 0,
        "terminal_reason": None,
    }],
}
```

Add independent partition and collision coverage:

```python
def test_runs_are_partitioned_by_scenario(tmp_path):
    first = TrajectoryLogger(tmp_path, now=Clock())
    second = TrajectoryLogger(tmp_path, now=Clock())

    key_dir = first.start_attempt("find_key")
    contract_dir = second.start_attempt("find_contract")

    assert key_dir.parents[1].name == "find_key"
    assert contract_dir.parents[1].name == "find_contract"
    assert key_dir.parent.name == contract_dir.parent.name
```

- [ ] **Step 2: Write failing identifier and invariant tests**

Add unsafe identifier cases and ensure validation precedes filesystem writes:

```python
@pytest.mark.parametrize(
    "scenario_id",
    ["", ".", "..", "../find_key", "/tmp/find_key", "FindKey", "find/key"],
)
def test_start_attempt_rejects_unsafe_scenario_before_writing(
    tmp_path,
    scenario_id,
):
    logger = TrajectoryLogger(tmp_path, now=Clock())

    with pytest.raises(ValueError, match="invalid scenario_id"):
        logger.start_attempt(scenario_id)

    assert list(tmp_path.iterdir()) == []
```

Assert that an active run cannot mix scenarios:

```python
def test_active_run_rejects_a_different_scenario(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    logger.start_attempt("find_key")
    logger.finish_attempt("failure", "max_requests")

    with pytest.raises(ValueError, match="scenario_mismatch"):
        logger.start_attempt("find_contract")
```

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_trajectory_logger.py -q
```

Expected: failures show `start_attempt` does not accept `scenario_id`, paths
are not scenario-partitioned, and summaries lack the new fields.

- [ ] **Step 4: Implement scenario validation and partitioned allocation**

Add a conservative identifier expression and validate before mutation:

```python
import re

SCENARIO_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


def _validate_scenario_id(value):
    if type(value) is not str or SCENARIO_ID_PATTERN.fullmatch(value) is None:
        raise ValueError("invalid scenario_id")
    return value
```

Change attempt creation to:

```python
def start_attempt(self, scenario_id):
    scenario_id = _validate_scenario_id(scenario_id)
    with self._lock:
        self._require_available_locked()
        if self._run is not None and self._run["scenario_id"] != scenario_id:
            raise ValueError("scenario_mismatch")
        ...
```

Allocate new runs below `self.root / scenario_id`, keeping collision suffixes
local to that directory. Initialize:

```python
self._run = {
    "scenario_id": scenario_id,
    "started_at": started_at.isoformat(),
    ...
}
```

Initialize every attempt summary with:

```python
{
    "attempt": attempt_number,
    "status": "in_progress",
    "total_steps": 0,
    "terminal_reason": None,
}
```

- [ ] **Step 5: Write failing terminal reason tests**

Update result-summary tests to pass reasons and add first-terminal preservation:

```python
logger.finish_attempt("success", "key_picked_up")
run = load_json(attempt_dir.parent / "run.json")
assert run["attempts"][0]["terminal_reason"] == "key_picked_up"
assert load_json(attempt_dir / "trajectory.json")["result"] == {
    "total_steps": 0,
    "status": "success",
}

logger.finish_attempt("stopped", "bridge_disconnected")
run = load_json(attempt_dir.parent / "run.json")
assert run["attempts"][0]["terminal_reason"] == "key_picked_up"
```

- [ ] **Step 6: Run focused tests and verify RED**

Run the same focused pytest command. Expected: `finish_attempt` rejects the
new argument or the summary lacks `terminal_reason`.

- [ ] **Step 7: Implement terminal reason persistence**

Change:

```python
def finish_attempt(self, status, terminal_reason):
    if status not in self.TERMINAL_STATUSES:
        raise ValueError("invalid trajectory status")
    if type(terminal_reason) is not str or not terminal_reason:
        raise ValueError("invalid terminal reason")
    ...
    summary["terminal_reason"] = terminal_reason
```

Keep the early return for an already terminal attempt so the first reason is
immutable. Change `close()` to finish an active attempt as
`stopped/mcp_shutdown` in the run summary while leaving
`trajectory.json.result` unchanged apart from its existing status.

- [ ] **Step 8: Run logger tests and verify GREEN**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_trajectory_logger.py -q
```

Expected: all logger tests pass.

- [ ] **Step 9: Commit the logger unit**

```bash
git add ai_play/src/ai_play/trajectory_logger.py \
  ai_play/tests/test_trajectory_logger.py
git commit -m "feat: partition trajectory logs by scenario"
```

---

### Task 2: Pass scenario and terminal lifecycle metadata from GameSession

**Files:**
- Modify: `ai_play/tests/test_game_session.py`
- Modify: `ai_play/src/ai_play/game_session.py`

**Interfaces:**
- Consumes: `GameSession.attach(send_packet, scenario_id)`.
- Consumes: validated `game_over.reason`, `escape_stop`, MCP stop acknowledgements, bridge detach reasons, and MCP shutdown.
- Calls: `TrajectoryLogger.start_attempt(scenario_id)`.
- Calls: `TrajectoryLogger.finish_attempt(status, terminal_reason)`.

- [ ] **Step 1: Update the recording fake and write failing scenario test**

Use explicit event tuples:

```python
class RecordingLogger:
    def start_attempt(self, scenario_id):
        self.events.append(("start", scenario_id))

    def finish_attempt(self, status, terminal_reason):
        self.events.append(("finish", status, terminal_reason))
```

Add:

```python
def test_successful_attach_starts_log_for_selected_scenario():
    logger = RecordingLogger()
    session = GameSession(Config(), trajectory_logger=logger)

    session.attach(lambda packet: True, "put_book")

    assert logger.events == [("start", "put_book")]
```

- [ ] **Step 2: Write failing terminal mapping tests**

Update game-over expectations to include the exact validated reason:

```python
assert logger.events == [
    ("start", "find_contract"),
    ("finish", expected, reason),
]
```

Add or update cases for:

```python
("success", "correct_password")
("success", "key_picked_up")
("success", "book_in_box")
("success", "meeting_door_closed")
("failure", "wrong_password")
("failure", "max_requests")
```

Assert lifecycle mappings:

```python
("escape stop", "stopped", "escape_stop")
("MCP stop acknowledgement", "stopped", "mcp_stop")
("connection_closed", "stopped", "bridge_disconnected")
("mcp_shutdown", "stopped", "mcp_shutdown")
```

Repeat terminal notifications and detach cleanup to prove the first terminal
reason is emitted only once.

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_game_session.py -q
```

Expected: recording fake signature/tuple assertions fail because the session
currently passes only status and omits the scenario.

- [ ] **Step 4: Pass scenario to logger only after session checks**

Set `_scenario_id` before starting the log, then call:

```python
self._scenario_id = scenario_id
self._start_log_attempt_locked(scenario_id)
```

Implement:

```python
def _start_log_attempt_locked(self, scenario_id):
    self._trajectory_logger.start_attempt(scenario_id)
```

If log creation fails, restore `_scenario_id` to its previous value so a
rejected attachment does not partially claim the session.

- [ ] **Step 5: Carry status and reason as one claimed terminal tuple**

Use:

```python
def _claim_log_finish_locked(self, status, terminal_reason):
    if not self._log_attempt_active:
        return None
    self._log_attempt_active = False
    return status, terminal_reason


def _finish_log_attempt(self, terminal):
    status, terminal_reason = terminal
    self._trajectory_logger.finish_attempt(status, terminal_reason)
```

Call it with:

```python
self._claim_log_finish_locked(safe["outcome"], safe["reason"])
self._claim_log_finish_locked("stopped", "escape_stop")
self._claim_log_finish_locked("stopped", "mcp_stop")
self._claim_log_finish_locked(
    "stopped",
    "mcp_shutdown" if reason == "mcp_shutdown" else "bridge_disconnected",
)
```

Normal MCP stop completion is identified by `receive_stop_ack`; physical
Escape is identified by `receive_stop`. Existing one-shot claiming prevents
detach from overwriting either reason.

- [ ] **Step 6: Run session and bridge tests and verify GREEN**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_game_session.py \
  ai_play/tests/test_bridge_server.py -q
```

Expected: all selected tests pass, including scenario-aware hello behavior.

- [ ] **Step 7: Commit lifecycle integration**

```bash
git add ai_play/src/ai_play/game_session.py \
  ai_play/tests/test_game_session.py
git commit -m "feat: record scenario terminal reasons"
```

---

### Task 3: Documentation, compatibility, and complete verification

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

**Interfaces:**
- Documents: `mcplogs/<scenario_id>/<timestamp>/`.
- Documents: `run.json.scenario_id`.
- Documents: `attempts[].terminal_reason`.
- Preserves: the public MCP tool list and `trajectory.json` schema.

- [ ] **Step 1: Update operator documentation**

Replace the flat run tree with:

```text
mcplogs/
└── find_key/
    └── 20260725-14-45/
        ├── run.json
        └── attempt-01/
            ├── trajectory.json
            └── imgs/
```

Document that one run contains up to three attempts of one task, that
`run.json` repeats `scenario_id`, and that `terminal_reason` records the
scenario outcome or stable stop cause. Explicitly state that
`trajectory.json.result` still has only `total_steps` and `status`.

- [ ] **Step 2: Run focused Python compatibility tests**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_trajectory_logger.py \
  ai_play/tests/test_game_session.py \
  ai_play/tests/test_bridge_server.py \
  ai_play/tests/test_mcp_server.py \
  ai_play/tests/test_scenarios.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run the complete Python suite**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
```

Expected: all tests pass.

- [ ] **Step 4: Run repository shell checks affected by AI Play**

Run:

```bash
bash tests/check_ai_play_start_script.sh
bash tests/check_ai_play_mcp_only.sh
bash tests/check_ai_play_scenario_wiring.sh
```

Expected: each command exits zero.

- [ ] **Step 5: Verify formatting and worktree scope**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only planned files are modified.

- [ ] **Step 6: Commit documentation**

```bash
git add ai_play/README.md docs/wiki/ai-play/system-guide.md
git commit -m "docs: explain scenario-aware trajectory logs"
```

- [ ] **Step 7: Run fresh final verification**

Repeat the complete Python suite, three shell checks, and
`git diff --check`. Record exact pass counts and explicitly report that no real
external MCP/model session or Godot GUI acceptance was run.
