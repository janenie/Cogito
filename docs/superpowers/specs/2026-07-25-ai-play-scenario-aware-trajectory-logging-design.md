# AI Play Scenario-Aware Trajectory Logging Design

## Goal

Extend the existing MCP trajectory logger so saved runs are unambiguously
associated with the AI Play scenario that produced them. This supports
task-specific replay and later self-reflection without changing the public MCP
tool results or the per-attempt trajectory contract.

This is a compatibility update to the trajectory logging design. It does not
implement retry orchestration, model reflection, or real external-client
acceptance.

## Scenario-Partitioned Run Layout

The configured log root remains:

```text
~/workspace/cogito_logs/mcplogs
```

Each run is placed below its validated `scenario_id`:

```text
mcplogs/
├── find_contract/
│   └── 20260725-14-30/
│       ├── run.json
│       └── attempt-01/
│           ├── trajectory.json
│           └── imgs/
├── find_key/
│   └── 20260725-14-45/
├── put_book/
│   └── 20260725-15-10/
└── greet_npc_meeting/
    └── 20260725-15-25/
```

Minute-level collision suffixes retain their existing meaning and are resolved
within one scenario directory. For example, two `find_key` runs started in the
same minute become `20260725-14-45` and `20260725-14-45-02`.

A run groups at most three attempts of one scenario. The logger must never
append an attempt with a different `scenario_id` to an existing run. This
invariant is enforced in the logger even though the current `GameSession`
already rejects switching scenarios after its first attachment.

The logger independently accepts only conservative scenario identifiers:
lowercase ASCII letters and digits, optionally followed by lowercase letters,
digits, underscores, or hyphens. Empty identifiers, separators, dots, absolute
paths, and other values are rejected before filesystem mutation. The bridge
continues to perform the authoritative supported-scenario check.

## Lifecycle Integration

Godot supplies `scenario_id` in its validated bridge hello packet. The bridge
passes it to `GameSession.attach`, and `GameSession` passes it to
`TrajectoryLogger.start_attempt`.

The scenario must be assigned and validated before the logger creates the
attempt. A missing or invalid scenario therefore cannot produce an
unclassified log directory.

Logging still starts only after the bridge has accepted the Godot connection.
MCP Server startup and pre-connection calls do not create a run.

## Run Summary Contract

`run.json` gains a top-level `scenario_id`. Each attempt summary gains
`terminal_reason`, which is `null` until the attempt finishes:

```json
{
  "scenario_id": "find_key",
  "started_at": "2026-07-25T14:45:00+08:00",
  "max_attempts": 3,
  "completed_attempts": 1,
  "status": "in_progress",
  "successful_attempt": null,
  "attempts": [
    {
      "attempt": 1,
      "status": "failure",
      "total_steps": 50,
      "terminal_reason": "max_requests"
    }
  ]
}
```

Scenario-specific Godot outcomes retain their already validated public reason,
such as `key_picked_up`, `book_in_box`, `meeting_door_closed`,
`wrong_password`, or `max_requests`.

Non-game terminal paths use stable local summary reasons:

- `mcp_stop`: the MCP `stop` tool ended the attempt.
- `escape_stop`: Godot reported the physical emergency stop.
- `bridge_disconnected`: the bridge connection ended unexpectedly.
- `mcp_shutdown`: server shutdown ended a nonterminal attempt.

The attempt status remains the coarse result used by existing run aggregation:
`success`, `failure`, or `stopped`. `terminal_reason` explains that status but
does not alter it.

If the attempt has already reached a terminal state, later disconnect or
shutdown cleanup cannot overwrite its first terminal reason.

## Trajectory Compatibility

`trajectory.json` remains unchanged and continues to contain exactly:

```json
{
  "trajectory": [],
  "result": {
    "total_steps": 0,
    "status": "in_progress"
  }
}
```

In particular, `scenario_id` and `terminal_reason` are run-index metadata, not
new trajectory result fields. Existing consumers that process individual
attempt trajectories therefore remain compatible.

The recorded MCP tool scope also remains unchanged: `observe`, `act`, and
`stop` are recorded; `briefing` is excluded.

## Current Scenario-System Compatibility

The updated branch introduces scenario-aware bridge hello validation,
scenario-specific briefing selection, per-scenario request limits, and new
terminal reasons. Integrating logging must preserve those flows:

- bridge hello passes `scenario_id` through without weakening registry checks;
- `briefing` still waits for the connected scenario before loading its public
  whitelist;
- tool wrappers still record only the approved `observe`, `act`, and `stop`
  boundaries;
- scenario-specific request limits and terminal outcome validation remain
  authoritative in `GameSession`;
- the logger receives only the validated scenario identifier and approved
  terminal reason.

Overlapping changes in `bridge_server.py`, `game_session.py`, `mcp_server.py`,
tests, README, and Wiki must be merged semantically rather than by selecting
one side wholesale.

## Privacy and Failure Handling

The privacy boundary from the original trajectory logging design remains in
force. A scenario identifier and approved terminal reason are public runtime
metadata; no scene paths, hidden state, puzzle answers, developer notes, or
repository content are added.

Failure to create the scenario directory or persist the initial run rejects
the attachment as before. Invalid scenario identifiers fail before any
directory is created. Atomic JSON and image writes, owner-only permissions,
stderr-only diagnostics, and `logging_failed` behavior remain unchanged.

## Testing and Documentation

Tests must cover:

- one root containing separate directories for multiple scenario IDs;
- collision suffixes scoped to a scenario directory;
- `scenario_id` present in `run.json`;
- rejection of unsafe identifiers before filesystem mutation;
- three attempts never mixing scenarios;
- `terminal_reason` for success, failure, MCP stop, Escape, disconnect, and
  shutdown;
- first-terminal-reason preservation;
- unchanged two-field `trajectory.json.result`;
- scenario-aware bridge hello and briefing behavior coexisting with logging.

Update `ai_play/README.md` and the AI Play Wiki with the scenario-partitioned
layout and summary fields. Verification must run focused logger/session/bridge/
MCP tests, the full Python suite, relevant shell checks, and
`git diff --check`. Real external-client acceptance remains out of scope.
