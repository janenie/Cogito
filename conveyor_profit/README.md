# Conveyor Profit playable slice

This standalone Godot 4.7 scene is a playable management-game slice: sixteen ingredient plates circulate around a closed U-shaped conveyor while the player evaluates recipe profit and assembles food at the center tray.

Run the preview from the repository root:

```bash
godot --path . conveyor_profit/scenes/conveyor_profit_preview.tscn
```

## Controls and rules

- Left-click a moving ingredient to place it on the tray. The belt immediately replenishes the selected slot, so all sixteen positions remain occupied. The tray holds at most four ingredients, matching the largest public recipe.
- Left-click **UNDO** to remove the last tray ingredient.
- Left-click **MAKE** to consume the tray. Exact recipes earn their sale price; invalid combinations earn nothing but still pay every selected ingredient cost. Either result consumes the window's only make opportunity.
- The wall menu uses six bilingual full-name recipe stickers, so no ingredient abbreviations need to be memorized.
- A run contains ten 60-second windows. Each window's sixteen plates support exactly two distinct recipes with unequal net profit and no third recipe type.
- Net profit is revenue minus consumed ingredient cost. The final result succeeds at 80% or more of the hidden theoretical maximum across all ten windows.
- The default seed is `1337`. The constrained window generator is deterministic for a fixed seed.

Every human click enters through the ingredient's real 3D hit area. The same standalone scene also contains an explicitly disabled-by-default AI Play controller. Start it with:

```bash
godot --path . conveyor_profit/scenes/conveyor_profit_preview.tscn \
  -- --ai-play --ai-play-scenario=conveyor_profit
```

The allowlisted MCP scenario exposes only the public briefing, screenshot/HUD observation, and four semantic actions: `select_ingredient`, `undo`, `make`, and `wait_next_window`. The briefing publishes the same six fixed recipes shown on the wall, including their ingredient lists, sale prices, and net profits. AI selection chooses a currently visible matching plate through the same gameplay/economy path; a fifth selection returns `tray_full` without changing the tray, so the player can recover with `undo`. The scenario does not expose the current structured ingredient inventory, supply generation, candidate recipes, per-window optimum, future windows, seed, or target amount. While the external model is deciding, Godot pauses the window clock. After a make locks a window, `wait_next_window` advances exactly one window without making the AI wait for wall-clock time.

The food visuals are selected from Kenney Food Kit 2.0 under CC0. See [SOURCE.md](assets/kenney_food_kit/SOURCE.md) for exact file mappings and [LICENSE.txt](assets/kenney_food_kit/LICENSE.txt) for the bundled license.
