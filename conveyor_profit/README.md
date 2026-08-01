# Conveyor Profit playable slice

This standalone Godot 4.7 scene is a playable management-game slice: sixteen ingredient plates circulate around a closed U-shaped conveyor while the player evaluates recipe profit and assembles food at the center tray.

Run the preview from the repository root:

```bash
godot --path . conveyor_profit/scenes/conveyor_profit_preview.tscn
```

## Controls and rules

- Left-click a moving ingredient to place it on the tray. The belt replenishes that slot from a finite supply.
- Left-click **UNDO** to return the last tray ingredient to the remaining supply.
- Left-click **MAKE** to consume the tray. Exact recipes earn their sale price; invalid combinations earn nothing but still pay every selected ingredient cost.
- The wall menu uses six bilingual full-name recipe stickers, so no ingredient abbreviations need to be memorized.
- Net profit is revenue minus consumed ingredient cost. Reach `$100` to win; the run ends in failure when the remaining ingredients can no longer reach the target.
- The default seed is `1337`. Every generated batch is finite and contains at least `$120` attainable recipe profit before player mistakes.

Every human click enters through the ingredient's real 3D hit area. There is no semantic choose-by-name action. Lobby registration, the allowlisted `conveyor_profit` MCP scenario, and its public observer/terminal are the next milestone; no external MCP client is used by this standalone scene.

The food visuals are selected from Kenney Food Kit 2.0 under CC0. See [SOURCE.md](assets/kenney_food_kit/SOURCE.md) for exact file mappings and [LICENSE.txt](assets/kenney_food_kit/LICENSE.txt) for the bundled license.
