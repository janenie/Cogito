# Conveyor Profit Strategy-Stall Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** End a `conveyor_profit` round as formal `failure/strategy_stalled` after five consecutive identical actions each leave the approved public conveyor state unchanged.

**Architecture:** Keep detection in the trusted Python `GameSession`, using a narrow fingerprint of the already validated public `conveyor` observation and a canonical action batch. Reuse the existing one-shot trusted `end_game` state machine, while extending Python and Godot terminal allowlists symmetrically so the result follows normal logging, workflow-memory, input-release, UI, ACK, and supervised-exit paths.

**Tech Stack:** Python 3.11, pytest, Godot 4.7/GDScript, protocol-v4 JSON packets, existing AI Play trajectory logger and workflow memory.

---

## File map

- `ai_play/src/ai_play/scenarios.py`: Python scenario-specific terminal allowlist.
- `ai_play/src/ai_play/game_session.py`: trusted five-turn detector and generalized one-shot end-game sender.
- `ai_play/tests/test_scenarios.py`: Python allowlist regression coverage.
- `ai_play/tests/test_game_session.py`: detector, precedence, recovery, isolation, and durable terminal integration coverage.
- `ai_play/tests/test_workflow_memory.py`: failure-only persistence behavior for the new reason.
- `addons/cogito/AIPlay/ai_play_bridge.gd`: scenario-agnostic syntax validation for trusted end-game packets.
- `addons/cogito/AIPlay/ai_play_controller.gd`: scenario-specific semantic validation and formal terminal dispatch.
- `addons/cogito/AIPlay/ai_play_game_over_screen.gd`: dedicated result copy.
- `tests/ai_play/test_ai_play_controller.gd`: bridge/controller acceptance and rejection coverage.
- `tests/ai_play/test_ai_play_game_over_screen.gd`: result-copy coverage.
- `README_AI_PLAY.md`, `ai_play/README.md`, `docs/wiki/ai-play/system-guide.md`: public protocol and runtime behavior.

### Task 1: Add the Python terminal contract

**Files:**
- Modify: `ai_play/tests/test_scenarios.py`
- Modify: `ai_play/src/ai_play/scenarios.py`

- [ ] **Step 1: Write the failing scenario test**

Extend `test_terminal_results_are_scenario_specific()` with exact assertions:

```python
assert is_allowed_game_over(
    "conveyor_profit", "failure", "strategy_stalled"
)
for scenario_id in supported_scenario_ids():
    if scenario_id != "conveyor_profit":
        assert not is_allowed_game_over(
            scenario_id, "failure", "strategy_stalled"
        )
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src /Users/aidy/Projects/.venv-cogito-deepagents/bin/python \
  -m pytest ai_play/tests/test_scenarios.py::test_terminal_results_are_scenario_specific -q
```

Expected: FAIL because `conveyor_profit` does not yet allow `strategy_stalled`.

- [ ] **Step 3: Add the minimal allowlist entry**

Add only this tuple to the `conveyor_profit` `terminal_results` set:

```python
("failure", "strategy_stalled"),
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_play/src/ai_play/scenarios.py ai_play/tests/test_scenarios.py
git commit -m "feat(ai-play): allow conveyor stall terminal"
```

### Task 2: Detect five genuine no-progress turns

**Files:**
- Modify: `ai_play/tests/test_game_session.py`
- Modify: `ai_play/src/ai_play/game_session.py`

- [ ] **Step 1: Add conveyor observation/result test helpers**

In `test_game_session.py`, add a helper that extends the existing valid
`observation()` fixture with a fully valid public `conveyor` object. Accept
parameters for observation ID, window, clocks, tray, profit, dish, and finished.
Add a completed result helper such as:

```python
def conveyor_result(action_type, outcome):
    return [{
        "status": "completed",
        "type": action_type,
        "outcome": outcome,
    }]
```

Use only schema-valid ingredient/action/outcome values in every case.

- [ ] **Step 2: Write the complete failing detector test matrix**

Drive `session.act()` in worker threads using a `conveyor_profit` session. For
each request, return a completed `select_ingredient/tomato/
ingredient_not_available` result and a next observation whose substantive
conveyor fields are unchanged but whose observation ID and both clocks differ.
Assert turns one through four return `ready`. On turn five, assert the second
packet is exactly:

