# Session-scoped AI Play AWM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit, structured Agent Workflow Memory that is shared only by the Godot attempts inside one orchestrator session and is destroyed with the MCP sidecar.

**Architecture:** A new pure-Python `SessionWorkflowMemory` owns validation, attempt eligibility, promotion, deduplication, versioning, and snapshots. `GameSession` reports trusted attempt lifecycle events to it, while two unlogged FastMCP tools expose bounded reads and candidate updates to the isolated Codex player. The orchestrator only expands its MCP allowlist and prompt; Codex built-in memories and disk persistence remain disabled.

**Tech Stack:** Python 3.11+, dataclasses, threading locks, FastMCP, pytest, existing Cogito AI Play `GameSession` and orchestrator tests.

---

### Task 1: Pure in-memory workflow state machine

**Files:**
- Create: `ai_play/src/ai_play/workflow_memory.py`
- Create: `ai_play/tests/test_workflow_memory.py`

- [ ] **Step 1: Write failing tests for empty reads and trusted attempt lifecycle**

```python
from ai_play.workflow_memory import SessionWorkflowMemory, WorkflowMemoryError


def valid_candidate():
    return {
        "goal_pattern": "依据公开线索逐步完成当前任务",
        "workflow": [{
            "step": "先确认任务入口物",
            "precondition": "尚未获得第一条公开任务线索",
            "success_signal": "观察中出现下一阶段目标",
        }],
        "landmarks": [{"relation": "先建立出生区域与主要地标的相对方向"}],
        "avoid": ["没有交互提示时不要重复 interact"],
    }


def test_first_attempt_reads_empty_memory():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")

    assert memory.read("find_contract") == {
        "status": "ready",
        "scope": "current_orchestrator_session",
        "scenario": "find_contract",
        "version": 0,
        "completed_runs": 0,
        "memory": None,
    }


def test_success_promotes_all_candidate_sections():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")

    result = memory.update(valid_candidate())

    assert result["status"] == "updated"
    assert result["version"] == 1
    assert result["accepted"] == {
        "workflow": 1,
        "landmarks": 1,
        "avoid": 1,
    }
    assert memory.read("find_contract")["memory"]["workflow"][0]["step"] == (
        "先确认任务入口物"
    )
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
PYTHONPATH=ai_play/src ../../.venv/bin/python -m pytest \
  ai_play/tests/test_workflow_memory.py -q
```

Expected: collection fails with `ModuleNotFoundError: ai_play.workflow_memory`.

- [ ] **Step 3: Implement the public types and minimal successful promotion**

```python
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from threading import Lock
import unicodedata


class WorkflowMemoryError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class _Attempt:
    number: int
    scenario_id: str
    status: str = "in_progress"
    terminal_reason: str | None = None
    consumed: bool = False


class SessionWorkflowMemory:
    def __init__(self):
        self._lock = Lock()
        self._scenario_id = None
        self._active_attempt = None
        self._completed = []
        self._version = 0
        self._goal_pattern = None
        self._workflow = []
        self._landmarks = []
        self._avoid = []

    def start_attempt(self, scenario_id: str) -> int:
        with self._lock:
            if self._active_attempt is not None:
                raise WorkflowMemoryError("attempt_in_progress")
            if self._scenario_id not in (None, scenario_id):
                raise WorkflowMemoryError("scenario_mismatch")
            self._scenario_id = scenario_id
            number = len(self._completed) + 1
            self._active_attempt = _Attempt(number, scenario_id)
            return number

    def finish_attempt(self, status: str, terminal_reason: str) -> None:
        with self._lock:
            if self._active_attempt is None:
                return
            self._active_attempt.status = status
            self._active_attempt.terminal_reason = terminal_reason
            if status not in {"success", "failure"}:
                self._active_attempt.consumed = True
            self._completed.append(self._active_attempt)
            self._active_attempt = None

    def read(self, scenario_id: str) -> dict:
        with self._lock:
            if self._scenario_id is None:
                raise WorkflowMemoryError("scenario_not_ready")
            if scenario_id != self._scenario_id:
                raise WorkflowMemoryError("scenario_mismatch")
            snapshot = None if self._version == 0 else self._snapshot_locked()
            return {
                "status": "ready",
                "scope": "current_orchestrator_session",
                "scenario": scenario_id,
                "version": self._version,
                "completed_runs": len(self._completed),
                "memory": deepcopy(snapshot),
            }
```

