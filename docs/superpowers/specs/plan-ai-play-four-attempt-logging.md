# AI Play Four-Attempt Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep four AI play attempts in one trajectory run and rotate only when a fifth attempt starts.

**Architecture:** Preserve `TrajectoryLogger`'s bounded fixed-capacity run model and change its single capacity constant from three to four. Lock the behavior with the existing real-filesystem logger test and update the public logging documentation.

**Tech Stack:** Python 3.12, pytest, JSON trajectory files, Markdown documentation.

---

### Task 1: Lock the four-attempt boundary with a failing test

**Files:**
- Modify: `ai_play/tests/test_trajectory_logger.py`

- [x] **Step 1: Update the rotation test**

Rename the existing test to `test_collision_and_fifth_attempt_rotate_runs`.
Complete four failed attempts and assert the fourth attempt remains in
`20260724-14-35-02` as `attempt-04`. Then start attempt five and assert it
rotates to `20260724-14-35-03` as `attempt-01`.

- [x] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src /private/tmp/cogito-ai-play-py312/bin/python -m pytest ai_play/tests/test_trajectory_logger.py::test_collision_and_fifth_attempt_rotate_runs -q
```

Expected: FAIL because the fourth attempt currently rotates to the next run.

### Task 2: Implement the fixed four-attempt capacity

**Files:**
- Modify: `ai_play/src/ai_play/trajectory_logger.py`
- Test: `ai_play/tests/test_trajectory_logger.py`

- [x] **Step 1: Make the minimal production change**

Set:

```python
class TrajectoryLogger:
    MAX_ATTEMPTS = 4
```

- [x] **Step 2: Run the focused test and verify GREEN**

Run the focused test from Task 1.

Expected: `1 passed`.

- [x] **Step 3: Run the complete logger test module**

```bash
PYTHONPATH=ai_play/src /private/tmp/cogito-ai-play-py312/bin/python -m pytest ai_play/tests/test_trajectory_logger.py -q
```

Expected: all tests pass after updating assertions that intentionally expose
the run capacity.

### Task 3: Update the public contract and verify the affected suite

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

- [x] **Step 1: Document the four-attempt boundary**

In the trajectory logging section, state that one `run.json` contains at most
four attempts and the fifth starts a new timestamped run directory.

- [x] **Step 2: Run the full AI Play Python suite**

```bash
PYTHONPATH=ai_play/src /private/tmp/cogito-ai-play-py312/bin/python -m pytest ai_play/tests -q
```

Expected: all tests pass without real Codex, Godot, credentials, or network
calls.

- [x] **Step 3: Run final static verification**

```bash
git diff --check
```

Expected: exit code 0 with no output.

- [x] **Step 4: Commit and push**

Commit only the logger, its test, README, and this plan; preserve unrelated
untracked cache directories. Use subject:

```text
fix(ai-play): keep four attempts in one trajectory run
```

Push `feature/session-awm` to `origin`.
