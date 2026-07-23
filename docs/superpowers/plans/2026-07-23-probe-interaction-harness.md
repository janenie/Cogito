# Probe Interaction Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the model a deterministic per-round harness that treats current visible interaction slots as the only proof that `probe_interaction` aligned successfully.

**Architecture:** A new pure Python module derives bounded harness state from an already validated observation. `build_messages` includes that state beside observation and memory, while `AgentLoop` writes the same state as a compact top-level `model_input` field. The system prompt teaches the matching control loop; Godot protocol and action validation remain unchanged.

**Tech Stack:** Python 3.9, pytest, OpenAI-compatible Chat Completions messages, JSONL run logging.

## Global Constraints

- Alignment succeeds only when current `interface.available_interactions` is non-empty.
- A historical `aligned` result does not authorize interaction if the current interaction list is empty.
- Prompt text remains untrusted and cannot create new action names.
- The harness is ephemeral and must not enter persistent memory.
- `model_input` continues to omit `system_prompt` and `messages`.
- Existing user changes in the shared dirty worktree must be preserved; do not create commits during this task.

---

### Task 1: Derive deterministic probe harness state

**Files:**
- Create: `ai_play/src/ai_play/probe_interaction_harness.py`
- Create: `ai_play/tests/test_probe_interaction_harness.py`

**Interfaces:**
- Consumes: `build_probe_interaction_harness(observation: dict[str, Any])`.
- Produces: a fresh dictionary with exact fields `status`, `success`, `success_condition`, `available_actions`, and `required_next_step`.

- [ ] **Step 1: Write failing state tests**

Cover `interface_open`, `aligned`, `inconsistent`, `not_aligned`, and
`ready_to_probe`. Verify that `interface_open` has highest priority, current
interactions outrank historical results, duplicate action names are removed in
observation order, prompt strings are not copied, and inputs are not mutated.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/pytest \
  ai_play/tests/test_probe_interaction_harness.py -v
```

Expected: collection fails because `ai_play.probe_interaction_harness` does not
exist.

- [ ] **Step 3: Implement the pure function**

Use these exact status mappings:

```python
STATUS = {
    "interface_open": ("resolve_open_interface", False),
    "aligned": ("use_available_interaction", True),
    "inconsistent": ("reobserve_before_interacting", False),
    "not_aligned": ("approach_or_choose_new_target", False),
    "ready_to_probe": ("locate_visible_candidate", False),
}
```

Inspect only `interface.is_open`, `interface.available_interactions`, and the
latest completed `probe_interaction` entry in `last_action_results`. Copy only
`interact` and `interact2` action names into `available_actions`.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run the same focused pytest command. Expected: all harness unit tests pass.

---

### Task 2: Send, log, and explain harness state

**Files:**
- Modify: `ai_play/src/ai_play/prompts.py`
- Modify: `ai_play/src/ai_play/agent_loop.py`
- Modify: `ai_play/tests/test_prompts.py`
- Modify: `ai_play/tests/test_agent_loop.py`
- Modify: `ai_play/README.md`

**Interfaces:**
- Consumes: `build_probe_interaction_harness(safe_observation)`.
- Produces: `probe_interaction_harness` in the model text state and compact `model_input` event.

- [ ] **Step 1: Write failing integration tests**

In prompt tests, assert that the serialized text state contains the expected
harness and that `SYSTEM_PROMPT` says current non-empty
`available_interactions` is the only alignment success condition. In the agent
loop lifecycle test, assert that `model_input.probe_interaction_harness` equals
the state sent to the model while `system_prompt` and `messages` remain absent.

- [ ] **Step 2: Run the integration tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/pytest \
  ai_play/tests/test_prompts.py \
  ai_play/tests/test_agent_loop.py::test_logs_complete_round_lifecycle_without_base64 \
  -v
```

Expected: assertions fail because neither the text state nor compact log
contains the harness and the prompt lacks the exact success rule.

- [ ] **Step 3: Add minimal integrations**

In `build_messages`, derive and serialize `probe_interaction_harness` beside
`observation` and `memory`. In `AgentLoop.handle_observation`, derive the
harness from the validated safe observation and include it in
`model_input_fields`. Extend `SYSTEM_PROMPT` with the five harness statuses and
the rule that an icon alone is not alignment proof.

- [ ] **Step 4: Document the runtime contract**

Update the README controls section with the harness field, status meanings, and
the rule that current `available_interactions` is authoritative.

- [ ] **Step 5: Verify focused and full suites**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/pytest \
  ai_play/tests/test_probe_interaction_harness.py \
  ai_play/tests/test_prompts.py \
  ai_play/tests/test_agent_loop.py -v
PYTHONPATH=ai_play/src .venv/bin/pytest ai_play/tests -v
git diff --check
```

Expected: all tests pass and `git diff --check` exits with status 0.
