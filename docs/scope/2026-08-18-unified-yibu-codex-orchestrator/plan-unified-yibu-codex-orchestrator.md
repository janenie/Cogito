# Unified Yibu Codex Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one isolated Codex harness entry that can run any image-capable Yibu Responses model without model-specific provider code.

**Architecture:** A generic Yibu orchestrator owns credential parsing, temporary Codex model metadata, process wiring and safe defaults. The loopback Responses proxy flattens the single approved MCP namespace before forwarding and restores only request-derived, allowlisted calls on the response. The existing Gemini entry becomes a compatibility facade; all game, AWM, supervisor and trajectory behavior stays in the existing shared components.

**Tech Stack:** Python 3.12, Codex CLI 0.145 Responses wire protocol, MCP Streamable HTTP, `httpx`, `pytest`, Godot AI Play supervisor.

---

### Task 1: Preserve CC Switch Attribution

**Files:**
- Create: `tools/third_party/cc-switch/SOURCE.md`
- Create: `tools/third_party/cc-switch/LICENSE`

- [ ] **Step 1: Add the pinned source record**

```markdown
# CC Switch source attribution

The model-catalog design and namespace flatten/restore behavior used by the
Cogito Yibu Codex adapter are adapted from CC Switch commit
`a98829ba1e8bd99a1df671e3c36c8bb6aa537e47`.

Source: https://github.com/farion1231/cc-switch
Relevant upstream files: `src-tauri/src/codex_config.rs` and
`src-tauri/src/proxy/providers/transform_codex_responses_namespace.rs`.
```

- [ ] **Step 2: Add the upstream MIT license verbatim**

Copy the CC Switch MIT license headed `Copyright (c) 2025 Jason Young` into
`tools/third_party/cc-switch/LICENSE`; do not replace the Cogito root license.

- [ ] **Step 3: Verify attribution files**

Run: `rg -n "a98829ba|Jason Young|MIT License" tools/third_party/cc-switch`

Expected: the source commit appears in `SOURCE.md`; copyright and license text appear in `LICENSE`.

- [ ] **Step 4: Commit**

```bash
git add tools/third_party/cc-switch
git commit -m "docs(ai-play): attribute CC Switch adapter design"
```

### Task 2: Flatten and Restore Codex MCP Namespaces

**Files:**
- Modify: `tests/test_ai_play_responses_namespace_proxy.py`
- Modify: `tools/ai_play_responses_namespace_proxy.py`

- [ ] **Step 1: Write failing request transformation tests**

Add tests using this request shape:

```python
request = {
    "tools": [
        {"type": "function", "name": "plain", "parameters": {}},
        {
            "type": "namespace",
            "name": "mcp__cogito_ai_play",
            "tools": [
                {"type": "function", "name": "briefing", "parameters": {}},
                {"type": "function", "name": "observe", "parameters": {}},
            ],
        },
    ],
    "input": [{
        "type": "function_call",
        "name": "briefing",
        "namespace": "mcp__cogito_ai_play",
        "arguments": "{}",
    }],
    "tool_choice": {"type": "namespace", "name": "mcp__cogito_ai_play"},
}
```

Assert that `transform_request_namespaces()` produces top-level functions named
`mcp__cogito_ai_play__briefing` and `mcp__cogito_ai_play__observe`, rewrites replayed calls,
sets namespace tool choice to `"auto"`, and returns a reverse map. Add rejection tests for an
unapproved namespace child, a flat-name collision, and two different owners producing the same
bounded name.

- [ ] **Step 2: Run request tests and observe the expected failure**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest -q tests/test_ai_play_responses_namespace_proxy.py -k 'flatten or collision'`

Expected: FAIL because `transform_request_namespaces` is not defined.

- [ ] **Step 3: Implement bounded deterministic flattening**

Add request-derived immutable mapping data and these focused helpers:

```python
@dataclass(frozen=True)
class NamespacedToolName:
    namespace: str
    name: str


def flatten_namespace_tool_name(namespace: str, name: str) -> str:
    full_name = f"{namespace}__{name}"
    if len(full_name.encode("utf-8")) <= MAX_TOOL_NAME_BYTES:
        return full_name
    digest = hashlib.sha256(full_name.encode("utf-8")).hexdigest()[:12]
    suffix = f"__{digest}"
    return _utf8_prefix(full_name, MAX_TOOL_NAME_BYTES - len(suffix)) + suffix


