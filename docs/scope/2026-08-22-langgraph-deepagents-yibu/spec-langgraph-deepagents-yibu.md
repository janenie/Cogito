> 由 scope skill 于 2026-08-22 生成

# LangGraph Deep Agents Yibu AI Play 接入

## 目标

在顶层新建 `tools_langgraph_deepagents/`，为 Cogito AI First Play 提供一个单一
Python 应用入口。该应用直接创建 LangGraph Deep Agent，直接连接 Yibu
OpenAI 兼容 Chat Completions API，并通过持久 stdio MCP 会话控制 Godot。它可在内部启动现有
Godot supervisor 和 MCP Server，但绝不启动或依赖 Codex CLI/runtime。用户只运行
一条启动命令；应用获得确认后自主串行玩到目标正式终局数，同时在终端流式
展示模型文本、工具调用和运行状态。这个新入口的核心目的是绕过 Codex CLI
对 Yibu 的不完整兼容，而不是再为 Yibu 包一层其他模型 CLI。

## 决策

- 从 `save_token_ai_play` 当前已同步的 HEAD 创建并在
  `tools_langgraph_deepagents` 分支实施。
- 首版是完整可运行入口，不是只连接手工启动 Godot 的 PoC。
- 用户只看到一个 Python 启动入口；Yibu 模型、Deep Agent、MCP 会话、
  supervisor 和日志生命周期都由该应用内部管理，不再拆分成多个用户入口。
- 不调用 `codex`，不创建 `CODEX_HOME`，不加载 Codex 配置，不运行
  Responses namespace proxy，不导入任何 `ai_play_codex_*_orchestrator.py`，
  也不实现 Codex turn/restart 语义。
- Deep Agents 作为应用内嵌的 Python library 运行；模型请求由 LangChain 模型对象
  在进程内直接发往 Yibu HTTPS Chat Completions API，不经过任何外部 Agent CLI。
- 默认模型为 `gemini-3.6-flash`；模型名可通过单一应用的启动参数覆盖。
- 凭据默认从已忽略的仓库根目录 `newak.py` 读取变量 `ak`；启动参数可显式
  选择同文件中的其他凭据变量，但不在账户之间自动轮换。新包自身实现字面量解析与
  HTTPS `/v1` base URL 校验，不从 Codex 编排器导入；密钥不得写入仓库、会话
  元数据、checkpoint 或日志。
- 使用 LangChain `ChatOpenAI`，显式设置 `use_responses_api=False`，使请求发往
  Yibu `/v1/chat/completions`，而不是 `/v1/responses`。
- 游戏 MCP 使用持久 stdio `ClientSession`，整次 Agent 运行只有一个会话。
- 创建 Deep Agent 时禁用默认文件、Shell 和子 Agent 工具，不向模型提供仓库工作区；
  只暴露当前模式下允许的 AI Play MCP 工具。
- 模型每次只能产生一个游戏工具调用，不并行执行 `act`；过期
  `observation_id` 或工具错误作为可见错误返回 Agent，不绕过 Godot 校验。
- system prompt 要求 Agent 在正常响应中为新 RGB/深度图记录短 caption。
  模型调用中间件在每次请求前硬性只保留最近 10 张图；旧图块从当次模型输入删除，
  文本观察和已有 caption 保留，不为 caption 单独发起 API 请求。
- MCP adapter 把结构化结果、RGB 和深度图保留为 LangChain 标准多模态
  `ToolMessage` 内容块，直接作为下一轮 Yibu Chat Completions 的模型输入，
  不做 Responses 格式转换，不伪造用户消息。
- Agent checkpoint 保存在仓库外的运行目录，可包含对话文本与未裁剪的 MCP
  图片内容；信任日志继续由现有 MCP logger 生成。续跑时同时校验游戏进度和
  Deep Agent thread/checkpoint 身份。
- 真实外部运行前必须在终端明确确认模型、场景、局数、图片上传、费用和
  本地 checkpoint/轨迹持久化影响；非交互运行需要显式确认参数。
- `Ctrl-C`、Agent 异常、MCP 退出和 supervisor 退出都必须进入现有安全停止路径，
  释放模拟输入并回收子进程。
- 依赖在 `tools_langgraph_deepagents/` 内单独声明和锁定，不改变 Godot
  运行时的基础 Python 依赖范围。
- 首轮实施和自动测试不调用真实 Yibu API，不启动真实外部模型验收。

## 架构

