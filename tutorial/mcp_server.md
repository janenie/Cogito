# 从 stdio、JSON-RPC 到 Cogito MCP Server

本文面向第一次接触 MCP 的读者。目标不是只记住几个 API，而是能够回答这些问题：

- stdio 是什么，两个进程怎样通过它交换消息？
- JSON-RPC 和 MCP 分别负责什么？
- MCP Host、MCP Client、MCP Server 和模型是什么关系？
- `ai_play` 中每个 Python 文件承担什么职责？
- 一次 `observe()` 或 `act()` 调用怎样从外部客户端到达 Godot，再返回给客户端？

本文使用的 MCP 报文以当前稳定协议版本 `2025-11-25` 为背景。示例为了教学会省略与
Cogito 无关的可选能力和元数据；实际报文由 MCP Python SDK 生成和解析，不应在项目代码中
手工拼接。

## 1. 先建立整体认识

Cogito AI First Play 中存在两条通信链路：

```text
模型
  │ 由 MCP Host 决定何时把工具提供给模型
  ▼
MCP Host / MCP Client
  │
  │ stdin + stdout
  │ 标准 MCP，消息编码为 JSON-RPC
  ▼
ai_play Python 进程
  │
  │ WebSocket：127.0.0.1:8765
  │ Cogito 自定义桥协议，protocol_version = 4
  ▼
Godot AIPlayController
  ├─ Observer：生成截图和公开状态
  └─ Executor：校验并执行玩家动作
```

这里最容易混淆的是“协议”和“传输方式”：

| 层次 | 本项目使用的东西 | 负责什么 |
| --- | --- | --- |
| 传输 | stdin/stdout | 在两个本地进程之间传递字节 |
| 消息格式 | JSON-RPC 2.0 | 表示请求、响应、通知和错误 |
| 应用协议 | MCP | 定义 `initialize`、`tools/list`、`tools/call` 等方法 |
| 游戏桥协议 | Cogito protocol v4 | 定义 `observation`、`action_batch`、`game_over` 等游戏消息 |

可以把它类比成寄快递：

- stdin/stdout 是运输道路；
- JSON-RPC 是统一的快递单格式；
- MCP 规定可以办理哪些业务；
- `briefing`、`observe`、`act`、`stop` 是这家服务器实际提供的业务。

## 2. stdin、stdout 和 stdio 是什么

操作系统启动一个进程时，通常会为它准备三个标准流：

- stdin，标准输入，文件描述符通常是 `0`；
- stdout，标准输出，文件描述符通常是 `1`；
- stderr，标准错误，文件描述符通常是 `2`。

在普通终端程序中：

```text
键盘输入 ──> stdin ──> 程序
程序 ──> stdout ──> 终端正常输出
程序 ──> stderr ──> 终端错误或日志输出
```

但在 stdio MCP 中，MCP Host 会把 Server 作为子进程启动，并为标准流接上管道：

```text
Host 写入管道 ──> Server stdin
Host 读取管道 <── Server stdout
Host 可选读取  <── Server stderr
```

所以 stdio 不是“在终端里让人输入命令”，而是两个进程借助操作系统管道通信。MCP
Python SDK 负责异步读取和写入这些管道。

本项目的 Host 示例在
[`tutorial/ai_play_api_host.py`](ai_play_api_host.py) 中创建 stdio Server：

```python
server = StdioServerParameters(
    command=str(MCP_COMMAND),
    cwd=REPO_ROOT,
)
async with stdio_client(server) as (read_stream, write_stream):
    async with ClientSession(read_stream, write_stream) as mcp_session:
        await mcp_session.initialize()
```

`stdio_client(...)` 会启动 `ai_play/start_ai.sh`，并把子进程的 stdin/stdout 包装成 MCP
SDK 可以使用的流。

### 为什么 stdout 不能打印普通日志

stdio MCP 要求每条消息：

- 使用 UTF-8；
- 是一个 JSON-RPC 请求、响应或通知；
- 以换行分隔；
- 消息本身不能包含未转义的实际换行；
- stdout 中不能混入非 MCP 内容。

假设 Server 正要返回：

```json
{"jsonrpc":"2.0","id":3,"result":{"tools":[]}}
```

如果代码先执行：

```python
print("准备返回工具列表")
```

Host 可能先从 stdout 读到：

```text
准备返回工具列表
```

这不是合法 JSON-RPC 消息，协议流就被污染了。日志应该写入 stderr：

```python
print("准备返回工具列表", file=sys.stderr)
```

这也是 `mcp_server.py` 捕获配置错误后使用 `file=sys.stderr` 的原因。

## 3. JSON-RPC 2.0 解决什么问题

stdio 只负责传输字节，并不知道这些字节表示“列出工具”还是“调用动作”。JSON-RPC
在字节流之上提供统一的远程调用格式。

