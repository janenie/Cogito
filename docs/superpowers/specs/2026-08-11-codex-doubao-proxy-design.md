# Codex Doubao Responses Compatibility Proxy Design

## Summary

Add a dedicated `ai_play_codex_doubao_orchestrator.py` entry that keeps Codex
CLI as the agent loop while routing its Responses API traffic through a private
loopback compatibility proxy. The proxy translates the newer Codex Responses
dialect into the subset accepted by Yibu/Doubao and streams the response back
to Codex. It never makes gameplay decisions or calls MCP tools itself.

The entry defaults to model `doubao-seed-2-1-pro-260628`, three runs, enabled
workflow memory, and `8192` maximum output tokens per model request.

## Goals

- Keep Codex CLI responsible for conversation state, planning, tool selection,
  MCP invocation, and the overall agent loop.
- Make current Codex CLI requests compatible with Yibu's Responses endpoint.
- Reuse the existing trusted MCP sidecar, Godot supervisor, run directory,
  scenario allowlist, AWM, timeout, retry, and emergency-stop behavior.
- Expose only the approved AI Play MCP tools to Doubao.
- Keep the real Yibu credential out of the Codex process, generated Codex
  configuration, process command lines, session metadata, and trajectory logs.
- Preserve streaming behavior and avoid proxy-side request retries that could
  duplicate billable inference.

## Non-goals

- Implementing a custom agent loop outside Codex.
- Teaching the proxy about game state, observations, actions, or terminal
  outcomes.
- Changing the Godot-to-Python protocol or exposing additional MCP tools.
- Replacing or silently changing the existing Gemini, Claude, Kimi, or standard
  Codex orchestrators.
- Guaranteeing compatibility with arbitrary OpenAI-compatible providers. This
  entry targets the observed Yibu/Doubao Responses behavior.

## Evidence and Compatibility Boundary

A captured Codex 0.145 request for the existing Gemini/Yibu orchestrator was
54,885 bytes and reached Yibu before any MCP call. Replaying that request
identified these deterministic incompatibilities:

1. Yibu rejected `reasoning.summary` as an unknown field.
2. After removing the reasoning extension, Yibu rejected tool type
   `namespace`.
3. After flattening namespace tools, Yibu rejected `client_metadata`.

After removing those unsupported fields and flattening the MCP namespace into
ordinary function tools, the same full-size request returned HTTP 200 and the
model emitted a `briefing` function call. Yibu reported a service default of
32,768 maximum output tokens. This establishes that authentication, request
size, model tool use, and the game prompt are not the primary failure; the
wire dialect is.

The proxy transformation is therefore deliberately narrow and covered by
contract tests. Unknown future Codex or Yibu fields must fail visibly rather
than being guessed away.

## Components

### Public orchestrator

`tools/ai_play_codex_doubao_orchestrator.py` is the user-facing entry point. It
parses and validates CLI arguments, reads credentials, creates the isolated run
metadata, builds the trusted MCP and supervisor commands, and delegates process
lifecycle management to `ai_play_orchestrator_common.py`.

It launches an internal player wrapper rather than invoking Codex directly.
The wrapper starts the loopback proxy, writes the private temporary Codex
configuration with the proxy's selected port, launches Codex, relays Codex's
exit status, and shuts down the proxy on every exit path.

### Responses compatibility proxy

`tools/ai_play_doubao_responses_proxy.py` contains the transport-neutral request
and SSE transformation functions plus the loopback HTTP server. It binds only
the exact numeric address `127.0.0.1` on an operating-system-selected port.

The proxy accepts only:

- `GET /healthz` for local readiness checks; and
- authenticated `POST /v1/responses` requests.

All other paths and methods fail closed. The request body has a bounded size.
The maximum request body is 16 MiB, and an upstream non-success error body is
forwarded only up to 64 KiB. Upstream connect timeout is 30 seconds and the
per-read timeout is 660 seconds, slightly longer than the outer default idle
timeout so that the orchestrator remains the owner of stalled-session policy.
The server uses the existing HTTP stack available through AI Play dependencies
and does not introduce a second agent framework.

### Codex CLI

Codex runs with the existing hardened player prompt, empty player workspace,
ephemeral home, MCP allowlist, disabled shell/web/apps/plugins/subagents, and
loopback-only player network policy. Its model provider points to the local
proxy and continues to use `wire_api = "responses"`.

Codex receives a random per-session proxy bearer token through its provider
environment key. It never receives the real Yibu token.

## Credential Handling