```python
{
    "type": "end_game",
    "protocol_version": 4,
    "observation_id": next_observation_id,
    "outcome": "failure",
    "reason": "strategy_stalled",
}
```

Send the matching `game_over` packet and assert the fifth `act()` returns the
formal terminal while retaining the fifth action result.

Before implementation, add separate tests proving:

- a state-changing first action plus four no-progress repeats does not trigger;
- a different action starts a new streak at one;
- changing each retained conveyor field clears the streak;
- changing only observation ID, clocks, capture time, screenshot, player,
  interface, bindings, or prior action results does not clear it;
- missing `conveyor` data cannot increment or reset a streak;
- empty, partial, error, blocked, cancelled, and stopped results contribute zero
  and preserve the prior completed streak even when the accompanying observation
  changed;
- invalid/stale requests and action timeout/recovery contribute zero and preserve
  the prior completed streak;
- detach plus a new hello/new round resets the streak;
- a formal game terminal immediately resets the streak, and the next attempt
  starts from zero;
- five valid repeated `find_contract` wait actions and ordinary observations
  never trigger the conveyor-only guard;
- when request cap and the fifth match coincide, the packet reason is
  `max_requests`;
- a gameplay terminal returned on the fifth call wins over both trusted failure
  reasons.

- [ ] **Step 3: Run the detector tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src /Users/aidy/Projects/.venv-cogito-deepagents/bin/python \
  -m pytest ai_play/tests/test_game_session.py -q
```

Expected: the positive terminal/reset/precedence tests FAIL because no stall
tracking exists; isolation tests may already pass.

- [ ] **Step 4: Implement narrow pure helpers**

In `game_session.py`, add constants and module-private helpers:

```python
CONVEYOR_STALL_TURN_LIMIT = 5
_CONVEYOR_STALL_FIELDS = (
    "window", "dish", "net_profit", "tray", "last_receipt",
    "market", "contracts", "finished",
)

def _conveyor_progress_fingerprint(observation):
    conveyor = observation.get("conveyor") if isinstance(observation, dict) else None
    if not isinstance(conveyor, dict):
        return None
    projected = {key: conveyor.get(key) for key in _CONVEYOR_STALL_FIELDS}
    return json.dumps(projected, sort_keys=True, separators=(",", ":"))

def _canonical_action_batch(actions):
    return json.dumps(actions, sort_keys=True, separators=(",", ":"))

def _results_match_actions(actions, results):
    return (
        isinstance(results, list)
        and len(results) == len(actions)
        and all(
            result.get("status") == "completed"
            and result.get("type") == action.get("type")
            for action, result in zip(actions, results)
        )
    )
```

Import `json` and use these immutable canonical strings for equality; do not serialize screenshots,
timestamps, clocks, player/interface state, or `last_action_results`.

- [ ] **Step 5: Add per-attempt tracking and reset points**

Initialize a previous candidate key and count in `GameSession.__init__`.
Reset both when `attach()` starts a new attempt, `detach()` disconnects, and a
terminal/stopped attempt is cleared. Also clear immediately in
`receive_game_over()`, `receive_stop()`, and `receive_stop_ack()` when those
paths establish their terminal/stopped result, rather than waiting for a later
attach. Do not mutate tracking on validation errors, stale IDs, timeouts, or
`recover_action`.

- [ ] **Step 6: Record only genuine candidates after a completed turn**

Inside `_execute_act()`'s condition lock, deep-copy the caller's action batch
*before* validation. Validate that snapshot, canonicalize it, capture the current
conveyor fingerprint, and dispatch the same snapshot so caller mutation cannot
change the batch between validation, transmission, and later result matching.
Return this private progress context with the completed result. After
`_execute_act()` returns `ready`, qualify results before inspecting fingerprints:

```python
if not _results_match_actions(validated_actions, result.action_results):
    pass  # preserve tracking unchanged
elif pre_fingerprint is None or post_fingerprint is None:
    pass  # preserve tracking unchanged