JSON-RPC 2.0 主要有三种消息。

### 3.1 请求

请求表示“请执行一个方法，并给我响应”：

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/list",
  "params": {}
}
```

关键字段：

- `jsonrpc`：固定为 `"2.0"`；
- `id`：由请求方选择，用来关联请求和响应；
- `method`：要调用的方法；
- `params`：传给方法的参数。

多个请求可以依次发出，响应不必严格按照请求顺序返回。调用方根据 `id` 找到每个响应属于
哪个请求。

### 3.2 成功响应

成功响应保留相同的 `id`，并包含 `result`：

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "tools": []
  }
}
```

### 3.3 JSON-RPC 错误响应

如果 RPC 方法不存在、参数无法解析，或者协议层发生异常，响应包含 `error`：

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32601,
    "message": "Method not found"
  }
}
```

同一个响应不能同时包含 `result` 和 `error`。

### 3.4 通知

通知表示“告诉你一件事，但不需要响应”。它没有 `id`：

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

判断方法很简单：

- 有 `method` 和 `id`：请求；
- 有 `method`、没有 `id`：通知；
- 有 `id` 和 `result` 或 `error`：响应。

## 4. MCP 在 JSON-RPC 之上增加了什么

JSON-RPC 只定义通用信封，不定义业务方法。MCP 在这个信封中规定了标准方法、生命周期和
数据结构，例如：

- `initialize`：协商协议版本、能力和实现信息；
- `notifications/initialized`：客户端确认初始化完成；
- `tools/list`：列出 Server 提供的工具；
- `tools/call`：调用某个工具；
- `resources/list`、`resources/read`：发现和读取资源；
- `prompts/list`、`prompts/get`：发现和获取提示模板。

Cogito Server 只需要工具能力，没有注册 MCP Resources 或 Prompts。

### MCP 不是模型 API

MCP 规定“工具如何被发现和调用”，但不规定必须使用哪个模型，也不自动调用模型。

本项目中的角色是：

| 角色 | 本项目中的实现 | 职责 |
| --- | --- | --- |
| 模型 | 由外部 Host 选择 | 根据截图和状态决定是否调用工具 |
| MCP Host | `tutorial/ai_play_api_host.py` 或其他外部客户端 | 管理模型、MCP Client 和对话循环 |
| MCP Client | Host 中的 `ClientSession` | 与 MCP Server 初始化、列工具、调用工具 |
| MCP Server | `ai_play.mcp_server` | 注册六个工具并执行调用；教学 Host 只向玩家开放四个单局工具 |
| 游戏 | Godot Lobby | 产生观察、校验动作、执行输入、判断终局 |

因此 API Key 只可能由使用模型 API 的 Host 持有。`ai_play` MCP Server 本身不需要，也
不应该接收 API Key。

## 5. 一次 MCP 会话的报文

下面展示一条 stdio 连接上的典型顺序。为了可读性，JSON 被格式化为多行；真实 stdio
传输中，每个 JSON 对象会序列化成单独一行。

### 5.1 初始化请求

Client 首先发出 `initialize`：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": {
      "name": "cogito-tutorial-host",
      "version": "1.0.0"
    }
  }
}
```

这里的 `protocolVersion` 是 MCP 版本。它是日期字符串，不是 Cogito WebSocket 桥的
`protocol_version: 4`。

Server 返回双方将使用的版本、Server 能力和实现信息。字段细节可能随 SDK 版本和启用
能力略有不同：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-11-25",
    "capabilities": {
      "tools": {
        "listChanged": false
      }
    },
    "serverInfo": {
      "name": "Cogito AI Play",
      "version": "..."
    }
  }
}
```

Client 接受协商结果后发送通知：

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

通知没有 `id`，Server 不返回响应。初始化阶段完成后才进入正常操作阶段。

在教程 Host 里，这一整段由：

```python
await mcp_session.initialize()
```

完成。项目代码不需要手工处理这些 JSON。

### 5.2 列出工具

Client 请求工具列表：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

Server 返回工具声明。以下以 JSONC 摘要展示 `act`；实际声明的 `$defs` 会分别完整列出
十四种动作的精确字段、枚举和范围：

```jsonc
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "briefing",
        "description": "Read the public game objective, rules, object guide, and reference atlas.",
        "inputSchema": {
          "type": "object",
          "properties": {}
        }
      },
      {
        "name": "observe",
        "description": "Read the latest approved game observation and screenshot.",
        "inputSchema": {
          "type": "object",
          "properties": {}
        }
      },
      {
        "name": "act",
        "description": "Execute one typed batch of one to three actions and return the next observation.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "observation_id": {
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            },
            "actions": {
              "type": "array",
              "minItems": 1,
              "maxItems": 3,
              "items": {
                "anyOf": [
                  {"$ref": "#/$defs/LookAction"},
                  {"$ref": "#/$defs/MoveAction"},
                  {"$ref": "#/$defs/SprintAction"}
                  // 其余 jump、crouch、interact、enter_digits、
                  // close_ui、wait、probe_interaction、select_ingredient、
                  // undo、make、wait_next_window 定义从略
                ]
              }
            }
          },
          "required": [
            "observation_id",
            "actions"
          ]
        }
      },
      {
        "name": "stop",
        "description": "Stop AI control and release all simulated inputs.",
        "inputSchema": {
          "type": "object",
          "properties": {}
        }
      }
    ]
  }
}
```

具体 schema 可能包含 SDK 生成的额外标题或约束，但来源仍是 Python 函数签名和
docstring：

```python
@mcp.tool()
async def act(
    observation_id: ObservationIdInput,
    actions: ActionBatchInput,
) -> CallToolResult:
    """Execute one typed batch of one to three actions and return the next observation."""
