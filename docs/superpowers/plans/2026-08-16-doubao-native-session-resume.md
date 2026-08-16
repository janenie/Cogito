# Doubao Native Codex Session Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep Doubao gameplay in one native Codex session across normally completed turns, and stop only on a trusted Supervisor terminal, an explicit safety limit, signal, or infrastructure error.

**Architecture:** The Doubao wrapper owns one temporary `CODEX_HOME` and proxy, starts one non-ephemeral `codex exec`, then sequentially invokes `codex exec resume --last` after exit code 0. The common orchestrator gains an opt-in immediate-player-stop policy for Supervisor terminal events, while all existing players retain their final-response grace behavior.

**Tech Stack:** Python 3, Codex CLI non-interactive `exec`/`resume`, pytest, Cogito AI Play MCP/Supervisor.

---

## File map

- `tools/ai_play_codex_doubao_orchestrator.py`: Doubao-only initial/resume command construction, wrapper-lifetime signal handling, native resume loop, CLI and metadata.
- `tools/ai_play_orchestrator_common.py`: generic opt-in policy to terminate a player immediately after Supervisor exit.
- `tests/test_ai_play_codex_doubao_orchestrator.py`: command, lifecycle, limit, secret-isolation, and native resume integration coverage.
- `tests/test_ai_play_codex_orchestrator.py`: common orchestrator regression and immediate-stop behavior.
- `ai_play/README.md`: operator-facing Doubao CLI and lifecycle documentation.
- `docs/wiki/ai-play/system-guide.md`: long-term architecture and safety contract.

### Task 1: Add Supervisor-terminal immediate stop policy

**Files:**
- Modify: `tools/ai_play_orchestrator_common.py:604-742`
- Test: `tests/test_ai_play_codex_orchestrator.py:998-1090`

- [ ] **Step 1: Write a failing test**

Add a common-orchestrator test that passes `stop_player_on_supervisor_exit=True`, makes Supervisor exit while the player is still running, and asserts the player is terminated immediately instead of being polled through `player_final_grace_seconds`. Retain the existing test proving the default permits a final response.

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `.venv/bin/pytest tests/test_ai_play_codex_orchestrator.py -k 'supervisor_terminal_exit' -q`

Expected: FAIL because `run_orchestrated_session` does not accept `stop_player_on_supervisor_exit`.

- [ ] **Step 3: Implement the opt-in policy**

Add `stop_player_on_supervisor_exit: bool = False` to `run_orchestrated_session`. When Supervisor exits and the flag is true, terminate the player before returning the Supervisor code; otherwise preserve `_finish_after_supervisor` unchanged.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `.venv/bin/pytest tests/test_ai_play_codex_orchestrator.py -k 'supervisor_terminal_exit' -q`

Expected: PASS.

- [ ] **Step 5: Commit the common lifecycle change**

Commit: `fix(ai-play): stop resumable player at supervisor terminal`

### Task 2: Build native initial and resume commands

**Files:**
- Modify: `tools/ai_play_codex_doubao_orchestrator.py:303-360`
- Test: `tests/test_ai_play_codex_doubao_orchestrator.py:220-280`

- [ ] **Step 1: Write failing command and CLI tests**

Assert the Doubao initial command is exactly based on `codex exec --cd <workspace> --skip-git-repo-check -` and excludes `--ephemeral`. Assert the resume command uses `codex exec resume --last --skip-git-repo-check -`. Update defaults to expose `--codex-max-resumes 8` and reject the removed `--codex-max-restarts` spelling.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `.venv/bin/pytest tests/test_ai_play_codex_doubao_orchestrator.py -k 'command or defaults or restart' -q`

Expected: FAIL because Doubao delegates to the generic ephemeral command and has no resume command.

- [ ] **Step 3: Implement minimal builders and argument migration**

Create Doubao-specific `build_codex_initial_command` and `build_codex_resume_command`. Rename the recovery text builder to `build_player_resume_prompt`; add `--runs` and `--max-resumes` to the internal wrapper command so the wrapper can construct the correct recovery prompt. Rename the public option to `--codex-max-resumes`.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `.venv/bin/pytest tests/test_ai_play_codex_doubao_orchestrator.py -k 'command or defaults or restart or resume_prompt' -q`

Expected: PASS.

- [ ] **Step 5: Commit the command contract**

Commit: `feat(ai-play): add native Doubao resume commands`

### Task 3: Keep the wrapper alive across native Codex turns

**Files:**
- Modify: `tools/ai_play_codex_doubao_orchestrator.py:360-525`
- Test: `tests/test_ai_play_codex_doubao_orchestrator.py:280-560`
- Test: `tests/test_ai_play_codex_orchestrator.py:869-998`

- [ ] **Step 1: Write failing lifecycle tests**

Use queued fake processes to prove: exit 0 starts one resume in the same `CODEX_HOME`, cwd, proxy, and environment; the first stdin is the full player prompt and the second is the recovery prompt; nonzero exits return unchanged; reaching the configured resume limit returns exact constant `NATIVE_RESUME_LIMIT_EXIT_CODE = 6`; a signal recorded between turns prevents another `Popen`; proxy and relay failures still terminate the current child. Before implementation, also update the Doubao `main` test to require `player_restart_limit=0`, `player_restart_prompt=None`, `stop_player_on_supervisor_exit=True`, and safe `native_resume_limit` metadata. Add a common-runner characterization test whose Doubao-labeled player exits with code 6 while Supervisor is still running; assert the runner returns 6 directly, starts the player exactly once, does not restart or emit a fabricated `game_over`. Normal `finally` cleanup may terminate the still-running Supervisor; that cleanup is not Run advancement.

