> 由 scope skill 于 2026-07-23 生成

# AI Play MCP 服务

## 目标

将当前由 Python sidecar 内置模型驱动的 AI First Play 改造成一个本地 stdio MCP Server。外部 MCP 客户端负责决策，Python 只负责把 MCP 工具调用与已显式启用的 Godot Lobby 连接起来；Godot 继续拥有获准观察、动作校验、正常输入执行、断线清理和 Escape 急停的最终权限。首版只要求现有 `find_contract` Demo 可通过 MCP 完成观察、操作和停止，不自动启动 Godot，不访问外部模型或 API。

## 决策

- MCP 客户端是外部 AI 应用；Python 不再调用 `AgentLoop`、`ApiClient` 或任何模型 API。
- MCP 传输使用 stdio。MCP 进程在后台运行现有风格的本地 Godot WebSocket 桥，桥只能绑定精确地址 `127.0.0.1`，默认端口仍为 `8765`。
- MCP 只暴露三个工具：`observe`、`act`、`stop`。不为每种动作额外创建独立工具。
- `act` 复用现有动作白名单和 1～3 个动作批次；调用必须带上最近一次观察的 `observation_id`，用于拒绝过期动作。
- `act` 是同步回合：服务端串行化工具调用，等待 Godot 完成动作、返回动作结果并产生下一次观察后才返回。返回内容包含动作结果、最新观察或终局状态。
- `observe` 在没有当前观察时等待 Godot 首次观察；已有观察则返回当前观察。等待有明确超时，不会无限阻塞 stdio 会话。
- `stop` 发送固定原因 `mcp_stop`，要求 Godot 取消当前动作并释放所有模拟输入。物理键盘 Escape 仍是独立且优先的紧急停止键。
- MCP 结果使用标准多模态内容：结构化 JSON 只放获准运行时状态和动作结果，截图作为 MCP `ImageContent` 返回；不在结构化结果中重复 Base64 图片。
- 不新增服务端截图、令牌、模型输入、模型输出、记忆或游玩轨迹持久化。MCP 客户端是否保存工具结果不属于本服务的控制范围。
- 首版只支持 `COGITO_3_Lobby.tscn` 中的 `find_contract` 终局事件；控制动作和观察 DTO 保持可复用，不为其他场景增加自动启动或任务编排。
- 内部 Godot/Python 桥协议升级为版本 `2`，明确区分 MCP 请求、Godot 观察、动作结果、终局和停止确认，拒绝旧版本数据。Godot 的 JSON 解析会把数值规范化为浮点；Python 到 Godot 的 `protocol_version` 因此只要是非布尔数值且精确等于 `2` 即有效，并会被桥规范化为整数 `2`。
- 使用官方 MCP Python SDK 稳定 v1.x 兼容线，依赖约束为 `mcp[cli]>=1.28,<2`；不依赖仍在预发布阶段的 v2 API。

## 架构

Python 进程由 MCP 宿主通过 stdio 启动。`FastMCP` 注册三个工具，工具实现调用线程安全的 `GameSession`；`GameSession` 管理唯一 Godot WebSocket 连接、当前观察、动作回合、终局状态、停止状态和等待者。WebSocket 服务器运行在后台线程，MCP 工具通过有界等待与其同步，不阻塞 MCP 的事件循环。Godot 的 `AIPlayController`、`AIPlayObserver`、`AIPlayExecutor` 和交互探测器仍是执行侧；Python 不能读取仓库文件、场景源码、节点路径或隐藏游戏状态。

### MCP 工具接口

工具名称和语义固定如下：

- `observe()`：返回当前 `observation_id`、截图、玩家公开状态、界面公开状态、绑定和上一次动作结果；若游戏已经终局或停止，返回对应状态而不是伪造新观察。
- `act(observation_id, actions)`：`observation_id` 必须等于当前观察 ID；`actions` 必须是 1～3 个严格动作对象。服务端先用当前界面上下文执行 Python DTO 校验，再向 Godot 发送批次。返回 `action_results` 与下一次观察，或返回终局/停止状态。
- `stop()`：请求 Godot 取消正在执行的批次、释放 `forward`、`back`、`left`、`right`、`sprint` 等保持输入，并结束 MCP 控制会话。已停止时重复调用是安全幂等操作。

工具错误使用 MCP 的错误结果，错误消息只描述协议、状态或动作校验失败，不包含源码、谜题答案、隐藏节点信息或凭据。执行过程中发生 Godot 断线、无效数据、超时或桥线程异常时，当前动作失败并清空会话中的保持输入；后续 `observe` 只能报告等待连接或安全停止状态。

### 内部桥协议版本 2

Godot 到 Python 的消息包括：

- `hello`：仅包含 `type` 与 `protocol_version`。
- `observation`：包含现有获准观察 DTO，以及 `type` 和版本字段。
- `action_results`：包含对应 `observation_id` 和经 Godot 清理后的结果数组。
- `stop`：物理 Escape 触发，原因只能是 `escape_stop`，可带当前动作结果。
- `game_over`：包含 `observation_id`、`outcome` 和终局原因；`find_contract` 只允许 `success/correct_password` 或 `failure/wrong_password`，不再携带模型请求计数。

Python 到 Godot 的消息包括：

- `hello`：桥连接确认。
- `action_batch`：包含当前 `observation_id` 和已校验动作数组，不包含模型理由、记忆或请求计数。
- `stop_request`：原因只能是 `mcp_stop`，用于 MCP 工具触发的停止。
- `error`：有限的协议错误码。

