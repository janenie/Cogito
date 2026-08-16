# Doubao 原生 Codex Session 恢复设计

## 背景

Doubao 玩家当前以 `codex exec --ephemeral -` 启动一次非交互 turn。模型只要输出最终文本而
不再调用 MCP 工具，Codex 就以退出码 0 正常结束。外层 orchestrator 虽会重新启动玩家，新的
临时 `CODEX_HOME` 却没有上一 turn 的 session、截图和工具历史；默认 8 次重启耗尽后，即使
Godot 仍未产生可信 `game_over`，当前场景也会被收束，后续 Run 因而不会启动。

本改动的目标是让正常结束的 Codex turn 只成为“继续同一游戏 session”的边界。当前 Run 仍然
只能由 Godot 的正式 `game_over` 结束，不伪造游戏结果，也不自行实现模型工具循环。

## 方案比较

### 方案 A：在 Doubao wrapper 内原生 resume（采用）

首次运行使用非 ephemeral 的 `codex exec`。同一个 wrapper 生命周期内保留临时
`CODEX_HOME`、回环代理和 MCP 配置；Codex 以退出码 0 提前结束时，wrapper 启动
`codex exec resume --last` 并发送恢复提示。工具选择、模型调用和 agent loop 始终由 Codex CLI
负责。Supervisor 产生终局后，公共 orchestrator 终止 wrapper，wrapper 再清理临时 home 和代理。

优点：保留完整 session 历史；改动集中；不改变 MCP/Godot 协议；不实现自定义 agent loop。
代价：正常完成多个 Codex turn 时会持续产生 token 费用；如果模型反复不调用工具，会在配置的
原生 resume 上限、人工 Escape、基础设施错误或外层生命周期控制处停止。

### 方案 B：外层 orchestrator 跨进程保存 home 并 resume

让每次公共 player restart 复用稳定 home，再由新 wrapper 恢复上一 session。

优点：复用现有 restart 结构。缺点：需要把代理端口、临时凭据、home 所有权和 session 选择跨
wrapper 协调，安全清理与竞态明显更复杂。

### 方案 C：玩家退出时伪造 game_over（拒绝）

优点：能立即推动 Run 2。缺点：把模型/基础设施退出误记为游戏失败，破坏 Godot 作为可信终局
权威的协议和 benchmark 语义。

## 架构与数据流

Doubao 专用 wrapper 新增两条明确命令构造路径：

1. 初始命令：`codex exec ... -`，不带 `--ephemeral`。
2. 恢复命令：`codex exec resume --last ... -`，从同一临时 `CODEX_HOME` 和玩家工作目录选择
   唯一的最近 session。

`run_internal_player` 在单个代理和单个临时 home 上顺序运行 Codex 子进程。首个子进程读取完整
玩家提示；任何退出码 0 的子进程结束后，下一个子进程读取恢复提示。退出码非 0、代理失败、
输出 relay 失败或信号中断仍作为基础设施结果返回，不伪造终局。

公共 orchestrator 不再为 Doubao 正常退出配置外层 player restart。只要 wrapper 存活，Godot 和
MCP 会话保持不变；当 Supervisor 观察到正式终局并完成所请求的 Runs 后，公共 orchestrator 对
Doubao 启用“Supervisor 退出即停止玩家”策略，不等待 player final grace，避免终局后再产生一个
付费 resume。其他玩家继续沿用原有 grace 行为。

信号处理器覆盖代理与临时 home 的整个 wrapper 生命周期，而非只覆盖单个 Codex 子进程。它记录
停止信号，并终止当前子进程；每次创建 resume 前再次检查停止标志。因此信号即使落在两个 turn
之间，也会先退出 wrapper 并正常清理临时 home、代理与真实上游 token，不会创建新进程。

## 安全与持久化

- Codex rollout 只存在于本局权限为 `0700` 的临时 home，整个 wrapper 退出后删除，不归档到
  可信轨迹或用户日志。
- 临时 home 继续被玩家 shell 权限 profile 精确拒绝，模型不能读取 rollout、配置或凭据。
- Yibu token 仍只存在于可信 wrapper/代理环境；Codex 只获得一次性本地 bearer。
- MCP 公开字段、截图白名单、Godot 协议和正式终局集合均不改变。
- `--codex-max-restarts` 迁移为 `--codex-max-resumes`，控制同一原生 session 中允许的恢复次数；
  默认值保持 8 以维持显式费用边界。达到上限属于基础设施未完成，wrapper 返回非 0，既不伪造
  `game_over`，也不推进下一 Run。session metadata 对应记录 `player_restart_limit = 0` 与新的
  `native_resume_limit`。旧参数不再接受，CLI 会明确报未知参数，README 与 Wiki 同步迁移。

## 错误处理

- 初始 Codex 非 0：返回该退出码，按基础设施失败收束。
- resume Codex 非 0：返回该退出码，不启动新的 session。
- resume 次数达到配置上限：返回专用非 0 状态，不伪造游戏结果。
- `resume --last` 找不到 session：返回 Codex 错误，不回退到新 session，避免静默丢失上下文。
- 代理线程失败：终止当前 Codex 并返回 wrapper 错误。
- Supervisor 终局：公共 orchestrator 立即终止 Doubao wrapper；wrapper 生命周期级信号处理器禁止
  后续 resume，并清理临时资源。

## 测试

单元测试覆盖：

- Doubao 初始命令不含 `--ephemeral`，标准 Codex 入口保持原行为。
- resume 命令精确使用 `exec resume --last` 和 stdin 恢复提示。
- 首个 Codex 退出 0 后在同一 home、代理和工作目录启动 resume。
- resume 非 0、代理失败、信号与输出 relay 异常正确收束。
- 信号落在 turn 间隙时不会创建 resume，Supervisor 退出会立即停止 Doubao wrapper。
- Doubao 外层 player restart limit 为 0；原生 resume 上限被解析、记录并在触顶时以非 0 收束。
- 临时配置、凭据隔离、图片传输和现有 proxy 测试不回归。
- 无真实凭据的本地集成测试使用真实 Codex、fake upstream/MCP 验证第二个进程确实从临时 home
  `resume --last`；fake upstream 在恢复 turn 的工具结果请求上阻塞，测试观察到恢复后的 MCP 调用
  后终止 wrapper，并验证当前进程有界退出、没有启动第三个 Codex 子进程（第二次 resume）和资源
  泄漏。Responses API 在同一个 Codex 进程内为工具调用产生后续请求属于原生 agent loop，不计作
  新的 resume，也不应被测试禁止。

最后运行受影响单元测试、完整 Python 套件、密钥扫描和 `git diff --check`。
