# AI Play MCP Trajectory Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist each Godot-connected AI Play attempt as an atomic MCP trajectory with structured results and separately stored JPEGs, grouped into collision-safe three-attempt runs.

**Architecture:** A new thread-safe `TrajectoryLogger` is the only filesystem writer. `GameSession` owns attempt lifecycle notifications because it already validates bridge attachment and terminal state; `mcp_server.py` owns tool-call logging because it sees the exact approved MCP request/result boundary. No public tool or bridge packet changes.

**Tech Stack:** Python 3, standard-library `pathlib`/`json`/`tempfile`/`threading`, FastMCP, pytest.

## Global Constraints

- Default log root is `~/workspace/cogito_logs/mcplogs`; `AI_PLAY_LOG_ROOT` overrides it.
- A run starts only when Godot successfully attaches and uses `YYYYMMDD-HH-MM`, then `-02`, `-03`, and so on for collisions.
- One run contains at most three attempts; later attachments rotate to a new run.
- `trajectory.json` has exactly `trajectory` and `result` at the top level.
- Record `observe`, `act`, and `stop`; never record `briefing`.
- Count every `act()` invocation that reaches the Python function before the attempt terminates, including invalid and stale requests.
- Persist JPEG bytes under `attempt-NN/imgs/`; never persist image Base64 in JSON.
- Preserve the current public MCP tools, protocol-v3 bridge contract, loopback-only binding, Escape stop, and input-release behavior.
- Never persist credentials, prompts, hidden state, source paths, repository notes, tests, specs, plans, `game_script/`, or `code_read/`.
- Do not run a real external MCP/model acceptance test.
- Preserve unrelated existing edits in Godot scripts/tests and `tutorial/__pycache__/`.

---

### Task 1: Configuration and Atomic Trajectory Logger

**Files:**
- Create: `ai_play/src/ai_play/trajectory_logger.py`
- Create: `ai_play/tests/test_trajectory_logger.py`
- Modify: `ai_play/src/ai_play/config.py`
- Modify: `ai_play/tests/test_config.py`
- Modify: `ai_play/.env.example`

**Interfaces:**
- Consumes: `AI_PLAY_LOG_ROOT`, timezone-aware wall-clock datetimes, approved MCP request/result dictionaries, and optional JPEG bytes.
- Produces: `Config.log_root: pathlib.Path`.
- Produces: `LogPersistenceError`, `ToolCallToken(run_sequence: int, attempt: int, event_index: int)`.
- Produces: `TrajectoryLogger(root: Path, now: Callable[[], datetime] | None = None)`.
- Produces: `start_attempt() -> Path`, `begin_tool_call(tool: str, request: dict) -> ToolCallToken | None`, `complete_tool_call(token: ToolCallToken | None, is_error: bool, structured_content: dict, image_bytes: bytes | None = None) -> None`, `finish_attempt(status: str) -> None`, and `close() -> None`.
- Produces: read-only `current_attempt_number: int | None`.

- [ ] **Step 1: Write failing log-root configuration tests**

Add:

```python
from pathlib import Path


def test_config_defaults_log_root_under_workspace(monkeypatch):
    monkeypatch.delenv("AI_PLAY_LOG_ROOT", raising=False)
    assert Config.from_env().log_root == (
        Path("~/workspace/cogito_logs/mcplogs").expanduser()
    )


def test_config_expands_log_root_override(monkeypatch):
    monkeypatch.setenv("AI_PLAY_LOG_ROOT", "~/custom-cogito-logs")
    assert Config.from_env().log_root == Path("~/custom-cogito-logs").expanduser()


def test_config_rejects_empty_log_root(monkeypatch):
    monkeypatch.setenv("AI_PLAY_LOG_ROOT", "   ")
    with pytest.raises(ValueError, match="AI_PLAY_LOG_ROOT"):
        Config.from_env()
```

- [ ] **Step 2: Run configuration tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_config.py -q
```

Expected: FAIL because `Config` has no `log_root`.

- [ ] **Step 3: Implement log-root configuration**

Add to `Config` and `from_env()`:

```python
from pathlib import Path


