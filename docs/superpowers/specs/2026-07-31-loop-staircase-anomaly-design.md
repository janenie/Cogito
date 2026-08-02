# Loop Staircase Anomaly Design

## Goal

Build a standalone Cogito demo scene for a looping stairwell reasoning task. The player climbs through ten stairwell floors across multiple loops, observes stable details and anomalies, reads clue notes, and selects the single true exit floor at the final terminal.

The first version should be small enough to implement and test reliably, but rich enough to evaluate long-term memory and reasoning in AI Play.

## Player Experience

The scene starts at a lower stairwell landing. The player climbs from 2F through 10F. Passing the top loop trigger returns the player to the 2F landing and advances the loop count. The layout remains recognizable, but some floor details change between loops.

The player must remember each floor's state across loops:

- floor sign number
- lamp color
- box count
- wall symbol
- clue note text

After the configured observation loops, a final terminal appears. The terminal asks the player to choose the true exit floor from 2F through 10F. Choosing the unique correct floor completes the task.

## Scope

Version 1 includes:

- One new standalone scene, separate from the existing lobby.
- Ten observable floors: 2F through 10F.
- Three observation loops.
- Seeded random puzzle generation.
- One true exit floor per run.
- Four clue rules per run.
- Three to four anomaly changes per loop, only on non-answer floors.
- A final answer terminal or exit door interaction.
- A clear success/failure result for future AI Play integration.

Version 1 does not include:

- Procedural geometry generation for arbitrary floor counts.
- Complex UI menus.
- Save/load persistence for puzzle state.
- Multiple simultaneous correct answers.
- Full AI Play scenario registration. The scene should remain AI Play-ready, but scenario registration is a follow-up after the playable prototype works.

## Scene Layout

The scene should use existing Cogito and Kenney/ksi assets where possible:

- `res://addons/cogito/PackedScenes/cogito_player.tscn`
- `res://addons/cogito/DemoScenes/DemoPrefabs/ksi_steps_single.tscn`
- `res://addons/cogito/DemoScenes/DemoPrefabs/ksi_steps_flat.tscn`
- `res://addons/cogito/DemoScenes/DemoPrefabs/ksi_wall_painted.tscn`
- existing boxes, plants, lights, readable notes, and door or terminal prefabs
- `res://addons/cogito/AIPlay/ai_play_controller.tscn` when AI Play support is added

The layout should prioritize legibility over visual complexity. Each floor should have a compact landing with clear sightlines to its sign, lamp, boxes, symbol, and optional clue note. The stairwell should be easy for a player or AI agent to navigate without getting stuck.

## Randomized Puzzle Model

Each run creates a puzzle from a seed. If no seed is configured, the scene can choose one automatically and expose it in debug output for reproduction.

Randomized values:

- `true_floor`: one floor from 2F through 10F.
- `exit_symbol`: one of circle, triangle, square, or star.
- `clue_floors`: four distinct floors that hold readable notes.
- `anomaly_floors`: non-answer floors selected per loop.
- `anomaly_types`: lamp color change, box count change, floor sign duplication, or symbol change.

Hard constraints:

- The true floor never receives an anomaly.
- The true floor satisfies every clue rule.
- Every incorrect candidate violates at least one clue rule by the final loop.
- The final answer is unique.
- The same seed produces the same puzzle.

If a generated puzzle does not satisfy these constraints, generation retries with the same seed stream until it finds a valid puzzle.

## Clue Rules

Version 1 uses four rule families:

- The true exit symbol is a specific symbol.
- The true floor's lamp color does not change across loops.
- The true floor's box count does not change across loops.
- Fake floors may duplicate another floor's sign number.

Clue note examples:

- `The true exit uses the star symbol.`
- `The true floor keeps the same lamp color.`
- `The true exit keeps the same number of boxes.`
- `A false floor may borrow another floor number.`

The exact clue text can be English for AI Play readability. If later needed, the notes can be localized.

## Loop State

The initial loop presents the baseline state for all floors. Later loops apply anomalies to non-answer floors. The player can complete the task after the final observation loop unlocks the terminal.

Recommended defaults:

- `floor_min = 2`
- `floor_max = 10`
- `total_loops = 3`
- `anomalies_per_loop = 3`
- `max_act_requests = 160` for AI Play

## Interactions

Readable clue notes should use existing Cogito readable interaction patterns if they are easy to instantiate. If that becomes too expensive, Version 1 can use simple interactable labels or static 3D text with collision prompts.

The final answer area should use repeated interaction objects, one per answer from 2F through 10F. This avoids building a custom terminal UI in Version 1 while still giving the player an explicit final choice.

Wrong answers immediately end the run with a failure result. They do not reset the loop in Version 1.

Result mapping:

- `success: correct_floor_selected`
- `failure: wrong_floor_selected`
- `failure: max_requests`

## AI Play Integration

The scene should be designed so AI observations can describe the relevant state:

- current loop number
- nearby floor sign
- visible lamp color
- visible symbol
- visible box count
- readable clue text when near a note
- terminal choices when near the final terminal

The future scenario id should be `loop_staircase_anomaly`.

Briefing should instruct the agent to observe all floors across loops, remember stable and changing details, read clue notes, and select the only floor that satisfies all rules.

## Testing

Focused tests should cover:

- seeded generation is deterministic
- generated puzzle has exactly one answer
- true floor is never anomalous
- final terminal reports success for the correct floor
- final terminal reports failure for an incorrect floor
- loop trigger advances loops and preserves puzzle state
- AI Play-readable state remains easy to expose later

Manual verification should cover:

- player can navigate from 2F through 10F
- top trigger loops back without trapping the player
- signs, symbols, lamps, and boxes are visually readable
- final terminal appears only after the required loops
- the correct answer can be inferred from displayed clues and anomalies

## Decisions

Resolved decisions:

- Use the mixed anomaly plus reasoning design.
- Use ten stairwell floors.
- Randomize each run with a reproducible seed.
- Keep the first implementation as a standalone scene.
- Wrong answers immediately fail the run.
- Keep full AI Play scenario registration as a follow-up.
- Use simple per-floor answer interactables instead of a custom terminal UI in Version 1.
