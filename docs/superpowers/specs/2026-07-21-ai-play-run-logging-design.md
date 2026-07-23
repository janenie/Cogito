# AI Play Run Logging and Escape Stop Design

## Purpose

Make an autonomous AI play session inspectable end to end. A reviewer must be
able to reconstruct each model round from the multimodal request, raw and
validated model response, dispatched Godot actions, and Godot execution
results. Physical input must not accidentally interrupt autonomous play; Escape
is the sole human stop control and must continue to open the existing pause
menu.

## Scope

This change covers:

- Escape-only human termination of an active AI session.
- A run-scoped log directory outside the repository.
- Saved image inputs and append-only JSONL lifecycle events.
- Immediate Godot action-result reporting to the Python sidecar.
- Error and stop events needed to explain incomplete rounds.

It does not add video capture, replay execution, a log viewer, analytics, or
automatic deletion and retention policies.

## Input and Stop Behavior

While AI control is active, physical keyboard keys other than Escape, mouse
motion, mouse buttons, and controller input do not disable the AI controller.
Synthetic events emitted by the AI executor also do not disable it.

A non-echo physical Escape press performs these operations in order:

1. Cancel the current AI action batch and release held movement controls.
2. Send a terminal `escape_stop` event and any available cancellation result to
   the sidecar.
3. Disable and disconnect the AI controller.
4. Leave the Escape event unconsumed so the game's existing menu input opens
   the pause menu normally.

The controller must not reinterpret the AI executor's synthetic `close_ui`
action as a human Escape stop.

## Run Directory

The Python sidecar owns all filesystem logging. On startup it creates one run
directory under a configurable root. The default root is
`~/workspace/cogito_logs`, and `AI_PLAY_LOG_ROOT` may override it.

For model `gemini-3.5-flash`, a run started at 10:45 on July 21, 2026 has this
shape:

```text
~/workspace/cogito_logs/
└── gemini-3_5-flash/
    └── 20260721-10-45/
        ├── gemini_godot.jsonl
        └── img/
            ├── 000001.jpg
            ├── 000002.jpg
            └── ...
```

Every dot in the model name becomes an underscore. Any other character unsafe
for a single path component also becomes an underscore. If the minute-level run
directory already exists, the sidecar selects the first free numeric suffix,
starting with `-02`, rather than overwriting it.

The run directory is created once per sidecar process, not once per WebSocket
reconnection. Round indices increase monotonically within that run and never
reset after a reconnect.

## Round Identity and Images

One accepted Godot observation that reaches the model boundary is one round.
The logger assigns a positive, monotonic `round_idx` independent of Godot's
`observation_id`. Each event contains both values when an observation ID is
available.

Before the API call, the sidecar decodes the observation's base64 image and
writes it to `img/<round_idx padded to six digits>.jpg`. The saved bytes are the
same JPEG bytes represented by the image content sent to the model. Failure to
decode or save the image fails that round before the API request and produces a
`round_error` event.

## JSONL Event Stream

`gemini_godot.jsonl` is UTF-8, append-only, and contains one compact JSON object
per line. The sidecar serializes access and flushes every event before
continuing. API keys, authorization headers, and the base64 image payload are
never written.

Every event has:

- `event`: event type.
- `timestamp`: timezone-aware ISO 8601 wall-clock timestamp.
- `round_idx`: positive integer round identifier when applicable.
- `observation_id`: Godot observation identifier when applicable.

### `model_input`

Written after the image is saved and immediately before the API request. It
contains:

- `model`.
- `image_path`, relative to the run directory.
- `reference_atlas_path` when the request includes a visual reference atlas.
- The structured observation sent to the model, excluding image base64.
- The current bounded memory supplied to the model.

It intentionally omits the system prompt and final Chat Completions `messages`
envelope. Those values are request-construction details and substantially
duplicate the structured fields above.

### `model_output`

Written immediately after a successful API response, before parsing or action
validation. It contains:

- `raw_content`: the model response text without modification.
- `latency_ms`: elapsed API-call duration.

This preserves malformed model output for diagnosis. API transport failures
produce `round_error` instead because no model output exists. The raw response
is not redacted and may include candidate passwords or other sensitive
model-generated text, so the run directory must be treated as sensitive
harness-debugging data.

