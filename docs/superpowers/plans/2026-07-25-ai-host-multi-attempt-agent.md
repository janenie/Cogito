# AI Host Multi-Attempt Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new `ai_host/` program that can run one AI Play scenario for up to 3 fresh Godot attempts, restart the game between failed attempts, ask the agent to summarize process-level mistakes, and feed that strategy into the next attempt without leaking hidden game state.

**Architecture:** `ai_host` is an outer supervisor, not part of the MCP server. It owns Godot process lifecycle, MCP stdio connection lifecycle, attempt logs, reflection memory, and final report generation. The first implementation should support a direct OpenAI Responses API adapter; the same interfaces should allow a later external-agent adapter such as Codex CLI, where Codex itself plays through MCP and writes a structured attempt report.

**Tech Stack:** Python 3.11+, `asyncio`, `subprocess`, existing `mcp` Python SDK, existing `openai` SDK from `tutorial/requirements.txt`, existing `ai_play/start_ai.sh`, Godot CLI.

## Global Constraints

- Do not put retry/self-evolution logic inside `ai_play/src/ai_play/mcp_server.py`.
- Do not pass scene source, node paths, test files, `game_script/`, `code_read/`, hidden seeds, puzzle answers, or internal random choices into model prompts.
- Each attempt must launch a fresh Godot process with `-- --ai-play --ai-play-scenario=<scenario_id>`.
- Each failed attempt must terminate Godot and start a new process so game state, random seed, and MCP act count reset.
- Default attempt count is 3; default scenario for this feature is `daily_routine_cleanup`.
- Store attempt logs under an ignored runtime directory such as `ai_host/runs/`; do not commit screenshots, model transcripts, API keys, or runtime logs.
- API keys stay in the outer host environment only. MCP server and Godot never receive model credentials.
- If an external agent such as Codex is used, `ai_host` treats it as a black-box child process and requires a structured JSON attempt report from that child process.

---

## File Structure

- Create `ai_host/README.md`
  - User-facing usage guide for running 3 attempts.
  - Explain API adapter vs external-agent/Codex adapter.
  - Include exact Godot scenario examples.

- Create `ai_host/requirements.txt`
  - Depend on `../tutorial/requirements.txt` or list `openai` plus existing `ai_play` requirements.

- Create `ai_host/__init__.py`
  - Empty package marker.

- Create `ai_host/config.py`
  - Parse environment variables and CLI args into a typed config object.
  - Own defaults: scenario, scene path, max attempts, model, Godot command, MCP command, run directory.

- Create `ai_host/godot_process.py`
  - Start/stop one Godot attempt process.
  - Ensure termination on success/failure/KeyboardInterrupt.

- Create `ai_host/mcp_client.py`
  - Start existing `ai_play/start_ai.sh` via stdio.
  - Initialize MCP client session and expose tool list/call helpers.
  - Reuse logic from `tutorial/ai_play_api_host.py` without changing MCP server.

- Create `ai_host/attempt_state.py`
  - Define attempt result dataclasses and JSON serialization.
  - Track terminal status, reason, step count, reflection, and next strategy.

- Create `ai_host/reflection.py`
  - Build safe reflection prompts.
  - Strip exact coordinates and prohibit concrete previous-run object locations in carry-over memory.

- Create `ai_host/agents/base.py`
  - Define a common `AgentAdapter` protocol:
    - `run_attempt(attempt_context) -> AttemptResult`

- Create `ai_host/agents/openai_responses.py`
  - Direct API adapter based on `tutorial/ai_play_api_host.py`.
  - The host itself calls MCP tools requested by the model.

- Create `ai_host/agents/external_command.py`
  - External black-box adapter for Codex or another CLI agent.
  - Host writes an attempt prompt file, runs a configured command, waits for a required JSON report file.
  - This adapter does not inspect internal MCP tool calls.

- Create `ai_host/runner.py`
  - Main loop:
    - for attempt 1..N
    - start Godot
    - connect/play via selected adapter
    - stop MCP and Godot
    - if success stop early
    - if failure generate safe reflection and continue
    - write final report

