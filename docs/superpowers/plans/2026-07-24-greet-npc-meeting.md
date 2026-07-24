# Greet NPC Meeting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fourth AI-playable Lobby game where the player reads a task card, greets a patrolling NPC within 1 meter using one of three randomized greetings, enters the meeting room, and closes the meeting room door within 100 MCP act requests.

**Architecture:** Follow the existing multi-scenario pattern: one focused Godot monitor under `AIPlayController`, one Python scenario/briefing loader, scenario-specific terminal whitelist, docs, and tests. Reuse the existing `FriendlyHumanNPC`, its route markers, the existing meeting-room door, and the shared Lobby scene.

**Tech Stack:** Godot 4.7 GDScript, Python MCP scenario registry, shell/Godot headless tests.

## Global Constraints

- Scenario ID is `greet_npc_meeting`.
- MCP hard cap is 100 `act` requests.
- Success terminal is `success/meeting_door_closed`.
- Failure terminal is `failure/max_requests`.
- NPC greeting must occur first and only counts within 1 meter.
- Greeting phrase is selected per round from `你好`, `要去开会了么？`, and `hi`.
- The public briefing must not expose route points, scene paths, random seed, or hidden state.

---

### Task 1: Python scenario registry and briefing

**Files:**
- Create: `ai_play/src/ai_play/greet_npc_meeting_briefing.py`
- Modify: `ai_play/src/ai_play/scenarios.py`
- Modify: `ai_play/tests/test_scenarios.py`
- Modify: `ai_play/tests/test_briefing.py`
- Modify: `ai_play/tests/test_game_session.py`

- [ ] Add failing tests for registry support, 100-step cap, terminal whitelist, and public briefing privacy.
- [ ] Implement the briefing loader and scenario registry entry.
- [ ] Run the three Python test files.

### Task 2: Godot NPC greeting and scenario monitor

**Files:**
- Modify: `addons/cogito/DemoScenes/friendly_human_npc.gd`
- Create: `addons/cogito/AIPlay/ai_play_greet_npc_meeting_monitor.gd`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `addons/cogito/AIPlay/ai_play_game_over_screen.gd`
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`
- Create: `tests/ai_play/test_ai_play_greet_npc_meeting_monitor.gd`
- Create: `tests/check_ai_play_greet_npc_meeting_monitor.sh`
- Modify: `tests/check_ai_play_lobby.sh`

- [ ] Add failing Godot headless test for round initialization, randomized greeting/route start, greeting gate, and successful meeting-door close.
- [ ] Add NPC greeting signal and 1-meter acceptance.
- [ ] Add monitor that opens the meeting door at round start, starts NPC loop at a random point, writes task card, and emits success only after greeting plus door close in the meeting room.
- [ ] Wire the monitor into the Lobby scene and static scene checks.
- [ ] Run Godot and shell checks.

### Task 3: Documentation

**Files:**
- Create: `game_script/greet_npc_meeting.md`
- Modify: `README_AI_PLAY.md`
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

- [ ] Document gameplay rules, launch commands, 100-step cap, terminal reasons, and privacy constraints.
- [ ] Run `git diff --check`.