### `decision_validated`

Written after the raw response parses and passes the strict action schema. It
contains the exact validated decision. Parsing or validation failure produces a
`round_error` after `model_output`, and no action is dispatched.

### `action_dispatch_requested`

Written and flushed before sending an action batch to Godot. It contains the
reason, memory updates, and exact action list about to be delivered. It provides
durable evidence if transport succeeds but the later confirmation cannot be
written.

### `action_dispatched`

Written only after the action batch is successfully sent to Godot and its
associated memory update is committed. It contains the reason, memory updates,
and exact action list delivered to Godot.

### `godot_result`

Godot sends an `action_results` protocol packet as soon as an action batch
finishes. The event contains the exact sanitized executor results, including
statuses such as `completed`, `blocked`, `error`, `cancelled`, or `stopped`.
This is not delayed until the next observation. Duplicate result packets for an
already completed round are ignored or recorded as a protocol error; they do
not create a second successful result.

### `round_error`

Written for image persistence, API, parsing, validation, transport, or protocol
failures. It contains:

- `stage`: stable failure stage name.
- `error_type`: exception or protocol error category.
- A bounded, non-secret `message` where safe.

### `session_stop`

Written when Godot reports Escape termination or an explicit controller stop.
It contains a stable `reason`, the active round when known, and any final
sanitized cancellation results. A disconnect without a stop packet is recorded
separately so an interrupted final round remains explainable.

## Protocol and Data Flow

The existing observation/action loop remains authoritative:

1. Godot captures an observation and sends it to the sidecar.
2. The sidecar assigns `round_idx`, saves the JPEG, and appends `model_input`.
3. The sidecar calls the configured OpenAI-compatible Chat Completions API.
4. It appends `model_output`, parses and validates the decision, then appends
   `decision_validated`.
5. It appends `action_dispatch_requested`, sends the action batch to Godot,
   commits staged memory, then appends `action_dispatched` after successful
   delivery.
6. Godot executes the batch and sends `action_results` with its originating
   observation ID.
7. The sidecar correlates that ID to the round and appends `godot_result`.
8. Godot captures the next observation. Its existing `last_action_results`
   remains available to model memory logic, but is not the primary logging
   transport.

The sidecar maintains a bounded mapping from outstanding observation IDs to
round indices. Entries are removed after a terminal result or error so a long
session does not grow memory without bound.

## Failure Handling

- Logging failures are fail-closed for model calls: if the input cannot be
  persisted, the screenshot is not sent externally and Godot receives a safe
  decision error.
- Failure to append `model_output`, `decision_validated`, or
  `action_dispatch_requested` prevents action dispatch, because an unlogged
  action would violate auditability.
- If appending `action_dispatched` fails after transport has succeeded, the
  sidecar closes the controller session and reports the logging failure to
  stderr. The durable `action_dispatch_requested` event preserves evidence that
  the action may have reached Godot.
- If Godot disconnects after dispatch but before reporting results, the JSONL
  retains `action_dispatched` and adds a disconnect error; the missing
  `godot_result` visibly marks the round incomplete.
- A malformed `action_results` or stop packet cannot write arbitrary fields or
  paths; protocol validation and the existing bounded result schema apply.
- Log messages never include credentials or complete HTTP headers.

## Testing

Python tests use a temporary `AI_PLAY_LOG_ROOT` and verify:

- Model-name sanitization and collision-safe run directories.
- Monotonic round indices across reconnects.
- Exact JPEG byte persistence and base64 exclusion from JSONL.
- Input, raw output, validated decision, dispatch request, confirmed dispatch,
  result, stop, and error events.
- Flush-visible JSONL after each event.
- Fail-closed behavior when image or JSONL persistence fails.
- Correlation and deduplication of action results.
- No API key or authorization data appears in logs.

Godot tests verify:

- Only physical Escape disables AI.
- Escape remains available to the existing pause-menu input.
- Other physical and synthetic inputs do not terminate AI.
- Held movement is released on Escape.
- Completed, blocked, failed, cancelled, and stopped action batches emit one
  correlated `action_results` packet.

An opt-in integration check runs a short live session and verifies that its run
directory contains readable images plus a chronologically complete JSONL event
sequence without inspecting game scripts or seeding solution knowledge.
