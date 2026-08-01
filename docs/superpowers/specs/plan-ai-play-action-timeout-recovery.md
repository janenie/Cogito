# AI Play Action Timeout Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover a timed-out action in the same Godot run from the actual post-cancellation world state, without returning a stale observation or triggering a supervisor retry.

**Architecture:** Protocol v4 adds a Python-to-Godot `recover_action` packet. `GameSession` enters a dedicated recovering state after an action deadline, blocks new actions, and waits for a different observation ID. `AIPlayController` handles recovery in executing, capture-pending, and already-observed races while preserving applied world changes.

**Tech Stack:** Python 3.14, pytest, Godot 4.7, GDScript, loopback WebSocket protocol.

---

### Task 1: Python recovery state machine

**Files:**
- Modify: `ai_play/src/ai_play/game_session.py`
- Test: `ai_play/tests/test_game_session.py`

- [ ] **Step 1: Write failing tests for timeout recovery**

Add tests that assert the timeout sends an exact protocol-v4 recovery packet, a second `act` raises
`action_recovery_in_progress`, `observe` does not return observation 7, and observation 8 restores ready:

```python
with pytest.raises(SessionError, match="action_timeout"):
    session.act(7, actions, timeout=0.01)
assert sent[-1] == {
    "type": "recover_action",
    "protocol_version": 4,
    "observation_id": 7,
    "reason": "action_timeout",
}
with pytest.raises(SessionError, match="action_recovery_in_progress"):
    session.act(7, actions, timeout=0.01)
session.receive_observation(observation(8))
assert session.observe(timeout=0.1).observation["observation_id"] == 8
```

- [ ] **Step 2: Verify the focused tests fail for missing recovery behavior**

Run: `PYTHONPATH=ai_play/src /tmp/cogito-ai-play-test-venv/bin/python -m pytest ai_play/tests/test_game_session.py -q`

Expected: assertions fail because the session returns to `ready`, sends protocol 3 packets, and exposes the cached observation.

- [ ] **Step 3: Implement the minimal Python recovery state**

Set `PROTOCOL_VERSION = 4`, add `_recovering_observation_id`, and on the action deadline send:

```python
{
    "type": "recover_action",
    "protocol_version": PROTOCOL_VERSION,
    "observation_id": observation_id,
    "reason": "action_timeout",
}
```

Keep `_state = "recovering"`; make `_require_ready_action_state_locked` reject it; make `observe`
wait instead of returning `_latest_observation`; clear recovery only when a different valid observation arrives.
Allow validated late results for the recovering ID to be discarded. Give legal game-over and disconnect states priority.

- [ ] **Step 4: Verify Python recovery tests pass**

Run: `PYTHONPATH=ai_play/src /tmp/cogito-ai-play-test-venv/bin/python -m pytest ai_play/tests/test_game_session.py -q`

Expected: all game-session tests pass.

### Task 2: Bridge protocol-v4 recovery routing

**Files:**
- Modify: `ai_play/src/ai_play/bridge_server.py`
- Modify: `addons/cogito/AIPlay/ai_play_bridge.gd`
- Test: `ai_play/tests/test_bridge_server.py`
- Test: `tests/ai_play/test_ai_play_controller.gd`

- [ ] **Step 1: Write failing bridge tests**

Assert Python emits version 4 and the Godot bridge exposes a `recover_action_received` signal only for:

```json
{"type":"recover_action","protocol_version":4,"observation_id":7,"reason":"action_timeout"}
```

Also assert extra keys, booleans, fractional IDs, other reasons, and protocol 3 are rejected.

- [ ] **Step 2: Verify bridge tests fail**

