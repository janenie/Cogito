# Claude AI Player Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hardened Claude Code AI First Play orchestrator with full Codex feature parity while preserving the existing Codex CLI and safety behavior.

**Architecture:** Extract model-neutral run paths, trusted environments, player prompts, process supervision, and cleanup into `tools/ai_play_orchestrator_common.py`. Keep authentication, temporary configuration, CLI construction, and argument names in thin Codex and Claude entry points; the Claude entry point reads an explicitly selected trusted settings file, copies only approved provider variables into a private temporary settings file, and launches one bare non-persistent agent turn with only allowlisted MCP tools.

**Tech Stack:** Python 3 standard library, pytest, Claude Code CLI 2.1.212, FastMCP Streamable HTTP, Godot 4.7 supervisor integration.

---

### Task 1: Lock the existing Codex behavior before extraction

**Files:**
- Modify: `tests/test_ai_play_codex_orchestrator.py`
- Test: `tests/test_ai_play_codex_orchestrator.py`

- [ ] **Step 1: Add a failing compatibility test for the future common module boundary**

Add this test beside the existing path/environment tests:

```python
def test_codex_entry_reexports_common_orchestration_contract():
    orchestrator = load_orchestrator()

    assert orchestrator.DEFAULT_WS_HOST == "127.0.0.1"
    assert orchestrator.DEFAULT_WS_PORT == 8765
    assert orchestrator.DEFAULT_MCP_PORT == 8766
    assert orchestrator.BASE_PLAYER_TOOL_NAMES == (
        "briefing",
        "observe",
        "act",
    )
    assert orchestrator.AWM_PLAYER_TOOL_NAMES == (
        "briefing",
        "workflow_memory_read",
        "observe",
        "act",
        "workflow_memory_update",
    )
```

- [ ] **Step 2: Run the focused compatibility test**

Run:

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest \
  tests/test_ai_play_codex_orchestrator.py::test_codex_entry_reexports_common_orchestration_contract -q
```

Expected: PASS against the current file, establishing the names that the refactor must preserve.

- [ ] **Step 3: Run the complete existing orchestrator baseline**

Run:

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest \
  tests/test_ai_play_codex_orchestrator.py tests/test_ai_play_supervisor.py -q
```

Expected: PASS; record the test count before moving code.

- [ ] **Step 4: Commit the characterization test**

```bash
git add tests/test_ai_play_codex_orchestrator.py
git commit -m "test(ai-play): lock orchestrator compatibility contract"
```

### Task 2: Extract the model-neutral orchestration core

**Files:**
- Create: `tools/ai_play_orchestrator_common.py`
- Modify: `tools/ai_play_codex_orchestrator.py`
- Modify: `tests/test_ai_play_codex_orchestrator.py`
- Test: `tests/test_ai_play_codex_orchestrator.py`

- [ ] **Step 1: Change process tests to describe a generic player label**

Update the session-test calls from Codex-specific keyword names to this shared signature and keep `player_label="codex"` so observable labels remain unchanged:

```python
result = orchestrator.run_orchestrated_session(
    mcp_command=["python", "-m", "ai_play.mcp_server"],
    player_label="codex",
    player_command=["codex", "exec"],
    supervisor_command=["python", "supervisor.py"],
    prompt="briefing",
    mcp_env={},
    player_env={},
    supervisor_env={},
    mcp_cwd=tmp_path,
    player_cwd=tmp_path,
    supervisor_cwd=tmp_path,
    ws_port=8765,
    mcp_port=8766,
    mcp_start_timeout_seconds=1.0,
    player_exit_grace_seconds=0.0,
    idle_timeout_seconds=10.0,
    player_final_grace_seconds=0.0,
)
```

Apply this keyword mapping in `test_session_starts_trusted_mcp_before_codex_and_supervisor`,
`test_session_allows_codex_to_finish_after_supervisor_terminal_exit`,
`test_session_stops_when_all_children_are_idle`,
`test_sidecar_readiness_failure_never_starts_codex_or_supervisor`,
`test_codex_early_exit_terminates_trusted_mcp`, and
`test_keyboard_interrupt_terminates_all_started_processes`. Patch process helpers through
`orchestrator._common` after extraction; assertions must still expect
`started == ["mcp", "codex", "supervisor"]`.

- [ ] **Step 2: Run one renamed process test and verify the old implementation fails**