```

教程 Host 中对应：

```python
listed = await mcp_session.list_tools()
```

Host 随后把 MCP `Tool` 声明转换成模型 API 的 function tools：递归移除 SDK 标题，把单值
`const` 规范化为 `enum`，为每个对象补全 `required` 与
`additionalProperties: false`，并设置 `strict: true`。模型看到的是转换后的工具定义，
不会直接写 stdio 报文。工具结果有图片时，Host 把结构化 JSON、JPEG 和 PNG 一起放进与
原 `call_id` 关联的 `function_call_output`，不再新增一条伪造的 user 图片消息。

### 5.3 调用工具

Client 调用 `act`：

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "act",
    "arguments": {
      "observation_id": 7,
      "actions": [
        {
          "type": "wait",
          "duration_ms": 50
        }
      ]
    }
  }
}
```

注意：JSON-RPC 的 `method` 是统一的 `"tools/call"`，真正的 MCP 工具名位于
`params.name`。

成功时，Cogito Server 的响应类似：

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "image",
        "data": "<下一次观察的 JPEG Base64>",
        "mimeType": "image/jpeg"
      }
    ],
    "structuredContent": {
      "status": "ready",
      "action_results": [
        {
          "status": "completed",
          "type": "wait"
        }
      ],
      "movement_feedback": {
        "planar_delta_meters": [0.0, -0.25],
        "distance_moved_meters": 0.25,
        "blocked": false
      },
      "game_over": null,
      "observation": {
        "observation_id": 8,
        "captured_at_ms": 123456,
        "image": {
          "mime_type": "image/jpeg",
          "width": 1024,
          "height": 576
        },
        "player": {},
        "interface": {},
        "bindings": {},
        "last_action_results": []
      }
    },
    "isError": false
  }
}
```

`player`、`interface` 和 `bindings` 在这里只为缩短示例而省略，真实结果会通过完整
schema 校验后返回。

截图和深度图通过 MCP `ImageContent` 返回；结构化观察只保留图片元数据，不重复 Base64。
`movement_feedback` 仅由前后两份公开玩家位置计算，便于判断短步是否实际移动或被门框阻挡，
不会公开碰撞体、节点或隐藏导航状态。

### 5.4 工具业务错误和 JSON-RPC 错误的区别

如果工具已经找到并执行，但业务输入不安全，例如 `observation_id` 已过期，本项目返回
成功的 JSON-RPC 响应，其中工具结果标记为错误：

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "stale_observation"
      }
    ],
    "structuredContent": {
      "status": "error",
      "code": "stale_observation"
    },
    "isError": true
  }
}
```

这表示：

- JSON-RPC 层成功找到了 `tools/call` 并返回结果；
- MCP 工具 `act` 的业务执行失败；
- 模型可以看到错误并依据它修正行为。

如果调用了不存在的 RPC 方法，才会使用 JSON-RPC 顶层 `error`：

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "error": {
    "code": -32601,
    "message": "Method not found"
  }
}
```

## 6. `ai_play` 中的 Python 文件

Python 包位于 `ai_play/src/ai_play/`。

### 6.1 `mcp_server.py`：MCP 门面

它创建 FastMCP 实例：

```python
mcp = FastMCP("Cogito AI Play", json_response=True)
```

然后用装饰器注册六个工具。教学 Host 使用显式 allowlist，只把前四个单局工具交给玩家模型：

```python
@mcp.tool()
async def briefing() -> CallToolResult:
    ...

@mcp.tool()
async def observe() -> CallToolResult:
    ...

@mcp.tool()
async def act(
    observation_id: ObservationIdInput,
    actions: ActionBatchInput,
) -> CallToolResult:
    ...

@mcp.tool()
async def stop() -> CallToolResult:
    ...

