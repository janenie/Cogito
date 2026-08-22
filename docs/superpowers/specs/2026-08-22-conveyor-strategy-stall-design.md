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
external player. After each completed conveyor action it compares:

- the canonical submitted action batch;
- the public conveyor state, excluding observation identity, timestamps,
  screenshots, and the previous action-result envelope; and
- whether the turn returned a completed action result without producing a
  formal game terminal.

One completed turn starts a streak at one. The streak increases only when the
next turn submits the same canonical action batch and returns the same public
conveyor state. Any different action, public-state change, reconnect, new round,
or formal terminal clears the streak. This intentionally catches repeated
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

`max_requests` remains the global hard cap and is unchanged. If it is reached
before the stall threshold, its existing terminal reason wins.

## Persistence and Recovery

Because `strategy_stalled` is a formal failure, workflow-memory updates use the
existing failure contract: no promoted workflow or landmarks, only compact
avoid/failure-review lessons supplied by the model. If the process disconnects
before Godot acknowledges the terminal, existing interruption persistence and
resume behavior remain authoritative; the guard does not fabricate a completed
round.

Per-round stall tracking resets when a new hello attaches after a completed,
stopped, or disconnected attempt. Reconnecting to the same unfinished action
does not double-count an action request or a no-progress turn.

## Tests and Documentation

Python session tests cover four matching no-progress turns remaining playable,
the fifth producing `failure/strategy_stalled`, streak resets on action or
public-state changes, and non-conveyor scenarios remaining unaffected. Scenario
and bridge tests cover the new allowlisted terminal pair.

Godot controller tests cover accepting the trusted conveyor-only end-game
request, rejecting it for other scenarios, and using the normal terminal/input
release path. Public protocol documentation in `ai_play/README.md` and the AI
Play Wiki will describe the new conveyor-only failure reason and five-turn
threshold without exposing hidden game state.