elif pre_fingerprint != post_fingerprint:
    self._clear_stall_tracking()
else:
    stalled = self._record_stall_candidate(
        canonical_actions, post_fingerprint
    )
```

A changed action or unchanged fingerprint starts a new candidate streak at one;
the fifth exact candidate returns `stalled=True`.

- [ ] **Step 7: Generalize the one-shot trusted terminal sender**

Refactor `_request_limit_result()` into a reason-taking private helper, keeping
its existing lock, `_end_game_sent`, `ending`, timeout, pending-results, and
game-over waiting behavior. Keep `_request_limit_result()` as a narrow wrapper
for `max_requests`. Add a `strategy_stalled` wrapper that requires a non-null
latest observation ID.

Enforce this order in `act()`:

1. gameplay-produced `game_over` result;
2. `request_number >= act_request_limit` -> `max_requests`;
3. qualifying fifth conveyor no-progress turn -> `strategy_stalled`;
4. ordinary ready result.

- [ ] **Step 8: Run the detector tests and verify GREEN**

Run the command from Step 3. Expected: PASS.

- [ ] **Step 9: Run all game-session tests**

```bash
PYTHONPATH=ai_play/src /Users/aidy/Projects/.venv-cogito-deepagents/bin/python \
  -m pytest ai_play/tests/test_game_session.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add ai_play/src/ai_play/game_session.py ai_play/tests/test_game_session.py
git commit -m "feat(ai-play): stop repeated conveyor stalls"
```

### Task 3: Prove durable failure handling

**Files:**
- Modify: `ai_play/tests/test_game_session.py`
- Modify: `ai_play/tests/test_workflow_memory.py`

- [ ] **Step 1: Write the failing logger/observer integration test**

Construct the conveyor session with both `RecordingLogger` and
`RecordingAttemptObserver`, drive five matching no-progress turns, acknowledge
the terminal, and assert each event list contains exactly:

```python
[
    ("start", "conveyor_profit"),
    ("finish", "failure", "strategy_stalled"),
]
```

Call repeated observe/detach cleanup paths and prove no second finish event is
added.

- [ ] **Step 2: Run the integration characterization test**

Run the exact new test with pytest. It may pass immediately because Task 2 now
produces a formal terminal and the shared durable path is already implemented.
Confirm it exercises the real five-turn session flow and exact event lists; no
production persistence change is required if the characterization passes.

- [ ] **Step 3: Add workflow-memory failure-only coverage**

Parameterize the existing `finish_failure()` helper with `scenario_id`, or build
the attempt explicitly as `conveyor_profit`, then finish it with reason
`strategy_stalled` and a compact failure review. Read and reload memory using
`conveyor_profit`; assert the completed attempt has that terminal reason,
workflow and landmarks remain empty, and only the allowed avoid/failure-review
lesson is persisted.

- [ ] **Step 4: Run focused persistence tests**

```bash
PYTHONPATH=ai_play/src /Users/aidy/Projects/.venv-cogito-deepagents/bin/python \
  -m pytest ai_play/tests/test_game_session.py ai_play/tests/test_workflow_memory.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_play/tests/test_game_session.py ai_play/tests/test_workflow_memory.py
