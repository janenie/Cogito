# Render-Synchronized Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Godot AI Play observation wait for a newly completed render frame before capture.

**Architecture:** Route the normal observation timer through the controller's generation-guarded `_capture_observation_if_current()` coroutine. Wait up to one second for normal rendering; when a background window produces no `frame_post_draw`, force one main-thread Viewport redraw before capture. Keep the MCP protocol and AI-visible behavior unchanged.

**Tech Stack:** Godot 4.7, GDScript, existing headless controller test harness.

---

### Task 1: Reproduce the timer-path race

**Files:**
- Modify: `tests/ai_play/test_ai_play_controller.gd`

- [ ] **Step 1: Write the failing test**

Add `_test_interval_recapture_waits_for_rendering()` to the controller test sequence. Build a connected fixture, finish a normal completed `move`, emit the timer timeout, and assert `capture_count` stays unchanged until a full process frame and `RenderingServer.frame_post_draw` have occurred; then assert exactly one new capture.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: FAIL because `_on_observation_timer_timeout()` captures immediately.

### Task 2: Route timer capture through the render fence

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`

- [ ] **Step 1: Implement the minimal production fix**

Change `_on_observation_timer_timeout()` to capture the current generation and schedule `_capture_observation_if_current(generation, _last_results)` instead of calling `_capture_observation()` directly.

Add a bounded render helper used by `_capture_observation_if_current()`: wait at most one second for `frame_post_draw`, disconnect its one-shot callback on timeout, call `RenderingServer.force_draw(false)`, then capture only after rechecking generation/state/lifecycle guards.

- [ ] **Step 2: Run the focused controller test**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: PASS.

- [ ] **Step 3: Verify the background-render fallback**

Add a controller regression case that withholds `frame_post_draw` and uses a short test timeout, then asserts one observation is captured instead of hanging. Extend the rendered look test to pause the normal render loop, change the camera, call `force_draw(false)`, and assert the Viewport pixels change.

- [ ] **Step 4: Run rendered behavior tests**

Run:

```bash
godot --path . --script tests/ai_play/test_ai_play_rendered_look.gd
godot --path . --script tests/ai_play/test_ai_play_rendered_recovery.gd
```

Expected: PASS with pixel-change and recovery assertions true.

### Task 3: Document and verify the affected contract

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

- [ ] **Step 1: Update documentation**

State that normal interval captures as well as immediate/recovery captures wait for `process_frame` and `RenderingServer.frame_post_draw`, entirely inside Godot and without consuming an AI action.

- [ ] **Step 2: Run affected regression tests**

Run the AI Play Python suite and the relevant Godot observer/executor/controller tests described in `docs/wiki/development/contributor-guide.md`.

- [ ] **Step 3: Run repository hygiene checks**

Run the secret scan used by the AI Play suite and:

```bash
git diff --check
```

- [ ] **Step 4: Commit and push**

Commit the verified implementation on `feature/session-awm` and push `origin/feature/session-awm`. Do not switch, merge, or clean up the branch/worktree.