The default credential source is `.claude/settings.local.json`; callers may
override it with `--credentials PATH`. The trusted orchestrator parses JSON and
reads only these fields from the top-level `env` object:

- `ANTHROPIC_AUTH_TOKEN`, falling back to `ANTHROPIC_API_KEY`; and
- `ANTHROPIC_BASE_URL`.

The URL must be HTTPS, must not contain user information, a query, or a
fragment, and must have an empty path or `/v1`. An empty path is normalized to
`/v1`.

The real token enters only the internal wrapper/proxy environment. Before the
wrapper launches Codex, it constructs a fresh isolated environment containing
the random proxy token but no real Yibu, Anthropic, OpenAI, or unrelated API
credentials. Neither credential values nor credential source paths are written
to `session.json` or trusted MCP logs.

## Request Transformation

For every authenticated `/v1/responses` request, the proxy:

1. Parses a JSON object and validates the configured model name.
2. Removes `client_metadata`.
3. Removes the complete `reasoning` request member. Doubao is intentionally not
   given a Codex reasoning-effort setting.
4. Removes `reasoning.encrypted_content` from `include`; removes `include` if no
   entries remain.
5. Keeps only the configured AI Play MCP namespace and the enabled nested tool
   names. All Codex built-in tools are removed before the request reaches the
   model.
6. Converts each approved nested MCP tool to an ordinary function tool named
   with its canonical legacy Codex name, for example
   `mcp__cogito_ai_play__briefing`.
7. Rejects duplicate or ambiguous aliases rather than overwriting them.
8. Forces `parallel_tool_calls` to `false`.
9. Sets `max_output_tokens` to the validated orchestrator value, defaulting to
   `8192` and capped at `32768`.
10. Preserves the model input, instructions, streaming flag, storage flag,
    prompt cache key, and other known-compatible request members.

The proxy records only transformation metadata: timestamp, request byte count,
removed field names, exposed tool names, upstream status, response byte count,
duration, and upstream request ID when available. It does not log prompts,
images, function arguments, model output, authorization headers, or response
bodies.

## Response Streaming and Tool Routing

The proxy streams the upstream status, safe response headers, and SSE body as
they arrive. It must not buffer a full model response before forwarding it.

The flattened function names are canonical legacy Codex MCP names. A per-request
alias table is retained only in memory until the stream closes. Function-call
events are validated against that table and forwarded under the canonical name
that Codex routes to its registered MCP tool. Text, reasoning output, usage,
completion, and failure events otherwise pass through without semantic changes.

The SSE transformer parses complete event frames rather than individual TCP
chunks. For every JSON `data:` payload it recursively rewrites every object with
`type == "function_call"` and a mapped `name`. This covers incremental
`response.output_item.added` payloads and the output array embedded in
`response.completed`, without depending on a fixed event-name list. Non-JSON
keepalive/comment frames pass through. Before forwarding a completion frame,
the proxy validates the entire frame. A malformed JSON event, unknown function
alias, invalid UTF-8 sequence, or upstream disconnect aborts the upstream
request and closes the downstream stream without forwarding
`response.completed`; Codex must observe an inference stream failure rather
than a false success.

An integration contract test must prove the complete boundary: real Codex
builds a namespace request, a fake upstream emits the flattened `briefing`
function call, and Codex invokes `briefing` on a fake local MCP server. Passing
request-transformation unit tests without this observable MCP invocation is not
sufficient.

## Process Lifecycle

The outer lifecycle remains:

1. Start trusted MCP HTTP sidecar.
2. Start the internal Doubao player wrapper.
3. Start the Godot supervisor after the player/MCP boundary is ready.
4. Let Codex play all requested runs in one conversation, using AWM when
   enabled.
5. On terminal completion or failure, terminate Codex, proxy, MCP, and Godot in
   the existing bounded order and release all simulated input.

The internal wrapper lifecycle is:

1. Read the complete player prompt from wrapper stdin. An empty prompt is a
   startup error.
2. Bind the proxy to `127.0.0.1:0` and learn the selected port.
3. Generate a cryptographically random proxy bearer token.
4. Write a mode-`0600` Codex configuration pointing at that port.
5. Launch `codex exec ... -` with a sanitized environment, write the complete
   prompt to Codex stdin, and close Codex stdin.
6. Forward Codex stdout and stderr line-by-line to wrapper stdout without
   buffering. Proxy lifecycle/error messages also go to wrapper stdout, so the
   existing outer idle detector observes active inference and tool traffic.
7. Forward termination/interruption to Codex, then return Codex's exit status.
8. Cancel any active upstream stream, stop the proxy, and remove temporary
   configuration on normal exit, error, timeout, or interruption.