git commit -m "test(ai-play): verify stalled strategy persistence"
```

### Task 4: Accept and display the formal Godot terminal

**Files:**
- Modify: `tests/ai_play/test_ai_play_controller.gd`
- Modify: `addons/cogito/AIPlay/ai_play_bridge.gd`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `tests/ai_play/test_ai_play_game_over_screen.gd`
- Modify: `addons/cogito/AIPlay/ai_play_game_over_screen.gd`

- [ ] **Step 1: Write failing bridge tests**

Extend the bridge test to accept the exact packet
`failure/strategy_stalled` with an integer observation ID. Continue rejecting
wrong outcome, unknown reason, non-integer/null stall IDs, extra fields, and
wrong protocol versions. Preserve null-ID compatibility only for
`max_requests`.

- [ ] **Step 2: Write failing controller tests**

Using the existing controller fixture, assert a current-ID stall request:

- is accepted for active `conveyor_profit`;
- emits one formal `game_over` packet with the same reason;
- follows normal disable/input-release behavior;
- is rejected for another active scenario;
- is rejected in READY or EXECUTING states; and
- is rejected for null, stale, or future observation IDs.

- [ ] **Step 3: Run the controller script and verify RED**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: nonzero exit with the new assertions failing.

- [ ] **Step 4: Implement bridge syntax validation**

In `ai_play_bridge.gd`, allow only:

```gdscript
packet["outcome"] == "failure"
and packet["reason"] in ["max_requests", "strategy_stalled"]
and (
    normalized_observation_id["valid"]
    or (
        packet["reason"] == "max_requests"
        and packet["observation_id"] == null
    )
)
```

- [ ] **Step 5: Implement controller semantic validation**

Add `["failure", "strategy_stalled"]` only to the `conveyor_profit` terminal
results. In `_on_end_game_received()`, retain universal `max_requests`, but
accept `strategy_stalled` only for `_active_scenario_id == "conveyor_profit"`
while `State.WAITING_FOR_DECISION`, and only when its parsed observation ID
exactly equals `_pending_observation_id`. Do not accept an executing-action ID.
Pass the validated reason to `_finish_game()`.

- [ ] **Step 6: Run the controller script and verify GREEN**

Run the command from Step 3. Expected: exit 0 and all assertions pass.

- [ ] **Step 7: Write the failing game-over copy test**

Add:

```gdscript
await _test_result(
    screen_scene,
    "failure",
    "strategy_stalled",
    "经营失败",
    "策略连续五次没有取得进展",
)
```

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
```

Expected: FAIL with generic fallback copy.

- [ ] **Step 8: Add dedicated UI copy and verify GREEN**

Add `strategy_stalled` to `OUTCOME_TEXT` and `REASON_TEXT` with the exact copy
from Step 7. Re-run both Godot scripts. Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add addons/cogito/AIPlay/ai_play_bridge.gd \
  addons/cogito/AIPlay/ai_play_controller.gd \
  addons/cogito/AIPlay/ai_play_game_over_screen.gd \
  tests/ai_play/test_ai_play_controller.gd \
  tests/ai_play/test_ai_play_game_over_screen.gd
git commit -m "feat(ai-play): finish stalled conveyor rounds"
```

### Task 5: Synchronize docs and run full verification

**Files:**
- Modify: `README_AI_PLAY.md`
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

- [ ] **Step 1: Update public documentation**

Document that only `conveyor_profit` has the five-turn repeated no-progress
guard, define progress only in terms of approved public conveyor fields, state
that clocks do not count as progress, and list formal
`failure/strategy_stalled`. Preserve protocol version 4 and existing
`max_requests` behavior. Do not include source paths, hidden supplies, campaign
IDs, recipes selected by the authored strategy, seeds, or puzzle answers in any
runtime-facing prompt/briefing.

- [ ] **Step 2: Run the affected Python suite**

```bash
PYTHONPATH=ai_play/src:. /Users/aidy/Projects/.venv-cogito-deepagents/bin/python \
  -m pytest ai_play/tests ai_host/tests tests/*.py \
  tests/conveyor_profit/test_protocol_parity.py -q
```

Expected: PASS with no new warnings attributable to this change.

- [ ] **Step 3: Run affected Godot contract tests**

```bash
godot --headless --path . --editor --quit
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
```

Expected: all commands exit 0 without parser, UID, or script errors.

- [ ] **Step 4: Run repository hygiene checks**

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only intended tracked files and the user's
pre-existing untracked `ak_new.py` and `scripts/` appear. The implementation
plan itself is committed before Task 1 and must not remain untracked.

- [ ] **Step 5: Commit documentation**

```bash
git add README_AI_PLAY.md ai_play/README.md docs/wiki/ai-play/system-guide.md
git commit -m "docs(ai-play): document conveyor stall failure"
```

- [ ] **Step 6: Review the final branch**

Inspect `git log --oneline` and `git diff <base>...HEAD --stat`. Confirm no
credentials, runtime screenshots, model transcripts, `.godot/`, caches, or log
artifacts are tracked. Do not launch a real external model as part of automated
verification.
