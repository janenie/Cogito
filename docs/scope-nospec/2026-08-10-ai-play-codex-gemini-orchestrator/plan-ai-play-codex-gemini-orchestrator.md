# Codex Gemini AI Play Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a hardened `tools/ai_play_codex_gemini_orchestrator.py` entry that runs `gemini-3.6-flash` through the Codex harness while preserving AI Play's isolated MCP, AWM, supervisor, and trusted-log contracts.

**Architecture:** The new entry reuses the existing Codex orchestrator's process, sandbox, MCP, scene-registry, and session helpers. It reads the ignored `opus.py` credential file with `ast.literal_eval` instead of executing it, writes a temporary Codex custom-provider configuration using the Responses API, injects the key through one isolated environment variable, and deletes the temporary `CODEX_HOME` on every exit path. The model defaults to `gemini-3.6-flash`, records reasoning effort as `none`, and does not send Codex's `model_reasoning_effort` setting.

**Tech Stack:** Python 3.10+, Codex CLI custom model providers, OpenAI Responses-compatible yibu endpoint, pytest, Godot 4.7, MCP Streamable HTTP.

---

### Task 1: Credential and provider configuration contract

**Files:**
- Create: `tests/test_ai_play_codex_gemini_orchestrator.py`
- Create: `tools/ai_play_codex_gemini_orchestrator.py`

- [x] **Step 1: Write failing credential-loader tests**

```python
def test_load_yibu_credentials_reads_literal_without_executing_file(tmp_path):
    marker = tmp_path / "executed"
    source = tmp_path / "opus.py"
    source.write_text(
        'ak = {"key": "secret", "url": "https://yibuapi.com"}\n'
        f'open({str(marker)!r}, "w").write("bad")\n',
        encoding="utf-8",
    )
    credentials = load_orchestrator().load_yibu_credentials(source)
    assert credentials.api_key == "secret"
    assert credentials.base_url == "https://yibuapi.com/v1"
    assert not marker.exists()


@pytest.mark.parametrize("payload", ["ak = {}", 'ak = {"key": "", "url": "https://yibuapi.com"}', 'ak = {"key": "secret", "url": "http://yibuapi.com"}'])
def test_load_yibu_credentials_rejects_invalid_values(tmp_path, payload):
    source = tmp_path / "opus.py"
    source.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError):
        load_orchestrator().load_yibu_credentials(source)
```

- [x] **Step 2: Run the credential tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_ai_play_codex_gemini_orchestrator.py -q`

Expected: FAIL because `tools/ai_play_codex_gemini_orchestrator.py` does not exist.

- [x] **Step 3: Implement the literal credential loader**

```python
@dataclass(frozen=True)
class YibuCredentials:
    api_key: str
    base_url: str


def load_yibu_credentials(source: Path) -> YibuCredentials:
    tree = ast.parse(source.expanduser().read_text(encoding="utf-8"))
    payload = _find_literal_ak_assignment(tree)
    api_key = payload.get("key")
    raw_url = payload.get("url")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("yibu credential key must be a non-empty string")
    base_url = _normalize_yibu_base_url(raw_url)
    return YibuCredentials(api_key=api_key.strip(), base_url=base_url)
```

- [x] **Step 4: Write failing temporary-config and environment tests**

```python
def test_write_player_config_uses_responses_provider_without_secret_or_effort(tmp_path):
    path = load_orchestrator().write_player_codex_gemini_config(
        tmp_path,
        model="gemini-3.6-flash",
        base_url="https://yibuapi.com/v1",
        mcp_url="http://127.0.0.1:8766/mcp",
    )
    text = path.read_text(encoding="utf-8")
    assert 'model_provider = "yibu"' in text
    assert 'env_key = "YIBU_API_KEY"' in text
    assert 'wire_api = "responses"' in text
    assert "model_reasoning_effort" not in text
    assert "secret" not in text


def test_build_player_env_injects_only_yibu_key(tmp_path):
    env = load_orchestrator().build_player_env(
        tmp_path,
        "secret",
        base_env={"PATH": "/safe", "OPENAI_API_KEY": "drop"},
    )
    assert env["YIBU_API_KEY"] == "secret"
    assert "OPENAI_API_KEY" not in env
```

- [x] **Step 5: Run the config tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_ai_play_codex_gemini_orchestrator.py -q`

Expected: FAIL because the custom config and environment functions are missing.

- [x] **Step 6: Implement the minimal temporary Codex provider config and environment**

```python
def build_player_env(player_home: Path, api_key: str, base_env=None) -> dict[str, str]:
    env = _codex.build_player_env(player_home, base_env)
    env[YIBU_ENV_KEY] = api_key
    return env
```

The config must retain the existing `ai_play_player` filesystem/network permissions, MCP tool allowlist, disabled web/agents/memories/login shell, and credential stores, then add only `model_provider = "yibu"`, `model_supports_reasoning_summaries = false`, and `[model_providers.yibu]` with `base_url`, `env_key`, and `wire_api = "responses"`.

- [x] **Step 7: Run the focused tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_ai_play_codex_gemini_orchestrator.py -q`

Expected: PASS.

### Task 2: Full orchestrator lifecycle

**Files:**
- Modify: `tests/test_ai_play_codex_gemini_orchestrator.py`
- Modify: `tools/ai_play_codex_gemini_orchestrator.py`

- [x] **Step 1: Write failing CLI and orchestration-wiring tests**

```python
def test_parse_args_defaults_to_gemini_flash_and_no_reasoning_option():
    args = load_orchestrator().parse_args([])
    assert args.model == "gemini-3.6-flash"
    assert args.runs == 3
    assert not hasattr(args, "reasoning_effort")


