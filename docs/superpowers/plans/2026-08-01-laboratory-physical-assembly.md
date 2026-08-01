# Laboratory Physical Assembly Implementation Plan

**Goal:** Convert the Laboratory experiment from button selection to physical candidate search and four-slot assembly.

1. Add failing manager and scene contracts for a treatment slot, four-slot readiness, physical candidates, randomized anchors, and Chinese startup HUD.
2. Implement configurable carryable experiment components and typed snap slots using existing Cogito interactions.
3. Spawn candidate sets deterministically, connect slots to the manager, and remove direct selection controls.
4. Update HUD and task text for search, carry, assemble, and validate behavior.
5. Run Laboratory tests, full Godot import, `git diff --check`, and launch the scene for playtesting.