- [ ] **Step 2: Run lifecycle tests and confirm RED**

Run: `.venv/bin/pytest tests/test_ai_play_codex_doubao_orchestrator.py -k 'internal_wrapper or monitor' -q`

Also run the Doubao main test and confirm RED, then run the common-runner characterization and confirm it already PASSES:

```bash
.venv/bin/pytest tests/test_ai_play_codex_doubao_orchestrator.py \
  -k 'main_wires_wrapper' -q
.venv/bin/pytest tests/test_ai_play_codex_orchestrator.py \
  -k 'native_resume_limit_is_infrastructure_failure' -q
```

Expected: FAIL because `run_internal_player` starts only one generic ephemeral process and signal handlers cover only that process.

- [ ] **Step 3: Implement the native resume loop**

Install one signal-capture context around the proxy and temporary-home lifetime. Track the current child for immediate forwarding/termination, check the captured stop signal before every spawn, and sequentially run the initial command followed by at most `max_resumes` resume commands. Return `NATIVE_RESUME_LIMIT_EXIT_CODE` on limit exhaustion and never synthesize `game_over`.

- [ ] **Step 4: Wire Doubao main and metadata**

Pass `runs` and the native resume limit into the internal wrapper command. Call the common orchestrator with `player_restart_limit=0`, `player_restart_prompt=None`, and `stop_player_on_supervisor_exit=True`. Record `player_restart_limit: 0` and `native_resume_limit: <value>` without credentials. Do not add any synthetic terminal event or Run-advance signal.

- [ ] **Step 5: Run the Doubao unit suite and confirm GREEN**

Run:

```bash
.venv/bin/pytest tests/test_ai_play_codex_doubao_orchestrator.py -q
.venv/bin/pytest tests/test_ai_play_codex_orchestrator.py \
  -k 'native_resume_limit_is_infrastructure_failure' -q
```

Expected: PASS.

- [ ] **Step 6: Commit wrapper behavior**

Commit: `fix(ai-play): resume Doubao in one Codex session`

### Task 4: Verify real Codex resume locally without real credentials

**Files:**
- Modify: `tests/test_ai_play_codex_doubao_orchestrator.py:620-790`

- [ ] **Step 1: Extend the fake-upstream integration fixture**

Add/retain the exact test name `test_codex_proxy_routes_flat_function_call_to_mcp_across_native_resume`. Run the native Codex binary against the fake upstream and fake MCP. Make the first Codex process complete normally. On `resume --last`, return a tool call that leaves the same process waiting on a controlled event after the MCP call is observed. Wrap the real `subprocess.Popen` in an injected `popen_factory` that records every command and delegates to the real process.

- [ ] **Step 2: Terminate the wrapper and assert bounded cleanup**

Use an event wait capped at 10 seconds, then send SIGTERM after the resumed MCP call is observed. Assert the wrapper returns `128 + SIGTERM`, exactly two recorded commands are the initial command and one `resume --last`, no third Codex process is spawned, the captured temporary home no longer exists, and the loopback proxy no longer listens. Release every blocked fake-upstream event in `finally`. Do not forbid multiple Responses requests inside the same Codex process because those are Codex's native tool loop.

- [ ] **Step 3: Run the integration test**

Run: `.venv/bin/pytest tests/test_ai_play_codex_doubao_orchestrator.py -k 'proxy_routes_flat_function_call_to_mcp_across_native_resume' -q`

Expected: PASS without contacting Yibu or starting Godot.

- [ ] **Step 4: Commit integration coverage**

Commit: `test(ai-play): cover native Codex session resume`

### Task 5: Update operator documentation and verify the repository

**Files:**
- Modify: `ai_play/README.md:310-335`
- Modify: `docs/wiki/ai-play/system-guide.md:260-280`

- [ ] **Step 1: Update both documentation surfaces**

Document removal of `--ephemeral`, use of the same temporary `CODEX_HOME` with `exec resume --last`, `--codex-max-resumes`, immediate stop after Supervisor terminal, and the fact that limit exhaustion is infrastructure failure rather than a fabricated game result.

- [ ] **Step 2: Run focused and full Python verification**

Run: `.venv/bin/pytest tests/test_ai_play_codex_orchestrator.py tests/test_ai_play_codex_doubao_orchestrator.py -q`

Then run:

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest \
  ai_play/tests ai_host/tests tests/*.py \
  tests/conveyor_profit/test_protocol_parity.py -q
```

Expected: all tests PASS.

- [ ] **Step 3: Run static, secret, and diff checks**

Run:

```bash
bash tests/check_ai_play_lobby.sh
bash tests/check_ai_play_repair_lighting_circuit_monitor.sh
bash tests/check_ai_play_arrange_meeting_briefings_monitor.sh
bash tests/check_ai_play_garden.sh
bash tests/check_ai_play_start_script.sh
bash tests/check_friendly_human_npc.sh
bash tests/check_lobby_friendly_npc.sh
bash tests/test_ai_play_secret_scan.sh
if [ ! -x .venv/bin/sphinx-build ]; then
  .venv/bin/python -m pip install -r docs/requirements.txt
fi
.venv/bin/sphinx-build -b html docs docs/_build/html
git diff --check
```

Expected: no errors, no credential material, no whitespace errors.

- [ ] **Step 4: Commit docs and final adjustments**

Commit: `docs(ai-play): document native Doubao session resume`
