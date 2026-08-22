# Conveyor Profit Strategy-Stall Design

## Goal

Stop wasting model requests when an AI player repeats the same ineffective
`conveyor_profit` action without changing the public game state. After five
consecutive no-progress turns, finish the round through the normal formal
terminal path as `failure/strategy_stalled`, so trajectory logging and workflow
memory receive the same durable terminal information as other game failures.

This guard is specific to `conveyor_profit`. Other scenarios retain their
current behavior and request limits.

## Detection

The trusted Python `GameSession` observes only data already approved for the
external player. For each normally completed conveyor action it compares:

- the canonical submitted action batch;
- fingerprints built from `observation["conveyor"]` immediately before and
  after dispatch, excluding the volatile `total_time` and `window_time` clocks;
  and
- whether action results match the submitted batch in length and order, with
  every result reporting `status == "completed"` and the corresponding action
  `type`.

Observation IDs, capture timestamps, screenshots, player/interface state,
bindings, and the previous action-result envelope are never part of the
fingerprint. The retained conveyor fields are `window`, `dish`, `net_profit`,
`tray`, `last_receipt`, `market`, `contracts`, and `finished`, compared as a
canonical JSON-compatible value.

Only a turn whose pre-action and post-action fingerprints are identical is a
no-progress candidate. A normally completed turn that changes the fingerprint
clears the streak completely. The first no-progress candidate starts a streak
at one. A later candidate increments the streak only when its canonical action
batch and unchanged fingerprint match the previous candidate; otherwise it
starts a new streak at one. A new round or formal terminal also clears the
streak completely. Invalid or stale requests, error/blocked/
cancelled/stopped results, partial or empty result lists, action timeouts, and
in-connection `recover_action` handling neither increment nor reset the streak.
This intentionally catches repeated
requests such as selecting the same unavailable ingredient or repeatedly
calling `wait_next_window` before a dish is complete, while allowing the player
to change strategy immediately.

The fifth consecutive matching no-progress turn triggers the guard. The fifth
action result remains part of the returned terminal turn for auditability.

## Formal Terminal Flow

The guard reuses the existing trusted `end_game` transport rather than killing
the player or Godot process. It sends the current public observation ID with:

```text
outcome = failure
reason = strategy_stalled
```

Python and Godot allow this pair only for `conveyor_profit`. Godot follows its
existing terminal path: freeze the game, release simulated input, show the
result, acknowledge the terminal, and exit when supervised with
`--ai-play-exit-on-game-over`. The MCP result is a formal `game_over`, allowing
the trajectory logger and workflow memory to finish the attempt normally.

Terminal precedence follows the existing `act()` contract. A legal terminal
produced by gameplay wins first. If the completed call reaches the configured
act-request cap, `failure/max_requests` wins next. Only a nonterminal call below
that cap may trigger `failure/strategy_stalled`. The implementation reuses a
single one-shot `ending`/end-game-sent path so two trusted end-game packets
cannot race.

The protocol remains version 4. The Godot bridge has no scenario context, so it
syntax-allows only the exact trusted pairs `failure/max_requests` and
`failure/strategy_stalled`. The controller retains `max_requests` for every
scenario but accepts `strategy_stalled` only when the active scenario is
`conveyor_profit`. A stall request must carry the exact current pending
observation ID and may never use null.

## Persistence and Recovery

Because `strategy_stalled` is a formal failure, workflow-memory updates use the
existing failure contract: no promoted workflow or landmarks, only compact
avoid/failure-review lessons supplied by the model. If the process disconnects
before Godot acknowledges the terminal, existing interruption persistence and
resume behavior remain authoritative; the guard does not fabricate a completed
round.

A real WebSocket disconnect uses the existing `detach()` behavior, finishes the
attempt as disconnected, and clears stall tracking. A later hello starts a new
attempt with a zero streak. By contrast, an in-connection action timeout and
`recover_action` exchange contributes no stall turn and preserves the prior
completed streak; the next qualifying completed turn naturally restarts at one
if its public fingerprint or action changed.

## Tests and Documentation

Python session tests cover four matching no-progress turns remaining playable,
the fifth producing `failure/strategy_stalled`, streak resets on action or
public-state changes, timeout/recovery contributing zero turns, request-cap tie
precedence, and non-conveyor scenarios remaining unaffected. Scenario and
bridge tests cover the new allowlisted terminal pair. A session integration
test uses the recording trajectory logger and attempt observer to prove the
failure is finished exactly once. Workflow-memory coverage proves the terminal
remains failure-only: no workflow or landmarks are promoted, while a trusted
failure review may record the reason.

Godot bridge/controller tests cover syntax acceptance, accepting the trusted
conveyor-only end-game request with an exact non-null pending observation ID,
rejecting it for other scenarios or mismatched IDs, and using the normal
terminal/input-release path. The game-over screen receives dedicated copy and
test coverage for `strategy_stalled` rather than falling back to generic text.
Public protocol documentation in `README_AI_PLAY.md`, `ai_play/README.md`, and
the AI Play Wiki will describe the new conveyor-only failure reason and
five-turn threshold without exposing hidden game state.