- Create `ai_host/__main__.py`
  - CLI entrypoint: `python -m ai_host ...`

- Create tests:
  - `ai_host/tests/test_config.py`
  - `ai_host/tests/test_reflection.py`
  - `ai_host/tests/test_runner.py`
  - `ai_host/tests/test_external_command_agent.py`
  - `ai_host/tests/test_openai_agent_loop.py`

- Modify `.gitignore`
  - Add `ai_host/runs/`.

- Modify `README_AI_PLAY.md`
  - Add a short pointer to `ai_host/README.md`.

---

## Core Design: How Codex Fits

There are two viable ways to let “an AI agent such as Codex” play:

### Mode A: Direct API Host, recommended first

`ai_host` is the MCP Host. It starts the MCP server through stdio, passes tool definitions to the model API, executes model-requested tool calls, and sees every `briefing` / `observe` / `act` / `stop` result.

This is easiest to make reliable because `ai_host` can directly detect terminal states and summarize logs.

### Mode B: External Agent Host, for Codex CLI

`ai_host` starts a fresh Godot attempt, writes a prompt file for Codex, invokes a configured command, and waits for Codex to finish. Codex must have the Cogito MCP server configured in its own MCP config, then it plays the game using its own tool loop.

The contract between `ai_host` and Codex should be file-based:

```json
{
  "attempt_id": 1,
  "outcome": "success|failure|stopped|unknown",
  "reason": "cleanup_complete|cleanup_incomplete|max_requests|...",
  "summary": "short public summary",
  "mistakes": ["process-level mistake 1"],
  "next_strategy": ["process-level strategy 1"]
}
```

This avoids hardcoding Codex internals in `ai_host`. The command is configurable:

```bash
AI_HOST_AGENT_COMMAND='codex ... {prompt_file} ...'
```

The implementation should not assume exact Codex CLI flags until they are verified in the local environment.

---

## Task 1: Config and CLI Contract

**Files:**
- Create: `ai_host/config.py`
- Create: `ai_host/__main__.py`
- Test: `ai_host/tests/test_config.py`

**Interfaces:**
- Produces:
  - `HostConfig`
  - `parse_args(argv: list[str]) -> HostConfig`
- Consumes: none.

- [ ] Write failing tests for defaults:
  - scenario defaults to `daily_routine_cleanup`
  - scene defaults to `dailyroutine/scenes/home_daily_routine.tscn`
  - max attempts defaults to `3`
  - adapter defaults to `openai`
  - Godot command defaults to `godot`
  - MCP command defaults to `ai_play/start_ai.sh`

- [ ] Implement `HostConfig`.

- [ ] Implement CLI args:
  - `--scenario`
  - `--scene`
  - `--max-attempts`
  - `--adapter openai|external-command`
  - `--model`
  - `--run-dir`
  - `--godot-command`
  - `--mcp-command`
  - `--agent-command`

- [ ] Verify:

```bash
PYTHONPATH=. .venv/bin/python -m pytest ai_host/tests/test_config.py -q
```

---

## Task 2: Godot Process Lifecycle

**Files:**
- Create: `ai_host/godot_process.py`
- Test: `ai_host/tests/test_godot_process.py`

**Interfaces:**
- Consumes: `HostConfig`
- Produces:
  - `build_godot_command(config: HostConfig) -> list[str]`
  - `GodotAttemptProcess.start()`
  - `GodotAttemptProcess.stop()`

- [ ] Write tests for command construction:

Expected command shape:

```bash
godot --path . dailyroutine/scenes/home_daily_routine.tscn -- --ai-play --ai-play-scenario=daily_routine_cleanup
```

- [ ] Implement process wrapper.

- [ ] Ensure `stop()` first terminates, then kills only if process does not exit within a short timeout.

- [ ] Verify:

```bash
PYTHONPATH=. .venv/bin/python -m pytest ai_host/tests/test_godot_process.py -q
```

