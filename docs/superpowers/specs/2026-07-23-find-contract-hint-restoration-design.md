# Find Contract Hint Restoration Design

## Goal

Restore the five puzzle-specific `ReadableComponent` overrides that were
introduced in commit `0ebcacde` and later removed in commit `52e40bc8`.
Remove unrelated Cogito tutorial markers from the playable Lobby without
changing any puzzle text or newer AI Play integration.

## Puzzle hints to preserve

The following nodes remain visible, processed, and interactable:

- `DEMO_HINTS/Hint_01_Welcome`
- `CUBICLE_AREA/FindContract_ComputerRecord`
- `MEETING_ROOM/FindContract_AuditRecord`
- `UPPER_OFFICE_CEO/FindContract_CeoContract`
- `ARCHIVE/FindContract_ArchiveDecoyBox`

Their `ReadableComponent` title, content, and interaction text are restored
verbatim from commit `0ebcacde`.

## Tutorial hints to hide

The following unrelated demo tutorial nodes are hidden and disabled:

- `Hint_02_LampSwitch`
- `Hint_03_AdvancedSwitch`
- `Hint_04_Breakroom`
- `Hint_05_Platform`
- `Hint_06_AdvancedDoors`
- `Hint_07_Keypad`
- `Hint_08_Sittable_Static`
- `Hint_09_Sittable_Auto`
- `Hint_10_Sittable_Physics`
- `Hint_11_Sittable_Vehicle`

Each node receives:

- `visible = false`
- `process_mode = 4` (`PROCESS_MODE_DISABLED`)
- `collision_layer = 0`
- `collision_mask = 0`

This prevents rendering, processing, physics-query hits, and interaction while
leaving the original tutorial text in the scene for future manual restoration.

## Non-goals

- Do not change the puzzle wording, password, NPC dialogue, node transforms, or
  clue order.
- Do not restore the entire historical Lobby scene.
- Do not change AI prompts, harness behavior, or model configuration.
- Do not delete any Hint nodes.

## Verification

The Lobby scene check must assert that:

1. All five puzzle nodes have their expected historical titles and interaction
   text.
2. Puzzle nodes are not hidden or disabled.
3. All ten unrelated tutorial nodes are hidden, processing-disabled, and
   removed from collision queries.
4. Godot loads the Lobby and completes the existing AI Play Lobby integration
   test.
5. `git diff --check` reports no whitespace errors.
