# AI Play Run Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Escape the only physical AI stop control and persist every multimodal model round, response, dispatched action, and Godot execution result in a replayable run directory.

**Architecture:** A new Python `RunLogger` is the only filesystem writer and owns one run directory per sidecar process. `AgentLoop` assigns rounds and logs the model lifecycle; the WebSocket protocol gains immediate `action_results` and terminal `stop` packets so results are not delayed until the next screenshot. Godot keeps its current observation/action loop but reports execution outcomes with the originating observation ID.

**Tech Stack:** Python 3.9, OpenAI Python SDK, pytest, Godot 4.7, GDScript, WebSocket JSON protocol.

## Global Constraints

- Default log root: `~/workspace/cogito_logs`; `AI_PLAY_LOG_ROOT` overrides it.
- Model path component replaces dots and unsafe characters with underscores.
- Run directory format is `YYYYMMDD-HH-MM`, with collision suffixes beginning at `-02`.
- JSONL never contains API keys, authorization headers, or base64 image data.
- Every accepted model observation has one positive monotonic `round_idx` for the lifetime of the sidecar process.
- Log writes are serialized and flushed per event.
- An input logging failure prevents the external API request; a pre-dispatch logging failure prevents action dispatch.
- Physical Escape is the only human input that disables AI, and the same event remains available to open the pause menu.
- Do not inspect game scripts for puzzle solutions or seed solution knowledge into prompts or memory.

---

## File Structure

- Create `ai_play/src/ai_play/run_logger.py`: run-directory allocation, image persistence, JSONL event writing, sanitization, and round correlation.
- Create `ai_play/tests/test_run_logger.py`: isolated filesystem and event-schema tests.
- Modify `ai_play/src/ai_play/config.py`: expose `log_root` configuration.
- Modify `ai_play/src/ai_play/api_client.py`: return raw response text and latency before parsing.
- Modify `ai_play/src/ai_play/agent_loop.py`: round lifecycle logging, parsing, dispatch correlation, result and stop recording.
- Modify `ai_play/src/ai_play/bridge_server.py`: route `action_results` and `stop` protocol packets.
- Modify `ai_play/src/ai_play/main.py`: create one logger per sidecar process.
- Modify `addons/cogito/AIPlay/ai_play_controller.gd`: Escape-only stop and correlated result packets.
- Modify Python and GDScript tests covering the touched boundaries.
- Modify `ai_play/README.md`: operator controls, log layout, privacy, and inspection commands.

---

### Task 1: Configure the Run Log Root

**Files:**
- Modify: `ai_play/src/ai_play/config.py`
- Modify: `ai_play/tests/test_config.py`
- Modify: `ai_play/.env.example`

**Interfaces:**
- Produces: `Config.log_root: pathlib.Path`.
- Consumes: environment variable `AI_PLAY_LOG_ROOT`.

- [ ] **Step 1: Write failing configuration tests**

```python
def test_config_uses_default_log_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    monkeypatch.delenv("AI_PLAY_LOG_ROOT", raising=False)
    assert Config.from_env().log_root == Path("~/workspace/cogito_logs").expanduser()


def test_config_expands_log_root_override(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    monkeypatch.setenv("AI_PLAY_LOG_ROOT", "~/custom-cogito-logs")
    assert Config.from_env().log_root == Path("~/custom-cogito-logs").expanduser()
```

- [ ] **Step 2: Run tests and verify RED**

```bash
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/python -m pytest ai_play/tests/test_config.py -q
```

Expected: both new tests fail because `Config` has no `log_root`.

- [ ] **Step 3: Implement configuration**

Add the dataclass field:

```python
log_root: Path = Path("~/workspace/cogito_logs").expanduser()
```

Pass this value from `from_env`:

```python
log_root=Path(os.environ.get("AI_PLAY_LOG_ROOT", str(cls.log_root))).expanduser(),
```

Add to `.env.example`:

```dotenv
AI_PLAY_LOG_ROOT=~/workspace/cogito_logs
```

- [ ] **Step 4: Run configuration tests and verify GREEN**

Run Step 2. Expected: all `test_config.py` tests pass.

- [ ] **Step 5: Commit**

```bash
git add ai_play/src/ai_play/config.py ai_play/tests/test_config.py ai_play/.env.example
git commit -m "feat: configure AI play run logs"
```

---

### Task 2: Build the Append-Only Run Logger

**Files:**
- Create: `ai_play/src/ai_play/run_logger.py`
- Create: `ai_play/tests/test_run_logger.py`