- [ ] **Step 4: Add failing tests for failure-only promotion and eligibility**

```python
def test_failure_only_promotes_avoid():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("failure", "max_requests")

    result = memory.update(valid_candidate())

    assert result["accepted"] == {
        "workflow": 0,
        "landmarks": 0,
        "avoid": 1,
    }
    snapshot = memory.read("find_contract")["memory"]
    assert snapshot["workflow"] == []
    assert snapshot["landmarks"] == []


@pytest.mark.parametrize("status", ["stopped", "disconnected", "shutdown"])
def test_ineligible_attempt_does_not_learn(status):
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt(status, "bridge_disconnected")

    with pytest.raises(WorkflowMemoryError, match="attempt_not_eligible"):
        memory.update(valid_candidate())


def test_completed_attempt_can_update_after_next_attempt_starts():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")
    memory.start_attempt("find_contract")

    assert memory.update(valid_candidate())["version"] == 1


def test_attempt_can_only_be_consumed_once():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")
    memory.update(valid_candidate())

    with pytest.raises(WorkflowMemoryError, match="attempt_already_updated"):
        memory.update(valid_candidate())
```

- [ ] **Step 5: Implement update selection, eligibility, deduplication, and server confidence**

Implement `update()` so it selects the oldest eligible, unconsumed completed attempt, never the active attempt. Mark stopped/disconnected/shutdown attempts consumed when they finish so they cannot block a later eligible attempt; when the latest completed attempt is ineligible and no eligible update is pending, return `attempt_not_eligible`. Mark an eligible attempt consumed only after the entire candidate validates. For `success`, merge every allowed section; for `failure`, merge only `avoid`. Normalize text before exact deduplication and calculate confidence from the number of successful supporting attempts divided by eligible completed attempts.

```python
def update(self, candidate: dict) -> dict:
    safe = validate_workflow_candidate(candidate)
    with self._lock:
        attempt = self._next_eligible_unconsumed_locked()
        if attempt is None:
            if self._active_attempt is not None:
                raise WorkflowMemoryError("attempt_in_progress")
            if (
                self._completed
                and self._completed[-1].status not in {"success", "failure"}
            ):
                raise WorkflowMemoryError("attempt_not_eligible")
            raise WorkflowMemoryError("attempt_already_updated")

        accepted = {"workflow": 0, "landmarks": 0, "avoid": 0}
        if attempt.status == "success":
            self._goal_pattern = safe["goal_pattern"]
            accepted["workflow"] = _merge_unique(
                self._workflow, safe["workflow"]
            )
            accepted["landmarks"] = _merge_unique(
                self._landmarks, safe["landmarks"]
            )
        accepted["avoid"] = _merge_unique(self._avoid, safe["avoid"])
        attempt.consumed = True
        self._version += 1
        return {
            "status": "updated",
            "version": self._version,
            "accepted": accepted,
        }
```

- [ ] **Step 6: Add failing validation and non-mutation tests**

Cover exact keys and types, maximum 8 workflow steps, 8 landmarks, 12 avoid rules, bounded normalized strings, control characters, six consecutive ASCII digits, decimal/tuple coordinates, URLs, absolute paths, `res://`, node paths, repository/test/spec terms, and action-like sequences. Assert rejected candidates do not consume an attempt or change the version.

```python
@pytest.mark.parametrize("unsafe", [
    "密码是 123456",
    "移动到 (12.4, 0, -3.2)",
    "读取 res://game_script/answer.gd",
    "查看 https://example.test/solution",
])
def test_rejects_non_reusable_or_internal_memory(unsafe):
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")
    candidate = valid_candidate()
    candidate["avoid"] = [unsafe]

    with pytest.raises(WorkflowMemoryError, match="invalid_workflow_memory"):
        memory.update(candidate)

    assert memory.read("find_contract")["version"] == 0
    candidate["avoid"] = ["没有提示时先重新观察"]
    assert memory.update(candidate)["version"] == 1
```

- [ ] **Step 7: Implement strict candidate validation**

Use small helpers `_validate_exact_dict`, `_normalize_text`, `_validate_list`, and explicit regexes. Reject the whole candidate with `WorkflowMemoryError("invalid_workflow_memory")`; never silently remove unsafe substrings. Return newly allocated dict/list values so callers cannot mutate stored state.

