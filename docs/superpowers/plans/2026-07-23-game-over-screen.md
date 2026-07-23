# Find Contract Game Over Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display a terminal result for Find Contract and freeze all further game input.

**Architecture:** A dedicated full-screen Control renders the result and pauses the SceneTree. The terminal monitor displays keypad outcomes, while the AI controller forwards request-limit outcomes through the same interface.

**Tech Stack:** Godot 4, GDScript, `.tscn` scenes, headless SceneTree tests.

## Global Constraints

- Correct password displays success.
- Wrong password and 1000 AI requests display failure.
- Manual and AI password entry behave identically.
- The result cannot be dismissed and all gameplay remains paused.

---

### Task 1: Result Screen

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_game_over_screen.gd`
- Create: `addons/cogito/AIPlay/ai_play_game_over_screen.tscn`
- Create: `tests/ai_play/test_ai_play_game_over_screen.gd`

**Interfaces:**
- Produces: `show_result(outcome: String, reason: String) -> void`

- [x] **Step 1: Write the failing test**

Test success and failure copy, visibility, and `SceneTree.paused`.

- [x] **Step 2: Run test to verify it fails**

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd`
Expected: FAIL because the result-screen scene does not exist.

- [x] **Step 3: Write minimal implementation**

Create a full-screen, input-blocking Control with title, outcome, and reason
labels. `show_result` fills the labels, shows the Control, and pauses the tree.

- [x] **Step 4: Run test to verify it passes**

Run the command from Step 2 and expect exit code 0.

### Task 2: Terminal Integration

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_find_contract_terminal.gd`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `tests/ai_play/test_ai_play_controller.gd`

**Interfaces:**
- Consumes: `show_result(outcome: String, reason: String) -> void`
- Produces: keypad and request-limit terminal outcomes shown exactly once.

- [x] **Step 1: Extend controller tests**

Record `show_result` calls in `FakeTerminalMonitor` and assert correct,
incorrect, local limit, and remote limit outcomes are displayed.

- [x] **Step 2: Run the controller test to verify it fails**

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd`
Expected: FAIL because no result is forwarded.

- [x] **Step 3: Implement forwarding**

Add an exported result-screen reference to the terminal monitor. Display keypad
results there and have the controller use the monitor for all terminal paths.

- [x] **Step 4: Run focused tests**

Run both AI Play Godot tests and expect exit code 0.

### Task 3: Lobby Wiring and Regression

**Files:**
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`
- Modify: `tests/check_ai_play_lobby.sh`

**Interfaces:**
- Consumes: the reusable result-screen scene.
- Produces: a configured `GameOverScreen` under `TerminalMonitor`.

- [x] **Step 1: Add a failing scene assertion**

Require the screen instance and terminal reference in the Lobby.

- [x] **Step 2: Run the scene check to verify it fails**

Run: `bash tests/check_ai_play_lobby.sh`
Expected: FAIL because the screen is not wired.

- [x] **Step 3: Wire the screen**

Add the packed scene resource, child instance, and exported NodePath.

- [x] **Step 4: Run regression tests and commit**

Run all AI Play Godot tests, Lobby checks, and the Python AI Play suite before
committing the verified implementation.
