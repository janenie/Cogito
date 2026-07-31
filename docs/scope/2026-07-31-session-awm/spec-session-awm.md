> 由 scope skill 于 2026-07-31 生成

# AI Play 会话级 Agent Workflow Memory

## 目标

为 `tools/ai_play_codex_orchestrator.py` 启动的同一次多局黑盒游玩增加显式、结构化的
Agent Workflow Memory（AWM）。当前 `--runs 3` 由同一个 Codex 会话连续完成，模型可以从
上下文和获准公开轨迹中隐式复用经验，但没有独立的工作流状态、终局晋升规则或可验证的读写
时序。本改动在可信 MCP sidecar 进程内维护仅限本次 orchestrator 会话的程序性记忆，让后续局
复用前序局已经验证的抽象流程和避坑规则，同时保持 Codex 内建 memories 关闭、玩家黑盒边界
不变，并禁止将本局随机答案或实现信息转化为后续提示。

## 决策

- AWM 只在同一次 orchestrator 的多局运行中有效。它不跨 orchestrator 启动复用，不启用
  Codex `[memories]`，也不改变 `codex exec --ephemeral`。
- AWM 位于现有 `ai_play.mcp_server` 进程内，由独立的 `SessionWorkflowMemory` 组件管理；
  不新增进程、端口、模型调用、数据库或玩家可写文件。
- 隔离玩家新增两个白名单 MCP 工具：`workflow_memory_read` 和
  `workflow_memory_update`。每局调用顺序是 `briefing`、`workflow_memory_read`、
  `observe/act`，终局后再调用一次 `workflow_memory_update`。
- memory 使用固定结构，只包含 `goal_pattern`、带 `step`/`precondition`/
  `success_signal` 的 `workflow`、抽象 `landmarks`、`avoid` 和由服务端计算的
  `confidence`。图片可以作为模型提炼经验的公开证据，但 memory 不保存图片、图片引用、
  Base64、embedding 或逐帧轨迹。
- `GameSession` 的真实 attempt 生命周期决定是否允许晋升，不信任工具调用方提交的胜负。
  成功局可以合并 workflow、landmarks 和 avoid；正常失败局只能合并 avoid；stopped、
  disconnected、MCP shutdown、异常退出和未终局 attempt 都不能晋升。
- 每个已终局 attempt 最多接受一次更新。MCP sidecar 必须保留独立于 Godot 连接重启的
  attempt 序号、终局资格和是否已消费状态，避免下一局快速连接时把更新归到错误 attempt。
- 服务端对所有字段做严格字段集、类型、数量、长度、Unicode 规范化和控制字符校验，并去重。
  禁止六位密码或其他具体谜题答案、绝对坐标、逐帧动作序列、文件/资源/节点路径、URL、
  源码/测试/spec/开发者笔记事实以及超长自由文本。非法候选整体拒绝，不进行部分静默清洗。
- `workflow_memory_update` 不回显候选正文，只返回新版本和各类别接受数量；
  `workflow_memory_read` 只返回已经通过验证和终局晋升的内容。第一局返回版本 0 和
  `memory: null`。
- AWM 工具不接入 `TrajectoryLogger`，请求、候选、快照和工具结果都不写入
  `trajectory.json`、`run.json` 或其他文件。MCP 进程退出后内存自然释放；不保留审计副本。
- 现有 `briefing`、`observe`、`act` 的公开范围和 Godot/Python 协议不扩大。AWM 只能处理
  玩家已经通过获准工具取得的信息，不能读取 Godot 隐藏状态、可信日志文件或仓库内容来自动
  补全 memory。
- 首版不进行语义向量检索。一次 orchestrator 固定一个 scenario，数据量最多来自前两局，
  因此读取当前 scenario 的完整、受限结构化 workflow 比引入 embedding 更简单且可验证。

## 架构