def test_entry_reuses_scene_and_mcp_contracts():
    orchestrator = load_orchestrator()
    assert orchestrator.DEFAULT_WS_HOST == "127.0.0.1"
    assert orchestrator.DEFAULT_WS_PORT == 8765
    assert orchestrator.DEFAULT_MCP_PORT == 8766
    assert orchestrator.resolve_scene("find_contract", None) == orchestrator.DEFAULT_SCENE
```

- [x] **Step 2: Run the lifecycle tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_ai_play_codex_gemini_orchestrator.py -q`

Expected: FAIL because CLI parsing and orchestration exports are incomplete.

- [x] **Step 3: Implement the CLI and trusted orchestration lifecycle**

```python
parser.add_argument("--runs", type=int, default=3)
parser.add_argument("--scenario", default="find_contract")
parser.add_argument("--model", default="gemini-3.6-flash")
parser.add_argument("--yibu-credentials", type=Path, default=REPO_ROOT / "opus.py")
parser.add_argument("--workflow-memory", choices=("enabled", "disabled"), default="enabled")
```

`main()` must validate the model, isolated session root, scenario, credential literal, Codex binary, request counts, timeouts, and both fixed ports before creating run paths. It must call `create_run_paths(..., player="codex", reasoning_effort="none")`, start the existing MCP sidecar and Godot supervisor, create an empty temporary `CODEX_HOME`, write the provider config, and call `run_orchestrated_session()` with the key only in `player_env`.

- [x] **Step 4: Run focused and existing Codex orchestrator tests**

Run: `.venv/bin/python -m pytest tests/test_ai_play_codex_gemini_orchestrator.py tests/test_ai_play_codex_orchestrator.py -q`

Expected: PASS.

### Task 3: Public run documentation and long-term Wiki

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

- [x] **Step 1: Add the supported invocation to `ai_play/README.md`**

```bash
.venv/bin/python tools/ai_play_codex_gemini_orchestrator.py \
  --runs 3 \
  --scenario find_contract \
  --model gemini-3.6-flash \
  --yibu-credentials ./opus.py \
  --workflow-memory enabled
```

Document that `opus.py` is parsed as data and never executed, the key is passed only as `YIBU_API_KEY` to the isolated Codex process, the provider uses `https://yibuapi.com/v1` Responses API, no reasoning effort is sent, real runs have screenshot/token/fee/log effects, and credentials never enter MCP, Godot, session metadata, or logs.

- [x] **Step 2: Update `docs/wiki/ai-play/system-guide.md`**

Add the stable Codex+Gemini boundary beside the current Codex orchestrator section: custom provider config lives only in temporary `CODEX_HOME`, the ignored credential source is literal-parsed, the environment key is player-only, AWM and trusted logging reuse the existing contracts, and real external acceptance still requires explicit confirmation.

- [x] **Step 3: Verify documentation and whitespace**

Run: `rg -n "codex_gemini|gemini-3.6-flash|YIBU_API_KEY" ai_play/README.md docs/wiki/ai-play/system-guide.md`

Expected: Both documents describe the same command and security contract.

Run: `git diff --check`

Expected: exit 0.

### Task 4: Full validation and Git handoff

**Files:**
- Verify: `tools/ai_play_codex_gemini_orchestrator.py`
- Verify: `tests/test_ai_play_codex_gemini_orchestrator.py`
- Verify: `ai_play/README.md`
- Verify: `docs/wiki/ai-play/system-guide.md`

- [x] **Step 1: Run focused Python tests**

Run: `.venv/bin/python -m pytest tests/test_ai_play_codex_gemini_orchestrator.py tests/test_ai_play_codex_orchestrator.py -q`

Expected: PASS.

- [x] **Step 2: Run the affected AI Play Python suite**

Run: `.venv/bin/python -m pytest ai_play/tests tests/test_ai_play_*orchestrator.py -q`

Expected: PASS.

- [x] **Step 3: Run syntax/help checks without credentials or network**

Run: `.venv/bin/python -m py_compile tools/ai_play_codex_gemini_orchestrator.py`

Expected: exit 0.

Run: `.venv/bin/python tools/ai_play_codex_gemini_orchestrator.py --help`

Expected: help lists `--yibu-credentials`, defaults the model internally, and has no reasoning-effort option.

- [x] **Step 4: Run final repository checks**

Run: `git diff --check`

Expected: exit 0.

Run: `git status --short --branch`

Expected: only this feature's files plus the user's pre-existing theme and UID changes are present.

- [x] **Step 5: Commit only feature files after successful validation**

```bash
git add tools/ai_play_codex_gemini_orchestrator.py tests/test_ai_play_codex_gemini_orchestrator.py ai_play/README.md docs/wiki/ai-play/system-guide.md docs/scope-nospec/2026-08-10-ai-play-codex-gemini-orchestrator/plan-ai-play-codex-gemini-orchestrator.md
git commit -m "feat(ai-play): add Codex Gemini orchestrator"
```

Do not stage `addons/cogito/Theme/Cogito_Theme_A.tres` or `tests/ai_play/test_ai_play_find_key_ceo_npc_stairs.gd.uid`.
