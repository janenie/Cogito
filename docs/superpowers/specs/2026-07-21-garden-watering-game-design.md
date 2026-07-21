# Garden Watering Game Design

## Objective

Create a standalone COGITO variant named `garden` in
`~/workspace/cogito_variants/garden`. The game is a bright, welcoming,
low-poly first-person garden-care game set in a compact residential block. A
successful day lasts about 38 real minutes. The player must care for three
different gardens in the required order, manage a finite-capacity watering can,
respond to a possible afternoon rainstorm, and finish every required task by
17:00.

The variant will start from the current `Phazorknight-Cogito` working tree and
will use a new Git branch named `garden`. Work in the variant must not mutate
the original checkout.

## Player Experience

The experience should feel calm and readable while retaining meaningful time
pressure. The player learns the neighborhood in the morning, plans routes
between gardens and the shared water tap, watches plants rather than relying on
exact numeric meters, and adapts to the afternoon weather.

The game is not a walking-time filler. Travel should support planning and
spatial memory while plant care, water management, observation, and weather
response provide most of the active play.

## Core Day

The playable day runs from 08:00 through 17:00. The target real duration is 38
minutes, so one real minute advances about 14.2 in-game minutes. The clock stops
while the game is paused.

The required task order is:

1. **08:00-10:00:** Collect the watering can and correctly water the sunflower
   garden.
2. **10:00-12:30:** Correctly complete the hydrangeas' first watering.
3. **12:30-14:30:** Inspect and moderately water the potted orchids.
4. **14:30:** Receive a diegetic and HUD weather forecast.
5. **15:00:** Begin rain when the run's 50 percent rain roll succeeds.
6. **15:00-about 15:45:** During rain, move all three orchids into their marked
   indoor positions, then return them to their outdoor stands after rain ends.
   During a dry run, inspect the orchids without moving them.
7. **About 15:45-16:30:** Correctly complete the hydrangeas' second watering.
8. **16:30-17:00:** Perform a final inspection.
9. **17:00:** Validate task order, timing, watering amounts, plant health, and
   orchid placement.

The day succeeds only when every required condition is satisfied. A key plant
reaching zero health ends the run immediately. An incomplete or incorrectly
ordered day fails at 17:00. Either failure restarts the day from 08:00.

## Plants

### Sunflowers

Sunflowers teach the watering interaction. They require one morning watering,
use about two seconds of continuous watering per plant, and have the widest safe
moisture range. Missing the morning deadline or severely overwatering them can
still kill the group.

### Hydrangeas

Hydrangeas consume water fastest. They require a morning and an afternoon
watering, with about four seconds per plant per session. Their moisture decays
faster than the sunflowers, making route planning and refilling important.

### Potted Orchids

The three orchids require about three seconds of watering each and tolerate
only a moderate moisture range. They are vulnerable to direct rain. When rain
occurs, all three must occupy marked positions inside the third house; after
rain, all three must return to their assigned outdoor stands. Remaining in rain
damages them and can end the run.

## Plant Feedback and Fairness

Plants track continuous moisture and health rather than simple interaction
counts. Too little or too much water reduces health after a readable warning
period. The game does not expose exact moisture numbers during normal play.

Feedback includes:

- soil color for dry, safe, and saturated states;
- leaf pose or color changes as health deteriorates;
- short contextual labels such as `Dry`, `Healthy`, and `Too wet`;
- an audible warning before a plant reaches a fatal state;
- task reminders before watering windows close.

Timing windows must have generous margins and must not require second-perfect
execution.

## Watering Can and Refill Loop

The watering can is an equipped COGITO wieldable with finite capacity. It
reuses `WieldableItemPD.charge_max`, `charge_current`, the existing wieldable
HUD, inventory persistence, and input pipeline.

Holding the primary wieldable action:

1. tilts or animates the can;
2. emits water particles and audio;
3. drains charge continuously;
4. adds moisture only to a valid plant in range;
5. stops when released, empty, or no valid target remains.

An empty can cannot water and provides a clear hint. A shared tap near the
center of the block refills the can through a short hold interaction. Refill
progress stops if the player moves away. Initial tuning targets a 100-unit can,
but final drain and capacity values must be set through playtesting so that the
player needs several intentional refills without constant busywork.

## Neighborhood Layout

The playable block is approximately 75 by 55 meters. It contains a player
start/tool room, a main residential road, three visually distinct houses, three
gardens, and a central water tap.

Each house has one enterable room and one attached garden. Houses use different
wall colors, fences, and landmark props for navigation. The first two rooms
primarily contain decoration and task context. The third room contains three
clearly marked orchid positions.

The main route layout is:

```text
             North road
 +--------------+--------------+--------------+
 | House 1      | House 2      | House 3      |
 | Sunflowers   | Hydrangeas   | Orchids      |
 |              |              | Indoor spots |
 +------+-------+------+-------+------+-------+
        |              |              |
        |       Shared water tap      |
        |          and bench          |
 =======+==============+==============+=======
                  Main street
              Player tool room
```

Garden side gates may provide short return routes after being opened from
inside. Trees, lights, mailboxes, benches, hedges, fences, paths, and small
water features establish the low-poly neighborhood without obscuring task
landmarks.

## Movement and Travel Budget

The packed COGITO player uses a walking speed of 4 meters per second and a
sprinting speed of 7 meters per second. Level dimensions must be derived from
those values.

