> 摘要：本目录维护 AI First Play 的系统架构、安全边界和跨语言契约。

# AI First Play

## 页面

- [`system-guide.md`](system-guide.md)：系统职责、通信方式、安全边界和跨层契约。

## 当前入口

AI First Play 当前通过本地 stdio MCP Server 接入外部 AI 客户端。操作者先启动
Python MCP 进程，再用精确的 `-- --ai-play` 参数启动 `COGITO_3_Lobby.tscn`；
普通 Lobby 启动保持 `auto_start = false`。外部 AI 通过四个工具获取简报并控制回合：

- `briefing`：读取经过白名单筛选的公开目标、规则、物体操作说明和参考图谱。
- `observe`：读取获准的结构化运行时状态和截图。
- `act`：携带最近观察 ID，提交 1～3 个安全动作，并同步获取动作结果和下一次观察。
- `stop`：请求取消当前动作并释放模拟输入；实体 Escape 仍是物理紧急停止键。

Godot 接收 JSON 时会把数值规范化为浮点；桥将数值精确等于 `2` 的非布尔协议版本和有限安全整数观察 ID 规范化为内部整数，保证 Python 侧的严格回合关联与 `stop_ack` 契约。

首版只覆盖 `find_contract` Demo，不自动启动 Godot、不调用内置模型，也不在服务端
持久化截图、令牌或游玩轨迹。完整契约和安全边界见
[`system-guide.md`](system-guide.md)。

## 来源

本页的当前入口来自已批准的
[`AI Play MCP spec`](../../scope/2026-07-23-ai-play-mcp/spec-ai-play-mcp.md)。
