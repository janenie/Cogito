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
- The wall menu has two switchable pages with five bilingual full-name recipe cards each. Every card lists the complete ingredients and fixed cost; its sale price and net profit refresh from the current category-demand multiplier.
- A run chooses one of five authored ten-window market campaigns. Every 60-second window defines three physically closed candidate recipes, then safely randomizes filler-food quantities and all sixteen plate positions without enabling a fourth recipe.
- The HUD publishes exact current multipliers for salad, soup, burger, omelet, and sandwich. Windows one through nine also publish two natural-language signals about the next window; the signals can reinforce or conflict. Window ten has no future signal.
- Each recipe may succeed at most twice per run. The player must remember accepted receipts; the HUD does not publish a cumulative quota table.
- Net profit is adjusted revenue minus fixed ingredient cost. Adjusted sale prices use `floor(base_sale_price * multiplier + 0.5)`. The final result succeeds at 90% or more of an authored online baseline that uses current evidence, one-window lookahead, and remembered recipe counts. A full omniscient dynamic-programming result remains developer-only and never decides success.

Every human click enters through the ingredient's real 3D hit area. The same standalone scene also contains an explicitly disabled-by-default AI Play controller. Start it with:

```bash
godot --path . conveyor_profit/scenes/conveyor_profit_preview.tscn \
  -- --ai-play --ai-play-scenario=conveyor_profit
```

The allowlisted MCP scenario exposes only the public briefing, screenshot/HUD observation, and three semantic actions: `select_ingredient`, `make`, and `wait_next_window`. The briefing publishes the same ten fixed recipes shown on the wall, including ingredient costs, complete recipes, base prices, base profits, category IDs, and the two-success quota. Each observation adds only the five exact current multipliers and this window's two public signals. AI selection chooses a currently visible matching plate through the same gameplay/economy path. A selected ingredient cannot be returned: a wrong selection must be submitted with `make`, consuming the tray and locking the window as an invalid combination. Any unsubmitted tray also expires and is charged at the window boundary. A sixth selection returns `tray_full` without changing the five-item tray, which must then be submitted. Accepted and quota-failed make results identify only the current attempted recipe, so the AI can maintain its own public-history count. The scenario does not expose the current structured ingredient inventory, campaign ID, candidate recipes, missing ingredients, cumulative recipe counts, baseline route or total, omniscient result, future market/supply, draw index, seed, or target amount. While the external model is deciding, Godot pauses the window clock. After a make locks a window, `wait_next_window` advances exactly one window without making the AI wait for wall-clock time.

The trusted supervisor passes logical conveyor attempts a nonnegative `--conveyor-draw-index=N`. A seeded five-item permutation guarantees five different campaigns before cycling; infrastructure retries reuse the same index and therefore the same campaign. Manual restarts in one Godot process use a private process-local counter. The draw index is trusted infrastructure state and is absent from the briefing, observation, action results, and player HUD.

The food visuals are selected from Kenney Food Kit 2.0 under CC0. See [SOURCE.md](assets/kenney_food_kit/SOURCE.md) for exact file mappings and [LICENSE.txt](assets/kenney_food_kit/LICENSE.txt) for the bundled license.