@mcp.tool()
async def workflow_memory_read() -> CallToolResult:
    ...

@mcp.tool()
async def workflow_memory_update(
    goal_pattern: PublicText,
    workflow: WorkflowInput,
    landmarks: LandmarksInput,
    avoid: AvoidInput,
) -> CallToolResult:
    ...
```

FastMCP 负责：

- MCP 初始化和能力声明；
- `tools/list`；
- 根据工具名路由 `tools/call`；
- 根据函数签名生成输入 schema；
- 解析参数并调用 Python 函数；
- 把 `CallToolResult` 编码成 MCP/JSON-RPC 响应；
- stdio 消息的读写与分帧。

项目代码负责：

- 工具的业务含义；
- 调用 `GameSession`；
- 把图片放入 `ImageContent`；
- 把公开 JSON 放入 `structuredContent`；
- 将 `SessionError` 转成模型可见的工具错误。

`main()` 依次执行：

```python
config = Config.from_env()
game_session = GameSession(config)
bridge = start(config, game_session)
mcp.run(transport="stdio")
```

退出时关闭 WebSocket Bridge，并唤醒仍在等待的会话操作。

### 6.2 `bridge_server.py`：Godot WebSocket 入口

这个文件启动另一个 Server，但它不是 MCP Server，而是项目内部的 WebSocket Server。

它只绑定 `127.0.0.1`，默认端口为 `8765`，并在后台线程中运行。Godot 是这个 WebSocket
连接的客户端。

#### 先简单理解 WebSocket

WebSocket 可以理解成两个已经在运行的程序之间建立的一条“持续双向通话线路”。

普通 HTTP 更像一问一答：

```text
Client ──请求──> Server
Client <──响应── Server
```

Server 通常要等 Client 请求后才响应。WebSocket 连接建立后，双方都可以随时主动发送
消息：

```text
Python  ── action_batch ──> Godot
Python  <── observation ─── Godot
Python  <─ action_results ─ Godot
Python  ── stop_request ──> Godot
Python  ─── end_game ─────> Godot
```

这里的 “WebSocket Server” 和 “WebSocket Client” 只表示连接如何建立：

- Python Server 在 `127.0.0.1:8765` 等待连接；
- Godot Client 主动连接 `ws://127.0.0.1:8765`；
- 连接成功后，Python 和 Godot 都能发送和接收消息。

它不表示 Python 只能发送响应，也不表示 Godot 只能发送请求。

WebSocket 底层使用一条持续存在的 TCP 连接。建立连接时会先完成 WebSocket 自身的 HTTP
Upgrade 握手；连接成功后，库会把数据组织成一条条文本或二进制消息。本项目只发送文本
消息，每条文本都是一个 JSON 对象，例如：

```json
{
  "type": "action_batch",
  "protocol_version": 4,
  "observation_id": 7,
  "actions": [
    {
      "type": "wait",
      "duration_ms": 50
    }
  ]
}
```

这层 JSON 不是 JSON-RPC，也不是 MCP。它是 Cogito 自己定义的游戏桥协议：

- 用 `type` 判断消息种类；
- 用 `protocol_version` 检查双方协议是否兼容；
- 用 `observation_id` 把动作、结果和观察关联成一个回合。

本项目使用 WebSocket，是因为 Python 和 Godot 是两个独立启动的进程，而且双方都需要
主动推送消息：

- Python 需要随时把 MCP 动作转发给 Godot；
- Godot 需要主动发送新截图、动作结果、Escape 停止和游戏终局；
- 一条持续连接可以保留当前控制会话，不必为每个动作重新建立连接。

它和 stdio 的差异可以概括为：

| 对比 | stdio MCP | Godot WebSocket Bridge |
| --- | --- | --- |
| 连接对象 | MCP Host 与 Python 子进程 | Python 与独立运行的 Godot |
| 怎样建立 | Host 启动子进程并连接标准流 | Python 监听端口，Godot 主动连接 |
| 消息协议 | MCP，编码为 JSON-RPC | Cogito 自定义 JSON 协议 v4 |
| 消息方向 | 双向 | 双向 |
| 本项目用途 | 发现和调用 MCP 工具 | 交换观察、动作、停止和终局 |
| 网络范围 | 本地进程管道，不使用端口 | 只允许 `127.0.0.1:8765` |

`127.0.0.1` 表示本机回环地址：数据只在当前电脑内部流动。项目禁止绑定
`0.0.0.0` 或局域网地址，避免其他机器连接游戏控制桥。

#### WebSocket 连接后的项目握手

WebSocket 连接本身建立后，Cogito 还会进行一次应用层握手。Godot 必须先发送：

```json
{
  "type": "hello",
  "protocol_version": 4,
  "scenario_id": "find_contract"
}
```

