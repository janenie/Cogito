# AI Interaction Probe Design

## Objective

Add a bounded `probe_interaction` capability to AI First Play so the model can
turn a visually identified object into a normal crosshair interaction target.
The probe aligns the camera and searches a small area, but never activates an
interaction. The model receives a fresh observation and decides what to do next.

The normal sidecar continues to use the API key and base URL statically read
from the repository-root `api_key.py` when no `AI_PLAY_*` environment override
is present.

## Current Problem

The model can identify likely buttons, doors, drawers, and items in screenshots,
but `interact` is valid only after the player's narrow interaction ray or shape
cast has already selected an object. In the observed 46-round run, every
`available_interactions` list was empty. The model recognized a red button in
the image, but it could only issue movement and look actions because the harness
never exposed an interaction slot.

The missing capability is a closed loop between a visual target location and
the existing player interaction ray.

## Scope

This change adds:

- A model action that identifies a target in the current screenshot.
- Bounded camera alignment through ordinary synthetic mouse input.
- A small local scan using only the normal player interaction result.
- Immediate re-observation after a successful or unsuccessful probe.
- Structured probe outcomes in action results and runtime memory.

This change does not add:

- Automatic interaction, movement, or object selection.
- Scene-tree queries, hidden object lists, navigation data, or target metadata.
- Arbitrary mouse clicks, raw key presses, or unrestricted Godot method calls.
- Model training or weight updates.

## Action Contract

The model may return this action:

```json
{
  "type": "probe_interaction",
  "target_x": 0.18,
  "target_y": 0.26
}
```

`target_x` and `target_y` are finite normalized coordinates in the current
camera image. `(0, 0)` is the top-left corner and `(1, 1)` is the bottom-right
corner.

`probe_interaction` must be the only action in its batch. A preceding look or
move would make the image coordinates stale. The action is rejected while an
interface is open.

Both Python and Godot validate the exact action fields, coordinate bounds,
single-action batch rule, and closed-interface requirement.

## Camera Alignment

Godot converts the normalized image coordinate into a camera-relative angular
offset using the active camera field of view and viewport aspect ratio. It then
converts the angular offset into synthetic mouse motion using the player's
runtime mouse sensitivity and vertical-axis setting.

The probe uses the same input path as normal camera look. It does not set camera
or player transforms directly.

After coarse alignment, the probe checks the same approved interactions exposed
by `AIPlayObserver`. If none are available, it tests a fixed local scan pattern
around the aligned direction:

- At most nine scan positions.
- At most four degrees from the aligned direction on either axis.
- At least one process or physics frame between camera input and interaction
  inspection.
- Stop immediately when one or more approved interactions become available.

If the scan succeeds, the camera remains at the aligned position. If it fails,
the harness restores the pre-probe camera orientation through bounded synthetic
mouse input.

The probe never moves the player and never sends `interact` or `interact2`.

## Runtime Data Flow

1. Godot captures a screenshot and the normal whitelisted observation.
2. The model identifies a suspicious visible object and returns
   `probe_interaction` with its image coordinates.
3. Python validates that the probe is the only action and the interface is
   closed.
4. Godot repeats the same validation before execution.
5. Godot aligns the camera, performs the bounded local scan, and reports the
   outcome.
6. The controller immediately captures a new observation.
7. On success, the new observation contains every currently approved
   `available_interactions` entry for the aligned object.
8. The model decides in the next round whether to interact, which interaction
   slot to use, or whether to leave the object alone.

The existing interaction validation remains authoritative. An interaction can
execute only if its slot is still present in the new observation.

## Result Contract

A finished probe returns an action result shaped as:

```json
{
  "status": "completed",
  "type": "probe_interaction",
  "outcome": "aligned",
  "scan_steps": 3
}
```

For a completed probe, `outcome` is one of:

- `aligned`: at least one approved interaction is currently available.
- `not_found`: the bounded scan found no approved interaction.

`scan_steps` is a bounded nonnegative integer. It records how many local scan
positions were tested and is diagnostic context, not hidden world state.

An interrupted probe uses the existing cancellation shape and has no `outcome`
or `scan_steps` field:

```json
{
  "status": "cancelled",
  "reason": "escape_stop"
}
```

The controller immediately re-observes after any completed probe. The new image
and `available_interactions` list are the source of truth.

## Learning and Memory

Learning is in-session reasoning and bounded memory, not model fine-tuning.
Probe actions and their results enter the existing recent-step memory:

- `not_found` while the object remains visible suggests approaching or changing
  angle.
- Repeated `not_found` outcomes suggest abandoning that target.
- `aligned` with multiple interactions requires the model to choose from the
  visible prompts.
- A changed or missing prompt after interaction suggests the object state
  changed and should not be repeated mechanically.

Facts and landmarks enter persistent semantic or spatial memory only through
the existing model-authored memory update contract. A normal start without
`--resume` still begins with empty memory.

## Configuration

The normal entry point remains:

```bash
./ai_play/start_ai.sh
```

`Config.from_env()` statically reads the key and base URL from `api_key.py` when
the matching `AI_PLAY_API_KEY` or `AI_PLAY_BASE_URL` variable is absent. The
file is parsed as source and is not executed. Secrets are never written to logs
or prompts.

The YibuAPI-specific launcher is not used by this feature or by the normal
start command.

## Safety and Failure Handling

- Escape, WebSocket disconnect, controller disable, and scene teardown cancel
  an active scan and release synthetic input.
- A missing player, camera, observer, or valid mouse sensitivity returns a
  bounded error without direct transform fallback.
- Invalid coordinates, stale batches, open interfaces, and extra action fields
  are rejected before input execution.
- Scan count and angular extent are constants with hard upper bounds.
- A successful probe authorizes no interaction by itself.
- Interaction prompts remain untrusted text and cannot expand the action
  whitelist.
- The existing loopback-only bridge and two-layer action validation remain in
  place.

## Verification

Python tests cover:

- Exact `probe_interaction` schema.
- Finite normalized coordinate bounds.
- Single-action batch requirement.
- Rejection while an interface is open.
- Prompt documentation and output shape.
- Probe result observation validation and memory propagation.

Godot tests cover:

- Coordinate-to-mouse alignment for center, corners, and vertical-axis modes.
- Scan count and angular bounds.
- Immediate stop when an approved interaction appears.
- No interaction input during probing.
- Failed-probe view restoration.
- Cancellation and held-input cleanup.
- Immediate observation after both `aligned` and `not_found`.

An integration fixture exposes an interaction only after a known bounded camera
adjustment. It verifies:

```text
probe_interaction -> aligned -> fresh available_interactions -> model interact
```

All existing Python and Godot AI Play tests must continue to pass. After
credential-free verification, one intentional black-box run uses `api_key.py`
and the Lobby. The run log must show a probe, a fresh observation with visible
interaction prompts, a separately chosen interaction, and the resulting state
change.
