# AI First Play MCP

AI First Play 现在是一个本地 stdio MCP 服务：外部 AI 客户端负责观察和决策，Python 只负责把 MCP 工具调用转发给已显式启用的 Godot Lobby。Godot 仍是动作校验、输入执行、观察公开范围和安全停止的最终权威。

## 快速启动

在仓库根目录创建 Python 环境并安装依赖：

```bash
python3 -m venv .venv
.venv/bin/pip install -r ai_play/requirements.txt
```

终端 1 启动 stdio MCP Server（由 MCP Host 负责连接其标准输入/输出）：

```bash
ai_play/start_ai.sh
```

终端 2 单独启动 Godot Lobby：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn -- --ai-play
```

普通 Lobby 不会自动启用 AI；只有精确的用户参数 `-- --ai-play` 才会连接本地桥。MCP Server 不会自动启动、重启或关闭 Godot。

## MCP 工具

服务只注册三个游玩工具：

- `observe()`：等待并返回最新获准观察。已有观察会立即返回；未连接、断线、停止或终局会返回对应状态。
- `act(observation_id, actions)`：提交 1～3 个动作，`observation_id` 必须是最近观察的 ID。调用同步等待 Godot 返回动作结果和下一次观察，或返回终局/停止状态。
- `stop()`：发送固定原因 `mcp_stop`，请求取消当前动作、释放模拟输入并结束 MCP 控制会话；重复调用安全幂等。

动作批次使用现有安全白名单：

- `look`：`yaw` 在 -45～45，`pitch` 在 -30～30。
- `move` / `sprint`：`forward`、`right` 在 -1～1，`duration_ms` 在 50～1000。
- `jump`、`crouch`、`stop`、`close_ui`、`wait`；`wait.duration_ms` 在 50～2000。
- `interact` 只能使用当前观察中可用的 `interact` 或 `interact2`；`enter_digits` 只能在界面打开时输入 1～6 位 ASCII 数字。
- `probe_interaction` 只能单独使用，目标坐标各在 0～1，且界面必须关闭。

Python 会先校验批次，Godot 会再次校验。上下文变化动作必须是批次最后一个动作；非法批次不会产生 Godot 输入。

## 结果与隐私边界

工具结果使用标准 MCP 多模态内容：结构化 JSON 包含观察、动作结果和终局状态，截图作为 `ImageContent` 单独返回，结构化 JSON 不重复图片 Base64。只公开观察 schema 允许的玩家、界面、绑定、动作结果和截图；不会把源码、节点路径、隐藏状态、谜题答案、测试、规格或计划事实放进 MCP 结果。

服务端不保存截图、令牌、提示词、模型上下文、记忆或游玩轨迹。MCP Host 是否保存工具结果不属于本服务的控制范围。终局时 Godot 可在本地显示结果画面，MCP 同步返回受限的终局状态。

## 安全与桥协议

- Python 与 Godot 只通过精确的 `127.0.0.1:8765` 通信，内部桥协议版本为 2。
- 一个 MCP 会话只允许一个 Godot 控制器；握手、包大小、JSON 对象、协议版本和消息字段都经过边界校验。
- Godot 断线、Python 退出、节点销毁、执行器取消和 `stop` 都必须释放 `forward`、`back`、`left`、`right`、`sprint` 等保持输入。
- Escape 始终是物理紧急停止键，优先于 MCP 控制；它发送 `escape_stop`，不会被普通输入或 MCP 工具禁用。
- 首版只支持 `find_contract` Lobby 的运行时终局事件；不通过 MCP 提供场景源码或任务内部知识。

## 配置

默认配置不需要凭据：

```dotenv
AI_PLAY_WS_HOST=127.0.0.1
AI_PLAY_WS_PORT=8765
AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS=30
AI_PLAY_STOP_TIMEOUT_SECONDS=5
```

桥地址只能是 `127.0.0.1`。等待时间有界，配置错误会写入 stderr；MCP stdout 只由 MCP 协议使用。

## 测试

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
bash tests/check_ai_play_start_script.sh
bash tests/check_ai_play_mcp_only.sh
```

Godot headless 回归命令见 [`docs/wiki/development/contributor-guide.md`](../docs/wiki/development/contributor-guide.md)。架构、协议和验收边界见 [已批准 Spec](../docs/scope/2026-07-23-ai-play-mcp/spec-ai-play-mcp.md) 与 [AI First Play 系统指南](../docs/wiki/ai-play/system-guide.md)。