If Codex exits before the supervisor finishes, the existing bounded player
restart behavior is used. The public CLI exposes `--codex-max-restarts`, defaults
it to `8`, and records that value in session execution metadata. Each restart is
a fresh, potentially billable Codex conversation. The restart prompt instructs
Codex to call `workflow_memory_read`, `briefing`, and `observe` when AWM is
enabled (or `briefing` and `observe` otherwise), trust the MCP-reported completed
run count, resume the current supervisor session, and avoid treating a restart
as a newly completed run. Restarts do not create a second agent loop; they are
new Codex CLI invocations owned by the existing outer lifecycle.

## Error Handling

- Invalid local authentication, paths, JSON, body size, model, or tool aliases
  return an OpenAI-style local error without contacting Yibu.
- Upstream non-2xx statuses are forwarded with their status and bounded error
  body. Secrets and authorization headers are never forwarded to logs.
- The proxy performs no automatic upstream retry. Codex and the outer bounded
  restart policy remain the only retry owners.
- Connection timeouts, malformed SSE, and mid-stream disconnects terminate the
  current Codex inference visibly. They must not be converted into a successful
  completion.
- If the proxy dies, Codex loses its provider connection and the wrapper returns
  failure; the public orchestrator then performs normal cleanup.
- Disconnects and all process-destruction paths retain the existing guarantee
  that simulated input is released.

## CLI Contract

The public command supports the existing Codex/Gemini orchestration arguments
for runs, scenario, session root, model, workflow memory, Codex/Godot/Python
binaries, ports, benchmark seed, retry counts, and timeouts. Doubao-specific
defaults and additions are:

```text
--model doubao-seed-2-1-pro-260628
--credentials .claude/settings.local.json
--max-output-tokens 8192
--codex-max-restarts 8
```

There is no reasoning-effort option. Values for `--max-output-tokens` must be in
the inclusive range 1 through 32768.

The intended command is:

```bash
.venv/bin/python tools/ai_play_codex_doubao_orchestrator.py \
  --runs 3 \
  --scenario garden_watering \
  --workflow-memory enabled \
  --model doubao-seed-2-1-pro-260628
```

## Testing

### Unit tests

- Credential JSON parsing does not execute code and accepts only the whitelisted
  fields and safe HTTPS URL shape.
- Real credentials are present in the proxy environment and absent from the
  Codex environment, configuration, command, metadata, and logs.
- Request transformation removes the three confirmed incompatible extensions,
  filters built-in tools, flattens only approved MCP tools, prevents alias
  collisions, disables parallel calls, and injects the token limit.
- Invalid authentication, method, path, model, JSON, request size, and tool
  shapes fail closed without an upstream call.
- SSE forwarding covers text, reasoning output, function calls, usage,
  completion, upstream errors, malformed events, and interrupted streams.
- Wrapper cleanup covers normal Codex exit, failed startup, proxy failure,
  timeout, and interruption.
- Wrapper tests cover exact prompt forwarding, live Codex/proxy output relay for
  outer idle activity, and AWM-enabled versus AWM-disabled restart prompts.
- Main orchestration wiring preserves three-run/AWM behavior and does not expose
  credentials in captured arguments or metadata.

### Local integration tests

- Real Codex plus fake Yibu and fake MCP proves namespace-to-function conversion
  ends in an observable MCP `briefing` call.
- Fake Yibu error responses prove 400, 429, timeout, and broken SSE reach Codex
  as failures without proxy retries.
- Existing AI Play orchestrator, MCP, supervisor, and scenario-registry tests
  remain green.

### Real acceptance

Real external acceptance is never part of automated tests. After explicit
confirmation of screenshots, tokens, fees, and local trajectory persistence:

1. Run a minimal real Doubao probe through Codex, the proxy, and a controlled
   MCP surface; require an actual `briefing` call.
2. Run `garden_watering` with three runs and AWM enabled.
3. Archive the complete run directories under the operator-requested log root.
4. Report completed runs separately from protocol, provider, Codex lifecycle,
   and Godot gameplay failures.

## Documentation and Verification

Update `ai_play/README.md` and `docs/wiki/ai-play/system-guide.md` with the new
entry, trust boundary, CLI, token default, supported credential source, and
diagnostic error categories. Do not describe the proxy as an agent.

Run the narrow proxy/orchestrator tests first, then the affected AI Play Python
suite, and finally `git diff --check`. If Godot is unavailable, report the
missing engine validation explicitly; real credential tests remain manual.
