# Godot 渲染同步 Observation

## 目标

保证 AI Play 的每个新 observation 都在 Godot 完成动作并绘制新帧之后捕获，避免把新的玩家位置和朝向与旧的 Viewport 图片组合在一起。

## 根因

普通 `move`、`look` 和 `wait` 动作完成后，控制器通过 `ObservationTimer` 直接调用截图。该路径只等待固定时间，没有等待 Godot 的下一逻辑帧和 `RenderingServer.frame_post_draw`。玩家状态已在 CPU 侧更新时，Viewport 纹理仍可能停留在 GPU 上一次完成的渲染帧。

## 设计决策

- 修复只发生在 Godot 侧，对 AI、MCP 客户端和提示词透明。
- 保留现有 `observation_interval`，让动作结束后有既有的稳定时间。
- `ObservationTimer` 超时后不再直接截图，而是进入统一安全捕获路径：等待一次 `process_frame`，再等待最多 1 秒的 `RenderingServer.frame_post_draw`。
- 正常渲染在 1 秒内完成时直接截图；后台窗口没有产生渲染完成信号时，Godot 在主线程调用 `RenderingServer.force_draw(false)` 主动重绘所有 Viewport，然后截图。Godot 不得把被动等待延长到 Python 的约 30 秒 action timeout。
- 普通动作、交互动作和动作超时恢复都使用同一个渲染同步捕获方法。
- 等待渲染帧不算 AI action，不消耗 `find_key` 的 50 步额度，也不要求 AI 主动调用 `wait` 或 `observe` 刷新画面。
- 保留捕获 generation 和 controller state 检查，防止等待期间发生停止、断连或新一代捕获后发送过期 observation。

## 测试设计

- 先增加一个失败的 controller 测试，证明普通动作的 timer 到期后，在 `process_frame` 和 `frame_post_draw` 发生前不会捕获 observation。
- 在发出 `frame_post_draw` 后，断言恰好捕获并发送一个新 observation。
- 增加超时回归测试：不发出 `frame_post_draw`，断言 Godot 在内部渲染等待期限后仍能完成捕获，而不会无限等待到 Python action timeout。
- 实际 Metal 渲染测试应证明普通渲染循环暂停时，`force_draw(false)` 仍能把已改变的相机状态绘制成不同像素。
- 保留并运行现有 rendered look、rendered recovery 和 controller 测试，确保交互与恢复路径没有回归。
- 运行受影响的 AI Play Godot 测试、协议相关 Python 测试以及 `git diff --check`。

## 范围之外

- 不修改 MCP 协议、observation 数据结构或 observation ID。
- 不增加图片哈希、图片差异阈值或截图重试策略。
- 不修改 AI system prompt、AWM、步数上限或 supervisor 终局解析。
- 不使用固定 sleep 后直接读取旧纹理；1 秒只作为主动 `force_draw` 的 fallback 期限。

## 风险

- 每次 fallback 会多执行一次强制 Viewport 绘制，但 AI 动作频率远低于实时帧率，开销可控。
- 本修复保证正常路径等待渲染完成、后台路径主动重绘，但不额外判断两个静止画面的像素是否相同。
