# Codex Gemini MCP Namespace Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ai_play_codex_gemini_orchestrator.py` reliably dispatch Yibu Gemini function calls to the existing namespaced Cogito MCP tools.

**Architecture:** Add a trusted loopback-only Responses proxy that forwards Codex requests to the configured HTTPS Yibu `/v1/responses` endpoint and rewrites only response `function_call` items whose names match the orchestrator's enabled Cogito tool whitelist and whose namespace is absent. Extend the shared orchestrated-session lifecycle with an optional provider sidecar so readiness, output labeling, failure handling, and termination remain centralized; point the isolated Codex provider at the loopback proxy while keeping the API key only in the Codex player environment.

**Tech Stack:** Python 3.12, stdlib `http.server`, `httpx` streaming client, pytest, Codex Responses API, MCP streamable HTTP.

---

### Task 1: Responses namespace rewrite unit

**Files:**
- Create: `tools/ai_play_responses_namespace_proxy.py`
- Create: `tests/test_ai_play_responses_namespace_proxy.py`

- [x] **Step 1: Write failing rewrite tests**

```python
def test_rewrite_adds_namespace_only_to_allowed_plain_function_call():
    event = {"type": "response.output_item.done", "item": {
        "type": "function_call", "name": "briefing", "arguments": "{}"}}
    rewritten = proxy.rewrite_response_event(
        event, namespace="mcp__cogito_ai_play", allowed_tools={"briefing"})
    assert rewritten["item"]["namespace"] == "mcp__cogito_ai_play"

def test_rewrite_preserves_builtin_and_existing_namespace_calls():
    # `update_plan` remains plain and an existing namespace is not overwritten.
```

- [x] **Step 2: Verify RED**

Run: `.venv/bin/python -m pytest tests/test_ai_play_responses_namespace_proxy.py -q`
Expected: FAIL because the proxy module does not exist.

- [x] **Step 3: Implement the minimal recursive event and SSE-line rewrite**

```python
def rewrite_response_event(value, *, namespace, allowed_tools):
    if isinstance(value, dict):
        if (value.get("type") == "function_call"
                and value.get("name") in allowed_tools
                and not value.get("namespace")):
            value["namespace"] = namespace
        for child in value.values():
            rewrite_response_event(child, namespace=namespace,
                                   allowed_tools=allowed_tools)
    elif isinstance(value, list):
        for child in value:
            rewrite_response_event(child, namespace=namespace,
                                   allowed_tools=allowed_tools)
    return value
```

- [x] **Step 4: Verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_ai_play_responses_namespace_proxy.py -q`
Expected: PASS.

### Task 2: Fail-closed loopback HTTP/SSE proxy

**Files:**
- Modify: `tools/ai_play_responses_namespace_proxy.py`
- Modify: `tests/test_ai_play_responses_namespace_proxy.py`

- [x] **Step 1: Add failing tests for endpoint, headers, body limit, and streaming**

```python
def test_proxy_accepts_only_post_v1_responses():
    assert proxy.is_allowed_request("POST", "/v1/responses")
    assert not proxy.is_allowed_request("GET", "/v1/responses")
    assert not proxy.is_allowed_request("POST", "/v1/models")

def test_forward_headers_keep_auth_without_hop_by_hop_headers():
    headers = proxy.forward_request_headers({
        "Authorization": "Bearer secret", "Connection": "keep-alive"})
    assert headers["Authorization"] == "Bearer secret"
    assert "Connection" not in headers
```

- [x] **Step 2: Verify RED, then implement the server**

The server must bind the CLI-provided host, which the orchestrator fixes to `127.0.0.1`; accept only `POST /v1/responses`; cap request bodies at 64 MiB; forward to the validated HTTPS upstream with TLS verification; stream SSE line-by-line without persisting request or response bodies; rewrite both SSE and non-streaming JSON function calls; and return generic `400`, `404`, `413`, or `502` errors without upstream bodies or credentials.

- [x] **Step 3: Verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_ai_play_responses_namespace_proxy.py -q`
Expected: PASS.

### Task 3: Provider sidecar lifecycle

**Files:**
- Modify: `tools/ai_play_orchestrator_common.py`
- Modify: `tests/test_ai_play_codex_orchestrator.py`

- [x] **Step 1: Write failing lifecycle tests**