Godot 在处理 `stop_request` 后向 Python 发送 `stop_ack`，确认已取消执行并释放模拟输入。

#### JSON 数值规范化

Godot 接收 JSON 时无法保留 `2`、`2.0` 和 `2e0` 的词法差异；版本 2 的 Godot 接收边界将这些数值中精确等于 `2` 的非布尔表示视为同一协议版本，拒绝字符串、布尔值、非有限值和其他数值。桥会把有效版本规范化为整数 `2`，并把有效的有限安全整数 `observation_id`（0～2^53-1）规范化为整数后才发出 GDScript 信号或构造 `stop_ack`；非整数或越界 ID 仍由控制器拒绝。

观察和动作仍经过 Python 与 GDScript 两端的边界校验。Godot 断开连接、收到 `stop_request`、节点销毁或执行器取消时，必须调用既有的输入释放路径；Python 端的连接关闭和 MCP 进程退出也必须停止向 Godot 派发动作。

## 流程

1. 操作者先启动 Python MCP Server，再单独用精确参数 `-- --ai-play` 启动 `COGITO_3_Lobby.tscn`；普通 Lobby 启动保持 `auto_start = false`。
2. Godot 连接 `127.0.0.1:8765`，完成协议版本 2 握手并发送首个观察。Python 校验观察后缓存它，`observe` 可以返回它。
3. 外部 AI 调用 `observe`，读取结构化状态和截图。
4. 外部 AI 调用 `act`，提供观察 ID 和 1～3 个动作。Python 校验动作类型、字段、数值、界面状态和可用交互；失败时不向 Godot 发送输入。
5. Python 发送 `action_batch`。Godot 再次校验批次并通过正常输入系统执行，期间禁止并发批次。
6. Godot 发送 `action_results`，随后按现有立即重观察或定时观察逻辑发送下一观察；Python 将两者关联并完成同步 `act` 返回。
7. `find_contract` 的成功或错误密码失败由 Godot 发送 `game_over`；Python 唤醒等待工具并返回终局状态，之后拒绝新的 `act`。
8. 外部 AI 或实体 Escape 触发停止时，双方执行取消、输入释放和状态清理。断线、无效数据、超时和节点销毁走同一安全清理路径。

## 验收标准

- MCP 客户端通过 stdio 初始化后，只能发现 `observe`、`act`、`stop` 三个游玩工具；服务端 stdout 不输出日志或调试文本，日志只能去 stderr。
- 未设置任何 API Key、模型、Provider URL 或模型相关环境变量时，MCP Server 可以正常启动并等待 Godot；运行中不会导入、调用或要求 OpenAI SDK。
- Python 桥拒绝除 `127.0.0.1` 外的绑定地址；Godot 端拒绝 `localhost`、`::1` 和其他地址；协议版本错误、无效 JSON、过大数据包和并发第二连接都得到有界错误响应。
- `observe` 返回经过现有观察 schema 校验的公开运行时数据和 MCP 图片；返回中没有 Base64 图片副本、源码、节点路径、隐藏状态、任务答案、测试/规格/计划事实或凭据。
- `act` 在过期观察 ID、未知动作、额外字段、越界数值、不可用交互、错误界面状态、超过三个动作或不合法上下文变化时拒绝请求，且不产生 Godot 输入。
- 合法 `act` 只能串行执行；它等待动作结果和下一观察后返回，动作执行期间的重复调用不会并发改变角色。
- `stop`、Escape、Godot 断线、Python 断线和节点销毁都会释放全部保持输入；`stop` 的重复调用安全，Escape 仍保持物理急停行为。
- `find_contract` 的成功和失败终局可以从同步工具结果中观察到；终局后新的 `act` 被拒绝，不能重新注入动作。
- 启动脚本、README、Wiki 和测试不再要求 API Key、模型、模型请求上限、模型记忆或本地模型运行日志；仓库仍通过凭据扫描，不能新增真实密钥。

### 测试

- Python 单元测试覆盖动作批次校验、观察 DTO 清理、`GameSession` 的握手/单连接/观察等待/动作关联/过期 ID/终局/停止/断线/超时状态机。
- Python MCP 测试使用官方 SDK 的内存测试传输或等价无外部凭据测试，验证工具列表、结构化结果、图片内容、工具错误和 stdio stdout 清洁性。
- Godot headless 测试覆盖协议版本 2 的 JSON 数值规范化、动作批次字段、远程 `stop_request`、`stop_ack`、终局字段、Escape、断线和输入释放；保留 Lobby 的显式 `-- --ai-play` 与 `auto_start = false` 回归测试。
- Shell 测试覆盖 MCP 启动脚本的工作目录、`PYTHONPATH`、模块入口和凭据扫描。
- 不运行真实外部模型验收，不使用真实 API Key，不持久化截图、令牌或本地游玩轨迹作为自动化测试前提。

## 范围之外

- Streamable HTTP、SSE、远程 MCP、网络鉴权和多客户端共享会话。
- MCP Server 自动启动、重启或关闭 Godot。
- `find_contract` 之外场景的任务上下文、自动终局适配和场景选择工具。
- 任何内置模型、OpenAI 兼容 Provider、提示词、模型记忆、模型重试、模型请求上限和模型运行日志；旧的 `AgentLoop`/`ApiClient` 路径随迁移删除，不保留 legacy 模式。
- 服务端回放、持久化观察/截图、轨迹数据库、远程观战 UI 和 MCP 资源/提示词扩展。
