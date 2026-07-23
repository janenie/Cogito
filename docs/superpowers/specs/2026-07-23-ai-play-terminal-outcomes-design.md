# AI Play Terminal Outcomes Design

## Goal

End a `find_contract` AI run with an explicit result when the keypad checks a
complete password or when the run reaches 1000 model decision requests.

## Outcome Contract

A terminal result has exactly:

- `outcome`: `success` or `failure`
- `reason`: `correct_password`, `wrong_password`, or `max_requests`
- `request_count`: the number of top-level model decision requests made in this
  sidecar process

The result is sent across the existing loopback WebSocket, printed by the
sidecar, and written to the run JSONL as `game_over`. Godot then cancels active
input, releases held controls, stops observations, and disconnects.

## Request Counting

One request means one top-level AI decision call initiated for a validated
observation. A model response containing multiple game actions still counts as
one request. OpenAI SDK internal retries do not count as extra gameplay
requests.

The 1000th request is allowed to return and its action batch is allowed to run.
If that batch does not produce a keypad result, the run ends with
`failure/max_requests`. A sidecar-side API or decision failure on request 1000
also ends with `failure/max_requests`.

## Password Result

`CogitoKeypad` emits a result signal as soon as a complete entered code is
checked. The signal carries only whether the code was correct; it never exposes
the configured passcode.

The `find_contract` scene uses a small terminal monitor connected to the
ARCHIVE keypad. A correct check ends with `success/correct_password`. An
incorrect check ends immediately with `failure/wrong_password`; retries are not
allowed for this game mode.

## Ordering

Password results have priority over the request limit. If request 1000 submits
the correct password, the outcome is success. If it submits a wrong password,
the outcome is wrong-password failure. Only a non-terminal 1000th action batch
becomes max-request failure.

Terminal handling is idempotent. Once an outcome is recorded, later batch
completion, disconnect, timer, or keypad callbacks cannot replace it or send a
second result.

## Scope

The keypad signal is generic and reusable. The immediate wrong-answer rule and
1000-request terminal policy are enabled by the `find_contract` AI controller
configuration. Existing manual Escape stopping, generic AI actions, and normal
non-AI keypad behavior remain unchanged.

## Verification

- Godot keypad tests cover correct and incorrect result signals.
- Godot controller tests cover password priority, request 1000, idempotency,
  input release, and exact terminal packet fields.
- Python tests cover request counting, action-batch metadata, request-1000 API
  failure, protocol validation, logging, and connection termination.
- Existing Python and Godot AI Play suites remain green.
