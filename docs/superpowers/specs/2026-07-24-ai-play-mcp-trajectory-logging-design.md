# AI Play MCP Trajectory Logging Design

## Goal

Persist the approved MCP gameplay boundary for later inspection and
self-reflection. One run groups up to three Godot play attempts. Each attempt
records `observe`, `act`, and `stop` requests, their MCP-visible results, and
returned JPEGs without exposing credentials, hidden game state, repository
files, or image Base64 in JSON.

This change implements logging only. It does not restart Godot, invoke a model,
generate `review.json`, or orchestrate the three attempts.

## Session and Run Identity

The Python MCP Server creates a run only when Godot successfully attaches to
the loopback bridge. MCP Server startup and pre-connection tool calls do not
create a run.

The default root is:

```text
~/workspace/cogito_logs/mcplogs
```

`AI_PLAY_LOG_ROOT` may override it. On the current development machine the
default expands to:

```text
/Users/jan/workspace/cogito_logs/mcplogs
```

The first successful Godot attachment creates a minute-level run directory:

```text
YYYYMMDD-HH-MM
```

If that directory exists, the logger selects the first free suffix beginning
with `-02`. A later successful Godot attachment in the same MCP Server process
starts the next attempt in the existing run. Reconnection is therefore treated
as a new attempt, as agreed for this workflow.

The directory layout is:

```text
mcplogs/
└── 20260724-14-35/
    ├── run.json
    ├── attempt-01/
    │   ├── trajectory.json
    │   └── imgs/
    │       ├── 000001-observe-obs000001.jpg
    │       └── 000002-act-obs000002.jpg
    ├── attempt-02/
    │   ├── trajectory.json
    │   └── imgs/
    └── attempt-03/
        ├── trajectory.json
        └── imgs/
```

The logger groups at most three attachments in one run. If a successful run is
followed by another attachment, or if three attempts are already present, that
attachment starts a new collision-safe run directory. This is log rotation,
not retry execution: a future host/orchestrator still decides whether and when
Godot should be restarted.

## Attempt Trajectory Contract

`trajectory.json` always contains exactly two top-level fields:

```json
{
  "trajectory": [],
  "result": {
    "total_steps": 0,
    "status": "in_progress"
  }
}
```

The logger records only calls that begin while an attempt is active and before
its first terminal state. Calls rejected by the MCP SDK before dispatching the
Python tool function cannot be recorded.

The tool scope is:

- Record `observe`, `act`, and `stop`.
- Do not record `briefing`.
- Store the exact arguments that reached the Python tool function.
- Store the structured MCP result or the stable MCP error returned to the
  caller.
- Save returned JPEG bytes under the attempt's `imgs/` directory and place
  only relative image paths in JSON.

Each trajectory entry has:

```json
{
  "event_index": 2,
  "act_step": 1,
  "tool": "act",
  "requested_at": "2026-07-24T14:35:14.321+08:00",
  "completed_at": "2026-07-24T14:35:15.002+08:00",
  "request": {
    "observation_id": 1,
    "actions": [
      {
        "type": "move",
        "forward": 1,
        "right": 0,
        "duration_ms": 500
      }
    ]
  },
  "response": {
    "is_error": false,
    "structured_content": {
      "status": "ready",
      "action_results": [
        {
          "status": "completed",
          "type": "move"
        }
      ],
      "game_over": null,
      "observation": {}
    }
  },
  "images": [
    "imgs/000002-act-obs000002.jpg"
  ]
}
```

`act_step` appears only on `act` entries. `event_index` orders all recorded
tool calls. Image filenames use the event index, tool name, and returned
observation ID when available; `no-observation` is used when an image has no
observation ID.

A request is durably inserted with a null response before the gameplay tool is
executed. Completion updates the same entry with the response and image paths.
This preserves evidence of an interrupted in-flight call.

## Step and Result Semantics

`result.total_steps` counts each `act()` invocation that reaches the Python MCP
tool while the attempt is active and nonterminal. The count increments before
observation ID, action schema, session state, or Godot validation, so invalid,
stale, and otherwise rejected decisions still count. The `act()` call whose
execution produces the terminal result is included. Calls beginning after the
terminal state do not count and are not appended.

`result.status` is one of:

- `in_progress`: no terminal event has been received.
- `success`: Godot reported `game_over` with outcome `success`.
- `failure`: Godot reported `game_over` with outcome `failure`.
- `stopped`: MCP `stop`, physical Escape, bridge disconnection, or MCP Server
  shutdown ended the attempt without a game outcome.

