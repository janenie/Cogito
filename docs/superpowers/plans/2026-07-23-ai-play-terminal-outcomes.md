# AI Play Terminal Outcomes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Return and persist an explicit success or failure when `find_contract`
checks a password or consumes 1000 model decision requests.

**Architecture:** Python owns the model-request counter and annotates every
action batch. Godot owns authoritative gameplay outcomes through a keypad
result signal and a scene-specific terminal monitor. The controller combines
both sources with password-result priority and sends one `game_over` packet
back to the sidecar.

**Tech Stack:** Godot 4.7 GDScript, Python 3, synchronous `websockets`, pytest.

## Global Constraints

- Count one validated observation's top-level model decision call as one
  request; SDK retries do not increment the gameplay count.
- Allow request 1000's action batch to execute.
- Correct password wins, wrong password fails immediately, and a non-terminal
  request-1000 batch fails.
- Never expose the configured passcode in protocol packets or logs.
- Terminal handling must release controls and emit at most one result.

---

### Task 1: Keypad Result Signal

**Files:**
- Modify: `addons/cogito/CogitoObjects/cogito_keypad.gd`
- Modify: `tests/ai_play/test_ai_play_controller.gd`

**Interfaces:**
- Produces: `signal code_checked(is_correct: bool)`, emitted at the beginning of
  `check_entered_code()` after computing the comparison result.

- [ ] Add a failing Godot test that enters a complete correct code and a
  complete incorrect code and asserts exactly one boolean signal for each.
- [ ] Run the focused Godot test and confirm it fails because the signal does
  not exist.
- [ ] Add `code_checked` without changing normal unlock, error-color, clear, or
  close behavior.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Sidecar Request Counter

**Files:**
- Modify: `ai_play/src/ai_play/config.py`
- Modify: `ai_play/src/ai_play/agent_loop.py`
- Modify: `ai_play/tests/test_config.py`
- Modify: `ai_play/tests/test_agent_loop.py`

**Interfaces:**
- Produces: `Config.max_model_requests: int`, default `1000`.
- Produces: action-batch integer fields `request_count` and `request_limit`.
- Produces: a terminal response with `failure/max_requests` if request 1000
  cannot produce a valid action batch.

- [ ] Add failing tests for the default and validated request limit.
- [ ] Add failing tests proving consecutive decisions emit counts 1 and 2,
  while a multi-action response increments only once.
- [ ] Add a failing test proving an API/parse failure on the configured final
  request returns `game_over` rather than another recoverable error.
- [ ] Run the focused pytest files and confirm the expected failures.
- [ ] Implement the counter and exact packet metadata with no SDK-retry
  instrumentation.
- [ ] Re-run focused pytest and confirm it passes.

### Task 3: Godot Terminal Monitor and Controller

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_find_contract_terminal.gd`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`
- Modify: `tests/ai_play/test_ai_play_controller.gd`

**Interfaces:**
- `AIPlayFindContractTerminal` consumes `CogitoKeypad.code_checked`.
- It emits `game_finished(outcome: String, reason: String)`.
- `AIPlayController` sends:

```json
{
  "type": "game_over",
  "protocol_version": 1,
  "observation_id": 17,
  "outcome": "failure",
  "reason": "wrong_password",
  "request_count": 37
}
```

- [ ] Add failing controller tests for correct password, wrong password,
  non-terminal request 1000, password result on request 1000, duplicate
  callbacks, and held-input cancellation.
- [ ] Run the controller test and confirm failures are caused by missing
  terminal behavior.
- [ ] Implement the scene-specific monitor and connect it to `ARCHIVE/Keypad`.
- [ ] Validate `request_count` and `request_limit` before executing a batch.
- [ ] After a batch result is sent, terminate at the request limit only if no
  password result already terminated the session.
- [ ] Make `_finish_game` idempotent, send one packet, then call existing
  disable/cancellation paths.
- [ ] Re-run controller, executor, observer, and interaction-probe tests.

### Task 4: Sidecar Protocol, Logging, and Documentation

**Files:**
- Modify: `ai_play/src/ai_play/bridge_server.py`
- Modify: `ai_play/src/ai_play/agent_loop.py`
- Modify: `ai_play/tests/test_bridge_server.py`
- Modify: `ai_play/tests/test_agent_loop.py`
- Modify: `ai_play/README.md`
- Modify: `ai_play/.env.example`

**Interfaces:**
- Consumes the exact Godot `game_over` packet from Task 3.
- Produces a `game_over` JSONL event with `outcome`, `reason`, and
  `request_count`, then closes the controller session.

- [ ] Add failing bridge tests for valid success/failure packets and rejection
  of extra fields, invalid reasons, invalid counts, and stale observation IDs.
- [ ] Add a failing logger test for the exact terminal event.
- [ ] Run the focused pytest tests and confirm expected failures.
- [ ] Implement strict protocol validation and terminal logging.
- [ ] Document `AI_PLAY_MAX_MODEL_REQUESTS=1000`, request-count semantics, and
  all three result reasons.
- [ ] Run `PYTHONPATH=ai_play/src .venv/bin/pytest ai_play/tests -q`.
- [ ] Run all four Godot AI Play test scripts and `git diff --check`.