---

## Task 3: Attempt Result and Safe Reflection Memory

**Files:**
- Create: `ai_host/attempt_state.py`
- Create: `ai_host/reflection.py`
- Test: `ai_host/tests/test_reflection.py`

**Interfaces:**
- Produces:
  - `AttemptResult`
  - `ReflectionMemory`
  - `build_attempt_instructions(...) -> str`
  - `sanitize_reflection(text: str) -> str`

- [ ] Write tests that reject carry-over memory containing:
  - `res://`
  - `/Users/`
  - `NodePath`
  - `global_position`
  - exact coordinate-looking tuples such as `(1.2, 0.0, -3.4)`

- [ ] Write tests that preserve process-level strategy:
  - “check HUD before finishing”
  - “search rooms systematically”
  - “open fridge before assuming cleanup is complete”

- [ ] Implement reflection sanitizer.

- [ ] Implement prompt builder:
  - Attempt 1 gets no previous reflection.
  - Attempt 2/3 receive only sanitized strategy.
  - Prompt explicitly says every attempt has a fresh random seed and previous object positions are invalid.

- [ ] Verify:

```bash
PYTHONPATH=. .venv/bin/python -m pytest ai_host/tests/test_reflection.py -q
```

---

## Task 4: MCP Client Wrapper

**Files:**
- Create: `ai_host/mcp_client.py`
- Test: `ai_host/tests/test_mcp_client.py`

**Interfaces:**
- Consumes: existing `ai_play/start_ai.sh`
- Produces:
  - `McpGameClient.connect()`
  - `McpGameClient.list_tools()`
  - `McpGameClient.call_tool(name, arguments)`
  - `McpGameClient.stop()`

- [ ] Extract reusable MCP stdio startup logic from `tutorial/ai_play_api_host.py`.

- [ ] Do not alter `ai_play/src/ai_play/mcp_server.py`.

- [ ] Add tests using a fake session object for serialization and stop behavior.

- [ ] Verify:

```bash
PYTHONPATH=. .venv/bin/python -m pytest ai_host/tests/test_mcp_client.py -q
```

---

## Task 5: OpenAI Responses Agent Adapter

**Files:**
- Create: `ai_host/agents/base.py`
- Create: `ai_host/agents/openai_responses.py`
- Test: `ai_host/tests/test_openai_agent_loop.py`

**Interfaces:**
- Consumes:
  - `McpGameClient`
  - `AttemptResult`
  - `build_attempt_instructions`
- Produces:
  - `OpenAIResponsesAgent.run_attempt(context) -> AttemptResult`

- [ ] Start from the existing logic in `tutorial/ai_play_api_host.py`.

- [ ] Add terminal detection from MCP tool results:
  - `game_over`
  - `stopped`
  - `disconnected`
  - max agent turns

- [ ] Store only structured text summaries under `ai_host/runs/...`.

- [ ] Do not store Base64 screenshots by default.

- [ ] Verify with fake OpenAI responses and fake MCP tool results:

```bash
PYTHONPATH=. .venv/bin/python -m pytest ai_host/tests/test_openai_agent_loop.py -q
```

---

## Task 6: External Command Agent Adapter for Codex

**Files:**
- Create: `ai_host/agents/external_command.py`
- Test: `ai_host/tests/test_external_command_agent.py`

**Interfaces:**
- Consumes:
  - `AI_HOST_AGENT_COMMAND`
  - prompt file path
  - expected report file path
- Produces:
  - `ExternalCommandAgent.run_attempt(context) -> AttemptResult`

- [ ] Write prompt file per attempt:

```text
You are playing Cogito through the configured MCP server.
Scenario: daily_routine_cleanup.
Attempt: 2 of 3.
Every attempt has a fresh random seed. Do not reuse previous object positions.
Use only MCP tools and public observations.
At the end, write JSON to: <report_path>
```

- [ ] Run command with placeholder replacement:
  - `{repo_root}`
  - `{prompt_file}`
  - `{report_file}`
  - `{run_dir}`
  - `{attempt_id}`