```text
可信侧
orchestrator
  ├─ MCP sidecar（跨多次 Godot attempt 存活）
  │    ├─ FastMCP
  │    │    ├─ briefing / observe / act
  │    │    ├─ workflow_memory_read
  │    │    └─ workflow_memory_update
  │    ├─ GameSession ── attempt started/finished ─┐
  │    ├─ SessionWorkflowMemory ◄─────────────────┘
  │    └─ TrajectoryLogger（不接收 AWM 调用）
  └─ supervisor ── 每局重启 Godot

受限玩家侧
同一个 ephemeral Codex 会话
  └─ 通过白名单 MCP 工具读写抽象 workflow
```

`SessionWorkflowMemory` 是不依赖 FastMCP、日志器和文件系统的纯 Python 状态组件。它负责
attempt 生命周期、候选验证、晋升、去重、版本和置信度；MCP 工具只做异步边界适配和稳定错误
映射。`GameSession` 在成功 attach 后通知 attempt 开始，在既有终局/停止/断线收束点通知
attempt 结束，使 AWM 和 `TrajectoryLogger` 分别消费同一可信生命周期，而不从持久日志反推
状态。

### MCP 工具

`workflow_memory_read()` 无参数。只有已经建立合法 scenario 的 attempt 才返回：

```json
{
  "status": "ready",
  "scope": "current_orchestrator_session",
  "scenario": "find_contract",
  "version": 1,
  "completed_runs": 1,
  "memory": {
    "goal_pattern": "依据公开线索逐步完成调查任务",
    "workflow": [
      {
        "step": "先定位并读取任务入口物",
        "precondition": "入口物已通过公开观察或交互提示确认",
        "success_signal": "公开观察给出下一阶段线索"
      }
    ],
    "landmarks": [
      {"relation": "先在出生区域建立主要地标的相对方向"}
    ],
    "avoid": [
      "没有可用交互提示时不要重复提交 interact"
    ],
    "confidence": 0.67
  }
}
```

`workflow_memory_update(goal_pattern, workflow, landmarks, avoid)` 提交当前 Codex 从最近一个
已终局且未消费 attempt 中提炼的候选。服务端根据真实终局决定可晋升字段，成功返回：

```json
{
  "status": "updated",
  "version": 2,
  "accepted": {
    "workflow": 2,
    "landmarks": 1,
    "avoid": 1
  }
}
```

稳定错误码至少包括 `server_not_ready`、`scenario_not_ready`、`attempt_in_progress`、
`attempt_not_eligible`、`attempt_already_updated` 和 `invalid_workflow_memory`。错误结果不得
包含候选正文、终局隐藏细节、源码位置或 Python 异常文本。

## 流程

1. orchestrator 启动一次 MCP sidecar、一个 ephemeral Codex 会话和多局 supervisor，并把两个
   AWM 工具加入现有玩家工具白名单。
2. 第一局 Godot attach 后，`GameSession` 通知 AWM 开始 attempt 1。Codex 调用
   `briefing` 和 `workflow_memory_read`；此时得到版本 0、`memory: null`，随后正常游玩。
3. 终局到达时，`GameSession` 先按现有路径唤醒工具调用和完成轨迹，再以规范化的
   success/failure/stopped/disconnected 分类通知 AWM。该记录在 Godot 退出和下一局 attach
   之间仍保存在 MCP 进程内。
4. Codex 根据本局公开观察和动作结果调用 `workflow_memory_update`。成功局晋升全部获准字段；
   失败局仅晋升 avoid；不合资格终局返回稳定错误且 memory 不变。
5. 第二局 attach 后，Codex 在第一次 observe 前读取已晋升版本并将其作为高层指导，而不是无需
   观察即可执行的动作脚本。新证据仍必须来自本局最新 observation。
6. 后续局重复读取、游玩、终局晋升。新候选按规范化文本去重；服务端置信度依据支持该条目的
   合资格 attempt 数计算，模型不能直接设置。
