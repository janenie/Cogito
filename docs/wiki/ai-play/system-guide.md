> 摘要：本页维护 AI First Play 的架构、不可妥协的安全边界和跨层契约。

# AI First Play 系统指南

AI First Play 是一套需要显式启用的自主游玩系统：

- `addons/cogito/AIPlay/` 下的 Godot 代码捕获获准公开的观察数据，并执行有严格限制的输入动作。
- `ai_play/` 下的 Python 进程是 stdio MCP Server，负责暴露 `briefing`、`observe`、`act`、`stop` 工具、验证 DTO，并通过本机回环 WebSocket 桥与 Godot 串行交换观察和动作结果。
- 外部 MCP 客户端负责游玩决策；Python 不调用模型 API、不读取任务源码、不保存截图或游玩轨迹。
- Godot 与 Python 默认通过精确地址 `127.0.0.1:8765` 通信，内部桥协议版本为 3。

只有模型 API 时，可使用 [`tutorial/ai_play_api_host.py`](../../../tutorial/ai_play_api_host.py)
作为最小 Host 参考实现。该教学代码在客户端侧连接本地 stdio MCP、把工具定义映射为
模型 function tools，并将 MCP 的结构化结果和图片送回模型；它不改变 MCP Server 或
Godot 桥的安全边界。

## 不可妥协的安全边界

- AI 游玩必须保持显式启用。正常启动 Lobby 时 `auto_start = false`；精确的 Godot 用户参数是 `-- --ai-play`。
- Escape 是物理紧急停止键。断开连接、无效数据、API 失败和节点销毁都必须释放所有模拟输入。
- Godot 到 Python 的服务器必须使用精确的数字回环地址 `127.0.0.1`，不得扩大到局域网或公网接口。
- 绝不能提交 API 密钥，也不能把密钥复制到源代码、测试、文档、测试夹具、命令参数或日志。MCP Server 本身不需要 API Key；外部 MCP 客户端的凭据不进入本仓库或 Godot/Python 桥协议。
- 外部 AI 只能通过 MCP 工具接收 `ai_play.briefing` 白名单允许的公开简报和参考图，以及文档规定的相机图像、可见交互文本、获准公开的玩家状态、动作结果和运行时按键绑定。
- 绝不能把场景源码、节点路径、隐藏状态、仓库文件、谜题答案，或来自 `game_script/`、`code_read/`、测试、规格和计划的事实加入提示词、种子记忆、API 载荷或黑盒验收提示。
- 除非用户明确要求，并且了解截图、令牌、费用和本地轨迹持久化的影响，否则不要运行真实外部 MCP/模型验收。自动化测试必须不依赖真实凭据。

## 跨层契约

- Python 和 GDScript 两端的协议常量、数据包字段、动作名称、数值边界和上下文门控必须保持同步。版本 3 的桥协议使用 `action_batch`、`action_results`、`game_over`、`stop_request`、`stop_ack`，以及仅由 Python 发给 Godot 的 `end_game/failure/max_requests` 明确关联回合和终局。
- 所有不可信数据都必须在两端验证。保留精确字段检查、有限数检查、观察编号关联、每批最多三个动作，以及改变上下文的动作必须位于批次末尾等规则。
- Godot 的 JSON 解析会把数值规范化为浮点；其接收边界将非布尔且数值精确等于 `3` 的 `protocol_version` 规范化为整数 `3`，并将有限安全整数 `observation_id` 规范化为整数后再发出桥信号或发送确认包。字符串、布尔、非整数和越界 ID 必须继续被拒绝。
- `act` 必须携带最近的 `observation_id`，服务端只允许一个动作回合在途；校验失败或观察过期时不得向 Godot 派发输入。
- `AI_PLAY_MAX_ACT_REQUESTS` 默认是 `500`。所有到达 Python `act()` 的调用都计数，即使随后因观察过期、动作非法、上下文不允许或动作在途而失败；其他三个工具不计数。第 N 次请求先按正常规则处理，密码终局优先，否则返回 `failure/max_requests`。Godot 成功附加或重连时计数清零。
- Godot 执行器必须使用 COGITO 的常规输入、用专用设备 ID 标记合成事件，并在所有退出路径中释放持续按下的移动输入。
- `observe` 和 `act` 返回获准结构化状态及 MCP 图片内容；结构化结果不得重复 Base64 图片，也不得包含隐藏状态。
- `briefing` 只返回经过筛选的任务目标、规则和物体操作说明，并把固定参考图作为 MCP 图片内容；不得返回 `assets.json` 的内部类名、任何文件路径、线索原文、密码或正确解谜顺序。
- 修改公开协议、环境变量、控制方式或隐私行为时，必须在同一改动中更新 `ai_play/README.md` 和对应测试。

## 来源

本页整理自仓库根目录的 [`AGENTS.md`](../../../AGENTS.md)、已批准的 [`AI Play MCP spec`](../../scope/2026-07-23-ai-play-mcp/spec-ai-play-mcp.md) 和 [`ai_play/README.md`](../../../ai_play/README.md)。