Python 校验后返回：

```json
{
  "type": "hello",
  "protocol_version": 4,
  "scenario_id": "find_contract"
}
```

要区分这两个步骤：

1. WebSocket Upgrade 握手确认“网络连接和 WebSocket 协议可用”；
2. `hello` JSON 确认“连接者理解 Cogito 游戏桥协议 v4，并声明当前玩法”。

如果 `hello` 缺失、超时、字段多余、版本不匹配或 `scenario_id` 未进入公开玩法
白名单，Python 会拒绝把这个连接挂到 `GameSession`。版本 4 客户端省略
`scenario_id` 时默认使用 `find_contract`。

连接正常时，一小段典型时序是：

```text
Python Bridge                     Godot
     │                              │
     │<── 建立 WebSocket 连接 ──────│
     │<── hello, v4, scenario ──────│
     │─── hello, v4, scenario ─────>│
     │<── observation 7 ────────────│
     │─── action_batch for 7 ──────>│
     │<── action_results for 7 ─────│
     │<── observation 8 ────────────│
```

如果连接断开，Python 会把会话标记为 `disconnected` 并唤醒正在等待的 MCP 调用；Godot
一侧也必须取消动作并释放持续按下的模拟输入。因此这条 WebSocket 连接不仅传数据，也代表
“当前 AI 控制会话仍然存活”。

#### `bridge_server.py` 具体负责什么

完成上述握手后，Python 接收：

- `observation`
- `action_results`
- `stop`
- `stop_ack`
- `game_over`

并向 Godot 发送：

- `action_batch`
- `stop_request`
- `end_game`（只由请求上限逻辑生成，不是 MCP 工具）

它还负责：

- 限制数据包大小；
- 拒绝非文本或非 JSON 对象；
- 精确检查字段集合；
- 验证内部协议版本；
- 一次只允许一个 Godot 控制器；
- 断线时调用 `GameSession.detach()`。

### 6.3 `game_session.py`：会话和回合状态机

这是 Python 端的核心。它不解析 MCP 报文，也不直接操作 WebSocket，而是维护 MCP 工具与
Godot 消息之间的共享状态：

```python
self._latest_observation
self._pending_observation_id
self._pending_results
self._pending_next_observation
self._game_over
self._stopped_result
self._act_request_count
self._request_limit_pending
self._state
```

主要状态流是：

```text
waiting_for_game
    │ Godot 完成握手
    ▼
waiting_for_observation
    │ 收到第一份 observation
    ▼
ready
    │ act()
    ▼
executing
    │ 收到 action_results 和下一份 observation
    ▼
ready

任意阶段还可能进入：
disconnected / stopping / stopped / game_over
```

它保证：

- `act` 必须使用最新 `observation_id`；
- 每个到达 `act()` 的调用先计数，因此过期观察、非法动作、上下文错误和并发请求也消耗
  额度；`briefing`、`observe`、`stop` 不计数；
- Godot 每次成功附加或重连时把计数清零；
- 一次只能有一个动作批次在途；
- 动作结果必须关联正在执行的观察；
- 下一份观察不能仍使用旧 ID；
- 等待有超时；
- 断线、停止和终局会唤醒正在等待的工具调用；
- 返回给调用者的是深拷贝，外部不能修改内部状态。

### 6.4 `action_schema.py`：动作白名单

这个文件校验 MCP Client 提交的 `actions`：

- 批次只能包含 1～3 个动作；
- 动作类型必须在白名单内；
- 字段必须精确匹配，不能多也不能少；
- 数值必须有限并位于安全范围；
- `interact` 必须是当前观察中可用的交互；
- `enter_digits` 和 `close_ui` 要求界面已打开；
- 改变上下文的动作必须位于批次最后；
- `probe_interaction` 和 `wait_next_window` 必须单独调用；
- `select_ingredient`、`undo`、`make` 和 `wait_next_window` 只允许在
  `conveyor_profit` 使用，食材 ID 还必须来自固定公开白名单。

Python 校验通过后 Godot 仍会再次校验。Python 是第一道边界，Godot 是输入执行的最终
权威。

### 6.5 `observation_schema.py`：公开观察边界

这个文件校验 Godot 送来的观察，并构造新的安全 DTO。它限制：

- 字段集合；
- `observation_id` 和时间戳；
- 玩家位置、朝向、速度和可选比例；
- 界面可见文本；
- 最多两个获准交互；
- 允许公开的运行时按键绑定；
- 动作结果；
- `conveyor_profit` 获准公开的 HUD 级窗口、托盘、收据和利润状态；
- 1024×576、最大 2 MiB 的 JPEG；
- 第一人称 3D 玩法可选的 1024×576、0.05～20 米 8 位线性深度 PNG，20 米外和背景为白色；
- `conveyor_profit` 不返回深度图，只返回截图和获准的 HUD 级状态。

