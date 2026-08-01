# Loop Staircase Anomaly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone randomized ten-floor looping stairwell scene and register it as the `loop_staircase_anomaly` AI Play scenario.

**Architecture:** Put puzzle generation and scene state in a focused Godot manager script, with small interactable scripts for loop triggers and answer choices. Keep MCP-facing metadata in the existing AI Play registry and controller allowlists so Godot and the Python MCP server agree on scenario id, max request cap, briefing, and terminal results.

**Tech Stack:** Godot 4 GDScript scenes/tests, Cogito interaction components, Python pytest for `ai_play` scenario registry tests.

## Global Constraints

- Scenario id is `loop_staircase_anomaly`.
- Use ten observable floors: 2F through 10F.
- Use three observation loops.
- Use seeded random generation with deterministic output for the same seed.
- The final answer must be unique.
- The true floor must never receive an anomaly.
- Wrong answers immediately emit `failure: wrong_floor_selected`.
- Correct answers emit `success: correct_floor_selected`.
- MCP max act request cap is `160`.
- First playable implementation uses simple per-floor answer interactables, not a custom terminal UI.

---

### Task 1: Puzzle Model

**Files:**
- Create: `addons/cogito/DemoScenes/LoopStaircase/loop_staircase_manager.gd`
- Test: `tests/ai_play/test_loop_staircase_manager.gd`

**Interfaces:**
- Produces: `configure_round(seed_value: int = 0) -> void`
- Produces: `get_round_snapshot() -> Dictionary`
- Produces: `select_floor(floor_number: int) -> void`
- Produces signal: `game_finished(outcome: String, reason: String)`

- [ ] Write failing Godot tests for deterministic generation, unique answer, true floor stability, wrong answer failure, and correct answer success.
- [ ] Run the new Godot test and confirm it fails because the manager script does not exist.
- [ ] Implement the minimal puzzle generator and answer result logic.
- [ ] Run the Godot test and confirm it passes.

### Task 2: Playable Scene

**Files:**
- Modify: `addons/cogito/DemoScenes/LoopStaircase/loop_staircase_manager.gd`
- Create: `addons/cogito/DemoScenes/LoopStaircase/loop_staircase_loop_trigger.gd`
- Create: `addons/cogito/DemoScenes/LoopStaircase/loop_staircase_answer.gd`
- Create: `addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn`
- Test: `tests/ai_play/test_loop_staircase_scene.gd`

**Interfaces:**
- Consumes: `configure_round`, `get_round_snapshot`, `select_floor`, `game_finished`
- Produces playable scene at `res://addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn`

- [ ] Write failing scene test that loads the scene, confirms ten generated floor nodes, loop advancement, final answer visibility, and AIPlayController monitor wiring.
- [ ] Run the scene test and confirm it fails because the scene does not exist.
- [ ] Implement the scene and lightweight trigger/answer scripts.
- [ ] Run the scene test and confirm it passes.

### Task 3: AI Play MCP Contract

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Create: `ai_play/src/ai_play/loop_staircase_anomaly_briefing.py`
- Modify: `ai_play/src/ai_play/scenarios.py`
- Modify: `ai_play/tests/test_scenarios.py`
- Modify: `ai_play/tests/test_game_session.py`

**Interfaces:**
- Consumes Godot result reasons `correct_floor_selected`, `wrong_floor_selected`, `max_requests`
- Produces MCP scenario registry entry for `loop_staircase_anomaly`

- [ ] Write failing Python tests expecting `loop_staircase_anomaly` in supported scenarios, max cap `160`, briefing `game_id`, and terminal result allowlist.
- [ ] Run the Python tests and confirm they fail because the scenario is not registered.
- [ ] Add the briefing and registry/controller allowlist entries.
- [ ] Run the Python tests and confirm they pass.

### Task 4: Verification

**Files:**
- Review all files changed above.

- [ ] Run focused Godot tests for loop staircase manager and scene.
- [ ] Run focused Python AI Play tests.
- [ ] Run `git diff --check`.
- [ ] Report any unrelated pre-existing dirty worktree changes separately from this implementation.
