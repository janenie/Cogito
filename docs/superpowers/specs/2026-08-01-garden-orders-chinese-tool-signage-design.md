# Garden Orders Chinese Tool Signage Design

## Goal

Make the central area immediately understandable to a Chinese-speaking player and make every displayed gardening tool visually identifiable from the spawn point.

## Scope

This change updates presentation only. It does not add pickup, inventory, tool selection, order, or work interactions.

## Central HUD

Replace the English scene title and controls with:

- title: `园艺订单社区`;
- controls: `WASD 移动 · Shift 加速 · 鼠标旋转视角 · Esc 释放鼠标`.

The existing translucent panel, placement, and typography hierarchy remain unchanged.

## Tool Display

When the player faces the central tool shelter, the four displays read from left to right:

1. `肥料 ×2`;
2. `施肥器`;
3. `松土铲`;
4. `浇水壶`.

The node names remain English developer-facing identifiers so future code integrations do not need renaming. Only player-facing labels become Chinese.

The shovel and fertilizer spreader receive larger, clearer silhouettes. All four labels use a larger font, stronger outline, and disabled depth testing so the shelter geometry cannot hide the text. The existing object colors continue to distinguish water, metal, wood, and fertilizer.

## Validation

The neighborhood scene test will instantiate the real tool shelter and assert the four player-facing Chinese labels in their approved left-to-right order. It will also assert the two fertilizer bag meshes remain present. The full garden test suite, Godot editor import check, `git diff --check`, and a spawn-view screenshot will be rerun.

The running gameplay window must be restarted after the resource change so the user sees the new labels and model sizes.