Godot terminal events update the result even if the AI makes no later tool
call. A tool-call token created before the terminal event may still complete
its existing trajectory entry, but the result status and step count cannot be
changed afterward.

## Run Summary Contract

`run.json` is a compact index and never duplicates trajectories or images:

```json
{
  "started_at": "2026-07-24T14:35:00+08:00",
  "max_attempts": 3,
  "completed_attempts": 2,
  "status": "success",
  "successful_attempt": 2,
  "attempts": [
    {
      "attempt": 1,
      "status": "failure",
      "total_steps": 37
    },
    {
      "attempt": 2,
      "status": "success",
      "total_steps": 24
    }
  ]
}
```

`completed_attempts` counts attempts whose result is no longer `in_progress`.
The run remains `in_progress` while another attempt could start. It becomes
`success` immediately after a successful attempt, `failure` after three
attempts all end in `failure`, or `stopped` when the MCP Server shuts down
without success or when three completed attempts include at least one
`stopped` result and no success. The logger never creates `review.json`; that
file remains future host output so model interpretation cannot be confused
with the raw trajectory.

## Components and Data Flow

### `TrajectoryLogger`

A focused Python component owns directory allocation, attempt lifecycle,
tool-call tokens, JPEG persistence, and atomic JSON snapshots. It receives only
already approved MCP requests/results and terminal status notifications.

### `GameSession`

`GameSession` notifies the logger when:

- a Godot controller successfully attaches;
- an approved `game_over` packet is received;
- Escape or MCP stop is acknowledged;
- a bridge disconnect or MCP shutdown ends a nonterminal attempt.

The gameplay protocol and public MCP tool list do not change.

### MCP tool boundary

`mcp_server.py` begins a log entry before invoking `observe`, `act`, or `stop`,
then completes it with the exact `CallToolResult` projection and optional JPEG.
The existing MCP result never gains local filesystem paths; paths exist only in
the local log.

## Persistence and Failure Handling

- JSON files are UTF-8 with readable indentation.
- Every mutation writes a temporary sibling file, flushes it, and atomically
  replaces the destination so a crash cannot leave half-written JSON.
- JPEG bytes are written unchanged before their paths are committed to JSON.
- Directories use owner-only permissions where supported; JSON and JPEG files
  use owner read/write permissions where supported.
- Failure to create the run or first attempt rejects the Godot attachment, so
  an unlogged game cannot begin.
- Failure to persist a request prevents that tool from reaching `GameSession`.
- Failure while completing a tool result marks logging unavailable; later
  gameplay requests return `logging_failed` instead of dispatching new actions.
  The already persisted entry remains visibly incomplete.
- Logging diagnostics go only to stderr so MCP stdout remains protocol-clean.

## Privacy Boundary

The log may contain only data already approved for the external MCP caller:
tool arguments, structured tool results, and MCP JPEG content. It must not
contain:

- API keys, authorization headers, tokens, or external client configuration;
- system/developer prompts or unrelated model conversation;
- briefing content, because `briefing` is outside the agreed trajectory scope;
- image Base64;
- scene source, node paths, internal class names, hidden state, puzzle answers,
  tests, specs, plans, `game_script/`, or `code_read/`.

Local trajectory and screenshot persistence is intentional for this feature.
Real external-client acceptance remains opt-in because replaying stored images
into a model has separate token, cost, and privacy effects.

## Testing and Documentation

Python tests use temporary directories and fixed clocks to cover:

- default and overridden log roots;
- creation only after successful Godot attachment;
- collision-safe run names and monotonically numbered attempts;
- request-before-execution persistence;
- `observe`, valid/invalid `act`, and `stop` entries;
- exclusion of `briefing`;
- exact JPEG persistence and absence of Base64 in JSON;
- terminal status updates without a later tool call;
- terminal-producing steps, post-terminal calls, disconnect, and shutdown;
- atomic-write failure behavior and stable `logging_failed` results;
- run summary updates across up to three attempts.

Documentation updates cover `AI_PLAY_LOG_ROOT`, the layout, status/counting
semantics, privacy impact, and the distinction between logging and future
three-attempt orchestration. Verification runs the focused logger and MCP tests,
the complete Python AI Play suite, relevant shell checks, and
`git diff --check`. No real external MCP/model acceptance is run.