def transform_request_namespaces(
    payload: dict[str, Any],
    *,
    namespace: str,
    allowed_tools: frozenset[str],
) -> dict[str, NamespacedToolName]:
    ...
```

Only the exact configured namespace and exact allowed child tools may be lifted. Validate all
collisions before mutating the payload. Preserve ordinary top-level tools and child schemas.

- [ ] **Step 4: Write failing response restore tests**

Test non-streaming JSON and SSE events containing
`{"type":"function_call","name":"mcp__cogito_ai_play__observe"}`. Assert restoration to
`name="observe"` plus `namespace="mcp__cogito_ai_play"`. Assert unmapped names remain unchanged
and cannot acquire a namespace.

- [ ] **Step 5: Run restore tests and observe the expected failure**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest -q tests/test_ai_play_responses_namespace_proxy.py -k 'restore'`

Expected: FAIL because the response functions do not accept a request-derived reverse map.

- [ ] **Step 6: Implement response restoration and wire the handler**

Parse the request body once before forwarding, collect image metadata from the original payload,
transform a copy to safe compact JSON, and derive the reverse map. Pass that map to both JSON and
SSE response rewriting. Preserve the existing bare-name and `cogito_ai_play:<tool>` compatibility
only when no request-derived flat mapping applies. Return a generic 400/500 without forwarding on
invalid namespace input, collision, JSON parsing, or diagnostics persistence failure.

- [ ] **Step 7: Run the proxy suite**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest -q tests/test_ai_play_responses_namespace_proxy.py`

Expected: all proxy tests pass, including existing image metadata and 502 privacy tests.

- [ ] **Step 8: Commit**

```bash
git add tools/ai_play_responses_namespace_proxy.py tests/test_ai_play_responses_namespace_proxy.py
git commit -m "feat(ai-play): flatten Yibu MCP namespaces"
```

### Task 3: Generate Generic Yibu Model Metadata

**Files:**
- Create: `tools/ai_play_codex_yibu_orchestrator.py`
- Create: `tests/test_ai_play_codex_yibu_orchestrator.py`

- [ ] **Step 1: Seed the generic module from the tested Gemini entry**

Copy the current Gemini implementation into the new filename, rename Gemini-specific public
symbols to Yibu names, keep the AST credential loader and isolated permission profile, and make
the generic parser require `--model`.

- [ ] **Step 2: Write failing catalog and argument tests**

Test these exact model IDs with parametrization:

```python
MODELS = (
    "gemini-3.1-pro-preview",
    "grok-4.6",
    "h:qwen3.8-max-preview",
    "MiniMax-M3",
    "hy3",
)
```

For every model, call `write_player_codex_yibu_config()` and assert:

```python
catalog = json.loads((tmp_path / "model-catalog.json").read_text())
entry = catalog["models"][0]
assert entry["slug"] == model
assert entry["input_modalities"] == ["text", "image"]
assert entry["context_window"] == 128000
assert entry["max_context_window"] == 128000
assert entry["supports_parallel_tool_calls"] is False
assert (tmp_path / "model-catalog.json").stat().st_mode & 0o777 == 0o600
```

Also assert top-level config fields `model_context_window = 128000`,
`model_auto_compact_token_limit = 90000`, the `model_catalog_json` pointer, no reasoning effort,
and no secret.

- [ ] **Step 3: Run catalog tests and observe the expected failure**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest -q tests/test_ai_play_codex_yibu_orchestrator.py -k 'catalog or context'`

Expected: FAIL because the catalog generator and context CLI do not exist.

- [ ] **Step 4: Implement the minimal single-model catalog**

Use a neutral AI Play `base_instructions`, parser-required fields, byte truncation limit 10000,
`supports_image_detail_original = False`, no search, no parallel calls, and only text/image
modalities. Write both files with `0600` permissions. Add source comments pointing to
`tools/third_party/cc-switch/SOURCE.md` without copying CC Switch's full Codex prompt template.

- [ ] **Step 5: Implement context validation**

Add constants and a pure validator:

