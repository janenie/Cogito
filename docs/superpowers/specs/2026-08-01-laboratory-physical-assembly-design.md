# Laboratory Physical Assembly Design

## Goal

Replace the button-only Laboratory setup with a physical search, carry, assemble, and validate loop while preserving the three-attempt deduction puzzle and AI Play action surface.

## Player Loop

The Chinese HUD is visible immediately and exposes the public objective, environment, safe ranges, clues, and remaining attempts. The player searches two nearby laboratory zones for three batteries, three samples, three treatment modules, and one connector. Candidates spawn at deterministic shuffled anchors.

The player carries one object at a time with Cogito's existing `interact2` interaction. Returning to the start bench, the player moves each object into its matching battery, sample, treatment, or connector slot. A slot automatically aligns and freezes a matching carried object. Picking the object up again removes it from the setup.

Returning the fourth material to the start bench automatically runs the analysis without requiring the player to aim at another control. A wrong setup remains assembled and publishes bounded current, stability, temperature, and lamp measurements. Replacing one component completes the setup again and automatically starts the next attempt. The third correct analysis succeeds before exhaustion; the third wrong analysis fails.

## Architecture

- `laboratory_experiment_component.gd/.tscn`: one configurable physical candidate using the existing Cogito carry interaction.
- `laboratory_experiment_slot.gd`: scene-local typed snap slot that records the exact public component label without modifying shared Cogito snap behavior.
- `laboratory_experiment_station.gd`: deterministic candidate spawning, slot-to-manager synchronization, HUD updates, and automatic validation.
- `laboratory_experiment_manager.gd`: adds treatment-module installation and keeps hidden profile mappings out of public state.

All required actions remain `interact` or `interact2`. Hidden mappings and unexecuted outcomes remain unavailable to observations and briefing.

## Verification

Godot tests cover deterministic candidate placement, four-slot completeness, physical slot replacement, Chinese HUD startup content, and the existing unique-solution and three-attempt behavior.