- [ ] Require the report JSON file to exist and match the schema.

- [ ] If the child exits without a valid report, return `outcome="unknown"` and continue according to runner policy.

- [ ] Document that exact Codex CLI flags are environment-specific and must be configured by the user.

- [ ] Verify:

```bash
PYTHONPATH=. .venv/bin/python -m pytest ai_host/tests/test_external_command_agent.py -q
```

---

## Task 7: Multi-Attempt Runner

**Files:**
- Create: `ai_host/runner.py`
- Test: `ai_host/tests/test_runner.py`

**Interfaces:**
- Consumes:
  - `HostConfig`
  - `GodotAttemptProcess`
  - `AgentAdapter`
  - `ReflectionMemory`
- Produces:
  - `run_host(config: HostConfig) -> FinalReport`

- [ ] Write tests:
  - stops after first success
  - restarts Godot between failures
  - passes sanitized reflection from attempt 1 into attempt 2
  - stops after max attempts
  - always stops Godot on exception

- [ ] Implement loop:

```text
for attempt_id in 1..max_attempts:
    start fresh Godot
    run selected agent
    stop Godot
    save attempt result
    if success: break
    update sanitized reflection
write final report
```

- [ ] Verify:

```bash
PYTHONPATH=. .venv/bin/python -m pytest ai_host/tests/test_runner.py -q
```

---

## Task 8: Documentation and Local Usage

**Files:**
- Create: `ai_host/README.md`
- Modify: `README_AI_PLAY.md`
- Modify: `.gitignore`

**Documentation must include:**
- Direct OpenAI API mode:

```bash
export OPENAI_API_KEY="..."
PYTHONPATH=. .venv/bin/python -m ai_host \
  --adapter openai \
  --scenario daily_routine_cleanup \
  --scene dailyroutine/scenes/home_daily_routine.tscn \
  --max-attempts 3
```

- External Codex mode:

```bash
export AI_HOST_AGENT_COMMAND='your-codex-command-using-{prompt_file}-and-{report_file}'
PYTHONPATH=. .venv/bin/python -m ai_host \
  --adapter external-command \
  --scenario daily_routine_cleanup \
  --scene dailyroutine/scenes/home_daily_routine.tscn \
  --max-attempts 3
```

- Explain Codex prerequisite:
  - Codex must already be configured with the Cogito MCP server.
  - Codex must write the required JSON report to `{report_file}`.
  - `ai_host` does not depend on private Codex internals.

- [ ] Verify docs mention:
  - fresh Godot per attempt
  - random seed is not fixed
  - previous exact object positions are invalid
  - reflection is process-level only
  - logs are local and ignored

---

## Task 9: End-to-End Dry Run

**Files:**
- No new files unless tests reveal missing docs.

**Commands:**

```bash
PYTHONPATH=. .venv/bin/python -m pytest ai_host/tests -q
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_scenarios.py ai_play/tests/test_briefing.py ai_play/tests/test_game_session.py -q
bash tests/check_ai_play_home_daily_routine.sh
bash tests/check_home_player_wall_collision.sh
git diff --check
```

**Manual smoke test after implementation:**

```bash
PYTHONPATH=. .venv/bin/python -m ai_host \
  --adapter openai \
  --scenario daily_routine_cleanup \
  --scene dailyroutine/scenes/home_daily_routine.tscn \
  --max-attempts 3
```

Do not run the manual smoke test with real API credentials unless the user explicitly approves cost, screenshots, and local trace persistence.

---

## Execution Notes

- If the user wants “Codex plays it,” implement `external-command` after the direct API mode exists. The host should not try to control Codex internals. It should treat Codex as a process with two files: input prompt and output JSON report.
- If the user wants reliable autonomous benchmark data, prefer the direct OpenAI adapter because the host observes every MCP result and can produce deterministic attempt reports.
- If both modes are implemented, both should share the same reflection sanitizer and final report format.