```python
DEFAULT_CONTEXT_WINDOW = 128_000
DEFAULT_AUTO_COMPACT_TOKEN_LIMIT = 90_000
MAX_CONTEXT_WINDOW = 10_000_000


def validate_context_limits(context_window: int, auto_compact_limit: int) -> None:
    if not 1 <= context_window <= MAX_CONTEXT_WINDOW:
        raise ValueError("--context-window must be between 1 and 10000000")
    if not 1 <= auto_compact_limit < context_window:
        raise ValueError(
            "--auto-compact-token-limit must be positive and smaller than --context-window"
        )
```

Expose both CLI options and reject invalid values before credential loading or process creation.
Keep the shared `validate_model_argument` and add tests proving control characters, empty IDs and
overlong IDs are rejected while the colon-containing Qwen ID is accepted literally.

- [ ] **Step 6: Run generic configuration tests**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest -q tests/test_ai_play_codex_yibu_orchestrator.py`

Expected: all generic credential, catalog, isolation and CLI tests pass.

- [ ] **Step 7: Commit**

```bash
git add tools/ai_play_codex_yibu_orchestrator.py tests/test_ai_play_codex_yibu_orchestrator.py
git commit -m "feat(ai-play): add generic Yibu Codex config"
```

### Task 4: Wire Image-Capable Yibu Sessions

**Files:**
- Modify: `tools/ai_play_codex_yibu_orchestrator.py`
- Modify: `tests/test_ai_play_codex_yibu_orchestrator.py`

- [ ] **Step 1: Write failing main-wiring tests**

Using the existing fake-process pattern, assert:

```python
assert session["mcp_command"][-1] == "--codex-media-output"
assert session["provider_proxy_command"][-2:] == [
    "--diagnostics-jsonl",
    str(log_root / "provider_requests.jsonl"),
]
assert captured["run_path_kwargs"]["reasoning_effort"] == "none"
execution = captured["run_path_kwargs"]["runtime_metadata"]["execution"]
assert execution["model_context_window"] == 128000
assert execution["model_auto_compact_token_limit"] == 90000
```

Assert the Yibu key appears only in the Codex player environment, never in the config, proxy
environment, commands, run path arguments or session metadata.

- [ ] **Step 2: Run wiring tests and observe the expected failure**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest -q tests/test_ai_play_codex_yibu_orchestrator.py -k 'main or media'`

Expected: FAIL because the generic main still starts the default MCP representation and omits
context metadata.

- [ ] **Step 3: Wire the existing shared components**

Build MCP with:

```python
mcp_command = build_mcp_command(
    args.python_bin,
    args.mcp_port,
    codex_media_output=True,
)
```

Pass context fields into `collect_runtime_metadata(..., execution={...})`; generate the private
catalog before starting any player process; keep per-terminal turn rotation, AWM recovery and
the metadata-only provider request audit unchanged.

- [ ] **Step 4: Run generic and MCP media suites**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest -q tests/test_ai_play_codex_yibu_orchestrator.py ai_play/tests/test_mcp_server.py -k 'yibu or codex_media_output or parse_server_options'`

Expected: selected generic and MCP media tests pass.

- [ ] **Step 5: Commit**

```bash
git add tools/ai_play_codex_yibu_orchestrator.py tests/test_ai_play_codex_yibu_orchestrator.py
git commit -m "fix(ai-play): deliver MCP images to Yibu models"
```

### Task 5: Preserve the Gemini CLI as a Thin Facade

**Files:**
- Modify: `tools/ai_play_codex_gemini_orchestrator.py`
- Modify: `tests/test_ai_play_codex_gemini_orchestrator.py`

- [ ] **Step 1: Write failing compatibility tests**

Assert the Gemini module exports the prior credential/config helper names, defaults to
`gemini-3.6-flash`, keeps `--codex-max-restarts 2`, accepts the new context overrides, and delegates
main execution to the generic module with the Gemini default injected. Ensure the generic module
itself requires `--model`.

- [ ] **Step 2: Run compatibility tests and observe the expected failure**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest -q tests/test_ai_play_codex_gemini_orchestrator.py`

Expected: FAIL until the duplicated Gemini implementation is replaced by a facade.

- [ ] **Step 3: Replace duplication with explicit aliases and delegates**

