# Godot 渲染同步 Observation

## 目标

保证 AI Play 的每个新 observation 都在 Godot 完成动作并绘制新帧之后捕获，避免把新的玩家位置和朝向与旧的 Viewport 图片组合在一起。

## 根因

普通 `move`、`look` 和 `wait` 动作完成后，控制器通过 `ObservationTimer` 直接调用截图。该路径只等待固定时间，没有等待 Godot 的下一逻辑帧和 `RenderingServer.frame_post_draw`。玩家状态已在 CPU 侧更新时，Viewport 纹理仍可能停留在 GPU 上一次完成的渲染帧。

## 设计决策

- 修复只发生在 Godot 侧，对 AI、MCP 客户端和提示词透明。
- 保留现有 `observation_interval`，让动作结束后有既有的稳定时间。
- `ObservationTimer` 超时后不再直接截图，而是进入现有的安全捕获路径：等待一次 `process_frame`，再等待一次 `RenderingServer.frame_post_draw`，最后捕获并发送 observation。
- 普通动作、交互动作和动作超时恢复都使用同一个渲染同步捕获方法。
- 等待渲染帧不算 AI action，不消耗 `find_key` 的 50 步额度，也不要求 AI 主动调用 `wait` 或 `observe` 刷新画面。
- 保留捕获 generation 和 controller state 检查，防止等待期间发生停止、断连或新一代捕获后发送过期 observation。

## 测试设计

- 先增加一个失败的 controller 测试，证明普通动作的 timer 到期后，在 `process_frame` 和 `frame_post_draw` 发生前不会捕获 observation。
- 在发出 `frame_post_draw` 后，断言恰好捕获并发送一个新 observation。
- 保留并运行现有 rendered look、rendered recovery 和 controller 测试，确保交互与恢复路径没有回归。
- 运行受影响的 AI Play Godot 测试、协议相关 Python 测试以及 `git diff --check`。

## 范围之外

- 不修改 MCP 协议、observation 数据结构或 observation ID。
- 不增加图片哈希、图片差异阈值或截图重试策略。
- 不修改 AI system prompt、AWM、步数上限或 supervisor 终局解析。
- 不使用固定的额外 sleep 代替 Godot 渲染信号。

## 风险

- 如果平台完全停止渲染，等待 `frame_post_draw` 可能延长 action 返回时间；现有 MCP action timeout/recovery 仍负责处理这一异常。
- 本修复保证截图发生在新的渲染完成信号之后，但不额外判断两个静止画面的像素是否相同。
