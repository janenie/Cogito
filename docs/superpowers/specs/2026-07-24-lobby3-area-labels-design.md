# Lobby 3 Area Labels Design

## Goal

Add five clear English area labels to `COGITO_3_Lobby.tscn` so players can
identify the two lobby seating areas, meeting room, and two toilets.

## Labels and placement

- `LOBBY 1` floats above `ENTRANCE_AREA/loungeDesignSofa`.
- `LOBBY 2` floats above `ENTRANCE_AREA/loungeDesignSofa2`.
- `MEETING ROOM` is fixed above the meeting-room entrance.
- `TOILET 1` is fixed above the first bathroom entrance.
- `TOILET 2` is fixed above the second bathroom entrance.

## Visual treatment

Each sign is a `Label3D` node in `COGITO_3_Lobby.tscn`. The labels reuse the
font, sizing, and outline treatment of existing area signs such as `ARCHIVE`
and `BREAK ROOM`. They remain fixed in world space and do not rotate to follow
the player.

## Scope

This change only adds visual labels. It does not rename existing scene nodes,
change collision or interaction behavior, or modify AI Play behavior.

## Verification

- Load `COGITO_3_Lobby.tscn` successfully in Godot.
- Confirm all five `Label3D` nodes and their exact text exist.
- Check the labels visually from the normal player approach direction.
- Run `git diff --check`.