Keep only imports, compatibility aliases such as
`write_player_codex_gemini_config = write_player_codex_yibu_config`, and:

```python
DEFAULT_MODEL = "gemini-3.6-flash"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    return _yibu.parse_args(argv, default_model=DEFAULT_MODEL)


def main(argv: Sequence[str] | None = None) -> int:
    return _yibu.main(argv, default_model=DEFAULT_MODEL)
```

Do not copy credentials, config generation, proxy or process lifecycle logic into the facade.

- [ ] **Step 4: Run generic and compatibility suites together**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest -q tests/test_ai_play_codex_yibu_orchestrator.py tests/test_ai_play_codex_gemini_orchestrator.py`

Expected: all tests pass and old Gemini imports remain valid.

- [ ] **Step 5: Commit**

```bash
git add tools/ai_play_codex_gemini_orchestrator.py tests/test_ai_play_codex_gemini_orchestrator.py
git commit -m "refactor(ai-play): route Gemini through Yibu harness"
```

### Task 6: Finalize Documentation and Validation

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/wiki/ai-play/ai-play.md` only if its existing page index requires a changed description
- Modify: `docs/scope/2026-08-18-unified-yibu-codex-orchestrator/spec-unified-yibu-codex-orchestrator.md` only for implementation-status accuracy
- Modify: `docs/scope/2026-08-18-unified-yibu-codex-orchestrator/plan-unified-yibu-codex-orchestrator.md` to check completed steps

- [ ] **Step 1: Change approved-design wording to implemented behavior**

Document the exact generic command:

```bash
YIBU_RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/cogito-yibu.XXXXXX")"

.venv/bin/python tools/ai_play_codex_yibu_orchestrator.py \
  --model gemini-3.1-pro-preview \
  --runs 1 \
  --scenario find_key \
  --yibu-credentials ./opus.py \
  --context-window 128000 \
  --auto-compact-token-limit 90000 \
  --workflow-memory enabled \
  --session-root "$YIBU_RUN_ROOT"
```

State that the five named models are accepted IDs, not claims that paid preflight has passed.
Document image fail-closed behavior, audit fields, no history pruning, Gemini compatibility and
CC Switch attribution.

- [ ] **Step 2: Run the affected Python suites**

Run:

```bash
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest -q \
  tests/test_ai_play_responses_namespace_proxy.py \
  tests/test_ai_play_codex_yibu_orchestrator.py \
  tests/test_ai_play_codex_gemini_orchestrator.py \
  tests/test_ai_play_codex_grok_orchestrator.py \
  tests/test_ai_play_codex_doubao_orchestrator.py \
  tests/test_ai_play_codex_orchestrator.py \
  tests/test_ai_play_supervisor.py \
  ai_play/tests/test_mcp_server.py
```

Expected: all selected tests pass without reading real credentials or making external requests.

- [ ] **Step 3: Run repository hygiene checks**

Run: `git diff --check`

Expected: no whitespace errors. Confirm `git status --short` contains only files from this plan.
No Godot engine test is required because this implementation changes no GDScript, scene or resource.

- [ ] **Step 4: Commit documentation and plan**

```bash
git add ai_play/README.md docs/wiki/ai-play/system-guide.md \
  docs/scope/2026-08-18-unified-yibu-codex-orchestrator
git commit -m "docs(ai-play): document unified Yibu harness"
```

- [ ] **Step 5: Rebase, rerun checks and push**

```bash
git fetch origin main
git rebase origin/main
PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest -q \
  tests/test_ai_play_responses_namespace_proxy.py \
  tests/test_ai_play_codex_yibu_orchestrator.py \
  tests/test_ai_play_codex_gemini_orchestrator.py \
  tests/test_ai_play_codex_grok_orchestrator.py \
  tests/test_ai_play_codex_doubao_orchestrator.py \
  tests/test_ai_play_codex_orchestrator.py \
  tests/test_ai_play_supervisor.py \
  ai_play/tests/test_mcp_server.py
git diff --check origin/main...HEAD
git push -u origin feature/unified-yibu-codex-orchestrator
```

Expected: rebase is clean or only unambiguous conflicts are resolved; tests and diff check pass;
the remote feature branch points at the validated implementation. Do not merge to `main` while the
primary `main` worktree contains unrelated user changes.