| Route | Target distance | Walk target | Sprint target |
| --- | ---: | ---: | ---: |
| Start to Garden 1 | 35-45 m | 9-12 s | 5-7 s |
| Adjacent gardens | 20-28 m | 5-7 s | 3-4 s |
| Garden to tap | 12-20 m | 3-5 s | 2-3 s |
| Orchid stand to indoor spot | 12-16 m | 3-4 s | Sprint disabled while carrying |
| Start to farthest garden | 50-60 m | 13-16 s | 7-9 s |
| Full block loop | 150-180 m | 38-45 s | 22-26 s |

A graybox validation run must time at least four representative routes. Shrink
the layout when adjacent gardens take more than eight seconds to walk between
or the farthest garden takes more than eighteen seconds to reach.

The approximate day budget is 5-7 minutes of travel, 8-10 minutes of watering
and observation, 4-6 minutes of orchid/weather handling, 5-7 minutes of task
reading and initial exploration, and 8-10 minutes of scheduled rechecking and
planning.

## Weather

The run chooses its rain outcome once, at the start of a fresh day, using a 50
percent probability. Reloading a voluntary-exit save must preserve the existing
outcome rather than reroll it.

At 14:30 the game signals the outcome without exposing the random roll:

- a rain run darkens the sky, raises wind audio, moves foliage, and displays a
  warning to check rain-sensitive plants;
- a dry run shows clouds dispersing and reports that afternoon rain is
  unlikely.

Rain starts at 15:00 and lasts a tuned two to three real minutes, corresponding
to roughly 28-43 in-game minutes. Rain uses
particles, audio, lighting changes, and wet ground treatment. Outdoor orchids
receive rain moisture and health damage; indoor orchids do not.

## Task Guidance and UI

No NPCs are required. A garden quest controller provides sequential objectives,
deadline warnings, weather tasks, and the 17:00 result. The start room contains
the day's care list, and each garden has concise contextual instructions.

HUD additions are limited to:

- current in-game time;
- current objective and deadline;
- watering-can capacity;
- contextual plant condition;
- weather warnings;
- success and failure presentation.

The HUD must not reveal exact hidden moisture or health values during normal
play.

## Save, Resume, and Restart

Automatic resume points exist only to support voluntary exit and later
continuation. Saved state includes time, weather outcome and phase, plant
moisture and health, completed task sequence, watering-can charge, orchid
positions, and current objective.

Immediate plant death or a failed 17:00 evaluation invalidates the day's resume
state. Selecting retry starts a fresh 08:00 day with reset plants, tasks,
positions, and a new weather roll.

## Components

- `GardenGameManager`: lifecycle, completion, failure, retry, and 17:00
  evaluation.
- `GardenTimeSystem`: compressed clock and scheduled time events.
- `GardenWeatherSystem`: persistent per-run weather roll, warning, rain phases,
  and environmental presentation.
- `GardenPlant`: moisture, health, watering response, feedback, and death.
- `GardenPlantGroup`: garden-level requirements and completion state.
- `GardenWateringCan`: wieldable behavior, ray/area targeting, water effects,
  and continuous charge drain.
- `GardenRefillStation`: validated hold-to-refill interaction.
- `PortableOrchid`: carryable plant plus indoor/outdoor placement state.
- `GardenQuestController`: ordered objectives and deadline transitions.
- `GardenSaveManager`: voluntary-exit persistence and failure invalidation.

Components communicate through signals and narrow typed methods. Plant scripts
must not own global time or quest progression, and the quest controller must
not directly manipulate player input.

## Art and Asset Direction

Use a bright, friendly low-poly style. The first implementation may use COGITO
assets, existing Kenney assets, procedural graybox geometry, and clearly
licensed CC0 packs. Imported third-party assets must retain license and credit
records. Visual consistency takes priority over mixing high-detail realistic
plants into the low-poly environment.

The existing `GardenTest` remains a reference prototype. Production content
should be organized as reusable scenes rather than growing one monolithic scene
file.

## Implementation Strategy

Use vertical slices:

1. Build and verify one sunflower garden, the finite watering can, central tap,
   plant feedback, clock, and failure/retry path.
2. Expand to the complete graybox neighborhood and validate route timings.
3. Add hydrangea schedules and ordered quest progression.
4. Add orchids, indoor/outdoor placement, rain, and weather presentation.
5. Add voluntary-exit persistence and 17:00 evaluation.
6. Perform the low-poly art pass, audio pass, balancing, and full-day playtest.

## Verification

Automated tests cover:

- watering-can drain, empty behavior, and refill;
- moisture gain and dry/overwater health loss;
- distinct plant tuning and watering windows;
- deterministic testing of rain and dry outcomes;
- 14:30 forecast and 15:00 weather transition;
- indoor/outdoor orchid detection and rain protection;
- ordered task progression and invalid ordering;
- immediate plant-death failure;
- 17:00 success and incomplete-day failure;
- voluntary-exit save restoration and failure-state invalidation;
- pause behavior for time and plant simulation.

Manual acceptance verifies:

- all representative walking routes meet the travel budget;
- a successful first-time run lasts more than 30 minutes, targeting 38;
- the entire day is completable at walking speed without requiring sprinting;
- warnings are visible and audible before irreversible failure;
- both rain and dry runs are completable;
- the player can understand all required actions without an NPC;
- no failure checkpoint can be exploited to avoid restarting the day.

## Out of Scope for the First Playable Version

- conversational NPCs;
- multiple neighborhoods or seasons;
- gardening economy, shops, or character progression;
- procedural house layouts;
- multiplayer;
- combat;
- additional weather types beyond dry and rain;
- mobile or console-specific optimization.
