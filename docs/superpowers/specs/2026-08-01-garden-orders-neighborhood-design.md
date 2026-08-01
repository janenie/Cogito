# Garden Orders Neighborhood Scene Design

## Goal

Create a new, independently playable Godot scene for the garden-order game. The scene presents ten numbered suburban homes around a central spawn and tool area, giving later order, travel-time, and resource systems a stable spatial foundation.

## Scope

This slice builds the neighborhood only:

- a new scene separate from `garden/scenes/garden_vertical_slice.tscn`;
- ten numbered houses, each with a visible garden;
- small, medium, and large garden variants distributed across the ten lots;
- a central tool area and player spawn;
- a slightly elevated third-person player camera;
- a ring road, radial footpaths, ground, lighting, collision, and destination markers;
- placeholder displays for a watering can, shovel, fertilizer spreader, and two fertilizer bags;
- headless structural tests and an engine parse/import check.

The slice does not implement order publication, income, deadlines, work progress, material consumption, tool selection, AI commands, or automatic travel. Those systems will use the scene anchors in a later slice.

## Scene Architecture

The entry scene will be `garden/scenes/garden_orders_neighborhood.tscn`. It will own the environment, ground, roads, central plaza, ten lot instances, route markers, player, and lightweight HUD hint.

Reusable geometry will be split into focused packed scenes:

- `garden/scenes/components/garden_order_house.tscn` represents one house, its numbered sign, garden beds, fence, collision, and destination marker.
- `garden/scenes/components/garden_order_tool_area.tscn` represents the central tool shelter, visible tool placeholders, fertilizer stock, collision, and tool-area marker.
- `garden/scenes/components/garden_order_third_person_player.tscn` provides a basic character body, collision capsule, mesh, spring-arm camera, walking, sprinting, and mouse orbit.

The neighborhood scene places ten house instances explicitly around a ring. Explicit placement keeps addresses deterministic and inspectable in the editor. A small configuration script on each house exposes `house_number`, `garden_size`, and house accent color, and updates its label and garden scale without coupling it to future order state.

## Layout

The tool plaza sits at world origin. The player starts on the plaza facing the northern path. Ten houses form a wide ring around it, numbered clockwise from House 1. Each lot faces inward so the number sign, entrance, garden, and destination marker are visible from the ring road.

Four radial paths connect the tool plaza to the ring road. The road and paths use simple project-native meshes and materials. This creates readable travel geography without adding an external asset dependency or baking hidden shortest-path data into runtime AI observations.

Garden sizes are distributed as follows:

- small: Houses 1, 4, 7, and 10;
- medium: Houses 2, 5, and 8;
- large: Houses 3, 6, and 9.

## Existing Asset Use

No asset download is required. The scene will reuse resources already tracked in the repository:

- Kenney Furniture plant GLBs for garden vegetation;
- the existing outdoor HDR panorama for sky lighting;
- project-native primitive meshes and materials for house shells, roofs, roads, fences, garden beds, and tool placeholders.

The repository does not currently contain the complete Kenney Suburban or Kenney Nature packs. The first slice therefore keeps its forms deliberately low-poly and compatible with swapping those assets in later.

## Player and Camera

The player is a simple third-person `CharacterBody3D`, independent of the old first-person garden player. A `SpringArm3D` holds the camera above and behind the avatar, handles obstruction, and permits mouse orbit. Keyboard movement remains relative to the camera; sprint increases movement speed. Escape releases captured mouse input.

This player is for human scene inspection only. It does not expose low-level movement as an AI gameplay contract. Future AI play will issue high-level destination commands and let a separate travel system move the character.

## Collision and Anchors

Ground, house bodies, fences, and the tool shelter have static collision. The player has a capsule collision and must start above walkable ground without intersecting scenery.

Stable nodes provide future integration points:

- `CentralToolArea/Destination` for returning to the tool zone;
- `Houses/House01` through `Houses/House10` for deterministic addresses;
- one `Destination` marker and one `GardenWorkPoint` marker inside each house instance;
- `PlayerSpawn` at the center plaza.

These names are developer-facing structure. They must not be added to runtime AI briefings or observations.

## Presentation

The visual target is a clean, colorful low-poly prototype rather than a finished suburban art pass. Each house gets a distinct accent within a restrained palette. Garden sizes are legible through bed footprint and plant count. Large floating house-number signs make destinations readable while walking.

A minimal HUD identifies the scene as the garden-order neighborhood and lists movement controls. It does not display future orders, optimal routes, hidden timing, or any facts from `game_script/`.

## Testing and Validation

A new headless scene test will load and instantiate the neighborhood, then verify:

- the scene has exactly ten addressable house nodes;
- house numbers are unique and cover 1 through 10;
- the configured small, medium, and large garden counts are 4, 3, and 3;
- the central tool area, player spawn, player, roads, and HUD exist;
- each house has a destination marker, garden work point, visible label, and collision;
- the tool area exposes four tool/material display groups and collision;
- the third-person player contains a spring arm, camera, mesh, and capsule collision;
- the player starts close to the world center.

After the focused test passes, run the affected garden test suite, `godot --headless --path . --editor --quit`, and `git diff --check`. The old `garden_vertical_slice.tscn` and its tests must remain unchanged and passing.

## Safety and Privacy Boundaries

The new scene does not auto-start AI play and does not change the Lobby entry point. No runtime system reads `game_script/garden_orders.md`. The scene exposes only visual neighborhood content; future AI observation and briefing changes require their own explicitly reviewed slice and must preserve the repository's AI First Play whitelist and stop-safety rules.
