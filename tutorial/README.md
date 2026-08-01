# 用 OpenAI API 实现最小 MCP Host

[`ai_play_api_host.py`](ai_play_api_host.py) 是一个最小的本地 MCP Host 示例。它会：

1. 通过 stdio 启动 `ai_play/start_ai.sh`。
2. 从 MCP Server 读取 `briefing`、`observe`、`act`、`stop` 的工具定义。
3. 把这些定义转换成 `strict=true`、封闭对象的 OpenAI Responses API function tools。
4. 执行模型发出的工具调用，并把 MCP 返回的 JSON 和图片关联到同一个
   `function_call_output` 后送回模型。
5. 重复上述循环，直到 agent 结束、游戏结束或达到回合上限。

MCP Server 还注册了供多局 orchestrator 使用的两个工作流记忆工具；本示例使用显式
allowlist，不会把它们交给单局玩家模型。

API Key 只由这个 Host 读取，不会传给 MCP Server 或 Godot。

## 运行前须知

运行这个示例会产生真实 API 费用，并把公开游戏简报、游戏截图、公开状态和工具结果发送给
OpenAI。示例使用 `store=true` 和 `previous_response_id` 维持长回合上下文，服务端保留
行为取决于账户的数据控制与适用政策。终端还会打印工具参数和结构化结果，但示例本身不会
写入本地日志文件。请在理解这些影响后再运行。

## 安装

在仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/pip install -r tutorial/requirements.txt
```

设置 API Key；也可以通过 `OPENAI_MODEL` 改用账户有权访问的视觉模型：

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5.6"
```

不要把 Key 写入仓库文件。

## 运行

先关闭任何手动启动的 `ai_play/start_ai.sh`，因为这个 Host 会自行启动一份 MCP
Server，而 `127.0.0.1:8765` 同一时间只能有一个监听者。

从仓库根目录运行：

```bash
.venv/bin/python tutorial/ai_play_api_host.py
```

看到 `MCP 已连接` 后，另开一个终端启动游戏：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=find_contract
```

看到游戏窗口后，回到 Host 终端按 Enter。Agent 会先调用 `briefing()` 和一次
`observe()`；后续每次 `act()` 自带下一份观察，不再为同一帧重复调用 `observe()`。

按 `Ctrl-C` 可以中止 Host。Godot 中的物理 `Escape` 键始终是紧急停止方式。

默认最多进行 200 个模型回合，避免无界消耗 API。可在启动前调整：

```bash
export AI_PLAY_MAX_AGENT_TURNS=300
```

这是教学示例，不包含 Web UI、用户审批、重试、持久化、用量统计或生产级日志。
Responses API 原生的 MCP tool 目前面向具有 `server_url` 的远程 Streamable HTTP /
HTTP-SSE 服务；本项目是本地 stdio MCP，因此示例在本地读取 MCP 工具，再通过
function calling 把它们交给模型。

参考：

- [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI MCP and Connectors](https://developers.openai.com/api/docs/guides/tools-connectors-mcp)
