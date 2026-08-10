# Codex Doubao Compatibility Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hardened Codex CLI orchestrator that plays through Doubao/Yibu by translating Codex's Responses dialect in a private loopback proxy.

**Architecture:** A focused proxy module performs pure request/SSE transformations and serves authenticated `/v1/responses` on `127.0.0.1`. A new orchestrator reuses the existing AI Play lifecycle, runs Codex through an internal wrapper, and ensures the real Yibu credential reaches the proxy but never the Codex child.

**Tech Stack:** Python 3.11, stdlib HTTP/process primitives, `httpx`, Codex CLI, MCP, pytest, Godot 4.7.

---

### Task 1: Pure request transformation

**Files:**
- Create: `tools/ai_play_doubao_responses_proxy.py`
- Create: `tests/test_ai_play_doubao_responses_proxy.py`

- [ ] **Step 1: Write failing request-transformation tests**

Cover removal of `reasoning`, `reasoning.encrypted_content`, and
`client_metadata`; filtering all non-AI-Play tools; namespace expansion into
`mcp__cogito_ai_play__<tool>` function tools; `parallel_tool_calls=false`;
default/explicit `max_output_tokens`; alias collision, model mismatch, malformed
namespace, and output-limit validation.

- [ ] **Step 2: Run the narrow tests and verify RED**

Run: `.venv/bin/pytest -q tests/test_ai_play_doubao_responses_proxy.py`

Expected: collection/import failure because the proxy module does not exist.

- [ ] **Step 3: Implement the minimal pure transformer**

Add immutable proxy settings and a `transform_request(payload, settings)` API
that returns the transformed JSON plus an in-memory alias map. Keep transport,
credentials, and logging outside this function.

- [ ] **Step 4: Run the narrow tests and verify GREEN**

Run: `.venv/bin/pytest -q tests/test_ai_play_doubao_responses_proxy.py`

Expected: all request transformation tests pass.

### Task 2: Frame-safe SSE transformation

**Files:**
- Modify: `tools/ai_play_doubao_responses_proxy.py`
- Modify: `tests/test_ai_play_doubao_responses_proxy.py`

- [ ] **Step 1: Add failing SSE tests**

Feed arbitrarily split byte chunks containing comments, multi-line SSE data,
reasoning, text, incremental function calls, and a `response.completed` output
array. Assert recursive canonical-name validation/rewrite. Add failures for
unknown aliases, malformed JSON, invalid UTF-8, missing frame terminators, and
disconnect before completion; assert no completion frame is emitted after an
error.

- [ ] **Step 2: Run the SSE subset and verify RED**

Run: `.venv/bin/pytest -q tests/test_ai_play_doubao_responses_proxy.py -k sse`

Expected: failures for missing frame parser/transformer behavior.

- [ ] **Step 3: Implement incremental SSE framing**

Add a byte-buffered event parser that emits only complete blank-line-delimited
frames. Parse every JSON `data:` payload, recursively validate/rewrite dictionaries
whose type is `function_call`, preserve keepalives, and raise a typed stream
error before forwarding invalid completion data.

- [ ] **Step 4: Run the full proxy unit tests and verify GREEN**

Run: `.venv/bin/pytest -q tests/test_ai_play_doubao_responses_proxy.py`

Expected: all pure request and SSE tests pass.

### Task 3: Authenticated loopback proxy server

**Files:**
- Modify: `tools/ai_play_doubao_responses_proxy.py`
- Modify: `tests/test_ai_play_doubao_responses_proxy.py`

- [ ] **Step 1: Add failing HTTP boundary tests**

Start the server on `127.0.0.1:0` with a fake upstream transport. Test health,
method/path rejection, bearer authentication, 16 MiB request bound, 64 KiB
upstream error bound, safe response headers, no upstream retry, streaming before
completion, 400/429 forwarding, timeout, and interrupted SSE cleanup. Assert
the local proxy bearer is never forwarded upstream, the upstream Authorization
header contains only the real Yibu bearer, and logs contain only metadata and
never prompt, tool arguments, images, or either token.

- [ ] **Step 2: Run HTTP tests and verify RED**

Run: `.venv/bin/pytest -q tests/test_ai_play_doubao_responses_proxy.py -k http`

Expected: failures because no loopback server exists.

- [ ] **Step 3: Implement the minimal server**

Use a threaded stdlib loopback HTTP server and `httpx.Client.stream` for the
upstream request. Validate local auth before reading/forwarding inference data,
discard the inbound Authorization header, construct a fresh upstream header
from the proxy-only Yibu credential, apply the pure transformer, stream safe
frames, expose selected port/readiness, and provide deterministic shutdown that
closes active upstream responses.

- [ ] **Step 4: Run proxy tests and verify GREEN**

Run: `.venv/bin/pytest -q tests/test_ai_play_doubao_responses_proxy.py`

Expected: all proxy tests pass without external network access.

### Task 4: Credentials, Codex configuration, and internal wrapper

**Files:**
- Create: `tools/ai_play_codex_doubao_orchestrator.py`
- Create: `tests/test_ai_play_codex_doubao_orchestrator.py`

- [ ] **Step 1: Write failing credential/configuration tests**

Test JSON-only loading from `.claude/settings.local.json`, token precedence,
safe HTTPS `/v1` normalization, invalid/missing values, Doubao defaults, absence
of a reasoning-effort argument, loopback proxy provider configuration, MCP/AWM
tool allowlists, mode-`0600` temporary files, and secret absence from Codex
configuration and command.

- [ ] **Step 2: Write failing wrapper tests**