@dataclass(frozen=True)
class Config:
    log_root: Path = Path("~/workspace/cogito_logs/mcplogs").expanduser()

    @classmethod
    def from_env(cls) -> "Config":
        config = cls(
            ws_host=os.environ.get("AI_PLAY_WS_HOST", cls.ws_host).strip(),
            ws_port=_read_int("AI_PLAY_WS_PORT", cls.ws_port),
            wait_timeout_seconds=_read_float(
                "AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS",
                cls.wait_timeout_seconds,
            ),
            stop_timeout_seconds=_read_float(
                "AI_PLAY_STOP_TIMEOUT_SECONDS",
                cls.stop_timeout_seconds,
            ),
            max_act_requests=_read_int(
                "AI_PLAY_MAX_ACT_REQUESTS",
                cls.max_act_requests,
            ),
            log_root=_read_path("AI_PLAY_LOG_ROOT", cls.log_root),
        )


def _read_path(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return Path(default).expanduser()
    if not raw.strip():
        raise ValueError(f"{name} must not be empty")
    return Path(raw).expanduser()
```

Add:

```dotenv
AI_PLAY_LOG_ROOT=~/workspace/cogito_logs/mcplogs
```

to `ai_play/.env.example`.

- [ ] **Step 4: Run configuration tests and verify GREEN**

Run the command from Step 2. Expected: all configuration tests pass.

- [ ] **Step 5: Write failing logger lifecycle tests**

Create fixed-clock helpers and tests that assert the complete public contract:

```python
from datetime import datetime, timedelta, timezone
import json

from ai_play.trajectory_logger import LogPersistenceError, TrajectoryLogger


class Clock:
    def __init__(self):
        self.value = datetime(2026, 7, 24, 14, 35, tzinfo=timezone.utc)

    def __call__(self):
        current = self.value
        self.value += timedelta(milliseconds=1)
        return current


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_first_attachment_creates_run_and_attempt(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    attempt_dir = logger.start_attempt()

    assert attempt_dir == tmp_path / "20260724-14-35" / "attempt-01"
    assert load_json(attempt_dir / "trajectory.json") == {
        "trajectory": [],
        "result": {"total_steps": 0, "status": "in_progress"},
    }
    assert load_json(tmp_path / "20260724-14-35" / "run.json") == {
        "started_at": "2026-07-24T14:35:00+00:00",
        "max_attempts": 3,
        "completed_attempts": 0,
        "status": "in_progress",
        "successful_attempt": None,
        "attempts": [
            {"attempt": 1, "status": "in_progress", "total_steps": 0},
        ],
    }


def test_collision_and_fourth_attempt_rotate_runs(tmp_path):
    occupied = tmp_path / "20260724-14-35"
    occupied.mkdir()
    logger = TrajectoryLogger(tmp_path, now=Clock())

    assert logger.start_attempt().parent.name == "20260724-14-35-02"
    logger.finish_attempt("failure")
    logger.start_attempt()
    logger.finish_attempt("failure")
    logger.start_attempt()
    logger.finish_attempt("failure")
    assert logger.start_attempt().parent.name == "20260724-14-35-03"
    assert logger.current_attempt_number == 1
```

Add request, image, terminal, close, and persistence-failure tests using these
concrete assertions:

```python
def test_act_request_is_persisted_before_completion(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    attempt_dir = logger.start_attempt()
    token = logger.begin_tool_call("act", {
        "observation_id": 7,
        "actions": [{"type": "wait", "duration_ms": 50}],
    })

    snapshot = load_json(attempt_dir / "trajectory.json")
    assert snapshot["result"]["total_steps"] == 1
    assert snapshot["trajectory"][0]["act_step"] == 1
    assert snapshot["trajectory"][0]["response"] is None


def test_completion_saves_exact_jpeg_without_base64(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    attempt_dir = logger.start_attempt()
    logger.begin_tool_call("observe", {})
    token = logger.begin_tool_call("act", {
        "observation_id": 7,
        "actions": [{"type": "wait", "duration_ms": 50}],
    })
    jpeg = b"\xff\xd8\xfftrajectory-image\xff\xd9"
    logger.complete_tool_call(token, False, {
        "status": "ready",
        "observation": {"observation_id": 8},
    }, jpeg)

    relative = "imgs/000002-act-obs000008.jpg"
    assert (attempt_dir / relative).read_bytes() == jpeg
    serialized = (attempt_dir / "trajectory.json").read_text(encoding="utf-8")
    assert relative in serialized
    assert "base64" not in serialized


def test_terminal_attempt_ignores_later_calls(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    attempt_dir = logger.start_attempt()
    logger.begin_tool_call("act", {"observation_id": 7, "actions": []})
    logger.finish_attempt("success")

    assert logger.begin_tool_call("act", {
        "observation_id": 7,
        "actions": [],
    }) is None
    snapshot = load_json(attempt_dir / "trajectory.json")
    assert snapshot["result"] == {"total_steps": 1, "status": "success"}


def test_close_marks_active_attempt_and_run_stopped(tmp_path):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    attempt_dir = logger.start_attempt()
    logger.close()
    assert load_json(attempt_dir / "trajectory.json")["result"]["status"] == "stopped"
    assert load_json(attempt_dir.parent / "run.json")["status"] == "stopped"


def test_atomic_write_failure_disables_logger(tmp_path, monkeypatch):
    logger = TrajectoryLogger(tmp_path, now=Clock())
    logger.start_attempt()
    monkeypatch.setattr(
        logger,
        "_atomic_write_json",
        lambda path, payload: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(LogPersistenceError, match="logging_failed"):
        logger.begin_tool_call("observe", {})
    with pytest.raises(LogPersistenceError, match="logging_failed"):
        logger.begin_tool_call("observe", {})
```

- [ ] **Step 6: Run logger tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_trajectory_logger.py -q
```

Expected: collection fails because `ai_play.trajectory_logger` does not exist.

- [ ] **Step 7: Implement the focused logger**

Use these public types:

```python
class LogPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolCallToken:
    run_sequence: int
    attempt: int
    event_index: int


class TrajectoryLogger:
    MAX_ATTEMPTS = 3
    ALLOWED_TOOLS = {"observe", "act", "stop"}
    ALLOWED_STATUSES = {"in_progress", "success", "failure", "stopped"}

    def __init__(self, root, now=None):
        self.root = Path(root).expanduser()
        self._now = now or (lambda: datetime.now().astimezone())
        self._lock = Lock()
        self._run_dir = None
        self._run = None
        self._attempt_dir = None
        self._attempt = None
        self._run_sequence = 0
        self._attempt_states = {}
        self._failed = False
```

Implement `start_attempt()` under `_lock`:

```python
if self._run is None or self._run["status"] != "in_progress" or (
    len(self._run["attempts"]) >= self.MAX_ATTEMPTS
):
    self._create_run_locked()
attempt_number = len(self._run["attempts"]) + 1
self._attempt_dir = self._run_dir / f"attempt-{attempt_number:02d}"
self._attempt_dir.mkdir(mode=0o700)
(self._attempt_dir / "imgs").mkdir(mode=0o700)
self._attempt = {
    "trajectory": [],
    "result": {"total_steps": 0, "status": "in_progress"},
}
self._attempt_states[(self._run_sequence, attempt_number)] = (
    self._attempt_dir,
    self._attempt,
)
self._run["attempts"].append({
    "attempt": attempt_number,
    "status": "in_progress",
    "total_steps": 0,
})
self._write_snapshots_locked()
return self._attempt_dir
```

`begin_tool_call()` must deep-copy the request, append the pending entry, update
the act count before any gameplay validation, and persist before returning:

```python
if self._failed:
    raise LogPersistenceError("logging_failed")
if self._attempt is None or self._attempt["result"]["status"] != "in_progress":
    return None
if tool not in self.ALLOWED_TOOLS:
    return None
event_index = len(self._attempt["trajectory"]) + 1
entry = {
    "event_index": event_index,
    "tool": tool,
    "requested_at": self._timestamp(),
    "completed_at": None,
    "request": deepcopy(request),
    "response": None,
    "images": [],
}
if tool == "act":
    self._attempt["result"]["total_steps"] += 1
    entry["act_step"] = self._attempt["result"]["total_steps"]
self._attempt["trajectory"].append(entry)
self._sync_attempt_summary_locked()
self._write_snapshots_locked()
return ToolCallToken(
    self._run_sequence,
    self.current_attempt_number,
    event_index,
)
```

`complete_tool_call()` uses
`self._attempt_states[(token.run_sequence, token.attempt)]` to locate the
token's original attempt even if a reconnect has already started another one.
It writes the JPEG unchanged, then stores:

```python
entry["completed_at"] = self._timestamp()
entry["response"] = {
    "is_error": bool(is_error),
    "structured_content": deepcopy(structured_content),
}
```

The filename uses:

```python
observation = structured_content.get("observation")
observation_id = (
    observation.get("observation_id")
    if isinstance(observation, dict)
    else None
)
suffix = (
    f"obs{observation_id:06d}"
    if type(observation_id) is int
    else "no-observation"
)
relative = f"imgs/{token.event_index:06d}-{entry['tool']}-{suffix}.jpg"
```

`finish_attempt()` is idempotent for an already terminal attempt, synchronizes
the compact run entry, and derives the run status:

```python
if status == "success":
    self._run["status"] = "success"
    self._run["successful_attempt"] = self.current_attempt_number
elif len(self._run["attempts"]) == self.MAX_ATTEMPTS:
    statuses = [item["status"] for item in self._run["attempts"]]
    self._run["status"] = (
        "failure" if all(item == "failure" for item in statuses) else "stopped"
    )
```

Implement `_atomic_write_json(path, payload)` using a same-directory
`tempfile.NamedTemporaryFile(delete=False)`, `json.dump(..., ensure_ascii=False,
indent=2)`, `flush()`, `os.fsync()`, `os.chmod(temp_name, 0o600)`, and
`os.replace(temp_name, path)`. On any persistence exception, unlink the
temporary file if present, set `_failed = True`, and raise
`LogPersistenceError("logging_failed")`.

- [ ] **Step 8: Run focused logger and configuration tests**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_config.py \
  ai_play/tests/test_trajectory_logger.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit Task 1**

```bash
git add \
  ai_play/src/ai_play/config.py \
  ai_play/src/ai_play/trajectory_logger.py \
  ai_play/tests/test_config.py \
  ai_play/tests/test_trajectory_logger.py \
  ai_play/.env.example
git commit -m "feat: add MCP trajectory logger"
```

---

### Task 2: Connect Attempt Lifecycle to `GameSession`

**Files:**
- Modify: `ai_play/src/ai_play/game_session.py`
- Modify: `ai_play/tests/test_game_session.py`

**Interfaces:**
- Consumes: `TrajectoryLogger.start_attempt()`, `finish_attempt(status)`, and `close()`.
- Produces: `GameSession(config, trajectory_logger=None)` with fail-closed attach and terminal notifications.

- [ ] **Step 1: Write failing lifecycle tests**

Add a recording fake:

```python
class RecordingLogger:
    def __init__(self, fail_start=False):
        self.fail_start = fail_start
        self.events = []

    def start_attempt(self):
        if self.fail_start:
            raise LogPersistenceError("logging_failed")
        self.events.append(("start", None))

    def finish_attempt(self, status):
        self.events.append(("finish", status))

    def close(self):
        self.events.append(("close", None))
```

Add focused tests:

```python
def test_successful_attach_starts_log_attempt():
    logger = RecordingLogger()
    session = GameSession(Config(), trajectory_logger=logger)
    session.attach(lambda packet: True)
    assert logger.events == [("start", None)]


def test_logging_failure_rejects_attach_without_controller():
    logger = RecordingLogger(fail_start=True)
    session = GameSession(Config(), trajectory_logger=logger)
    with pytest.raises(SessionError, match="logging_failed"):
        session.attach(lambda packet: True)
    assert session._send_packet is None
```

Add terminal and disconnect assertions:

```python
@pytest.mark.parametrize(
    ("outcome", "reason", "expected"),
    [
        ("success", "correct_password", "success"),
        ("failure", "wrong_password", "failure"),
        ("failure", "max_requests", "failure"),
    ],
)
def test_game_over_finishes_log_without_later_tool_call(
    outcome, reason, expected
):
    logger = RecordingLogger()
    session = GameSession(Config(), trajectory_logger=logger)
    session.attach(lambda packet: True)
    session.receive_observation(observation(7))
    session.receive_game_over({
        "type": "game_over",
        "protocol_version": 3,
        "observation_id": 7,
        "outcome": outcome,
        "reason": reason,
    })
    assert logger.events == [("start", None), ("finish", expected)]


def test_disconnect_finishes_attempt_once():
    logger = RecordingLogger()
    session = GameSession(Config(), trajectory_logger=logger)
    session.attach(lambda packet: True)
    session.detach("connection_closed")
    session.detach("connection_closed")
    assert logger.events == [("start", None), ("finish", "stopped")]


def test_mcp_shutdown_closes_log():
    logger = RecordingLogger()
    session = GameSession(Config(), trajectory_logger=logger)
    session.attach(lambda packet: True)
    session.detach("mcp_shutdown")
    assert logger.events == [
        ("start", None),
        ("finish", "stopped"),
        ("close", None),
    ]
```

Extend the existing `test_stop_sends_mcp_stop_and_acknowledges_cancellation`
assertion with:

```python
assert logger.events[-1] == ("finish", "stopped")
```

Add an Escape packet test using `session.receive_stop(...)` and the same final
assertion. Re-send the identical terminal packet and assert the events list did
not grow.

- [ ] **Step 2: Run focused lifecycle tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_game_session.py -q -k "log or logging"
```

Expected: FAIL because `GameSession` has no logger dependency or notifications.

- [ ] **Step 3: Implement lifecycle notifications**

Change construction and add stable adapters:

```python
class GameSession:
    def __init__(self, config, trajectory_logger=None):
        self.config = config
        self._trajectory_logger = trajectory_logger

    def _start_log_attempt_locked(self):
        if self._trajectory_logger is None:
            return
        try:
            self._trajectory_logger.start_attempt()
        except LogPersistenceError as error:
            raise SessionError("logging_failed") from error

    def _finish_log_attempt(self, status):
        if self._trajectory_logger is None:
            return
        try:
            self._trajectory_logger.finish_attempt(status)
        except LogPersistenceError as error:
            raise SessionError("logging_failed") from error
```

Call `_start_log_attempt_locked()` after attach state validation but before
assigning `_send_packet`. In `receive_game_over()`, derive `success` or
`failure` from the validated outcome after committing and notifying the session
state. In `receive_stop()`, `receive_stop_ack()`, and a nonterminal `detach()`,
finish as `stopped`.

Preserve `reason` in `detach(reason)`. For `mcp_shutdown`, call
`trajectory_logger.close()` after session state is safe. Logger notifications
must not hold `_condition` while performing disk I/O except for the pre-attach
start gate; capture the notification status under the condition lock, then call
the logger after releasing it.

- [ ] **Step 4: Run focused and complete session tests**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_game_session.py -q
```

Expected: all tests pass, including request-limit behavior.

- [ ] **Step 5: Commit Task 2**

```bash
git add ai_play/src/ai_play/game_session.py ai_play/tests/test_game_session.py
git commit -m "feat: bind trajectory logs to game sessions"
```

---

### Task 3: Record MCP Requests, Results, Errors, and Images

**Files:**
- Modify: `ai_play/src/ai_play/mcp_server.py`
- Modify: `ai_play/tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `TrajectoryLogger.begin_tool_call()` and `complete_tool_call()`.
- Produces: durable logging wrappers for `observe`, `act`, and `stop` without changing their public schemas.

- [ ] **Step 1: Write failing MCP boundary tests**

Add a recording fake:

```python
class RecordingTrajectoryLogger:
    def __init__(self, fail_begin=False, fail_complete=False):
        self.fail_begin = fail_begin
        self.fail_complete = fail_complete
        self.begun = []
        self.completed = []

    def begin_tool_call(self, tool, request):
        if self.fail_begin:
            raise LogPersistenceError("logging_failed")
        token = ToolCallToken(1, 1, len(self.begun) + 1)
        self.begun.append((tool, request))
        return token

    def complete_tool_call(
        self, token, is_error, structured_content, image_bytes=None
    ):
        if self.fail_complete:
            raise LogPersistenceError("logging_failed")
        self.completed.append(
            (token, is_error, structured_content, image_bytes)
        )
```

Configure it alongside the fake game session and add:

```python
def test_observe_logs_request_result_and_exact_image(monkeypatch):
    logger = RecordingTrajectoryLogger()
    configure_server(monkeypatch, logger=logger)
    result = call_tool("observe", {})

    assert logger.begun == [("observe", {})]
    assert logger.completed[0][1] is False
    assert logger.completed[0][2] == result.structuredContent
    assert logger.completed[0][3] == b"\xff\xd8\xffmcp-image\xff\xd9"


def test_act_error_is_logged(monkeypatch):
    logger = RecordingTrajectoryLogger()
    configure_server(monkeypatch, logger=logger)
    arguments = {
        "observation_id": 6,
        "actions": [{"type": "wait", "duration_ms": 50}],
    }
    result = call_tool("act", arguments)

    assert logger.begun == [("act", arguments)]
    assert logger.completed[0][1] is True
    assert logger.completed[0][2] == {
        "status": "error",
        "code": "stale_observation",
    }
    assert result.isError is True


def test_stop_is_logged_without_image(monkeypatch):
    logger = RecordingTrajectoryLogger()
    configure_server(monkeypatch, logger=logger)
    call_tool("stop", {})
    assert logger.begun == [("stop", {})]
    assert logger.completed[0][3] is None


def test_briefing_is_not_logged(monkeypatch):
    logger = RecordingTrajectoryLogger()
    configure_server(monkeypatch, logger=logger)
    call_tool("briefing", {})
    assert logger.begun == []
    assert logger.completed == []


def test_logging_begin_failure_prevents_session_call(monkeypatch):
    session = fake_ready_session()
    logger = RecordingTrajectoryLogger(fail_begin=True)
    configure_server(monkeypatch, session=session, logger=logger)
    result = call_tool("act", {
        "observation_id": 7,
        "actions": [{"type": "wait", "duration_ms": 50}],
    })
    assert result.structuredContent == {
        "status": "error",
        "code": "logging_failed",
    }
    assert session.act_calls == []


def test_logging_completion_failure_returns_stable_error(monkeypatch):
    logger = RecordingTrajectoryLogger(fail_complete=True)
    configure_server(monkeypatch, logger=logger)
    result = call_tool("observe", {})
    assert result.structuredContent == {
        "status": "error",
        "code": "logging_failed",
    }
```

Implement `call_tool()` as a small test helper around
`create_connected_server_and_client_session`, and add `act_calls` to
`FakeReadySession`. Keep the existing tool-list assertion exactly:

```python
assert [tool.name for tool in tools.tools] == [
    "briefing",
    "observe",
    "act",
    "stop",
]
```

- [ ] **Step 2: Run MCP tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_mcp_server.py -q
```

Expected: logging assertions fail because the MCP boundary does not use a logger.

- [ ] **Step 3: Implement MCP logging wrappers**

Add the global and helpers:

```python
trajectory_logger = None


def _begin_logged_call(tool, request):
    try:
        return trajectory_logger.begin_tool_call(tool, request)
    except LogPersistenceError:
        return _error("logging_failed")


def _complete_logged_call(token, result, image_bytes=None):
    try:
        trajectory_logger.complete_tool_call(
            token,
            bool(result.isError),
            result.structuredContent,
            image_bytes,
        )
    except LogPersistenceError:
        return _error("logging_failed")
    return result
```

Refactor each agreed tool into this order:

```python
@mcp.tool()
async def act(observation_id: int, actions: list[dict]) -> CallToolResult:
    request = {"observation_id": observation_id, "actions": actions}
    token = _begin_logged_call("act", request)
    if isinstance(token, CallToolResult):
        return token
    try:
        session_result = await asyncio.to_thread(
            game_session.act,
            observation_id,
            actions,
            config.wait_timeout_seconds,
        )
    except SessionError as error:
        return _complete_logged_call(token, _error(str(error)))
    payload, image_bytes = game_session.to_mcp_payload(session_result)
    return _complete_logged_call(
        token,
        _result(payload, image_bytes),
        image_bytes,
    )
```

Apply the same wrapper to `observe` and `stop`. Leave `briefing` unchanged.
`_configured()` must require `trajectory_logger` for recorded tools.

Construct and share one logger in `main()`:

```python
global config, game_session, trajectory_logger
config = Config.from_env()
trajectory_logger = TrajectoryLogger(config.log_root)
game_session = GameSession(config, trajectory_logger=trajectory_logger)
```

The logger creates no directory until `GameSession.attach()`.

- [ ] **Step 4: Run MCP, logger, and session tests**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest \
  ai_play/tests/test_trajectory_logger.py \
  ai_play/tests/test_game_session.py \
  ai_play/tests/test_mcp_server.py -q
```

Expected: all focused tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add ai_play/src/ai_play/mcp_server.py ai_play/tests/test_mcp_server.py
git commit -m "feat: record MCP gameplay trajectories"
```

---

### Task 4: Document Persistence and Verify the Affected System

**Files:**
- Modify: `ai_play/README.md`
- Modify: `README_AI_PLAY.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Test: `ai_play/tests/test_config.py`
- Test: `ai_play/tests/test_trajectory_logger.py`
- Test: `ai_play/tests/test_game_session.py`
- Test: `ai_play/tests/test_mcp_server.py`

**Interfaces:**
- Consumes: implemented environment variable, directory layout, privacy boundary, status semantics, and verification commands.
- Produces: operator-facing documentation consistent with runtime behavior.

- [ ] **Step 1: Update the AI Play README**

Replace the obsolete “server does not persist trajectories” statement with:

```markdown
启用 AI Play 后，MCP Server 会把 `observe`、`act`、`stop` 的获准公开请求、
结构化结果和 JPEG 保存到 `AI_PLAY_LOG_ROOT`。默认目录是
`~/workspace/cogito_logs/mcplogs`。日志不包含 `briefing`、图片 Base64、提示词、
凭据、隐藏状态或仓库文件。
```

Document the `run.json`, `attempt-NN/trajectory.json`, and `imgs/` layout;
`total_steps`; the four status values; three-attempt rotation; screenshot
persistence impact; and:

```dotenv
AI_PLAY_LOG_ROOT=~/workspace/cogito_logs/mcplogs
```

- [ ] **Step 2: Update the root guide and Wiki**

Change `README_AI_PLAY.md` and `docs/wiki/ai-play/system-guide.md` from
“不保存截图或游玩轨迹” to the new opt-in AI Play persistence contract. State
that the logger records only approved MCP boundary data and that replaying
stored images into a real model remains a separately confirmed token/cost/privacy
operation. Keep credentials and hidden-state prohibitions unchanged.

While touching the Wiki, align the existing bridge reference with the current
protocol version `3` and its private `end_game/failure/max_requests` packet.

- [ ] **Step 3: Run the complete Python AI Play suite**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
```

Expected: all tests pass.

- [ ] **Step 4: Run affected shell checks**

Run:

```bash
bash tests/check_ai_play_start_script.sh
bash tests/check_ai_play_mcp_only.sh
```

Expected: both scripts exit 0.

- [ ] **Step 5: Run final repository checks**

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` exits 0. Status shows only intentional logging
changes plus the pre-existing unrelated Godot edits and
`tutorial/__pycache__/`.

- [ ] **Step 6: Commit Task 4**

```bash
git add \
  ai_play/README.md \
  README_AI_PLAY.md \
  docs/wiki/ai-play/system-guide.md
git commit -m "docs: explain MCP trajectory persistence"
```