**Interfaces:**
- Produces: `sanitize_model_name(model: str) -> str`.
- Produces: `RunLogger.create(root: Path, model: str, now: datetime | None = None) -> RunLogger`.
- Produces: `RunLogger.begin_round(observation_id: int, image: dict) -> RoundRef`.
- Produces: `RunLogger.write_event(event: str, round_ref: RoundRef | None = None, **fields) -> None`.
- Produces: `RunLogger.round_for_observation(observation_id: int) -> RoundRef | None` and `RunLogger.finish_round(observation_id: int) -> RoundRef | None`.

- [ ] **Step 1: Write failing path, image, and JSONL tests**

Use fixed time `datetime(2026, 7, 21, 10, 45, tzinfo=timezone.utc)` and assert:

```python
assert sanitize_model_name("gemini-3.5-flash") == "gemini-3_5-flash"
assert sanitize_model_name("vendor/model:latest") == "vendor_model_latest"
assert logger.run_dir.name == "20260721-10-45"
assert second_logger.run_dir.name == "20260721-10-45-02"
```

Use known JPEG bytes encoded with `base64.b64encode`, call
`begin_round(17, image)`, and assert:

```python
assert round_ref.round_idx == 1
assert round_ref.observation_id == 17
assert (logger.run_dir / "img/000001.jpg").read_bytes() == jpeg_bytes
```

Write an event, reopen `gemini_godot.jsonl` before closing the logger, and
assert the line is immediately visible and contains no base64 payload.

- [ ] **Step 2: Run logger tests and verify RED**

```bash
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/python -m pytest ai_play/tests/test_run_logger.py -q
```

Expected: collection fails because `ai_play.run_logger` does not exist.

- [ ] **Step 3: Implement focused logger types**

```python
@dataclass(frozen=True)
class RoundRef:
    round_idx: int
    observation_id: int
    image_path: str
```

Create the model directory with `mkdir(parents=True)` and select the first run
candidate whose `mkdir()` succeeds. Open `gemini_godot.jsonl` in line-buffered
UTF-8 append mode. Serialize events under `threading.Lock`:

```python
payload = {
    "event": event,
    "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
}
if round_ref is not None:
    payload.update(round_idx=round_ref.round_idx, observation_id=round_ref.observation_id)
payload.update(deepcopy(fields))
self._stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
self._stream.flush()
```

Accept only `image/jpeg`, decode with `base64.b64decode(encoded, validate=True)`,
write `img/%06d.jpg`, and register the round only after persistence succeeds.
Reject duplicate outstanding observation IDs and remove entries in
`finish_round`.

- [ ] **Step 4: Add failure and correlation tests**

Test malformed base64, unsupported MIME, duplicate observation IDs, unknown
results, two increasing rounds, and mapping removal after `finish_round`.

- [ ] **Step 5: Run logger tests and verify GREEN**

Run Step 2. Expected: all logger tests pass.

- [ ] **Step 6: Commit**

```bash
git add ai_play/src/ai_play/run_logger.py ai_play/tests/test_run_logger.py
git commit -m "feat: add append-only AI run logger"
```

---

### Task 3: Preserve Raw Model Output and Latency

**Files:**
- Modify: `ai_play/src/ai_play/api_client.py`
- Modify: `ai_play/tests/test_api_client.py`

**Interfaces:**
- Produces: `ModelCompletion(raw_content: str, latency_ms: int)`.
- Produces: `ApiClient.complete(messages) -> ModelCompletion`.
- Produces: `parse_model_json(raw_content: str) -> dict`.

- [ ] **Step 1: Write failing API adapter tests**

