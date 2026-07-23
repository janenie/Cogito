# Nearby Interactables Observation Design

## Goal

Give the model bounded spatial information about the five nearest usable
objects that are actually visible in the current camera image. This supplements
the screenshot and player pose without bypassing normal movement,
`probe_interaction`, or the existing interaction success condition.

## Candidate objects

The collector enumerates nodes in the COGITO `interactable` group. A candidate
is excluded when:

- it is invalid or is not a `Node3D`;
- it has no enabled `InteractionComponent`;
- it or its relevant visual hierarchy is not visible in the scene tree;
- its interaction point is outside the active camera frustum;
- a physics ray from the active camera to its interaction point is blocked by
  another object.

The list can include enabled Hints, doors, drawers, NPCs, readable objects,
buttons, keypads, pickups, and other COGITO interactables. It is not restricted
to Find Contract puzzle objects.

## Interaction point

Spatial calculations use the same kind of point a player would aim at:

1. an explicit prompt marker when the object provides one;
2. the configured AABB/visual center when supported;
3. the object's global position as a safe fallback.

The collector must not use a developer node name to describe an object.

## Distance and selection

Distance is the three-dimensional Euclidean distance from the player's current
global position to the candidate's interaction point:

```text
distance_m = player.global_position.distance_to(interaction_point)
```

After frustum and line-of-sight filtering, candidates are sorted by
`distance_m` ascending. At most the first five are returned. Screen-center
distance and crosshair distance do not affect ranking.

## Observation shape

Each normal observation adds:

```json
{
  "nearby_interactables": [
    {
      "tracking_id": 123456,
      "category": "readable",
      "distance_m": 3.4,
      "world_position": [4.2, 1.3, -12.5],
      "relative_position": {
        "forward": 3.1,
        "right": 1.2,
        "up": 0.4
      },
      "relative_yaw_degrees": 21.2,
      "relative_pitch_degrees": -5.8,
      "screen_position": {
        "x": 0.68,
        "y": 0.44
      },
      "interactions": [
        {
          "action": "interact",
          "prompt": "Read task"
        }
      ]
    }
  ]
}
```

Field rules:

- `tracking_id` is an opaque runtime identifier stable only while that object
  instance exists. It carries no puzzle semantics.
- `category` is derived from public object or interaction component types, not
  from internal scene node names.
- `world_position` is the selected interaction point.
- `relative_position` is expressed in the player's current frame:
  positive `forward` is ahead, positive `right` is to the player's right, and
  positive `up` is above.
- relative yaw and pitch point from the current view toward the interaction
  point.
- screen coordinates are normalized to `[0, 1]`, matching
  `probe_interaction.target_x` and `target_y`.
- `interactions` contains only enabled `interact` or `interact2` slots and their
  public prompts.

The array is recalculated for every observation.

## Model-use rules

The system prompt explains:

- use `distance_m` and relative position to decide whether to approach;
- use `screen_position` as an estimated `probe_interaction` target;
- object presence does not mean the crosshair is aligned;
- `available_interactions` being non-empty remains the only alignment success
  condition;
- after moving, looking, or probing, use the next observation rather than old
  coordinates.

No readable content, password, internal node path, or developer-only object name
is included.

## Components and data flow

1. A focused Godot collector enumerates, filters, projects, sorts, and bounds
   nearby interactables.
2. `ai_play_observer.gd` adds the collector result to each observation.
3. `ai_play_find_contract_observer.gd` retains this field while continuing to
   remove health and stamina.
4. Python `observation_schema.py` validates the exact nested shape, five-object
   limit, finite numeric ranges, normalized screen coordinates, and bounded
   strings.
5. `prompts.py` sends the validated field as part of the existing observation
   JSON and adds only the short usage rules above.

If the active camera is unavailable or the collector cannot safely describe an
object, that object is omitted. A collector failure returns an empty list and
must not prevent the rest of the observation from reaching the model.

## Verification

Godot tests cover:

- enabled Hint, door, NPC, and readable candidates;
- disabled candidates;
- camera-frustum filtering;
- wall occlusion;
- distance measured from player position to interaction point;
- ascending distance order and the five-object cap;
- normalized screen coordinates;
- forward/right/up and relative yaw conventions;
- absence of internal node names and readable content.

Python tests cover:

- a valid five-object observation;
- rejection of a sixth item;
- rejection of NaN, infinity, invalid coordinates, invalid actions, oversized
  strings, or extra fields;
- preservation of `nearby_interactables` in the model input;
- prompt guidance that does not weaken the current probe success condition.

Existing observation, action-schema, probe harness, and Lobby integration tests
must continue to pass.