`prepare_mcp_observation()` 还把图片 Base64 从结构化 JSON 中移除，返回：

```python
public_observation, image_bytes, depth_image_bytes
```

`mcp_server.py` 再把结构化数据放进 `structuredContent`，两张图片分别放进按固定顺序排列的
`ImageContent`。

### 6.6 `scenarios.py` 与 `briefing.py`：按白名单选择公开简报

`briefing()` 先等待 Godot 握手确定 `scenario_id`，再由 `scenarios.py` 从明确白名单
选择 loader。当前 `briefing.py` 返回 `find_contract` 经过人工筛选的：

- 任务背景；
- 目标和终局条件；
- 游玩规则；
- 物体类别说明；
- 固定参考图。

它不会把 `assets.json` 中的内部类名、资源路径、节点路径或谜题答案返回给 MCP Client。

### 6.7 `config.py`：有限配置

配置只包含：

- WebSocket host；
- WebSocket port；
- MCP 工具等待超时；
- stop 等待超时。

host 必须精确等于 `127.0.0.1`。这里没有模型名或 API Key，因为模型调用属于 Host，
不是 MCP Server。

### 6.8 `__init__.py`

目前它只是把目录标记为 Python 包，没有额外逻辑。

## 7. 为什么同时使用 asyncio 和线程

这里有两个不同的并发模型：

- FastMCP 工具函数是 `async def`，运行在 asyncio 事件循环中；
- `websockets.sync.server` 和 `GameSession` 使用同步线程与 `threading.Condition`。

`GameSession.observe()` 可能等待 Godot 的下一份观察：

```python
self._condition.wait(timeout=remaining)
```

如果直接在异步工具函数中调用它，就会阻塞整个 FastMCP 事件循环。因此
`mcp_server.py` 使用：

```python
result = await asyncio.to_thread(
    game_session.observe,
    config.wait_timeout_seconds,
)
```

可以理解为：

```text
FastMCP asyncio 主循环
    │
    ├─ 保持处理 MCP 消息
    │
    └─ 把阻塞的 GameSession 等待放到工作线程

WebSocket Bridge 后台线程
    │
    └─ 收到 Godot 消息后更新 GameSession 并 notify_all()
```

`threading.Condition` 让等待方在没有新消息时休眠，而不是不断轮询消耗 CPU。

## 8. 一次 `observe()` 的完整链路

Host 调用：

```python
result = await mcp_session.call_tool("observe", {})
```

逻辑链路是：

```text
ClientSession
  │ tools/call(name="observe")
  ▼
FastMCP
  │ 路由到 observe()
  ▼
mcp_server.observe()
  │ asyncio.to_thread(...)
  ▼
GameSession.observe()
  │
  ├─ 已有最新观察：立即返回
  └─ 尚无观察：Condition.wait()
                       ▲
                       │ WebSocket observation
                Godot Observer
```

Godot 送来的内部桥消息类似：

```json
{
  "type": "observation",
  "protocol_version": 4,
  "observation_id": 7,
  "captured_at_ms": 123456,
  "image": {
    "mime_type": "image/jpeg",
    "base64": "<JPEG Base64>",
    "width": 1024,
    "height": 576
  },
  "player": {},
  "interface": {},
  "bindings": {},
  "last_action_results": []
}
```

这里同样省略了嵌套对象的真实字段。`bridge_server.py` 检查外层字段，
`observation_schema.py` 检查完整内容，然后 `GameSession` 保存最新观察并唤醒等待者。

最终 `mcp_server.py` 把观察转换成 MCP `CallToolResult`，FastMCP 再生成与原请求具有相同
JSON-RPC `id` 的响应。

正常玩家只需在 `briefing` 后调用一次 `observe()`。成功的 `act()` 已同步返回下一份观察；
再次 `observe()` 只会取得当前缓存观察，通常会重复传输同一组图片。

## 9. 一次 `act()` 的完整链路

假设最新观察 ID 为 `7`。

### 第一步：MCP Client 调用工具

stdio 上的 MCP 请求：

```json
{
  "jsonrpc": "2.0",
  "id": 20,
  "method": "tools/call",
  "params": {
    "name": "act",
    "arguments": {
      "observation_id": 7,
      "actions": [
        {
          "type": "move",
          "forward": 1,
          "right": 0,
          "duration_ms": 100
        }
      ]
    }
  }
}
```

### 第二步：Python 校验当前回合

`GameSession.act()` 首先记录这次请求，然后检查：

- 当前不是 stopped、game_over 或 disconnected；
- 没有另一个动作批次在执行；
- 已收到观察；
- 请求的 ID 正是最新观察 ID；
- Godot WebSocket 仍可用。