- [ ] **Step 8: Run the workflow memory tests**

Run:

```bash
PYTHONPATH=ai_play/src ../../.venv/bin/python -m pytest \
  ai_play/tests/test_workflow_memory.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit the state machine**

```bash
git add ai_play/src/ai_play/workflow_memory.py \
  ai_play/tests/test_workflow_memory.py
git commit -m "feat(ai-play): add session workflow memory state"
```

### Task 2: Connect trusted GameSession attempt lifecycle

**Files:**
- Modify: `ai_play/src/ai_play/game_session.py`
- Modify: `ai_play/tests/test_game_session.py`

- [ ] **Step 1: Add a recording lifecycle observer to GameSession tests**

```python
class RecordingAttemptObserver:
    def __init__(self):
        self.started = []
        self.finished = []

    def start_attempt(self, scenario_id):
        self.started.append(scenario_id)

    def finish_attempt(self, status, terminal_reason):
        self.finished.append((status, terminal_reason))


def test_attempt_observer_receives_successful_lifecycle(config):
    observer = RecordingAttemptObserver()
    session = GameSession(config, attempt_observer=observer)
    session.attach(lambda packet: None, "find_contract")

    assert observer.started == ["find_contract"]

    # Reuse the test module's existing valid observation/game-over helpers.
    session.receive_observation(valid_observation(17))
    session.receive_game_over(valid_game_over("success", "correct_password", 17))

    assert observer.finished == [("success", "correct_password")]
```

- [ ] **Step 2: Run the focused lifecycle test and verify it fails**

Run:

```bash
PYTHONPATH=ai_play/src ../../.venv/bin/python -m pytest \
  ai_play/tests/test_game_session.py -k attempt_observer -q
```

Expected: FAIL because `GameSession.__init__` does not accept `attempt_observer`.

- [ ] **Step 3: Add the observer dependency and central lifecycle helpers**

```python
class GameSession:
    def __init__(
        self,
        config,
        trajectory_logger=None,
        attempt_observer=None,
    ):
        self.config = config
        self._trajectory_logger = trajectory_logger
        self._attempt_observer = attempt_observer
        # existing fields unchanged

    def _start_attempt_locked(self, scenario_id):
        self._start_log_attempt_locked(scenario_id)
        if self._attempt_observer is not None:
            self._attempt_observer.start_attempt(scenario_id)

    def _finish_attempt(self, terminal):
        status, terminal_reason = terminal
        if self._attempt_observer is not None:
            self._attempt_observer.finish_attempt(status, terminal_reason)
        self._finish_log_attempt(terminal)
```

Replace direct log lifecycle calls with these helpers while preserving lock boundaries and the existing logging failure behavior.

- [ ] **Step 4: Add tests for failure, stop, disconnect, shutdown, and duplicate terminal events**

Assert mappings:

```python
[
    ("success", "correct_password"),
    ("failure", "wrong_password"),
    ("stopped", "mcp_stop"),
    ("disconnected", "bridge_disconnected"),
    ("shutdown", "mcp_shutdown"),
]
```

Each attempt must emit exactly one `finish_attempt`. Duplicate game-over packets and detach after an already completed game must not emit a second event.

- [ ] **Step 5: Implement exact lifecycle mappings**

Keep gameplay outcomes as `success`/`failure`. Map physical or MCP stops to `stopped`, bridge loss to `disconnected`, and MCP process closure to `shutdown`. Do not alter the `TrajectoryLogger` status schema; it may continue recording its existing `stopped` classification independently.

- [ ] **Step 6: Run all GameSession tests**

Run:

```bash
PYTHONPATH=ai_play/src ../../.venv/bin/python -m pytest \
  ai_play/tests/test_game_session.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit lifecycle wiring**

```bash
git add ai_play/src/ai_play/game_session.py \
  ai_play/tests/test_game_session.py
git commit -m "feat(ai-play): report trusted attempt lifecycle"
```

### Task 3: Expose bounded, unlogged AWM MCP tools

**Files:**
- Modify: `ai_play/src/ai_play/mcp_server.py`
- Modify: `ai_play/tests/test_mcp_server.py`

- [ ] **Step 1: Extend the MCP test fixture and write failing tool-list/read tests**

