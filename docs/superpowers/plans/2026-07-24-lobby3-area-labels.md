# Lobby 3 Area Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fixed `LOBBY 1`, `LOBBY 2`, `MEETING ROOM`, `TOILET 1`, and `TOILET 2` signs to Lobby 3.

**Architecture:** Add five `Label3D` children directly to the scene objects they identify, so each sign inherits the correct object/entrance orientation. Reuse the existing Montserrat font resource and the established outline treatment used by other Lobby 3 area signs.

**Tech Stack:** Godot 4.7 scene resources (`.tscn`), `Label3D`, Bash static scene checks.

## Global Constraints

- Modify `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`; do not rename existing scene nodes.
- Labels remain fixed in world space and do not rotate to follow the player.
- This change must not alter collision, interaction, or AI Play behavior.
- Preserve all unrelated changes already present in the working tree.

---

### Task 1: Add and verify the five area labels

**Files:**
- Create: `tests/check_lobby3_area_labels.sh`
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`

**Interfaces:**
- Consumes: Existing font `ExtResource("12_72tca")` and the Lobby 3 scene nodes `ENTRANCE_AREA/loungeDesignSofa`, `ENTRANCE_AREA/loungeDesignSofa2`, `MEETING_ROOM/ConferenceDoor`, `BATHROOM_STALL/wallDoorway2`, and `BATHROOM_STALL2/wallDoorway2`.
- Produces: Five fixed `Label3D` nodes named `Label_Lobby1`, `Label_Lobby2`, `Label_MeetingRoom`, `Label_Toilet1`, and `Label_Toilet2`.

- [ ] **Step 1: Write the failing static scene test**

Create `tests/check_lobby3_area_labels.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

scene="addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"

assert_label() {
	local name="$1"
	local parent="$2"
	local text="$3"
	local block
	block="$(awk -v name="$name" '
		/^\[node / {
			if (capture) exit
			capture = ($0 ~ ("name=\"" name "\""))
		}
		capture { print }
	' "$scene")"
	grep -Fq "type=\"Label3D\" parent=\"$parent\"" <<<"$block"
	grep -Fqx "text = \"$text\"" <<<"$block"
	grep -Fqx 'font = ExtResource("12_72tca")' <<<"$block"
	grep -Fqx 'outline_size = 10' <<<"$block"
}

assert_label "Label_Lobby1" "ENTRANCE_AREA/loungeDesignSofa" "LOBBY 1"
assert_label "Label_Lobby2" "ENTRANCE_AREA/loungeDesignSofa2" "LOBBY 2"
assert_label "Label_MeetingRoom" "MEETING_ROOM/ConferenceDoor" "MEETING ROOM"
assert_label "Label_Toilet1" "BATHROOM_STALL/wallDoorway2" "TOILET 1"
assert_label "Label_Toilet2" "BATHROOM_STALL2/wallDoorway2" "TOILET 2"
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
bash tests/check_lobby3_area_labels.sh
```

Expected: non-zero exit status because `Label_Lobby1` and the other new nodes do not exist.

- [ ] **Step 3: Add the five `Label3D` nodes**

Add these scene blocks beside their corresponding parent objects in
`COGITO_3_Lobby.tscn`:

```text
[node name="Label_Lobby1" type="Label3D" parent="ENTRANCE_AREA/loungeDesignSofa"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 1.12, 1.35, 0)
text = "LOBBY 1"
font = ExtResource("12_72tca")
font_size = 64
outline_size = 10

[node name="Label_Lobby2" type="Label3D" parent="ENTRANCE_AREA/loungeDesignSofa2"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 1.12, 1.35, 0)
text = "LOBBY 2"
font = ExtResource("12_72tca")
font_size = 64
outline_size = 10

[node name="Label_MeetingRoom" type="Label3D" parent="MEETING_ROOM/ConferenceDoor"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0.425, 2.3, 0)
text = "MEETING ROOM"
font = ExtResource("12_72tca")
font_size = 64
outline_size = 10

[node name="Label_Toilet1" type="Label3D" parent="BATHROOM_STALL/wallDoorway2"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 1.87, 2.25, 0)
text = "TOILET 1"
font = ExtResource("12_72tca")
font_size = 64
outline_size = 10

[node name="Label_Toilet2" type="Label3D" parent="BATHROOM_STALL2/wallDoorway2"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0.9, 2.25, 0)
text = "TOILET 2"
font = ExtResource("12_72tca")
font_size = 64
outline_size = 10
```

- [ ] **Step 4: Run static and engine verification**

Run:

```bash
bash tests/check_lobby3_area_labels.sh
godot --headless --path . --editor --quit
git diff --check
```

Expected: all commands exit with status `0`; Godot reports no parse error for
`COGITO_3_Lobby.tscn`.

- [ ] **Step 5: Inspect the placement in a normal Lobby 3 run**

Run:

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn
```

Expected: both lobby signs float above their corresponding sofas, the meeting
room sign is centered above its entrance, and both toilet signs are centered
above their respective entrances. None of the labels follows the camera.

- [ ] **Step 6: Commit only the area-label implementation**

```bash
git add addons/cogito/DemoScenes/COGITO_3_Lobby.tscn tests/check_lobby3_area_labels.sh
git commit -m "feat: label Lobby 3 areas"
```