Run: `PYTHONPATH=ai_play/src /tmp/cogito-ai-play-test-venv/bin/python -m pytest ai_play/tests/test_bridge_server.py -q`

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd`

Expected: protocol-version and missing-signal assertions fail.

- [ ] **Step 3: Route the exact recovery packet**

Add `signal recover_action_received(request: Dictionary)` to the Godot bridge and route the validated type.
Update Python/Godot protocol constants and all hello fixtures to version 4. Keep the exact numeric loopback and packet-size boundaries unchanged.

- [ ] **Step 4: Verify bridge tests pass**

Run the two focused commands from Step 2 and expect both to pass.

### Task 3: Godot same-run recovery controller

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `addons/cogito/AIPlay/ai_play_executor.gd`
- Test: `tests/ai_play/test_ai_play_controller.gd`
- Test: `tests/ai_play/test_ai_play_executor.gd`

- [ ] **Step 1: Write failing controller race tests**

Cover these independent states:

```gdscript
# EXECUTING: cancel remaining work, keep controller enabled, force observation 18.
# READY after batch_finished: invalidate delayed capture and force observation 18.
# WAITING_FOR_DECISION with observation 18: duplicate recovery for 17 is a no-op.
# A mismatched current ID or malformed request disables and releases inputs.
```

The executing fixture must record `action_timeout` cancellation without reporting an old action result packet.

- [ ] **Step 2: Verify the controller tests fail**

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd`

Expected: recovery signal/state handling assertions fail.

- [ ] **Step 3: Implement recovery across controller races**

Connect `recover_action_received`. Track `_recovering_observation_id` and `_last_completed_observation_id`.
For matching executing recovery, mark recovery before `cancel_all("action_timeout")` so the synchronous
`batch_finished` callback suppresses the old `action_results`. For matching READY recovery, stop the timer.
In both cases increment capture generation and schedule `_capture_observation_if_current` with cancelled
last results. Treat an old recovery after a newer pending observation as an idempotent no-op. Remove the
temporary duplicate-`action_batch` recovery behavior.

- [ ] **Step 4: Verify Godot unit tests pass**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: both scripts print their passed markers and exit 0.

### Task 4: Rendered recovery integration

**Files:**
- Create: `tests/ai_play/test_ai_play_rendered_recovery.gd`

- [ ] **Step 1: Write a failing graphical recovery test**

Launch the player/controller fixture, begin a timed movement, allow at least one process frame of movement,
emit `recover_action`, and assert:

```gdscript
_assert(player.global_position != spawn_position, "partial movement is preserved")
_assert(controller.get_state() != controller.State.DISABLED, "recovery keeps AI enabled")
_assert(latest_observation_id > timed_out_id, "recovery emits a fresh observation")
_assert(latest_image_hash != old_image_hash, "recovery captures the actual current view")
```

- [ ] **Step 2: Verify the rendered test fails before full integration**

Run: `godot --path . --script tests/ai_play/test_ai_play_rendered_recovery.gd`

Expected: missing recovery routing or fresh-observation assertion fails.

- [ ] **Step 3: Make only fixture-level adjustments required by the test**

Reuse the existing rendered-look fixture patterns and real executor/controller. Do not introduce production
shortcuts or hidden state into MCP observations.

- [ ] **Step 4: Verify the rendered test passes**

Run the command from Step 2 and expect exit 0 with a recovery passed marker.

### Task 5: Documentation, full verification, and publication

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `tests/test_ai_play_codex_orchestrator.py` only if protocol text is asserted there

- [ ] **Step 1: Replace temporary duplicate-batch documentation**

Document protocol 4, `recover_action`, Python `recovering`, preservation of partial effects, fresh observation
requirements, no request-count/AWM impact, and supervisor behavior. Remove claims that repeated
`action_batch` is the recovery mechanism.

- [ ] **Step 2: Run affected full suites**

Run:

```bash
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-test-venv/bin/python -m pytest ai_play/tests -q
/tmp/cogito-ai-play-test-venv/bin/python -m pytest tests/test_ai_play_codex_orchestrator.py tests/test_ai_play_supervisor.py tests/test_find_contract_awm_comparison.py -q
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --path . --script tests/ai_play/test_ai_play_rendered_recovery.gd
git diff --check
```

Expected: all suites pass and diff check is clean.

- [ ] **Step 3: Commit and push intentionally**

Stage only the spec, plan, protocol implementation, tests, README and Wiki. Do not stage `__pycache__` or runtime logs.

```bash
git commit -m "fix(ai-play): recover timed-out actions in place"
git push origin feature/session-awm
```