```python
from ai_play.workflow_memory import SessionWorkflowMemory


def configure_server(monkeypatch, session=None, logger=None, memory=None):
    # existing fixture assignments
    monkeypatch.setattr(
        mcp_server,
        "workflow_memory",
        memory or SessionWorkflowMemory(),
        raising=False,
    )


def test_mcp_exposes_game_and_workflow_memory_tools(monkeypatch):
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    configure_server(monkeypatch, memory=memory)

    result = call_tool("workflow_memory_read", {})

    assert result.structuredContent["version"] == 0
```

Update the list-tools assertion to:

```python
[
    "briefing",
    "observe",
    "act",
    "stop",
    "workflow_memory_read",
    "workflow_memory_update",
]
```

- [ ] **Step 2: Run focused MCP tests and verify failure**

Run:

```bash
PYTHONPATH=ai_play/src ../../.venv/bin/python -m pytest \
  ai_play/tests/test_mcp_server.py -k workflow_memory -q
```

Expected: FAIL because the tools are not registered.

- [ ] **Step 3: Register the in-memory manager and read tool**

```python
from .workflow_memory import SessionWorkflowMemory, WorkflowMemoryError

workflow_memory = None


@mcp.tool()
async def workflow_memory_read() -> CallToolResult:
    """Read validated workflows learned in this orchestrator session."""
    if not _configured() or workflow_memory is None:
        return _error("server_not_ready")
    try:
        scenario_id = await asyncio.to_thread(
            game_session.wait_for_scenario,
            config.wait_timeout_seconds,
        )
        payload = workflow_memory.read(scenario_id)
    except SessionError as error:
        return _error(str(error))
    except WorkflowMemoryError as error:
        return _error(error.code)
    return _result(payload)
```

Initialize one manager in `main()` and inject it into `GameSession` as `attempt_observer`. Do not recreate it on each Godot attach.

- [ ] **Step 4: Write failing update policy and non-logging tests**

Use a valid candidate helper, finish the manager attempt as success/failure, call the MCP tool, and assert accepted counts. Pass invalid content and assert `invalid_workflow_memory` without echoed text. Use `RecordingTrajectoryLogger` and assert both `begun` and `completed` remain empty after read/update.

- [ ] **Step 5: Implement the update tool without an outcome argument**

```python
@mcp.tool()
async def workflow_memory_update(
    goal_pattern: str,
    workflow: list[dict],
    landmarks: list[dict],
    avoid: list[str],
) -> CallToolResult:
    """Promote a validated workflow candidate after a trusted terminal result."""
    if not _configured() or workflow_memory is None:
        return _error("server_not_ready")
    candidate = {
        "goal_pattern": goal_pattern,
        "workflow": workflow,
        "landmarks": landmarks,
        "avoid": avoid,
    }
    try:
        return _result(workflow_memory.update(candidate))
    except WorkflowMemoryError as error:
        return _error(error.code)
```

Do not call `_begin_logged_call` or `_complete_logged_call` in either AWM tool.

- [ ] **Step 6: Run MCP and trajectory logger tests**

Run:

```bash
PYTHONPATH=ai_play/src ../../.venv/bin/python -m pytest \
  ai_play/tests/test_mcp_server.py \
  ai_play/tests/test_trajectory_logger.py -q
```

Expected: all tests pass and trajectory schemas remain unchanged.

- [ ] **Step 7: Commit MCP tools**

```bash
git add ai_play/src/ai_play/mcp_server.py \
  ai_play/tests/test_mcp_server.py
git commit -m "feat(ai-play): expose session AWM tools"
```

### Task 4: Allow and instruct the isolated Codex player

**Files:**
- Modify: `tools/ai_play_codex_orchestrator.py`
- Modify: `tests/test_ai_play_codex_orchestrator.py`

- [ ] **Step 1: Write failing allowlist and prompt tests**