Run:

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest \
  tests/test_ai_play_codex_orchestrator.py::test_session_starts_trusted_mcp_before_codex_and_supervisor -q
```

Expected: FAIL with an unexpected `player_label` keyword.

- [ ] **Step 3: Create the common module with the exact shared surface**

Move these definitions byte-for-byte from the Codex module into `tools/ai_play_orchestrator_common.py`, preserving their existing behavior: `RunPaths`, `_is_relative_to`, `validate_isolated_session_root`, `create_run_paths`, `validate_model_argument`, `build_player_developer_instructions`, `build_core_env`, `build_trusted_mcp_env`, `build_supervisor_env`, `build_mcp_command`, `build_supervisor_command`, `build_player_prompt`, `_start_output_reader`, `wait_for_listener`, `_start_process`, `_read_labeled_output`, `_print_available_output`, `_terminate_process`, and `is_port_listening`. Move their required imports and these constants with them:

```python
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SESSION_ROOT = (
    Path(REPO_ROOT.anchor) / "cogito_ai_player_runs"
    if os.name == "nt"
    else Path("/tmp/cogito_ai_player_runs")
)
DEFAULT_WS_HOST = "127.0.0.1"
DEFAULT_WS_PORT = 8765
DEFAULT_MCP_PORT = 8766
BASE_PLAYER_TOOL_NAMES = ("briefing", "observe", "act")
AWM_PLAYER_TOOL_NAMES = (
    "briefing",
    "workflow_memory_read",
    "observe",
    "act",
    "workflow_memory_update",
)
CORE_ENV_NAMES = ("PATH", "PATHEXT", "SystemRoot", "WINDIR", "ComSpec")
```

Extract the repeated HOME/AppData/temp construction from the existing Codex player and supervisor environment builders into this model-neutral helper:

```python
def build_isolated_process_env(
    environment_root: Path,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    root = environment_root.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    home_dir = root / "home"
    appdata_dir = root / "appdata"
    localappdata_dir = root / "localappdata"
    temp_dir = root / "tmp"
    for directory in (home_dir, appdata_dir, localappdata_dir, temp_dir):
        directory.mkdir(mode=0o700, exist_ok=True)
    env = build_core_env(base_env)
    env.update({
        "HOME": str(home_dir),
        "USERPROFILE": str(home_dir),
        "APPDATA": str(appdata_dir),
        "LOCALAPPDATA": str(localappdata_dir),
        "TEMP": str(temp_dir),
        "TMP": str(temp_dir),
        "TMPDIR": str(temp_dir),
    })
    return env
```

Make `build_supervisor_env` delegate to this helper. Keep `build_player_env` in the Codex module and implement it as:

```python
def build_player_env(
    player_home: Path,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = build_isolated_process_env(player_home, base_env)
    env.update({
        "CODEX_HOME": str(player_home.resolve()),
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    })
    return env
```

Implement the shared runner with generic player names while retaining the existing return codes and cleanup order:

```python
def run_orchestrated_session(
    mcp_command: Sequence[str],
    player_label: str,
    player_command: Sequence[str],
    supervisor_command: Sequence[str],
    prompt: str,
    mcp_env: Mapping[str, str],
    player_env: Mapping[str, str],
    supervisor_env: Mapping[str, str],
    mcp_cwd: Path,
    player_cwd: Path,
    supervisor_cwd: Path,
    ws_port: int,
    mcp_port: int,
    mcp_start_timeout_seconds: float,
    player_exit_grace_seconds: float,
    idle_timeout_seconds: float,
    player_final_grace_seconds: float,
) -> int:
    outputs: queue.Queue[tuple[str, str | None]] = queue.Queue()
    mcp = None
    player = None
    supervisor = None
    try:
        mcp = _start_process("mcp", mcp_command, mcp_cwd, mcp_env)
        _start_output_reader("mcp", mcp, outputs)
        if not wait_for_listener(
            mcp, DEFAULT_WS_HOST, mcp_port,
            mcp_start_timeout_seconds, outputs,
        ):
            print(
                "[orchestrator] trusted MCP sidecar did not listen on %s:%s "
                "within %.1fs"
                % (DEFAULT_WS_HOST, mcp_port, mcp_start_timeout_seconds),
                flush=True,
            )
            return 4
        if not wait_for_listener(
            mcp, DEFAULT_WS_HOST, ws_port,
            mcp_start_timeout_seconds, outputs,
        ):
            print(
                "[orchestrator] AI Play bridge did not listen on %s:%s within %.1fs"
                % (DEFAULT_WS_HOST, ws_port, mcp_start_timeout_seconds),
                flush=True,
            )
            return 4

        player = _start_process(
            player_label, player_command, player_cwd, player_env,
            stdin_text=prompt,
        )
        _start_output_reader(player_label, player, outputs)
        player_code = player.poll()
        if player_code is not None:
            return 3 if player_code == 0 else player_code

        supervisor = _start_process(
            "supervisor", supervisor_command, supervisor_cwd, supervisor_env,
        )
        _start_output_reader("supervisor", supervisor, outputs)
        last_activity_at = time.monotonic()

        while True:
            if _print_available_output(outputs):
                last_activity_at = time.monotonic()
            mcp_code = mcp.poll()
            supervisor_code = supervisor.poll()
            player_code = player.poll()
            if mcp_code is not None:
                return 4 if mcp_code == 0 else mcp_code
            if supervisor_code is not None:
                return _finish_after_supervisor(
                    supervisor_code, mcp, player, outputs,
                    player_final_grace_seconds,
                )
            if player_code is not None:
                deadline = time.monotonic() + player_exit_grace_seconds
                while time.monotonic() < deadline:
                    _print_available_output(outputs)
                    mcp_code = mcp.poll()
                    supervisor_code = supervisor.poll()
                    if mcp_code is not None:
                        return 4 if mcp_code == 0 else mcp_code
                    if supervisor_code is not None:
                        return supervisor_code
                    time.sleep(0.05)
                return 3 if player_code == 0 else player_code
            if time.monotonic() - last_activity_at > idle_timeout_seconds:
                print(
                    "[orchestrator] no child-process output for %.1fs; "
                    "stopping stalled session" % idle_timeout_seconds,
                    flush=True,
                )
                return 5
            time.sleep(0.05)
    finally:
        for process in (supervisor, player, mcp):
            if process is not None:
                _terminate_process(process)
        _print_available_output(outputs)
```

Use this generic terminal-grace helper:

```python
def _finish_after_supervisor(
    supervisor_code: int,
    mcp: subprocess.Popen[str],
    player: subprocess.Popen[str],
    outputs: queue.Queue[tuple[str, str | None]],
    grace_seconds: float,
) -> int:
    """Allow the player to consume the terminal result and emit its final response."""
    deadline = time.monotonic() + grace_seconds
    while True:
        _print_available_output(outputs)
        mcp_code = mcp.poll()
        player_code = player.poll()
        if mcp_code is not None:
            return 4 if mcp_code == 0 else mcp_code
        if player_code is not None or time.monotonic() >= deadline:
            return supervisor_code
        time.sleep(0.05)
```

- [ ] **Step 4: Make the Codex entry import and re-export the shared surface**

Replace moved definitions in `tools/ai_play_codex_orchestrator.py` with a module import and explicit re-exports so existing tests and callers retain the same names:

```python
try:
    from . import ai_play_orchestrator_common as _common
except ImportError:
    import ai_play_orchestrator_common as _common

AWM_PLAYER_TOOL_NAMES = _common.AWM_PLAYER_TOOL_NAMES
BASE_PLAYER_TOOL_NAMES = _common.BASE_PLAYER_TOOL_NAMES
DEFAULT_MCP_PORT = _common.DEFAULT_MCP_PORT
DEFAULT_SESSION_ROOT = _common.DEFAULT_SESSION_ROOT
DEFAULT_WS_HOST = _common.DEFAULT_WS_HOST
DEFAULT_WS_PORT = _common.DEFAULT_WS_PORT
REPO_ROOT = _common.REPO_ROOT
build_core_env = _common.build_core_env
build_isolated_process_env = _common.build_isolated_process_env
build_mcp_command = _common.build_mcp_command
build_player_developer_instructions = _common.build_player_developer_instructions
build_player_prompt = _common.build_player_prompt
build_supervisor_command = _common.build_supervisor_command
build_supervisor_env = _common.build_supervisor_env
build_trusted_mcp_env = _common.build_trusted_mcp_env
create_run_paths = _common.create_run_paths
is_port_listening = _common.is_port_listening
run_orchestrated_session = _common.run_orchestrated_session
validate_isolated_session_root = _common.validate_isolated_session_root
validate_model_argument = _common.validate_model_argument
```

Keep Codex-only code in this file: auth validation/copying, TOML escaping/config generation, Codex binary resolution, Codex command construction, Codex arguments, and `main`.

- [ ] **Step 5: Map Codex CLI names to the generic runner**

Use the new call without changing public Codex arguments:

```python
return run_orchestrated_session(
    mcp_command=mcp_command,
    player_label="codex",
    player_command=build_codex_command(codex_bin, paths.player_workspace),
    supervisor_command=supervisor_command,
    prompt=build_player_prompt(
        args.runs,
        workflow_memory_enabled=args.workflow_memory == "enabled",
        scenario=args.scenario,
    ),
    mcp_env=mcp_env,
    player_env=build_player_env(player_home),
    supervisor_env=supervisor_env,
    mcp_cwd=REPO_ROOT,
    player_cwd=paths.player_workspace,
    supervisor_cwd=REPO_ROOT,
    ws_port=DEFAULT_WS_PORT,
    mcp_port=args.mcp_port,
    mcp_start_timeout_seconds=args.mcp_start_timeout_seconds,
    player_exit_grace_seconds=args.codex_exit_grace_seconds,
    idle_timeout_seconds=args.idle_timeout_seconds,
    player_final_grace_seconds=args.codex_final_grace_seconds,
)
```

- [ ] **Step 6: Run Codex and supervisor regressions**

Run:

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest \
  tests/test_ai_play_codex_orchestrator.py tests/test_ai_play_supervisor.py -q
```

Expected: PASS with the same count as Task 1 plus the new characterization test.

- [ ] **Step 7: Commit the shared orchestration core**

```bash
git add tools/ai_play_orchestrator_common.py tools/ai_play_codex_orchestrator.py \
  tests/test_ai_play_codex_orchestrator.py
git commit -m "refactor(ai-play): share player orchestration core"
```

### Task 3: Build and validate private Claude settings and MCP configuration

**Files:**
- Create: `tools/ai_play_claude_orchestrator.py`
- Create: `tests/test_ai_play_claude_orchestrator.py`
- Test: `tests/test_ai_play_claude_orchestrator.py`

- [ ] **Step 1: Create a loader and add failing settings-boundary tests**

Start the test file with the same `importlib` loading pattern used by the Codex tests, pointing at `tools/ai_play_claude_orchestrator.py`. Add these tests:

```python
def test_load_claude_provider_env_keeps_only_explicit_service_keys(tmp_path):
    orchestrator = load_orchestrator()
    settings = tmp_path / "settings.local.json"
    settings.write_text(json.dumps({
        "env": {
            "ANTHROPIC_AUTH_TOKEN": "token",
            "ANTHROPIC_BASE_URL": "https://example.invalid",
            "ANTHROPIC_MODEL": "claude-test",
            "ANTHROPIC_SMALL_FAST_MODEL": "claude-small-test",
            "OPENAI_API_KEY": "must-drop",
            "AI_PLAY_LOG_ROOT": "/must/drop",
        },
        "hooks": {"PreToolUse": ["must-drop"]},
        "permissions": {"allow": ["Bash"]},
    }), encoding="utf-8")

    assert orchestrator.load_claude_provider_env(settings) == {
        "ANTHROPIC_AUTH_TOKEN": "token",
        "ANTHROPIC_BASE_URL": "https://example.invalid",
        "ANTHROPIC_MODEL": "claude-test",
        "ANTHROPIC_SMALL_FAST_MODEL": "claude-small-test",
    }


def test_temporary_claude_player_config_is_private_and_removed(tmp_path):
    orchestrator = load_orchestrator()
    provider_env = {
        "ANTHROPIC_AUTH_TOKEN": "token",
        "ANTHROPIC_BASE_URL": "https://example.invalid",
    }

    with orchestrator.temporary_claude_player_config(
        provider_env,
        "http://127.0.0.1:8766/mcp",
    ) as config:
        assert config.root.stat().st_mode & 0o777 == 0o700
        assert config.settings_path.stat().st_mode & 0o777 == 0o600
        assert config.mcp_path.stat().st_mode & 0o777 == 0o600
        assert json.loads(config.settings_path.read_text())["env"] == provider_env
        assert json.loads(config.mcp_path.read_text()) == {
            "mcpServers": {
                "cogito_ai_play": {
                    "type": "http",
                    "url": "http://127.0.0.1:8766/mcp",
                }
            }
        }
    assert not config.root.exists()
```

Also test missing files, malformed/non-object JSON, missing `env`, non-string values, absence of both `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN`, and non-HTTPS `ANTHROPIC_BASE_URL` values other than a deliberately supported local test fixture. Each case must raise `ValueError` before a run directory or child process is created.

- [ ] **Step 2: Run the settings tests and verify they fail**

Run:

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest \
  tests/test_ai_play_claude_orchestrator.py -q
```

Expected: FAIL because the Claude module does not exist.

- [ ] **Step 3: Implement strict settings extraction**

Create the Claude module and import the shared surface explicitly. Define:

```python
CLAUDE_PROVIDER_ENV_NAMES = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
)
DEFAULT_CLAUDE_SETTINGS = REPO_ROOT / ".claude" / "settings.local.json"


@dataclass(frozen=True)
class ClaudePlayerConfig:
    root: Path
    settings_path: Path
    mcp_path: Path


def load_claude_provider_env(settings_path: Path) -> dict[str, str]:
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing Claude settings file: {settings_path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid Claude settings file: {settings_path}") from error
    if not isinstance(payload, dict):
        raise ValueError("Claude settings root must be a JSON object")
    raw_env = payload.get("env")
    if not isinstance(raw_env, dict):
        raise ValueError("Claude settings must contain an env object")
    provider_env: dict[str, str] = {}
    for name in CLAUDE_PROVIDER_ENV_NAMES:
        value = raw_env.get(name)
        if value is None:
            continue
        if not isinstance(value, str) or not value:
            raise ValueError(f"Claude settings env {name} must be a non-empty string")
        provider_env[name] = value
    if not any(
        provider_env.get(name)
        for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    ):
        raise ValueError(
            "Claude settings must provide ANTHROPIC_API_KEY or "
            "ANTHROPIC_AUTH_TOKEN"
        )
    base_url = provider_env.get("ANTHROPIC_BASE_URL")
    if base_url is not None and not base_url.startswith("https://"):
        raise ValueError("ANTHROPIC_BASE_URL must use https")
    return provider_env
```

Do not copy the schema key, hooks, permissions, model-generated headers, arbitrary environment variables, or the source path into returned data. Error messages may name missing keys and the settings file but must never include credential values.

- [ ] **Step 4: Implement private temporary files with fail-safe cleanup**

Use `tempfile.TemporaryDirectory(prefix="cogito-ai-play-claude-")`; explicitly `chmod(0o700)` the directory and `chmod(0o600)` both JSON files after writing. Serialize only:

```python
settings_payload = {"env": provider_env}
mcp_payload = {
    "mcpServers": {
        "cogito_ai_play": {
            "type": "http",
            "url": mcp_url,
        }
    }
}
```

Yield `ClaudePlayerConfig`, and rely on the context manager's `finally` cleanup for normal return, `SystemExit`, and exceptions.

- [ ] **Step 5: Run the settings tests**

Run the command from Step 2.

Expected: PASS for settings/config tests; command and main tests added in later tasks may still be absent.

- [ ] **Step 6: Commit the private Claude configuration boundary**

```bash
git add tools/ai_play_claude_orchestrator.py tests/test_ai_play_claude_orchestrator.py
git commit -m "feat(ai-play): isolate Claude player configuration"
```

### Task 4: Construct a fail-closed Claude player command

**Files:**
- Modify: `tools/ai_play_claude_orchestrator.py`
- Modify: `tests/test_ai_play_claude_orchestrator.py`
- Test: `tests/test_ai_play_claude_orchestrator.py`

- [ ] **Step 1: Add failing binary and command tests**

Add:

```python
def test_build_claude_command_is_bare_nonpersistent_and_mcp_only(tmp_path):
    orchestrator = load_orchestrator()
    config = orchestrator.ClaudePlayerConfig(
        root=tmp_path,
        settings_path=tmp_path / "settings.json",
        mcp_path=tmp_path / "mcp.json",
    )

    command = orchestrator.build_claude_command(
        "/usr/local/bin/claude",
        config,
        model="claude-opus-test",
        effort="high",
        workflow_memory_enabled=True,
    )

    assert command[:2] == ["/usr/local/bin/claude", "--bare"]
    assert "--print" in command
    assert "--no-session-persistence" in command
    assert "--strict-mcp-config" in command
    assert command[command.index("--settings") + 1] == str(config.settings_path)
    assert command[command.index("--mcp-config") + 1] == str(config.mcp_path)
    assert command[command.index("--tools") + 1] == ""
    allowed = command[command.index("--allowed-tools") + 1]
    assert allowed.split(",") == [
        "mcp__cogito_ai_play__briefing",
        "mcp__cogito_ai_play__workflow_memory_read",
        "mcp__cogito_ai_play__observe",
        "mcp__cogito_ai_play__act",
        "mcp__cogito_ai_play__workflow_memory_update",
    ]
    assert "mcp__cogito_ai_play__stop" not in allowed
```

Add a second test for disabled workflow memory expecting only briefing/observe/act. Assert `--permission-mode dontAsk`, `--model`, `--effort`, and `--system-prompt` are present; assert `--dangerously-skip-permissions`, `--add-dir`, `--agent`, `--agents`, `--plugin-dir`, `--chrome`, `--continue`, and `--resume` are absent. Add binary-resolution tests equivalent to the Codex shim tests.

- [ ] **Step 2: Run the command test and verify it fails**

Run:

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest \
  tests/test_ai_play_claude_orchestrator.py::test_build_claude_command_is_bare_nonpersistent_and_mcp_only -q
```

Expected: FAIL because `build_claude_command` is missing.

- [ ] **Step 3: Implement exact MCP tool-name mapping**

```python
def claude_mcp_tool_names(workflow_memory_enabled: bool) -> tuple[str, ...]:
    tools = (
        AWM_PLAYER_TOOL_NAMES
        if workflow_memory_enabled
        else BASE_PLAYER_TOOL_NAMES
    )
    return tuple(f"mcp__cogito_ai_play__{name}" for name in tools)
```

- [ ] **Step 4: Implement the command builder**

Build this exact option order to make tests and logs deterministic:

```python
return [
    claude_bin,
    "--bare",
    "--print",
    "--no-session-persistence",
    "--strict-mcp-config",
    "--settings",
    str(config.settings_path),
    "--mcp-config",
    str(config.mcp_path),
    "--tools",
    "",
    "--allowed-tools",
    ",".join(claude_mcp_tool_names(workflow_memory_enabled)),
    "--permission-mode",
    "dontAsk",
    "--model",
    model,
    "--effort",
    effort,
    "--system-prompt",
    build_player_developer_instructions(),
]
```

The player prompt is not an argument; the shared process runner writes it to stdin and closes stdin. Never print settings contents or provider environment values.

Implement the Claude player environment without setting `CODEX_HOME`:

```python
def build_claude_player_env(
    player_root: Path,
    provider_env: Mapping[str, str],
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = build_isolated_process_env(player_root, base_env)
    env.update(provider_env)
    env.update({
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    })
    return env
```

Add a test asserting this environment contains the selected Anthropic values and isolated HOME paths, but contains neither `CODEX_HOME`, `AI_PLAY_LOG_ROOT`, `PYTHONPATH`, `OPENAI_API_KEY`, nor unrelated proxy variables from `base_env`.

- [ ] **Step 5: Run all Claude unit tests**

Run:

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest \
  tests/test_ai_play_claude_orchestrator.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the fail-closed command**

```bash
git add tools/ai_play_claude_orchestrator.py tests/test_ai_play_claude_orchestrator.py
git commit -m "feat(ai-play): restrict Claude player tools"
```

### Task 5: Add the full Claude CLI and orchestration lifecycle

**Files:**
- Modify: `tools/ai_play_claude_orchestrator.py`
- Modify: `tests/test_ai_play_claude_orchestrator.py`
- Test: `tests/test_ai_play_claude_orchestrator.py`

- [ ] **Step 1: Add failing argument and main-lifecycle tests**

Mirror the Codex entry tests for scenario resolution, isolated session roots, port collision, positive numeric limits, unsafe model/effort control characters, start order, early player exit, sidecar readiness failure, idle timeout, keyboard interrupt, and cleanup. Add this hardened-options assertion:

```python
def test_parse_args_exposes_only_hardened_claude_options():
    orchestrator = load_orchestrator()
    args = orchestrator.parse_args([
        "--model", "claude-opus-test",
        "--effort", "high",
    ])

    assert args.claude_settings == orchestrator.DEFAULT_CLAUDE_SETTINGS
    assert args.claude_bin == "claude"
    assert args.workflow_memory == "enabled"
    assert args.mcp_port == 8766
    assert not hasattr(args, "permission_mode")
    assert not hasattr(args, "allowed_tools")
    assert not hasattr(args, "dangerously_skip_permissions")
```

Add a main cleanup test that monkeypatches `temporary_claude_player_config`, captures its yielded path, forces `run_orchestrated_session` to return, and asserts the temporary root no longer exists. Assert settings validation happens before `create_run_paths` and binary resolution where possible.

- [ ] **Step 2: Run new main tests and verify they fail**

Run:

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest \
  tests/test_ai_play_claude_orchestrator.py -q
```

Expected: FAIL on missing `parse_args`/`main` behavior.

- [ ] **Step 3: Implement the Claude argument parser**

Expose the shared Codex-equivalent options with Claude-specific names:

```python
parser.add_argument("--runs", type=int, default=3)
parser.add_argument("--scenario", default="find_contract")
parser.add_argument("--session-root", type=Path, default=DEFAULT_SESSION_ROOT)
parser.add_argument("--claude-settings", type=Path, default=DEFAULT_CLAUDE_SETTINGS)
parser.add_argument("--model", required=True)
parser.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max"), required=True)
parser.add_argument("--workflow-memory", choices=("enabled", "disabled"), default="enabled")
parser.add_argument("--claude-bin", default="claude")
parser.add_argument("--python-bin", default=sys.executable)
parser.add_argument("--godot-bin", default="godot")
parser.add_argument("--scene")
parser.add_argument("--mcp-port", type=int, default=DEFAULT_MCP_PORT)
parser.add_argument("--max-retries", type=int, default=2)
parser.add_argument("--timeout-seconds", type=float, default=100000.0)
parser.add_argument("--mcp-start-timeout-seconds", type=float, default=30.0)
parser.add_argument("--claude-exit-grace-seconds", type=float, default=5.0)
parser.add_argument("--idle-timeout-seconds", type=float, default=600.0)
parser.add_argument("--claude-final-grace-seconds", type=float, default=30.0)
```

Do not expose source-setting selection, tool permission, system prompt, MCP URL, bridge host/port, settings output, or persistence flags beyond the fixed hardened options above.

- [ ] **Step 4: Implement validation and main orchestration**

Follow Codex `main` ordering: validate model/effort, session root, scenario, provider settings, binary, counts, ports, and timeouts before creating run paths. Then create trusted environments/commands and use:

```python
with temporary_claude_player_config(
    provider_env,
    f"http://{DEFAULT_WS_HOST}:{args.mcp_port}/mcp",
) as player_config:
    return run_orchestrated_session(
        mcp_command=mcp_command,
        player_label="claude",
        player_command=build_claude_command(
            claude_bin,
            player_config,
            args.model,
            args.effort,
            workflow_memory_enabled=args.workflow_memory == "enabled",
        ),
        supervisor_command=supervisor_command,
        prompt=build_player_prompt(
            args.runs,
            workflow_memory_enabled=args.workflow_memory == "enabled",
            scenario=args.scenario,
        ),
        mcp_env=mcp_env,
        player_env=build_claude_player_env(player_config.root, provider_env),
        supervisor_env=supervisor_env,
        mcp_cwd=REPO_ROOT,
        player_cwd=paths.player_workspace,
        supervisor_cwd=REPO_ROOT,
        ws_port=DEFAULT_WS_PORT,
        mcp_port=args.mcp_port,
        mcp_start_timeout_seconds=args.mcp_start_timeout_seconds,
        player_exit_grace_seconds=args.claude_exit_grace_seconds,
        idle_timeout_seconds=args.idle_timeout_seconds,
        player_final_grace_seconds=args.claude_final_grace_seconds,
    )
```

`build_claude_player_env` must receive the temporary Claude root so HOME, application data, and temp paths are isolated; overlay only the selected provider variables needed by Claude. Never add `CODEX_HOME`, `AI_PLAY_LOG_ROOT`, `PYTHONPATH`, the source settings path, or repository paths to the player environment.

- [ ] **Step 5: Run Claude, Codex, and supervisor tests together**

Run:

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest \
  tests/test_ai_play_claude_orchestrator.py \
  tests/test_ai_play_codex_orchestrator.py \
  tests/test_ai_play_supervisor.py -q
```

Expected: PASS; no test launches Claude, MCP, or Godot.

- [ ] **Step 6: Run non-network CLI capability checks**

Run:

```bash
claude --version
claude --help
```

Expected: version 2.1.212 or a compatible newer version; help contains `--bare`, `--print`, `--no-session-persistence`, `--strict-mcp-config`, `--mcp-config`, `--allowed-tools`, `--tools`, `--permission-mode`, `--model`, `--effort`, and `--system-prompt`. Do not invoke `claude -p` and do not start a real MCP/Godot session.

- [ ] **Step 7: Commit the Claude entry point**

```bash
git add tools/ai_play_claude_orchestrator.py tests/test_ai_play_claude_orchestrator.py
git commit -m "feat(ai-play): orchestrate Claude black-box player"
```

### Task 6: Publish the implemented runbook and run final verification

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/wiki/development/contributor-guide.md`
- Modify: `docs/wiki/architecture/repository-map.md`
- Modify: `docs/scope/2026-08-04-claude-ai-player/spec-claude-ai-player.md` only if implementation discovers a contradiction requiring user approval
- Test: `tests/test_ai_play_claude_orchestrator.py`
- Test: `tests/test_ai_play_codex_orchestrator.py`
- Test: `tests/test_ai_play_supervisor.py`

- [ ] **Step 1: Replace pending-design wording with implemented facts**

In all four approved documentation targets, change `设计已批准，入口尚待实施` / `已批准设计，待实施` to an implementation date of 2026-08-04. Document this command without including credential values:

```bash
python3 tools/ai_play_claude_orchestrator.py \
  --runs 3 \
  --scenario find_contract \
  --model claude-opus-5 \
  --effort high \
  --claude-settings .claude/settings.local.json
```

Explain that `--claude-settings` is trusted-side input only, only the documented provider-variable allowlist is copied, `stop` is never available to the player, and real execution still needs separate confirmation. Add the exact local pytest command from Task 5. Update the repository map to list the now-existing common and Claude files, and include the approved spec in source links.

- [ ] **Step 2: Run the focused orchestrator suite**

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest \
  tests/test_ai_play_claude_orchestrator.py \
  tests/test_ai_play_codex_orchestrator.py \
  tests/test_ai_play_supervisor.py -q
```

Expected: PASS.

- [ ] **Step 3: Run the affected Python test suite**

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest \
  ai_play/tests ai_host/tests tests/*.py \
  tests/conveyor_profit/test_protocol_parity.py -q
```

Expected: PASS. This remains local and must not launch a real Claude session.

- [ ] **Step 4: Run static safety checks**

```bash
bash tests/test_ai_play_secret_scan.sh
bash tests/check_ai_play_start_script.sh
bash tests/check_ai_play_mcp_only.sh
```

Expected: all commands exit 0 and no credential value appears in tracked files or output fixtures.

- [ ] **Step 5: Run final formatting and change-scope checks**

```bash
git diff --check
git status --short
git diff --stat
```

Expected: no whitespace errors; only the common/Claude/Codex orchestrator code, their tests, the approved spec/plan, and the four approved documentation targets are modified. Existing untracked `.claude/` and `opus.py` remain untouched and uncommitted.

- [ ] **Step 6: Record the engine-validation boundary**

Do not run Godot or a real Claude MCP player for this change. In the handoff, state that pure Python and static checks passed, while Godot engine validation and real Claude/Godot black-box acceptance were not run because the change does not alter engine code and the latter requires separate user approval for screenshots, tokens, cost, and persisted trajectories.

- [ ] **Step 7: Commit documentation and final verification state**

```bash
git add ai_play/README.md \
  docs/wiki/ai-play/system-guide.md \
  docs/wiki/development/contributor-guide.md \
  docs/wiki/architecture/repository-map.md \
  docs/scope/2026-08-04-claude-ai-player/spec-claude-ai-player.md \
  docs/scope/2026-08-04-claude-ai-player/plan-claude-ai-player.md
git commit -m "docs(ai-play): publish Claude player runbook"
```
