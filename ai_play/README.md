# AI First Play MCP

AI First Play 现在是一个本地 stdio MCP 服务：外部 AI 客户端负责观察和决策，Python 提供经过白名单筛选的公开游玩简报，并把回合工具调用转发给已显式启用的 Godot Lobby。Godot 仍是动作校验、输入执行、运行时观察公开范围和安全停止的最终权威。

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

只有模型 API、没有现成 MCP Host 时，可参考
[`tutorial/ai_play_api_host.py`](../tutorial/ai_play_api_host.py)。该示例在本地启动
stdio Server，把 MCP 工具转换成 Responses API function tools，并转发结构化结果和图片；
完整运行步骤见 [`tutorial/README.md`](../tutorial/README.md)。

## MCP 工具

服务只注册四个游玩工具：

- `briefing()`：返回 `find_contract` 的公开目标、规则、物体操作说明和参考图谱。它不需要 Godot 连接，可在首个 `observe` 前调用一次。
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

每个到达 Python `act()` 函数的请求都会消耗一次请求额度，包括过期观察、非法动作、
上下文不允许和已有动作在途等被拒绝的调用；`briefing`、`observe`、`stop` 不计数。
默认第 500 次 `act` 仍会完成正常处理：如果它产生密码正确或错误终局，以密码结果为准；
否则 Python 通过仅内部可见的桥消息请求 Godot 结束游戏，并返回
`failure/max_requests`。模型不能直接调用这个内部终局操作。

## 结果与隐私边界

工具结果使用标准 MCP 多模态内容：结构化 JSON 包含简报、观察、动作结果和终局状态，截图及参考图作为 `ImageContent` 单独返回，结构化 JSON 不重复图片 Base64。`briefing` 只公开 `ai_play.briefing` 中经过筛选的目标、规则和物体操作说明，并读取固定的 `ai_play/assets/find_contract/imgs/reference_atlas.jpg`；它不会返回资产清单里的内部类名或文件路径。回合工具只公开观察 schema 允许的玩家、界面、绑定、动作结果和截图。所有工具都不会返回源码、节点路径、隐藏状态、谜题答案、测试、规格或计划事实。

服务端不保存截图、令牌、提示词、模型上下文、记忆或游玩轨迹。MCP Host 是否保存工具结果不属于本服务的控制范围。终局时 Godot 可在本地显示结果画面，MCP 同步返回受限的终局状态。

## 安全与桥协议

- Python 与 Godot 只通过精确的 `127.0.0.1:8765` 通信，内部桥协议版本为 3。
- 一个 MCP 会话只允许一个 Godot 控制器；握手、包大小、JSON 对象、协议版本和消息字段都经过边界校验。
- Godot 会把 JSON 数值解析为浮点：Python 到 Godot 的协议版本接受非布尔且数值精确等于 `3` 的表示，并在桥内规范化为整数 `3`；有效的安全整数 `observation_id` 也会在发出信号或回复 `stop_ack`、`game_over` 前规范化为整数。字符串、布尔、非整数和越界 ID 仍会被拒绝。
- 请求计数属于当前 Python/Godot 桥连接；Godot 成功重连、重新进入 Lobby 或重启 MCP Server 都会清零。达到上限后，Python 只向 Godot 发送一次严格的 `end_game/failure/max_requests`，Godot 复用既有终局、输入释放和界面路径。
- Godot 断线、Python 退出、节点销毁、执行器取消和 `stop` 都必须释放 `forward`、`back`、`left`、`right`、`sprint` 等保持输入。
- Escape 始终是物理紧急停止键，优先于 MCP 控制；它发送 `escape_stop`，不会被普通输入或 MCP 工具禁用。
- 首版只支持 `find_contract` Lobby 的运行时终局事件和公开简报；不通过 MCP 提供场景源码、线索原文、密码或任务内部知识。

## 配置

默认配置不需要凭据：

```dotenv
AI_PLAY_WS_HOST=127.0.0.1
AI_PLAY_WS_PORT=8765
AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS=30
AI_PLAY_STOP_TIMEOUT_SECONDS=5
AI_PLAY_MAX_ACT_REQUESTS=500
```

桥地址只能是 `127.0.0.1`。请求上限必须是 `1..1000000` 的整数；等待时间有界，
配置错误会写入 stderr；MCP stdout 只由 MCP 协议使用。

## 测试

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
bash tests/check_ai_play_start_script.sh
bash tests/check_ai_play_mcp_only.sh
```

Godot headless 回归命令见 [`docs/wiki/development/contributor-guide.md`](../docs/wiki/development/contributor-guide.md)。架构、协议和验收边界见 [已批准 Spec](../docs/scope/2026-07-23-ai-play-mcp/spec-ai-play-mcp.md) 与 [AI First Play 系统指南](../docs/wiki/ai-play/system-guide.md)。