```python
def test_player_config_allows_only_gameplay_and_session_awm(tmp_path):
    orchestrator = load_orchestrator()
    home = tmp_path / "codex-home"
    orchestrator.write_player_codex_config(
        home,
        "gpt-5.6",
        "high",
        "http://127.0.0.1:8766/mcp",
    )

    text = (home / "config.toml").read_text(encoding="utf-8")
    assert 'enabled_tools = ["briefing", "workflow_memory_read", "observe", "act", "workflow_memory_update"]' in text
    assert "generate_memories = false" in text
    assert "use_memories = false" in text


def test_player_prompt_requires_awm_lifecycle(tmp_path):
    orchestrator = load_orchestrator()
    prompt = orchestrator.build_player_prompt(
        3, "find_contract", tmp_path / "ai_play_run_config.json"
    )

    assert "briefing，再调用 workflow_memory_read，再调用 observe" in prompt
    assert "终局后调用 workflow_memory_update" in prompt
    assert "成功局" in prompt
    assert "失败局只提交 avoid" in prompt
    assert "不要保存图片" in prompt
    assert "不要保存密码" in prompt
```

- [ ] **Step 2: Run focused orchestrator tests and verify failure**

Run:

```bash
../../.venv/bin/python -m pytest \
  tests/test_ai_play_codex_orchestrator.py \
  -k 'awm or workflow_memory' -q
```

Expected: FAIL because the allowlist and prompt do not include AWM.

- [ ] **Step 3: Expand only the fixed player tool allowlist**

```python
PLAYER_TOOL_NAMES = (
    "briefing",
    "workflow_memory_read",
    "observe",
    "act",
    "workflow_memory_update",
)
```

Keep `stop` excluded and preserve the existing filesystem, network, Web, agents, `[memories]`, and ephemeral settings.

- [ ] **Step 4: Update the player prompt with exact per-attempt rules**

Require:

1. `briefing -> workflow_memory_read -> observe/act`;
2. memory is high-level guidance and never authorizes actions without a fresh observation;
3. after a success, submit abstract workflow/landmarks/avoid;
4. after a normal failure, leave workflow/landmarks empty and submit only supported avoid rules;
5. after stopped/disconnected/abnormal attempts, do not call update;
6. never submit screenshots, image references, passwords, random clues, coordinates, action sequences, paths, or internal knowledge;
7. continue to the next run only after the eligible update response.

- [ ] **Step 5: Run all orchestrator and supervisor tests**

Run:

```bash
../../.venv/bin/python -m pytest \
  tests/test_ai_play_codex_orchestrator.py \
  tests/test_ai_play_supervisor.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit player wiring**

```bash
git add tools/ai_play_codex_orchestrator.py \
  tests/test_ai_play_codex_orchestrator.py
git commit -m "feat(ai-play): teach black-box player session AWM"
```

### Task 5: Finish documentation and repository verification

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/scope/2026-07-31-session-awm/spec-session-awm.md` only if implementation reveals an approved-design inconsistency

- [ ] **Step 1: Verify documentation states the implemented contract**

Confirm both documents say:

- the isolated player sees exactly five allowlisted tools;
- AWM is in MCP process memory and scoped to one orchestrator invocation;
- trusted terminal results control promotion;
- success learns workflow/landmarks/avoid, failure learns avoid only, abnormal attempts learn nothing;
- images can inform extraction but are never stored;
- AWM does not enter `TrajectoryLogger` and leaves no file after MCP exit;
- Codex built-in memories remain disabled.

- [ ] **Step 2: Run the full affected Python suite**

Run:

```bash
PYTHONPATH=ai_play/src ../../.venv/bin/python -m pytest \
  ai_play/tests \
  tests/test_ai_play_codex_orchestrator.py \
  tests/test_ai_play_supervisor.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run the affected Godot tests**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
```

Expected: each command exits 0 and prints its corresponding `tests passed` marker. No Godot protocol or gameplay behavior should have changed.

- [ ] **Step 4: Run static integration checks**

Run:

```bash
bash tests/check_ai_play_lobby.sh
bash tests/check_ai_play_garden.sh
git diff --check
git status --short
```

Expected: scripts exit 0, `git diff --check` prints nothing, and status contains only intentional AWM/doc changes.

- [ ] **Step 5: Commit documentation and final verification state**

```bash
git add ai_play/README.md \
  docs/wiki/ai-play/system-guide.md \
  docs/scope/2026-07-31-session-awm/plan-session-awm.md
git commit -m "docs(ai-play): document session workflow memory"
```

- [ ] **Step 6: Do not run real external acceptance without separate approval**

Do not start a real Codex/Godot orchestrated session. Such a run requires a new explicit confirmation covering screenshots, credentials, token cost, and local trajectory persistence.
