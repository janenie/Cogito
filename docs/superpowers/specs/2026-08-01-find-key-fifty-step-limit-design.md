# Find Key 50-Step Limit Design

## Goal

Make every newly started `find_key` round enforce a maximum of 50 `act` requests, regardless of the randomly selected key location, so the black-box player is evaluated against one clear budget.

## Runtime behavior

- `AIPlayFindKeyMonitor.get_act_request_limit()` always returns 50.
- `AIPlayController` accepts 50 from the active `find_key` monitor and includes it in the protocol-v4 `hello` packet.
- Python takes the minimum of the round limit and `AI_PLAY_MAX_ACT_REQUESTS`, so local configuration may still tighten the budget below 50 but cannot raise it.
- The fiftieth `act` is allowed to finish. If it does not produce the trusted success terminal, Python sends the existing `end_game/failure/max_requests` request.
- No key placement, spawn, observation, action, AWM, or supervisor behavior changes.

## Compatibility

Python and the bridge continue accepting an integer `act_request_limit` of either 50 or 100 from protocol-v4 `find_key` hello packets. This preserves compatibility with an older Godot process during a rolling local update. New Godot rounds only emit 50. Removing 100 from the protocol boundary would require a separately reviewed compatibility change.

## Public information and documentation

The public `find_key` briefing states a fixed maximum of 50 `act` requests. README and Wiki text no longer describe location-dependent 50/100 limits. Hidden key-location and spawn-selection state remain excluded from all model inputs.

## Verification

- A Godot monitor test covers representative key-location categories and expects 50 for each.
- Controller tests verify a `find_key` hello reports 50 and rejects values outside the compatibility set.
- Python scenario/session tests verify the default effective `find_key` limit is 50 while an explicitly received legacy round limit of 100 remains accepted and is capped by the scenario default.
- Run the affected Python suite, Godot monitor/controller tests, static safety checks, and `git diff --check` before the real Codex run.