7. orchestrator 收束子进程时，MCP sidecar 退出，AWM 与临时候选一同消失。现有可信轨迹仍按
   原策略保存，但其中没有 AWM 请求或结果。

## 验收标准

- `--runs 3` 使用同一个 MCP sidecar 时，第 1 局读取空 memory；成功晋升后第 2 局可读取版本
  1；第 2 局失败只能增加 avoid；第 3 局读取合并后的版本。
- 新 Godot attempt 不会清空 AWM；新 orchestrator/MCP 进程不会加载上一会话的 AWM。
- success、failure、stopped、disconnected、shutdown 和未终局状态分别执行约定的晋升策略；
  工具调用方伪造 outcome 不会改变策略，因为 update 接口不接收 outcome。
- 同一 attempt 第二次更新稳定失败且不改变版本；下一局已经 attach 时，上一局尚未消费的更新
  仍准确归属上一局。
- 非法字段、错误类型、超限列表、控制字符、谜题答案模式、绝对坐标、动作序列、路径、URL 和
  内部实现术语被整体拒绝；错误结果不回显敏感候选。
- AWM 读取结果只包含经过服务端验证的抽象语言，不包含截图、图片引用、Base64、原始观察、
  observation ID、密码、随机答案或隐藏状态。
- `TrajectoryLogger` 的允许工具集合和已有 JSON schema 不增加 AWM 工具；运行 AWM 读写后磁盘
  轨迹与未启用 AWM 时保持同样字段范围。
- 玩家临时 Codex 配置仍显式关闭内建 memories、Web、子代理和额外权限，只在
  `enabled_tools` 增加两个 AWM 工具；玩家不能通过文件系统直接访问或修改 memory。
- 现有 stdio MCP 客户端不会被强制使用 AWM；不调用两个新工具时，原有游玩工具行为不变。
- `ai_play/README.md` 与 `docs/wiki/ai-play/system-guide.md` 同步说明 AWM 生命周期、工具、
  晋升规则、图片边界、非持久化和验证方式。

### 测试

- 新增 `SessionWorkflowMemory` 纯单元测试：空读取、attempt 生命周期、成功/失败晋升、异常不
  晋升、一次性消费、跨 attach 保留、版本、去重、服务端置信度和所有拒绝规则。
- 扩展 `GameSession` 测试：合法 attach/终局/停止/断线/shutdown 的生命周期通知，通知失败时
  安全关闭且不影响输入释放。
- 扩展 MCP 测试：两个工具的结构化成功与稳定错误、无 outcome 入参、不回显非法候选、未调用
  `TrajectoryLogger`，以及 stdio/HTTP 工具注册一致。
- 扩展 orchestrator 测试：玩家工具白名单、临时配置、提示词逐局调用顺序、终局后更新和异常局
  不学习；测试仍只用伪进程和临时目录，不启动真实 Codex。
- 运行 `PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests
  tests/test_ai_play_codex_orchestrator.py tests/test_ai_play_supervisor.py -q`，再运行受影响的 Godot
  AI Play headless 测试和 `git diff --check`。
- 不运行真实外部 Codex/Godot 黑盒验收；如后续需要评估 AWM 性能，必须另行确认截图、令牌、
  费用和本地轨迹持久化影响，并以成功率、act 数、失败动作数、用时和 token 为对照指标。

## 范围之外

- 跨 orchestrator、跨用户、跨设备或跨 scenario 的持久 memory。
- 图片、视频、视觉 embedding、向量数据库、语义检索或 Visual Episodic Memory。
- 保存、回放或直接执行具体动作序列、坐标、密码和本局随机线索。
- 从可信轨迹自动调用额外模型提炼 workflow，或让服务端读取仓库/隐藏状态生成 memory。
- 修改 Godot/Python 桥协议、玩法逻辑、观察 schema、动作白名单或终局定义。
- AWM 管理 UI、磁盘审计文件、远程 memory 服务以及真实外部模型性能验收。
