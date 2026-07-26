# Find Key 100 Request Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the `find_key` MCP `act` request hard cap from 150 to 100 while preserving the configurable lower cap and terminal behavior.

**Architecture:** Keep the cap in the existing Python scenario registry and expose the same value through the public briefing. Verify registry, session, and briefing behavior before synchronizing current operator documentation.

**Tech Stack:** Python 3.12, pytest, Markdown.

## Global Constraints

- The `find_key` hard cap is exactly 100 `act` requests.
- The effective cap remains `min(100, AI_PLAY_MAX_ACT_REQUESTS)`.
- The 100th request keeps the existing success-first terminal ordering.
- Do not change other scenarios, bridge protocol, observations, or input release behavior.
- Preserve unrelated user changes already present in the working tree.

---

### Task 1: Change the tested runtime and briefing limit

**Files:**
- Modify: `ai_play/tests/test_scenarios.py`
- Modify: `ai_play/tests/test_game_session.py`
- Modify: `ai_play/tests/test_briefing.py`
- Modify: `ai_play/src/ai_play/scenarios.py`
- Modify: `ai_play/src/ai_play/find_key_briefing.py`

**Interfaces:**
- Consumes: `scenario_act_request_limit(scenario_id: str, configured_limit: int) -> int`.
- Produces: a 100-request `find_key` effective cap through `GameSession` and its public briefing.

- [ ] **Step 1: Write the failing expectations**

Change the registry assertion to:

```python
assert scenario_act_request_limit("find_key", 500) == 100
```

Rename the session test to `test_find_key_uses_100_request_hard_cap`, assert
`session.act_request_limit == 100`, and assert `"100"` appears in the loaded
`find_key` briefing failure condition.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_game_session.py \
  ai_play/tests/test_briefing.py -q
```

Expected: assertions fail because runtime and briefing still expose 150.

- [ ] **Step 3: Apply the minimal production changes**

Change the `find_key` registry entry to:

```python
max_act_requests=100,
```

Change the public briefing failure condition to:

```python
"failure_condition": "最多允许 100 次 act 请求；达到上限仍未拾取钥匙则失败。",
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Step 2 command again. Expected: all selected tests pass.

### Task 2: Synchronize current documentation and verify

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

**Interfaces:**
- Consumes: the tested 100-request runtime contract from Task 1.
- Produces: current operator documentation matching runtime behavior.

- [ ] **Step 1: Update current documentation**

Change only the current `find_key` hard-cap statements from 150 to 100. Do not
edit historical files under `docs/superpowers/specs/` or earlier plans.

- [ ] **Step 2: Run the full AI Play Python suite**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
```

Expected: all tests pass. Bridge tests require permission to bind only
`127.0.0.1` on a temporary local port.

- [ ] **Step 3: Check exact diff and whitespace**

Run:

```bash
git diff -- ai_play/src/ai_play/scenarios.py \
  ai_play/src/ai_play/find_key_briefing.py \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_game_session.py \
  ai_play/tests/test_briefing.py \
  ai_play/README.md \
  docs/wiki/ai-play/system-guide.md
git diff --check
```

Expected: the intended cap, tests, briefing, and current documentation are
consistent; `git diff --check` exits successfully.