```python
def test_session_starts_provider_proxy_before_mcp_player_and_supervisor(...):
    result = run_orchestrated_session(
        provider_proxy_command=["python", "proxy.py"],
        provider_proxy_env={}, provider_proxy_cwd=tmp_path,
        provider_proxy_port=18767, ...)
    assert started == ["provider-proxy", "mcp", "codex", "supervisor"]
    assert provider_proxy.terminated
```

Also assert a failed proxy readiness check starts no MCP/player/supervisor and that `KeyboardInterrupt` terminates the proxy.

- [x] **Step 2: Verify RED**

Run: `PYTHONPATH=ai_play/src .venv/bin/python -m pytest tests/test_ai_play_codex_orchestrator.py -q`
Expected: FAIL because `run_orchestrated_session` lacks provider sidecar parameters.

- [x] **Step 3: Implement optional provider sidecar arguments and cleanup**

Start the proxy first, label its output `provider-proxy`, wait for its loopback listener, and include it in every `finally` termination path. Existing callers omit the optional arguments and retain current behavior.

- [x] **Step 4: Verify GREEN**

Run: `PYTHONPATH=ai_play/src .venv/bin/python -m pytest tests/test_ai_play_codex_orchestrator.py -q`
Expected: PASS.

### Task 4: Wire the Gemini orchestrator to the proxy

**Files:**
- Modify: `tools/ai_play_codex_gemini_orchestrator.py`
- Modify: `tests/test_ai_play_codex_gemini_orchestrator.py`

- [x] **Step 1: Write failing wiring and validation tests**

```python
def test_main_routes_codex_provider_through_loopback_proxy(...):
    assert 'base_url = "http://127.0.0.1:18767/v1"' in config_text
    assert session["provider_proxy_port"] == 18767
    assert "fixture-secret" not in repr(session["provider_proxy_env"])
```

Cover invalid ports, collision with `8765`/`8766`, occupied proxy port, command composition, and AWM/non-AWM tool-name arguments.

- [x] **Step 2: Verify RED**

Run: `.venv/bin/python -m pytest tests/test_ai_play_codex_gemini_orchestrator.py -q`
Expected: FAIL because provider-proxy wiring is absent.

- [x] **Step 3: Implement minimal wiring**

Add `--provider-proxy-port` defaulting to `18767`; validate it is distinct and unused; build the proxy command with the upstream HTTPS URL, MCP namespace, and exact enabled tool names; generate Codex config with `http://127.0.0.1:<port>/v1`; and pass the sidecar settings to `run_orchestrated_session`. Keep `YIBU_API_KEY` only in `player_env`.

- [x] **Step 4: Verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_ai_play_codex_gemini_orchestrator.py -q`
Expected: PASS.

### Task 5: Documentation and verification

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/scope-nospec/2026-08-11-codex-gemini-mcp-namespace-proxy/plan-codex-gemini-mcp-namespace-proxy.md`

- [x] **Step 1: Document the compatibility boundary**

Explain that the trusted loopback proxy changes only missing namespaces on the enabled Cogito tool whitelist, never logs bodies or keys, forwards TLS to the configured HTTPS Yibu endpoint, and exits with the orchestrator.

- [x] **Step 2: Run focused and affected suites**

Run: `PYTHONPATH=ai_play/src .venv/bin/python -m pytest tests/test_ai_play_responses_namespace_proxy.py tests/test_ai_play_codex_gemini_orchestrator.py tests/test_ai_play_codex_orchestrator.py tests/test_ai_play_claude_orchestrator.py tests/test_ai_play_kimi_orchestrator.py -q`
Expected: PASS.

- [x] **Step 3: Run static and repository checks**

```bash
.venv/bin/python -m py_compile tools/ai_play_responses_namespace_proxy.py tools/ai_play_codex_gemini_orchestrator.py tools/ai_play_orchestrator_common.py
git diff --check
```

Expected: PASS with no credential text in diffs or generated metadata.

- [x] **Step 4: Run one approved real `garden_watering` acceptance**

Run the orchestrator for one AWM-enabled `garden_watering` attempt from an isolated `/tmp` session root. Success criterion for the compatibility fix is that `briefing`, `workflow_memory_read`, `observe`, and at least one `act` reach `cogito_ai_play` without `unsupported call`; then allow the one requested game to reach a trusted terminal result unless the user stops it.

- [x] **Step 5: Commit and push according to repository preferences**

Stage only the proxy, orchestrator/common code, related tests, README, Wiki, and this plan. Preserve unrelated theme and `.uid` changes. Commit only after all automated checks and the real compatibility acceptance pass; push the current branch according to `docs/user/git-preferences.md`.
