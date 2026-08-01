# Garden Route Signs and Garden Sizes Design

## Goal

Make travel costs complete and visible in the neighborhood scene, and make small, medium, and large gardens distinguishable without guessing from subtle plant differences.

## Scope

This slice adds public visual information only. Walking does not advance or deduct game time yet. A later travel system will consume the same route-cost rules when high-level destination movement is implemented.

## Travel-Cost Display

The central tool plaza receives a Chinese route-rules board with the complete deterministic cost model:

- `工具区 → 任意住宅：10 分钟`;
- `相隔 1 栋：5 分钟`;
- `相隔 2 栋：10 分钟`;
- `相隔 3 栋：15 分钟`;
- `相隔 4–5 栋：20 分钟`.

Each of the ten ring-road segments between adjacent houses also displays `步行 5 分钟`. The signs face the neighborhood center, use outlined Chinese `Label3D` text, and have depth testing disabled so the road or landscaping cannot hide them.

The rule board and road signs contain only public gameplay rules. They do not expose future orders, optimal routes, hidden state, or anything from `game_script/`.

## Garden Distribution

The ten addresses use this fixed distribution:

- large: Houses 3 and 6;
- medium: Houses 2, 5, and 8;
- small: Houses 1, 4, 7, 9, and 10.

This yields exactly two large, three medium, and five small gardens.

## Visual Size Language

Every garden receives a player-facing Chinese size label using the format `<house number>号 · <size>型花园`, for example `3号 · 大型花园`.

The soil-bed footprint and plant layout use deliberately separated scales:

- small: approximately 4 metres wide, 3 visible plants;
- medium: approximately 7 metres wide, 5 visible plants;
- large: approximately 10 metres wide, 7 visible plants.

The labels use a consistent size color: green for small, amber for medium, and orange-red for large. Existing address labels remain visible, and removed perimeter fences do not return.

## Structure

The reusable house component continues to own `house_number` and `garden_size`. Its refresh method updates the soil footprint, visible plant count, and new `Garden/SizeLabel` text and color. This keeps all ten instances consistent and avoids duplicate per-house logic.

The neighborhood scene owns the central route-rules board and ten road labels because travel presentation belongs to the map composition rather than an individual house.

## Validation

Headless tests will instantiate the real scenes and verify:

- the house component renders the correct Chinese label for each size;
- small, medium, and large soil widths are strictly increasing and materially separated;
- the full neighborhood contains exactly five small, three medium, and two large gardens at the approved addresses;
- the central rule board exposes all five route rules;
- exactly ten adjacent-road signs display `步行 5 分钟`;
- garden perimeter fences remain absent.

Run the full garden test suite, Godot editor import check, `git diff --check`, and local spawn/overview screenshots. Restart the running neighborhood window after validation.
