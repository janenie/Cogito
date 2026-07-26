# AI Play Supervisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small Godot terminal marker plus local supervisor/orchestrator scripts for three black-box `find_contract` attempts.

**Architecture:** Godot emits and optionally exits on a validated `game_over`; the supervisor consumes only process output and exit state. An orchestrator can create a fresh player workspace/log root and start both isolated Codex and the supervisor.

**Tech Stack:** Godot 4 GDScript, Python 3 standard library, existing shell/Godot tests.

## Global Constraints

- AI enablement remains explicit through `-- --ai-play`.
- Godot bridge remains bound to `127.0.0.1`.
- Supervisor must not read trajectory logs, screenshots, source files for gameplay hints, or model context.
- `--ai-play-exit-on-game-over` only exits when `--ai-play` is also present.
- Always finish verification with `git diff --check`.

---

### Task 1: Godot Terminal Marker

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Test: `tests/ai_play/test_ai_play_controller.gd`

**Interfaces:**
- Produces: `_should_exit_on_game_over_for_user_args(user_args: Array) -> bool`
- Produces: `AI_PLAY_GAME_OVER outcome=<outcome> reason=<reason>` stdout marker

- [ ] Add failing tests for the exit flag predicate.
- [ ] Implement the predicate and terminal marker.
- [ ] Exit with code `0` on success and `1` on failure only when the predicate is true.
- [ ] Run `godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd`.

### Task 2: Supervisor Script

**Files:**
- Create: `tools/ai_play_supervisor.py`
- Create: `tests/test_ai_play_supervisor.py`
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/wiki/development/contributor-guide.md`

**Interfaces:**
- Produces: CLI `python3 tools/ai_play_supervisor.py --runs 3 --scenario find_contract`
- Produces: summary entries with `attempt`, `status`, `reason`, `exit_code`, and `retries`

- [ ] Add failing tests for marker parsing and timeout/abnormal retry handling.
- [ ] Implement the supervisor with finite retries and live output forwarding.
- [ ] Document isolated-player usage and supervisor command.
- [ ] Run `PYTHONPATH=ai_play/src .venv/bin/python -m pytest tests/test_ai_play_supervisor.py -q`.

### Task 3: Verification

**Files:**
- No new production files.

- [ ] Run `bash tests/check_ai_play_lobby.sh`.
- [ ] Run relevant Python tests.
- [ ] Run relevant Godot controller test if Godot is available.
- [ ] Run `git diff --check`.

### Task 4: Codex Orchestrator

**Files:**
- Create: `tools/ai_play_codex_orchestrator.py`
- Create: `tests/test_ai_play_codex_orchestrator.py`
- Modify: `README.md`
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/wiki/development/contributor-guide.md`

**Interfaces:**
- Produces: CLI `python3 tools/ai_play_codex_orchestrator.py --runs 3 --scenario find_contract`
- Produces: fresh run directories under `--session-root`
- Produces: `player_workspace/ai_play_run_config.json` containing `ai_play_log_root`
- Produces: `player_workspace/mcplogs/` as the per-run `AI_PLAY_LOG_ROOT`

- [ ] Add failing tests for fresh run paths, config writing, Codex command construction, and child environment.
- [ ] Implement the orchestrator with isolated player workspace and per-run `AI_PLAY_LOG_ROOT`.
- [ ] Document the one-command managed run.
- [ ] Run `PYTHONPATH=ai_play/src .venv/bin/python -m pytest tests/test_ai_play_codex_orchestrator.py -q`.
