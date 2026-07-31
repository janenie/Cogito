# Semantic AI Look Control Design

## Goal

Make first-person camera control predictable for a visual AI player. The player
states a human-readable direction and a positive angle; trusted code owns the
sign convention and maps the request to Cogito camera rotation. The same change
also prevents unrequested physical or window-focus mouse motion from changing
the camera while AI control is active.

This addresses a recorded failure where the first requested turn and the next
screenshot disagreed: `left 45°, down 12°`-equivalent numeric input produced a
camera looking at the ceiling and a public pose change far larger than the
requested action.

## Public Action Contract

The existing numeric action:

```json
{"type": "look", "yaw": -30, "pitch": 0}
```

is replaced for MCP players by:

```json
{"type": "look", "direction": "left", "degrees": 30}
```

`direction` is exactly one of `left`, `right`, `up`, or `down`. `degrees` is a
finite positive number from 1 through 45 inclusive. A look action changes only
one axis, so the player must use two actions when it wants both horizontal and
vertical rotation.

The trusted mapping is:

| Direction | Internal yaw | Internal pitch |
| --- | ---: | ---: |
| `left` | `-degrees` | `0` |
| `right` | `degrees` | `0` |
| `up` | `0` | `-degrees` |
| `down` | `0` | `degrees` |

The public player never chooses or learns the internal sign convention.
Malformed directions, zero, negative, non-finite, boolean, or over-limit angles
are rejected before Godot input execution.

## Runtime Flow

1. Codex learns the semantic action from the approved `briefing` object guide
   and high-priority player instructions.
2. Python validates the exact action fields, direction enum, and degree range.
3. The bridge forwards the unchanged semantic action to Godot.
4. `AIPlayExecutor` validates it again, maps it to the existing internal
   yaw/pitch rotation path, and executes one bounded turn.
5. Godot waits for the rendered result before capturing the next observation.
6. The `act` result returns the new screenshot, public orientation, and action
   result. Codex compares this screenshot with the preceding observation and
   checks that landmarks moved in the expected direction before planning again.

The AWM-enabled and AWM-disabled comparison modes use this identical action
contract and visual-verification instruction.

## Input Isolation

While `AIPlayController` is enabled, Cogito's player ignores mouse-motion events
whose device is not `AIPlayExecutor.SYNTHETIC_DEVICE_ID`. This prevents physical
mouse motion and window-focus/cursor-capture events from being blended into an
AI turn. The guard is enabled before bridge connection and removed on every
disable, terminal, error, teardown, and explicit stop path.

Escape remains the physical emergency stop key and is never filtered. No other
physical input silently modifies an active AI camera. After AI control is
disabled, normal human mouse control is restored immediately.

The look implementation continues to use the player's supported camera path;
it does not write absolute coordinates or reveal them to the model.

## Error and Compatibility Behavior

- Numeric `yaw`/`pitch` look actions are no longer part of the public protocol
  and fail exact-field validation instead of being guessed or converted.
- Existing non-look actions retain their current schemas and limits.
- Invalid semantic look input produces the existing validation error shape and
  does not rotate the player or consume an executable action.
- Disconnect and cancellation retain their existing input-release behavior.
- Previously stored AWM entries contain no raw action sequences, so no memory
  migration is required.

## Player Guidance

The approved briefing and Codex developer instructions describe directions in
ordinary language and tell the player to:

- use a small turn when centering a nearby object and a larger turn while
  surveying an area;
- execute one-axis turns and observe after each action batch;
- compare the current screenshot with the previous tool-returned screenshot;
- infer relative rotation from landmark displacement and correct the next turn
  if the visual change differs from expectation.

The instructions do not expose scene source, hidden state, absolute world
coordinates, or screenshot files.

## Verification

### Automated tests

- Python action-schema tests accept four literal direction mappings at the
  1° and 45° boundaries and reject malformed fields and invalid degrees.
- Godot executor tests verify each semantic direction yields the hand-derived
  yaw/pitch delta and that numeric look fields are rejected.
- A real Cogito player input test verifies physical mouse motion cannot rotate
  the camera while the guard is active, synthetic look still rotates by the
  requested amount, and disabling the guard restores human rotation.
- Controller tests verify the guard is enabled and cleared on all lifecycle
  boundaries while Escape still stops and releases simulated input.
- Prompt and briefing tests verify the generated public contract contains only
  semantic look fields and visual comparison guidance.
- Relevant Python and Godot AI Play suites pass, followed by `git diff --check`.

### Real acceptance

Before the six-attempt AWM comparison, run a controlled first-turn check and
confirm that the requested direction/angle, public orientation delta, and
before/after screenshots agree. Then run three `find_contract` attempts without
AWM and three with AWM using `gpt-5.6-sol` at `high` reasoning effort.

## Documentation

Update `ai_play/README.md` for the public action and player-runtime contract, and
update `docs/wiki/ai-play/system-guide.md` because semantic camera control and
AI-only mouse isolation are stable cross-layer behavior.

## Out of Scope

- Free-form text parsing such as `turn a little left`.
- Simultaneous diagonal look actions.
- Absolute headings, target coordinates, object tracking, pathfinding, or depth
  estimation.
- Persisting screenshots or image embeddings in AWM.
- Changing non-look action limits or the `find_contract` game rules.
