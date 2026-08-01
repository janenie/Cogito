# Conveyor Profit playable slice

This standalone Godot 4.7 scene is a playable management-game slice: sixteen ingredient plates circulate around a closed U-shaped conveyor while the player evaluates recipe profit and assembles food at the center tray.

Run the preview from the repository root:

```bash
godot --path . conveyor_profit/scenes/conveyor_profit_preview.tscn
```

## Controls and rules

- Left-click a moving ingredient to place it on the tray. The belt immediately replenishes the selected slot, so all sixteen positions remain occupied. The tray holds at most five ingredients; a sixth selection is rejected without changing it.
- Left-click **UNDO** to remove the last tray ingredient.
- Left-click **MAKE** to consume the tray. Exact recipes below their run quota earn the sale price. Invalid combinations and a third submission of the same valid recipe earn nothing but still pay every selected ingredient cost. Every make result consumes the window's only opportunity.
- The wall menu has two switchable pages with five bilingual full-name recipe cards each. Every card lists the complete ingredients, cost, sale price, and net profit.
- A run randomly chooses one of five authored campaigns. Each campaign contains ten ordered 60-second windows; only the sixteen plate positions are shuffled.
- Each recipe may succeed at most twice per run. The player must remember accepted receipts; the HUD does not publish a cumulative quota table.
- Net profit is revenue minus consumed ingredient cost. The final result succeeds at 80% or more of the hidden campaign-wide optimum computed with recipe quotas.

Every human click enters through the ingredient's real 3D hit area. The same standalone scene also contains an explicitly disabled-by-default AI Play controller. Start it with:

```bash
godot --path . conveyor_profit/scenes/conveyor_profit_preview.tscn \
  -- --ai-play --ai-play-scenario=conveyor_profit
```

The allowlisted MCP scenario exposes only the public briefing, screenshot/HUD observation, and four semantic actions: `select_ingredient`, `undo`, `make`, and `wait_next_window`. The briefing publishes the same ten fixed recipes shown on the wall, including ingredient costs, complete recipes, sale prices, net profits, and the two-success quota. AI selection chooses a currently visible matching plate through the same gameplay/economy path; a sixth selection returns `tray_full` without changing the tray, so the player can recover with `undo`. Accepted and quota-failed make results identify only the current attempted recipe, so the AI can maintain its own public-history count. The scenario does not expose the current structured ingredient inventory, authored campaign, candidate recipes, missing ingredients, cumulative recipe counts, campaign optimum, future windows, seed, or target amount. While the external model is deciding, Godot pauses the window clock. After a make locks a window, `wait_next_window` advances exactly one window without making the AI wait for wall-clock time.

The food visuals are selected from Kenney Food Kit 2.0 under CC0. See [SOURCE.md](assets/kenney_food_kit/SOURCE.md) for exact file mappings and [LICENSE.txt](assets/kenney_food_kit/LICENSE.txt) for the bundled license.