然后 `action_schema.py` 检查动作本身。

如果 ID 已经过期，Python 返回 `stale_observation`，不会向 Godot 发送任何输入。
虽然没有产生输入，这次调用仍然计入 `AI_PLAY_MAX_ACT_REQUESTS`。默认配置上限是 150，
所有玩法的硬上限也统一为 150；如果通过环境变量收紧，则实际取两者较小值。

### 第三步：Python 发送内部桥消息

通过 WebSocket 发给 Godot：

```json
{
  "type": "action_batch",
  "protocol_version": 4,
  "observation_id": 7,
  "actions": [
    {
      "type": "move",
      "forward": 1,
      "right": 0,
      "duration_ms": 100
    }
  ]
}
```

此时 `GameSession` 进入 `executing`，并记录：

```text
pending_observation_id = 7
```

### 第四步：Godot 再次校验并执行

Godot 的 `AIPlayController` 验证消息字段、协议版本和观察 ID。`AIPlayExecutor` 再检查
动作并使用 COGITO 的常规输入系统执行。

这种“两端都校验”的原因是：跨进程数据始终被视为不可信，真正产生游戏输入的一端不能只
依赖 Python 已经检查过。

### 第五步：Godot 返回动作结果

```json
{
  "type": "action_results",
  "protocol_version": 4,
  "observation_id": 7,
  "results": [
    {
      "status": "completed",
      "type": "move"
    }
  ]
}
```

`GameSession.receive_action_results()` 要求这里的 ID 必须等于正在执行的 ID。

### 第六步：Godot 发送下一份观察

```json
{
  "type": "observation",
  "protocol_version": 4,
  "observation_id": 8,
  "...": "其余公开观察字段"
}
```

新观察不能继续使用 ID `7`。收到它后，`GameSession.act()` 完成本回合：

```text
观察 7
  → 针对观察 7 执行动作
  → 动作结果
  → 观察 8
```

### 第七步：返回 MCP 响应

Python 把动作结果、由观察 7 和 8 的公开位置差计算出的 `movement_feedback`、观察 8、截图
和深度图放进 `CallToolResult`。FastMCP 使用原请求 ID `20` 返回 JSON-RPC 响应。

因此对 MCP Client 来说，`act()` 是一次等待到“动作执行结束并得到下一观察”的同步工具
调用；内部实际上经历了多条 WebSocket 消息。Client 应直接用观察 8 规划下一步，不要再
调用 `observe()` 重传同一帧。

## 10. `stop`、Escape、断线和终局

### MCP `stop()`

MCP Client 调用 `stop` 后，Python 发给 Godot：

```json
{
  "type": "stop_request",
  "protocol_version": 4,
  "observation_id": 7,
  "reason": "mcp_stop"
}
```

Godot 取消正在执行的动作、释放模拟输入，并返回 `stop_ack`。重复调用 `stop()` 会返回
已保存的停止结果，不会再次产生输入。

### 物理 Escape

Escape 是 Godot 端的物理紧急停止键。它不需要先经过 MCP。Godot 会释放输入并向 Python
发送原因固定为 `escape_stop` 的 `stop` 消息。

### 断线

WebSocket 断开时：

- `bridge_server.py` 调用 `GameSession.detach()`；
- 在途回合被清理；
- 状态变为 `disconnected`；
- 等待中的 `observe()` 或 `act()` 被唤醒；
- Godot 端同样必须释放持续按下的模拟输入。

### 超时

`observe`、`act` 和 `stop` 都有有限超时。超时不会伪造成功结果，也不会允许
`pending_observation_id` 永久占住会话。

### 游戏终局

密码交互可以产生两组终局：

```text
success + correct_password
failure + wrong_password
```

此外，Python 会记录每个到达 `act()` 的请求。第 N 次请求仍先完成正常处理：

- 如果它产生 `success/correct_password` 或 `failure/wrong_password`，密码结果优先；
- 否则 Python 自动发送一次内部消息：

```json
{
  "type": "end_game",
  "protocol_version": 4,
  "observation_id": 8,
  "outcome": "failure",
  "reason": "max_requests"
}
```

这不是 MCP 工具，模型不能主动调用它。Godot 严格验证字段、结果组合和观察 ID，
然后复用原有终局路径：取消并释放输入、显示“达到最大步长”、暂停场景，再返回普通
`game_over/failure/max_requests`。如果当前确实没有观察，`observation_id` 可以是
`null`；否则必须匹配当前待决或在途观察。

达到上限后，后续 `act()` 不能继续派发。Godot 成功重连会清零计数；重启 MCP Server 或
重新进入 Lobby 也会建立新连接并清零。终局消息必须关联当前观察或在途回合，进入
`game_over` 后不能再提交动作。

## 11. 启动过程

