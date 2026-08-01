# AI Play 动作超时原地恢复设计

## 目标

当 Python 等待一次 `act` 的动作结果或后续观察超时时，AI Play 必须留在同一局、同一场景和
当前真实世界状态中恢复。恢复只取消尚未完成的输入，不回滚已经发生的位移、视角变化、交互或
场景变化，也不触发 Godot 重载、supervisor retry、AWM 更新或 `completed_runs` 增长。

成功恢复的唯一完成信号是一张由 Godot 在取消动作后重新捕获、且
`observation_id` 不同于超时动作 ID 的新观察。Codex 只能从这张新观察继续游玩。

## 非目标

- 不为任意协议错误提供宽松恢复；非法字段、不匹配的当前 ID 和非回环连接仍然 fail-closed。
- 不回滚已经发生的游戏状态。
- 不把恢复过程暴露成新的 MCP 工具，也不允许模型自行声明需要恢复。
- 不改变玩法终局、请求额度或 AWM 晋升规则。

## 协议

内部桥协议升级为版本 4。除版本号和新增消息外，现有消息字段与语义保持不变。Python 在一次
已派发动作超时后发送：

```json
{
  "type": "recover_action",
  "protocol_version": 4,
  "observation_id": 42,
  "reason": "action_timeout"
}
```

该消息只允许精确字段、非布尔安全整数 ID 和固定 reason。Godot 不发送单独 ack；严格晚于
超时动作的新 `observation` 是恢复完成确认。`recover_action` 必须幂等，重复接收不得重复执行
动作、回滚状态或关闭控制器。

协议版本升级是有意的：旧 Godot 不理解恢复消息，不能与会发送该消息的新 Python 安全混用。
Python、Godot、测试、README、Wiki 和启动握手必须同步更新。

## Python 状态机

一次动作派发后，Python 保存其 observation ID。在等待期限届满且仍未得到完整回合结果时：

1. 清理该工具调用的待返回动作结果，但保留最新公开观察供内部关联。
2. 将 session 从 `executing` 转为 `recovering`，记录超时 observation ID。
3. 发送一次 `recover_action`，随后让原 `act` 返回 `action_timeout`。
4. `recovering` 期间拒绝所有新 `act`，错误码固定为 `action_recovery_in_progress`。
5. `observe` 不得返回超时前缓存的旧观察；它等待新 ID、终局、停止或真实断线。
6. 收到不同 ID 的合法新观察后，将其设为 latest observation，清除恢复状态并回到 `ready`。

如果 `observe` 自身等待超时，返回 `action_recovery_timeout`，session 仍保持 `recovering`；后续
`observe` 可幂等重发恢复消息再等待。恢复超时本身不让 supervisor 重启。真实 WebSocket 断线、
Godot 退出或协议错误仍沿现有异常路径处理。

若游戏在恢复期间产生合法 `game_over`，终局优先，session 直接进入 `game_over`，不再等待新观察。
迟到的旧 `action_results` 可以校验后丢弃，但不能完成新的回合，也不能覆盖恢复后的观察。

## Godot 状态机

Controller 保存当前执行 ID、最近完成但尚未被新观察取代的 ID，以及 capture generation。
收到合法 `recover_action` 后按状态处理：

- `EXECUTING` 且 ID 匹配：取消 executor 的剩余工作，释放所有模拟输入，抑制该旧批次的正常
  `action_results` 发送，使 controller 回到 `READY`，废弃旧的延迟捕获并安排一次恢复捕获。
- `READY` 且 ID 等于最近完成 ID：动作已经结束但观察滞后。停止 observation timer，废弃旧的
  deferred capture，并安排一次恢复捕获。
- `WAITING_FOR_DECISION` 且 pending observation ID 已不同：恢复观察已经发送或正在传输，合法的
  重复恢复消息直接忽略。
- 已处理过同一恢复请求：直接忽略。
- 合法消息引用无法关联的当前 ID，或消息字段非法：沿现有协议错误路径 fail-closed。

恢复捕获必须等待一个完整 process frame 和 `RenderingServer.frame_post_draw`，然后再次校验
capture generation、controller 状态和节点生命周期。Observer 正常生成新的 observation ID；
截图和公开结构化状态反映取消后实际位置，不使用动作前缓存画面。

取消动作只停止剩余执行。例如 250ms 移动在 120ms 时被取消，则保留已经产生的 120ms 位移；
已经打开的门、界面和完成的交互同样保留。

## 与局次、额度和 AWM 的关系

- 原始 `act` 调用照常消耗一次请求额度。
- `recover_action`、恢复等待和恢复观察不额外消耗请求额度。
- 恢复不结束 attempt，不触发 supervisor retry，也不启动新 Godot。
- 恢复不改变 `completed_runs`，不产生 workflow-memory 晋升资格，也不调用 memory update。
- 轨迹保留原 `act` 的 `action_timeout` 和随后正常公开的新观察；不新增模型可写的日志字段。

## 测试与验收

Python 单元测试覆盖：

- `act` 超时后精确发送 `recover_action` 并进入 `recovering`。
- recovering 期间拒绝新动作，`observe` 不返回旧观察。
- 新 observation ID 解除恢复并允许下一次动作。
- 迟到 action results、重复恢复、恢复等待超时、终局和断线竞态。
- 恢复消息不增加动作请求计数，不改变 AWM attempt。

Godot 单元测试覆盖：

- 执行中恢复会取消剩余动作、释放输入、保持 controller 启用并生成新观察。
- 动作已完成但截图滞后时恢复会废弃旧 capture 并强制重新捕获。
- 新观察已发出后的重复恢复是幂等 no-op。
- 非法字段和无法关联的 ID 仍 fail-closed。

图形集成测试以一个有持续时间的移动为例：动作部分执行后触发恢复，验证玩家没有回到出生点，
新截图来自恢复后的视角，新 observation ID 已变化，随后动作能在同一 Godot 进程中继续执行。

最终回归运行受影响的完整 Python AI suite、Godot executor/controller/observer 与图形恢复测试，
最后运行 `git diff --check`。真实 Codex 三局验收只在这些测试通过后重新启动。

## 迁移

现有“收到重复在途 `action_batch` 时取消动作”的临时恢复逻辑及其文档将被删除。协议版本 4 的
`recover_action` 成为唯一超时恢复入口；普通重复动作仍按协议错误处理，避免把新决策误认为恢复。
