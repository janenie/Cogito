# Raw Model Output Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve `completion.raw_content` byte-for-byte and remove the system prompt and serialized message envelope from JSONL logs.

**Architecture:** Keep the actual API request, response, parsing, validation, dispatch, and memory flows unchanged. Reduce `model_input` to model identity, image paths, structured observation, and memory; change both model-output logging branches so valid and malformed responses bypass `_redact_for_log`; downstream structured logs and persisted memory retain their current redaction behavior.

**Tech Stack:** Python 3, pytest, append-only JSONL run logger.

## Global Constraints

- `model_output.raw_content` must equal the model response text without modification.
- The same rule applies whether JSON parsing succeeds or fails.
- `model_input` must not contain `system_prompt` or `messages`.
- `model_input` keeps `model`, `image_path`, optional `reference_atlas_path`, `observation`, and `memory`.
- Do not change redaction for `decision_validated`, dispatch events, or persisted memory.
- Do not log API keys, authorization headers, or image base64.
- Update `ai_play/README.md` because this fixes a documented logging/privacy contract.

---

### Task 1: Simplify model input logs and preserve exact model response text

**Files:**
- Modify: `ai_play/tests/test_agent_loop.py`
- Modify: `ai_play/src/ai_play/agent_loop.py`
- Modify: `ai_play/README.md`

**Interfaces:**
- Consumes: `ModelCompletion.raw_content: str` returned by `ApiClient.complete(messages)`.
- Produces: a `model_output` JSONL event whose `raw_content` field is exactly that string.

- [ ] **Step 1: Replace the logging expectations with failing contract tests**

For `model_input`, assert the event has no `system_prompt` or `messages` field and retains the current image path, structured observation, and memory. For malformed JSON, assert the logged value equals the complete malformed response, including digit strings. For valid JSON, provide explicit `raw_content` containing movement numbers and an `enter_digits` value, then assert exact equality in `model_output` while retaining an assertion that downstream structured logs redact the submitted digits.

- [ ] **Step 2: Run the focused tests and verify they fail for the expected reason**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/pytest \
  ai_play/tests/test_agent_loop.py::test_logs_raw_malformed_model_output_with_digits_before_parse_error \
  ai_play/tests/test_agent_loop.py::test_logs_exact_raw_model_output_before_redacting_downstream_events -v
```

Expected: the input contract test fails because `messages` and `system_prompt` are present, and both output tests fail because `model_output.raw_content` contains `[REDACTED]`.

- [ ] **Step 3: Make the minimal production changes**

Remove `system_prompt` and `messages` from the `model_input` event. Add `reference_atlas_path` only when a game context supplies one, while keeping `image_path`, `observation`, and `memory`.

In both the parse-error and successful-parse branches of `AgentLoop.handle_observation`, pass `completion.raw_content` directly to:

```python
self.run_logger.write_event(
    "model_output",
    round_ref,
    raw_content=completion.raw_content,
    latency_ms=completion.latency_ms,
)
```

Leave `_redact_for_log` in use for model input memory, validated decisions, dispatch events, results, and persisted memory.

- [ ] **Step 4: Clarify the README contract**

State that `model_input` intentionally omits the system prompt and Chat Completions message envelope. Also state that `model_output.raw_content` is stored verbatim, can include candidate passwords or other sensitive model-generated text, and is intended for harness diagnosis. Keep the existing warning that credentials, headers, and image base64 are never logged.

- [ ] **Step 5: Run focused and affected test suites**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/pytest ai_play/tests/test_agent_loop.py -v
PYTHONPATH=ai_play/src .venv/bin/pytest ai_play/tests -v
git diff --check
```

Expected: all tests pass and `git diff --check` exits with status 0.