```python
completion = client.complete(messages)
assert completion.raw_content == "```json\n{\"actions\": []}\n```"
assert type(completion.latency_ms) is int
assert completion.latency_ms >= 0
```

Assert `parse_model_json` strips only the supported JSON fence and continues to
reject `NaN` using the existing strict JSON behavior.

- [ ] **Step 2: Run API client tests and verify RED**

```bash
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/python -m pytest ai_play/tests/test_api_client.py -q
```

Expected: failure because `complete` and `ModelCompletion` do not exist.

- [ ] **Step 3: Implement completion capture**

```python
@dataclass(frozen=True)
class ModelCompletion:
    raw_content: str
    latency_ms: int
```

Measure only `chat.completions.create` with `time.monotonic_ns()`. Validate that
content is a string, return it unchanged, and move strict JSON loading into
`parse_model_json`. Retain the existing `decide(messages)` as a compatibility
wrapper that calls `complete` and `parse_model_json`; Task 4 switches AgentLoop
to the new boundary before the wrapper can be removed.

- [ ] **Step 4: Run API and full Python tests**

```bash
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/python -m pytest ai_play/tests/test_api_client.py -q
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/python -m pytest ai_play/tests -q
```

Expected: all tests pass after fake clients adopt the new interface.

- [ ] **Step 5: Commit**

```bash
git add ai_play/src/ai_play/api_client.py ai_play/tests
git commit -m "refactor: expose raw AI model completions"
```

---

### Task 4: Log the Model and Dispatch Lifecycle

**Files:**
- Modify: `ai_play/src/ai_play/agent_loop.py`
- Modify: `ai_play/src/ai_play/main.py`
- Modify: `ai_play/src/ai_play/prompts.py`
- Modify: `ai_play/tests/test_agent_loop.py`
- Modify: `ai_play/tests/test_main.py`
- Modify: `ai_play/tests/test_prompts.py`

**Interfaces:**
- Consumes: `RunLogger`, `ApiClient.complete`, and `parse_model_json`.
- Produces: `AgentLoop.record_action_results(observation_id: int, results: list) -> bool`.
- Produces: `AgentLoop.record_stop(reason: str, observation_id: int | None, results: list) -> None`.

- [ ] **Step 1: Write failing lifecycle tests**

For one valid observation assert this event order:

```python
assert logger.event_names == [
    "model_input",
    "model_output",
    "decision_validated",
    "action_dispatch_requested",
]
```

Assert `model_input` has the system prompt, observation, memory, log-safe
messages, and image path, but no base64. Assert malformed JSON produces
`model_output` followed by `round_error` with `stage == "parse"`.

- [ ] **Step 2: Run agent tests and verify RED**

```bash
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/python -m pytest ai_play/tests/test_agent_loop.py -q
```

Expected: lifecycle assertions fail because AgentLoop has no run logger.

- [ ] **Step 3: Add log-safe message projection**

Add `build_log_messages(messages, image_path)` in `prompts.py`. Deep-copy the
messages and replace the image content part with:

```python
{"type": "image_path", "image_path": image_path}
```

- [ ] **Step 4: Integrate the logger into AgentLoop**

Change construction to:

```python
AgentLoop(api_client, memory, run_logger, memory_path=None, resume=False)
```

In `handle_observation`, validate observation, call `begin_round`, construct
real and log-safe messages, then append `model_input`, `model_output`,
`decision_validated`, and `action_dispatch_requested` at their specified
boundaries. Store `RoundRef` in the staged batch. On error, append
`round_error` with a stable stage and exception type; omit unsafe exception
text.

- [ ] **Step 5: Log dispatch, results, and stop**

In `commit_action_batch_sent`, append `action_dispatched` after transport and
memory commit. Implement `record_action_results` to append `godot_result` and
finish correlation. Implement `record_stop` to append `session_stop` with
sanitized results.

- [ ] **Step 6: Construct one logger in main**

```python
run_logger = RunLogger.create(config.log_root, config.model)
agent_loop = AgentLoop(ApiClient(config), memory, run_logger, memory_path=memory_path, resume=args.resume)
print(f"AI_PLAY logs: {run_logger.run_dir}")
```

- [ ] **Step 7: Run focused and full tests**

```bash
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/python -m pytest ai_play/tests/test_agent_loop.py ai_play/tests/test_main.py ai_play/tests/test_prompts.py -q
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/python -m pytest ai_play/tests -q
```

Expected: all tests pass and use temporary log roots.

- [ ] **Step 8: Commit**

```bash
git add ai_play/src/ai_play ai_play/tests
git commit -m "feat: trace AI model rounds and dispatches"
```

---

### Task 5: Report Results and Stops over WebSocket

**Files:**
- Modify: `ai_play/src/ai_play/bridge_server.py`
- Modify: `ai_play/tests/test_bridge_server.py`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `tests/ai_play/test_ai_play_controller.gd`

**Interfaces:**
- Consumes: `{"type":"action_results","protocol_version":1,"observation_id":N,"results":[...]}`.
- Consumes: `{"type":"stop","protocol_version":1,"observation_id":N|null,"reason":"escape_stop","results":[...]}`.
- Calls: `AgentLoop.record_action_results(...)` and `AgentLoop.record_stop(...)`.

- [ ] **Step 1: Write failing Python protocol tests**

Extend the fake agent with recorded result and stop calls. Send valid packets
after hello and assert exact calls. Add rejection tests for missing/extra
fields, wrong types, unknown IDs, oversized arrays, and overlong result strings.

- [ ] **Step 2: Run bridge tests and verify RED**

```bash
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/python -m pytest ai_play/tests/test_bridge_server.py -q
```

Expected: new valid packets receive `unexpected_packet`.

- [ ] **Step 3: Route strictly validated packets**

Reuse the bounded last-action-result schema. Route `action_results`, returning a
protocol error for unknown/duplicate rounds. Route `stop`, record it, and end
the exclusive handler normally.

- [ ] **Step 4: Write failing Godot correlation tests**

Extend the fake bridge to record sent packets. Execute a batch for observation
17 and assert one matching packet. Cover completed, blocked, error, cancelled,
and stopped results. Assert results are sent before the next observation.

- [ ] **Step 5: Run Godot tests and verify RED**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: failure because `_on_batch_finished` sends no result packet.

- [ ] **Step 6: Add Godot execution correlation**

Store `_executing_observation_id` when accepting a batch. Before advancing in
`_on_batch_finished`, send:

```gdscript
{
    "type": "action_results",
    "protocol_version": PROTOCOL_VERSION,
    "observation_id": _executing_observation_id,
    "results": results.duplicate(true),
}
```

Clear the ID after send. A transport failure cancels safely and produces no new
observation.

- [ ] **Step 7: Run Python and Godot protocol tests**

Run Steps 2 and 5. Expected: both pass.

- [ ] **Step 8: Commit**

```bash
git add ai_play/src/ai_play/bridge_server.py ai_play/tests/test_bridge_server.py addons/cogito/AIPlay/ai_play_controller.gd tests/ai_play/test_ai_play_controller.gd
git commit -m "feat: report Godot AI action results"
```

---

### Task 6: Make Escape the Only Physical Stop

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `tests/ai_play/test_ai_play_controller.gd`

**Interfaces:**
- Produces: physical non-echo Escape sends `stop(reason="escape_stop")`, releases controls, disables AI, and remains unhandled.
- Preserves: synthetic executor input cannot stop AI.

- [ ] **Step 1: Write the approved input contract tests**

Table-drive physical W, mouse motion, left click, joypad button, and joypad axis
events and assert AI remains enabled. Assert physical Escape disables AI,
releases held input, and emits one stop packet. Assert synthetic Escape does not
stop AI. Assert the controller does not mark Escape handled.

- [ ] **Step 2: Run controller tests and verify RED**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: non-Escape physical input still disables AI.

- [ ] **Step 3: Implement Escape-only stop**

Set the default key to `KEY_ESCAPE`. Replace general takeover with:

```gdscript
if (
    event.device != EXECUTOR_DEVICE_ID
    and event is InputEventKey
    and event.pressed
    and not event.echo
    and (event.keycode == KEY_ESCAPE or event.physical_keycode == KEY_ESCAPE)
):
    _send_stop_packet("escape_stop")
    disable_ai("escape_stop")
```

Do not mark input handled. Remove the generic human-input predicate. Send the
stop packet before disconnect and avoid duplicating action results.

- [ ] **Step 4: Run Godot tests and verify GREEN**

Run Step 2. Expected: controller tests pass.

- [ ] **Step 5: Commit**

```bash
git add addons/cogito/AIPlay/ai_play_controller.gd tests/ai_play/test_ai_play_controller.gd
git commit -m "feat: stop AI play only with Escape"
```

---

### Task 7: Document and Verify the Feature

**Files:**
- Modify: `ai_play/README.md`
- Modify: `tests/check_ai_play_secrets.sh` only if its scan scope misses the new logger.

**Interfaces:**
- Documents log location, schema, controls, privacy, and inspection.

- [ ] **Step 1: Update the operator guide**

Document this layout and event sequence:

```text
~/workspace/cogito_logs/<sanitized-model>/<YYYYMMDD-HH-MM>/
├── gemini_godot.jsonl
└── img/000001.jpg
```

Explain `AI_PLAY_LOG_ROOT`, incomplete rounds, Escape plus pause-menu behavior,
screenshot privacy, and:

```bash
tail -f ~/workspace/cogito_logs/gemini-3_5-flash/<run>/gemini_godot.jsonl
```

- [ ] **Step 2: Run complete automated verification**

```bash
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-venv/bin/python -m pytest ai_play/tests -q
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --editor --quit
bash tests/check_ai_play_secrets.sh
git diff --check
```

Expected: zero Python failures; each Godot test reports passed; editor, secret
scan, and diff check exit 0.

- [ ] **Step 3: Perform the opt-in live integration check**

Start the sidecar from the repository root using ignored `api_key.py`, then
launch the Lobby with `-- --ai-play`. Allow at least three rounds, press Escape,
and verify the pause menu opens. Inspect the newest run and verify:

- At least three readable JPEGs exist.
- Every JSONL line parses.
- Completed rounds have input, output, decision, dispatch request, confirmed
  dispatch, and Godot result events.
- The final event records `escape_stop`.
- No line contains `base64`, `api_key`, `authorization`, or the real key.

- [ ] **Step 4: Commit documentation**

```bash
git add ai_play/README.md tests/check_ai_play_secrets.sh
git commit -m "docs: explain AI play run traces"
```

- [ ] **Step 5: Review final scope**

```bash
git status --short
git log --oneline --decorate -8
```

Confirm commits exclude `api_key.py`, generated logs, and unrelated Lobby/theme
runtime changes.
