# Find Key 150 Request Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the `find_key` MCP `act` request hard cap from 200 to 150 while preserving the existing configurable lower cap and terminal behavior.

**Architecture:** Keep the scenario-specific cap in the existing Python scenario registry. Verify it through registry behavior and `GameSession` boundary behavior, then synchronize the current operator documentation without rewriting historical records.

**Tech Stack:** Python 3, pytest, Markdown.

## Global Constraints

- The `find_key` hard cap is exactly 150 `act` requests.
- The effective cap remains `min(150, AI_PLAY_MAX_ACT_REQUESTS)`.
- The 150th request keeps the existing success-first terminal ordering.
- Do not change other scenarios, bridge protocol, observations, or input release behavior.
- Preserve unrelated user changes already present in the working tree.

---

### Task 1: Change the tested runtime limit

**Files:**
- Modify: `ai_play/tests/test_scenarios.py`
- Modify: `ai_play/tests/test_game_session.py`
- Modify: `ai_play/src/ai_play/scenarios.py`

**Interfaces:**
- Consumes: `scenario_act_request_limit(scenario_id: str, configured_limit: int) -> int`.
- Produces: `find_key` effective request limits and `GameSession` terminal behavior capped at 150.

- [ ] **Step 1: Write the failing expectations**

Change the `find_key` registry assertions to:

```python
assert scenario_act_request_limit("find_key", 500) == 150
assert scenario_act_request_limit("find_key", 80) == 80
```

Rename the session test to `test_find_key_uses_150_request_hard_cap`, exercise 149 non-terminal requests, and assert the 150th non-terminal request returns `failure/max_requests`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd ai_play
python -m pytest tests/test_scenarios.py tests/test_game_session.py -q
```

Expected: failures show the runtime still returns or enforces 200 instead of 150.

- [ ] **Step 3: Apply the minimal production change**

In `ai_play/src/ai_play/scenarios.py`, change only:

```python
"find_key": ScenarioDefinition(
    briefing_loader=load_find_key_briefing,
    max_act_requests=150,
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run:

```bash
cd ai_play
python -m pytest tests/test_scenarios.py tests/test_game_session.py -q
```

Expected: all selected tests pass.

### Task 2: Synchronize current documentation and verify

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

**Interfaces:**
- Consumes: the tested 150-request runtime contract from Task 1.
- Produces: current operator documentation that states the same cap.

- [ ] **Step 1: Update current documentation**

Change only the current `find_key` hard-cap statements from 200 to 150. Do not edit historical files under `docs/superpowers/specs/` or earlier plans.

- [ ] **Step 2: Run the affected Python suite**

Run:

```bash
cd ai_play
python -m pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 3: Check the exact diff and whitespace**

Run:

```bash
git diff -- ai_play/src/ai_play/scenarios.py ai_play/tests/test_scenarios.py ai_play/tests/test_game_session.py ai_play/README.md docs/wiki/ai-play/system-guide.md
git diff --check
```

Expected: only the intended cap, tests, and current documentation change; `git diff --check` exits successfully.