`ai_play/start_ai.sh` 最终执行：

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m ai_play.mcp_server
```

进程内部的启动顺序是：

```text
1. Config.from_env()
2. 创建 GameSession
3. 在后台线程监听 127.0.0.1:8765
4. 在主线程运行 FastMCP stdio 循环
5. 等待 MCP Host 从 stdin 发来 initialize
6. 等待 Godot 连接 WebSocket Bridge
```

第 5、6 步的先后不必完全固定。`briefing()` 和 `observe()` 都会等待 Godot；前者等待
握手中的玩法 ID，后者等待第一份公开观察。

MCP Server 不会自动启动 Godot，也不会调用模型。通常应由 MCP Host 启动
`ai_play/start_ai.sh`，然后单独使用精确参数启动 Lobby：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=find_contract
```

## 12. 推荐的代码阅读顺序

第一次阅读建议按调用链，而不是按文件名字母顺序：

1. `ai_play/src/ai_play/mcp_server.py`
   - 找到四个 `@mcp.tool()` 和 `main()`。
2. `ai_play/tests/test_mcp_server.py`
   - 看 SDK Client 怎样执行 `list_tools()` 和 `call_tool()`。
3. `tutorial/ai_play_api_host.py`
   - 看真实 Host 怎样启动 stdio Server。
4. `ai_play/src/ai_play/game_session.py`
   - 重点阅读 `observe()`、`act()`、`stop()`。
5. `ai_play/tests/test_game_session.py`
   - 跟随一个观察 ID 从 7 变为 8。
6. `ai_play/src/ai_play/bridge_server.py`
   - 看 WebSocket 消息怎样路由到 `GameSession`。
7. `action_schema.py` 和 `observation_schema.py`
   - 理解两个信任边界。
8. `addons/cogito/AIPlay/ai_play_bridge.gd`
   - 看 Godot WebSocket 客户端。
9. `addons/cogito/AIPlay/ai_play_controller.gd`
   - 看观察、动作结果、停止和终局如何串联。
10. `ai_play_executor.gd` 和 `ai_play_observer.gd`
    - 最后进入具体输入执行和观察捕获。

## 13. 常见误解

### “MCP Server 就是模型后端”

不是。MCP Server 提供上下文或工具，模型由 Host 选择和调用。

### “stdio Server 需要监听一个端口”

不需要。stdio 使用子进程管道。`8765` 是 Python 与 Godot 的内部 WebSocket 端口，不是
MCP stdio 的端口。

### “`mcp.run()` 会启动 Godot”

不会。它只运行 MCP 消息循环。WebSocket Bridge 也只是等待 Godot 主动连接。

### “工具名就是 JSON-RPC method”

不是。调用所有 MCP 工具时，JSON-RPC method 都是 `tools/call`；工具名位于
`params.name`。

### “`protocolVersion` 和 `protocol_version` 是同一个值”

不是：

- MCP：`protocolVersion: "2025-11-25"`；
- Cogito 内部桥：`protocol_version: 4`。

它们属于不同协议层，不能互换。

### “返回 `isError: true` 就是 JSON-RPC 失败”

不是。它通常表示 JSON-RPC 请求成功完成，但工具业务执行失败。JSON-RPC 协议错误使用
顶层 `error`。

### “Python 校验过动作，Godot 就可以直接信任”

不可以。Godot 是输入执行的最终权威，跨进程数据必须在接收端再次验证。

## 14. 用几个问题检查自己是否理解

读完后，可以尝试回答：

1. 为什么 `print("debug")` 可能破坏 stdio MCP？
2. JSON-RPC 请求、通知和响应分别怎样通过 `id` 区分？
3. 为什么 MCP Client 调用的 method 是 `tools/call`，而不是 `act`？
4. `GameSession` 为什么要保存最新 `observation_id`？
5. `act()` 为什么使用 `asyncio.to_thread()`？
6. 为什么 MCP 工具调用只有一组请求响应，内部却可以有多条 WebSocket 消息？
7. 为什么 `briefing()` 必须等待 Godot 上报 `scenario_id`？
8. API Key 为什么应该在 Host，而不是 MCP Server 或 Godot 中？

如果能不看代码回答这些问题，就已经掌握了这个 MCP Server 的主要实现。

## 参考

- [MCP 架构概览](https://modelcontextprotocol.io/docs/learn/architecture)
- [MCP 版本说明](https://modelcontextprotocol.io/docs/learn/versioning)
- [MCP stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [MCP 生命周期](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
- [MCP Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [JSON-RPC 2.0 规范](https://www.jsonrpc.org/specification)
- [`ai_play/README.md`](../ai_play/README.md)
- [`docs/wiki/ai-play/system-guide.md`](../docs/wiki/ai-play/system-guide.md)