Inject fake proxy/Codex factories. Assert the wrapper reads the exact outer
stdin prompt, rejects empty input, starts proxy before Codex, writes prompt to
Codex stdin, relays Codex/proxy output live, strips real Yibu/Anthropic/OpenAI
credentials from Codex env, supplies only the random proxy token, forwards
termination, preserves Codex exit status, and cleans all temporary state.
Include explicit proxy-thread failure, Codex startup failure, outer timeout,
and interruption cases in this lifecycle matrix.

- [ ] **Step 3: Run the orchestrator tests and verify RED**

Run: `.venv/bin/pytest -q tests/test_ai_play_codex_doubao_orchestrator.py`

Expected: collection/import failure because the orchestrator does not exist.

- [ ] **Step 4: Implement credentials, private config, and wrapper**

Reuse public constants and prompt/config patterns from
`ai_play_codex_orchestrator.py` without changing the Gemini entry. Add an
internal-player CLI mode that owns proxy and Codex child lifecycles. Keep
credential source paths out of child command lines by passing trusted values
only through the wrapper environment.

- [ ] **Step 5: Run the orchestrator tests and verify GREEN**

Run: `.venv/bin/pytest -q tests/test_ai_play_codex_doubao_orchestrator.py`

Expected: credential, config, and wrapper tests pass.

### Task 5: Public orchestration and restart recovery

**Files:**
- Modify: `tools/ai_play_codex_doubao_orchestrator.py`
- Modify: `tests/test_ai_play_codex_doubao_orchestrator.py`

- [ ] **Step 1: Add failing public wiring tests**

Assert validation happens before credentials/run-directory creation; defaults
are model `doubao-seed-2-1-pro-260628`, runs 3, AWM enabled, output limit 8192,
and restart limit 8; metadata records `reasoning_effort=none` and restart limit;
the player command is the internal wrapper; MCP/supervisor environments remain
separate; AWM-enabled and disabled restart prompts use the correct tool order;
and no credential or credential path appears in metadata or logged commands.

- [ ] **Step 2: Run wiring tests and verify RED**

Run: `.venv/bin/pytest -q tests/test_ai_play_codex_doubao_orchestrator.py -k 'main or restart or defaults'`

Expected: failures for missing public orchestration behavior.

- [ ] **Step 3: Implement public main and restart prompt**

Wire the existing scene resolver, run metadata, MCP command, supervisor command,
prompt, timeouts, and `run_orchestrated_session`. Pass `player_restart_limit=8`
and the public-state recovery prompt. Ensure the wrapper receives secrets only
through its isolated environment.

- [ ] **Step 4: Run affected orchestrator tests**

Run: `.venv/bin/pytest -q tests/test_ai_play_codex_doubao_orchestrator.py tests/test_ai_play_codex_gemini_orchestrator.py tests/test_ai_play_codex_orchestrator.py tests/test_ai_play_supervisor.py`

Expected: all tests pass.

### Task 6: Codex-to-MCP local integration contract

**Files:**
- Modify: `tests/test_ai_play_codex_doubao_orchestrator.py`
- Optionally create: `tests/fixtures/fake_doubao_responses_server.py`

- [ ] **Step 1: Write the failing integration test**

Use the installed Codex CLI when available, a fake upstream Responses SSE
server, and a fake local MCP. Require capture of a Codex namespace request,
upstream receipt of flat ordinary function tools, a fake
`mcp__cogito_ai_play__briefing` call, and observable `briefing` invocation on
the fake MCP. Skip only when Codex is unavailable; never use a real credential.

- [ ] **Step 2: Run and verify RED at the routing boundary**

Run: `.venv/bin/pytest -q tests/test_ai_play_codex_doubao_orchestrator.py -k codex_proxy_mcp_integration -s`

Expected: fail because the initial alias/SSE routing is not yet accepted by
Codex, or pass only after the production boundary is genuinely complete.

- [ ] **Step 3: Make the smallest routing correction**

Adjust only the proxy alias/response mapping required by the observed Codex
contract. Do not add an agent loop or provider-specific gameplay logic.

- [ ] **Step 4: Re-run integration and unit suites**

Run: `.venv/bin/pytest -q tests/test_ai_play_doubao_responses_proxy.py tests/test_ai_play_codex_doubao_orchestrator.py`

Expected: unit tests and observable MCP invocation pass.

### Task 7: Documentation and full verification

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

- [ ] **Step 1: Update operational documentation**

Document the dedicated Doubao entry, Codex/proxy trust boundary, default
credential source, no reasoning-effort option, 8192 output-token limit, restart
cost implication, command example, protocol/provider/Codex/Godot error
categories, and real-test confirmation requirements.

- [ ] **Step 2: Run focused and affected tests**

Run: `PYTHONPATH=ai_play/src:. .venv/bin/python -m pytest ai_play/tests ai_host/tests tests/*.py tests/conveyor_profit/test_protocol_parity.py -q`

Expected: all tests pass.

The existing Codex and supervisor tests are the current scenario-registry
coverage; keep their `resolve_scene`/unknown-scenario cases in this final suite.

- [ ] **Step 3: Run repository hygiene checks**

Run: `git diff --check`

Expected: no output and exit code 0.

- [ ] **Step 4: Offer, but do not automatically run, real acceptance**

Stop after local verification and request just-in-time confirmation of
screenshots, tokens, fees, local trajectory persistence, scenario/runs/AWM, and
the archive destination. Only after that confirmation, require a real
`briefing` call through Codex/proxy before starting the requested game run.
Use an isolated session root, copy only to the confirmed destination, and report
actual completed runs separately from provider, protocol, Codex, and Godot
failures.