`tools_langgraph_deepagents/` 是一个单一 Python 应用包。`__main__.py` 是唯一启动
入口；包内其余文件只是被调用的普通模块，分别负责 Yibu ChatModel、Deep Agent
构建、MCP 工具筛选、最近 10 图裁剪、终端流式输出和子进程安全清理。
应用只作为客户端启动现有 `tools/ai_play_supervisor.py` 和 `ai_play/start_ai.sh`；
它不启动任何其他 Agent 运行时，也不经过 Codex 中间层。

```text
单一 Python 应用 / 终端 Chat
    ↓ messages / stream
Deep Agents / LangGraph + Yibu Chat Completions
    ↓ 串行白名单工具
持久 stdio MCP ClientSession
    ↓ 127.0.0.1:8765 WebSocket
Godot AI Play Lobby

内部子进程：MCP Server + Godot supervisor
不存在：Codex CLI/runtime/proxy
```

## 流程

1. 单一 Python 应用校验启动参数、独立运行目录、续跑元数据、Yibu 凭据和端口占用。
2. 应用向用户展示外部运行影响并获取确认，然后在内部启动 Godot supervisor
   和 stdio MCP Server；此过程不搜索、解析或启动 Codex。
3. 持久 MCP session 初始化后校验并筛选工具，再创建 Yibu ChatModel 与 Deep Agent。
4. 用户发送开始指令；Agent 流式执行 `briefing` / AWM read / `observe` / `act`
   循环，直到 Godot 产生正式终局。
5. 每局终局后按现有规则更新 AWM，supervisor 旋转到下一局；未达到目标局数时
   在同一 Deep Agent thread 中继续。
6. 完成、中断或异常时执行安全清理，保留可续跑的仓库外日志和 checkpoint。

## 验收标准

- 分支中存在独立的 `tools_langgraph_deepagents/` 应用包、唯一 `__main__.py`
  启动入口、依赖文件和使用文档。
- 应用启动参数支持现有白名单场景、`--runs`、`--resume-run`、AWM 开关、外部 artifact
  目录、超时和 supervisor 重试参数。
- 运行时进程树中不存在 Codex，代码不导入 `ai_play_codex_*`，也不读写
  Codex 配置或启动 Codex 专用代理。
- Yibu 凭据被安全读取，只传入模型客户端，错误信息不泄漏密钥；本地
  fake server 能确认请求路径是 `/v1/chat/completions`。
- Agent 不可见文件、Shell、子 Agent 或非白名单游戏工具。
- 只使用一个持久 MCP session，游戏工具调用不并行，`act` 连续消费最新观察。
- 任意模型请求中的图片内容块不超过 10 个，被移除图片所在消息的文本部分保留。
- 终端能流式展示 Agent 文本、工具名称、工具结果状态和最终进度，不打印密钥或
  Base64 图片。
- 无交互确认或显式确认参数时不发起真实外部请求。
- `Ctrl-C`、模型异常、MCP 异常和 supervisor 异常都会请求安全停止并回收子进程。
- `--resume-run` 可从现有正式终局数和 Deep Agent checkpoint 继续，不重复计数已完成局。
- AI Play README 与系统 Wiki 记录启动方式、信任边界、图片裁剪和本地持久化影响。

### 测试

- 用单元测试覆盖启动参数校验、凭据校验、工具白名单、串行调用约束、
  Chat Completions 路径、MCP 多模态 `ToolMessage` 传递、10 图裁剪、流式输出脱敏、
  外部运行确认和安全清理。
- 用测试明确锁定命令构建与导入边界：只启动 supervisor/MCP，不引用或启动 Codex。
- 用 fake ChatModel、fake MCP session 和 fake supervisor 做本地集成测试，验证一次用户消息
  能驱动 Agent 到正式终局且不产生网络费用。
- 运行新包测试、现有 Python AI Play 受影响测试、密钥扫描和 `git diff --check`。
- 本轮不运行真实 Yibu/Gemini 或真实外部 MCP 客户端验收；如后续执行，
  必须再次明确确认截图上传、token/费用和本地持久化影响。

## 范围之外

- 不在 Godot 内嵌聊天 UI，不建设 React/Web 前端。
- 不修改游戏观察字段、动作 schema、协议版本或场景谜题逻辑。
- 不向 Deep Agent 暴露仓库源码、`code_read/`、`game_script/`、测试、规格或计划。
- 不为 Yibu 之外的模型 provider 建立新入口。
- 不在本轮运行 10 个场景的真实付费基准。
