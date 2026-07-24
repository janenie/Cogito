# AI Play Act Request Limit Design

## Goal

End one AI Play control session with `failure/max_requests` after the MCP Server
receives 500 `act()` tool requests without an earlier password terminal result.
Godot displays the existing game-over screen with the failure reason “达到最大步长”.

The limit is a safety terminal condition, not a model-visible action. The MCP
Server continues to expose only `briefing`, `observe`, `act`, and `stop`.

## Counting Contract

- One counted request is one invocation that reaches the Python `act()` MCP tool
  function.
- The counter increments before observation, action, session-state, or Godot
  validation, so stale observations, invalid action objects, invalid interface
  context, and concurrent in-flight attempts still consume the limit.
- `briefing()`, `observe()`, and `stop()` do not consume the limit.
- A malformed MCP/JSON request rejected by the MCP SDK before dispatching the
  Python `act()` function cannot be counted by this application.
- The default limit is 500 and is configured by
  `AI_PLAY_MAX_ACT_REQUESTS`.
- The value is a bounded positive integer. Invalid configuration prevents the
  MCP Server from starting.

The count belongs to the active Python/Godot bridge connection. It resets to
zero whenever a Godot controller successfully attaches to `GameSession`.
Disconnecting and reconnecting the bridge therefore starts a new count, as
does restarting the MCP Server. Reloading the Lobby also creates a new
connection and a new count.

## Limit Semantics

The 500th `act()` request is allowed to complete its normal processing:

- If it is valid, its action batch executes completely.
- If it is invalid, its normal tool error is superseded by the terminal result
  after the limit signal is acknowledged by Godot.
- If it causes a correct password result, the result is
  `success/correct_password`.
- If it causes a wrong password result, the result is
  `failure/wrong_password`.
- Otherwise the MCP Server automatically requests
  `failure/max_requests` after the request finishes.

Password results have priority over the request limit. Terminal handling is
idempotent, so delayed action completion, observations, disconnects, repeated
limit checks, or keypad callbacks cannot replace the first terminal result.

As soon as request 500 is recorded, the session marks the limit as pending.
Later `act()` calls cannot dispatch another batch while the 500th request is
being processed or while Godot is acknowledging the terminal condition.

## Architecture

### Python MCP boundary

`mcp_server.act()` asks `GameSession` to record the request before normal
validation. `GameSession` owns the counter because it already serializes the
single Godot controller, action-in-flight state, stop state, and terminal
state under one condition lock.

When the count is below the limit, the existing `act()` behavior remains
unchanged.

When request 500 finishes:

1. If `GameSession` already contains a password `game_over`, return it.
2. Otherwise send one internal request-limit terminal packet to Godot.
3. Wait within the configured bounded tool timeout for Godot's normal
   `game_over` packet.
4. Return that terminal state from the same 500th `act()` MCP call.

The public MCP tool schema does not gain a fifth tool and does not expose a
callable “end game” operation to the model.

### Internal WebSocket bridge

Python sends a new internal packet:

```json
{
  "type": "end_game",
  "protocol_version": 3,
  "observation_id": 42,
  "outcome": "failure",
  "reason": "max_requests"
}
```

Godot accepts this packet only when:

- its fields are exact;
- the protocol version is correct;
- `outcome` is exactly `failure`;
- `reason` is exactly `max_requests`;
- `observation_id` is null or matches the current pending/executing
  observation as required by controller state.

Godot then uses its existing `_finish_game()` path. That path sends the normal
Godot-to-Python `game_over` packet, cancels the executor, releases simulated
inputs, disconnects the bridge, displays the result, and pauses the scene.

The new Python-to-Godot packet and expanded terminal reason change the strict
bridge contract, so both ends move together from internal protocol version 2
to version 3. This version is independent of the standard MCP protocol date
version.

### Godot terminal boundary

`AIPlayController` accepts `max_requests` only for the
`failure/max_requests` pair. It does not count requests itself and cannot be
asked by the model to end the game.

The existing `AIPlayGameOverScreen` already recognizes `max_requests`; its
Chinese reason text changes from “已达到最大决策次数” to “达到最大步长”.

### Configuration

Python `Config` gains:

```text
AI_PLAY_MAX_ACT_REQUESTS=500
```

The value is not sent to the model, included in observations, or persisted in
logs. The internal end-game packet contains the terminal reason but does not
contain prompts, model metadata, credentials, or hidden game state.

## State and Error Handling

- If no Godot controller is attached, `act()` retains its normal disconnected
  or waiting error. A later successful attach resets the count to zero.
- If Godot disconnects before acknowledging the request-limit terminal,
  waiting callers wake and receive the existing disconnected error; reconnect
  starts a new count.
- If the end-game request cannot be sent, no success is fabricated.
- If the terminal acknowledgement times out, pending state is cleared safely
  and no later action is dispatched under the exhausted session.
- `stop()` and physical Escape remain higher-priority safety exits and release
  all simulated input.
- A password `game_over` received during request 500 is returned instead of
  sending or accepting a max-request result.

## Files and Documentation

Expected implementation scope:

- `ai_play/src/ai_play/config.py`
- `ai_play/src/ai_play/mcp_server.py`
- `ai_play/src/ai_play/game_session.py`
- `ai_play/src/ai_play/bridge_server.py`
- `addons/cogito/AIPlay/ai_play_bridge.gd`
- `addons/cogito/AIPlay/ai_play_controller.gd`
- `addons/cogito/AIPlay/ai_play_game_over_screen.gd`
- corresponding Python, GDScript, and shell tests
- `README_AI_PLAY.md`
- `ai_play/README.md`
- `docs/wiki/ai-play/system-guide.md`
- `tutorial/mcp_server.md`

The implementation does not modify `addons/input_helper/` or
`addons/quick_audio/`, does not add model credentials, and does not persist
request counts or play traces.

## Verification

Python tests cover:

- default and configured limit validation;
- reset on Godot attach/reconnect;
- valid and invalid `act()` requests consuming the count;
- request 499 remaining non-terminal;
- request 500 returning `failure/max_requests`;
- correct- and wrong-password priority on request 500;
- only one end-game packet;
- rejection of request 501 while terminal handling is pending;
- valid and invalid protocol-v3 end-game/game-over packets;
- disconnect and timeout behavior.

Godot tests cover:

- protocol version 3 normalization and rejection of other versions;
- exact `end_game` packet validation;
- `failure/max_requests` using the existing terminal path;
- input cancellation and release;
- idempotent terminal handling;
- the updated result text.

Repository verification runs the focused Python and Godot tests first, then the
affected AI Play suites and documentation checks, and finally
`git diff --check`. Real external MCP/model acceptance remains out of scope.
