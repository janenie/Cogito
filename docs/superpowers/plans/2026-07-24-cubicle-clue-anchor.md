# CUBICLE AREA Clue Anchor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the CUBICLE AREA clue from floor height to the player-facing right side of the desk.

**Architecture:** Keep the existing single `FindContractAnchor` and runtime reparenting flow. Encode the desk-top position and flat document orientation in the anchor transform so either movable clue uses the same visible placement.

**Tech Stack:** Godot 4.7 scene resources, Bash static checks, GDScript headless integration test.

## Global Constraints

- Modify only the clue anchor placement and its static regression assertion.
- Keep route selection, randomized content, rereading, and progress behavior unchanged.
- Preserve existing scene node names and NodePaths.

---

### Task 1: Move the CUBICLE AREA clue anchor

**Files:**
- Modify: `tests/check_ai_play_lobby.sh`
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`

**Interfaces:**
- Consumes: `TerminalMonitor.cubicle_anchor` NodePath pointing to `CUBICLE_AREA/FindContractAnchor`.
- Produces: A fixed desk-top transform used by `_reparent_to_anchor()` for either movable clue.

- [ ] **Step 1: Add the failing static assertion**

Add this check after the existing CUBICLE AREA anchor-node assertion:

```bash
grep -A1 'name="FindContractAnchor" type="Marker3D" parent="CUBICLE_AREA"' "$scene" \
	| grep -q 'transform = Transform3D(0, 1, 0, -1, 0, 0, 0, 0, 1, 7.15, 0.79, -0.55)'
```

- [ ] **Step 2: Verify the assertion fails against the floor-height anchor**

Run:

```bash
bash tests/check_ai_play_lobby.sh
```

Expected: exit code `1` because the current transform ends with
`7.61602, 0.05, -0.41817`.

- [ ] **Step 3: Move and orient the anchor**

Set the scene node to:

```text
[node name="FindContractAnchor" type="Marker3D" parent="CUBICLE_AREA" unique_id=1331940285]
transform = Transform3D(0, 1, 0, -1, 0, 0, 0, 0, 1, 7.15, 0.79, -0.55)
```

The position puts the clue on the desk’s player-facing right side. The basis matches the existing flat document placement rather than leaving the clue upright.

- [ ] **Step 4: Run affected verification**

Run:

```bash
bash tests/check_ai_play_lobby.sh
godot --headless --log-file /tmp/cogito_cubicle_anchor.log --path . --script tests/ai_play/test_ai_play_lobby_game_over.gd
git diff --check
```

Expected: all three commands exit `0`; the Godot test prints
`AIPlay Lobby game-over integration test passed`.

- [ ] **Step 5: Restart the ordinary Lobby for visual inspection**

Stop the currently running ordinary Lobby and launch:

```bash
godot --path . --log-file /tmp/cogito_cubicle_anchor_manual.log addons/cogito/DemoScenes/COGITO_3_Lobby.tscn
```

Expected: the Lobby opens with `auto_start=false`, and the CUBICLE AREA clue is visible and interactable on the right side of the desk.
