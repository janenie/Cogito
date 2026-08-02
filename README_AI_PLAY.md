# Cogito：让 AI Agent 通过 MCP 游玩

Cogito 是一个基于 Godot 4.7 的第一人称沉浸式模拟游戏模板。本分支包含
AI First Play：外部 AI agent 通过本地 stdio MCP 服务观察并操作游戏，Godot
负责限制动作、执行输入、公开安全的运行时观察，并在异常时释放模拟输入。

当前黑盒游玩流程支持
`addons/cogito/DemoScenes/COGITO_3_Lobby.tscn` 中的 `find_contract` 和
`find_key`、`put_book`、`greet_npc_meeting`、`repair_lighting_circuit`、
`arrange_meeting_briefings`，以及导入到当前仓库的
`dailyroutine/scenes/home_daily_routine.tscn` 中的 `daily_routine_cleanup` 和
`garden/scenes/garden_vertical_slice.tscn` 中的 `garden_watering`，以及独立场景
`conveyor_profit/scenes/conveyor_profit_preview.tscn` 中的 `conveyor_profit`，共 9 个任务。
MCP 服务不会启动 Godot、不会调用模型，也不需要 API Key。

## 1. 准备环境

需要：

- Godot 4.7
- Python 3.10 或更高版本
- 支持本地 stdio MCP Server 的客户端
- 本仓库的本地检出目录

在仓库根目录创建 Python 虚拟环境。

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/pip install -r ai_play/requirements.txt
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ai_play\requirements.txt
```

## 2. 配置 MCP Host

AI First Play 使用 stdio：通常应由 Codex、Claude Desktop 或其他 MCP Host
启动 Python 服务，而不是把 `ai_play/start_ai.sh` 当作普通后台服务手动运行。
MCP 协议独占该进程的标准输入和标准输出。

MCP Server 注册六个工具。直接单局游玩的 Host 应只向玩家模型开放前四个：

- `briefing()`：在 Godot 握手确认玩法后，取得该玩法的公开目标、规则、物体操作说明和
  参考图；应在首次观察前调用一次。
- `observe()`：取得最新的获准观察和截图；通常只在 `briefing` 后调用一次。
- `act(observation_id, actions)`：基于最新观察执行 1～3 个动作，并等待动作结果、公开移动反馈
  和下一次观察；成功后无需再调用 `observe` 刷新画面。
- `stop()`：结束 MCP 控制会话并释放所有模拟输入；重复调用是安全的。
- `workflow_memory_read()`：读取当前编排器会话中已经通过校验的抽象流程记忆。
- `workflow_memory_update(...)`：只在可信终局后提交固定结构的流程候选。

仓库内的教学 Host 和下方 Codex 配置都显式限制为 `briefing`、`observe`、`act`、`stop`；
工作流记忆工具只供多局 orchestrator 使用。

MCP 的 `act` 输入声明会完整列出每种动作的精确字段、枚举、数值范围以及每批 1～3 个动作
的限制；Python 和 Godot 仍会分别再次校验。教学 OpenAI Host 还会把声明转换为
`strict=true` 且所有对象 `additionalProperties=false` 的 Responses function tools，并把
结构化结果、截图和深度图放在同一个 `function_call_output` 中。

配置中请使用仓库的绝对路径，并把下方的示例路径替换为本机路径。

### Codex

Codex 可以使用用户级 `~/.codex/config.toml`；信任本项目后也可以使用项目级
`.codex/config.toml`：

```toml
[mcp_servers.cogito_ai_play]
command = "/ABSOLUTE/PATH/TO/Cogito/ai_play/start_ai.sh"
cwd = "/ABSOLUTE/PATH/TO/Cogito"
startup_timeout_sec = 10
tool_timeout_sec = 40
enabled_tools = ["briefing", "observe", "act", "stop"]
```

修改配置后，重新启动 Codex 或新建会话。配置字段的当前说明见
[Codex MCP 文档](https://learn.chatgpt.com/docs/extend/mcp#configure-with-configtoml)。

### Claude Desktop

在 macOS 上，把下列内容合并进 Claude Desktop 的
`claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "cogito-ai-play": {
      "command": "/ABSOLUTE/PATH/TO/Cogito/ai_play/start_ai.sh"
    }
  }
}
```

Windows 配置使用虚拟环境中的 Python，并显式设置模块路径：

```json
{
  "mcpServers": {
    "cogito-ai-play": {
      "command": "C:\\ABSOLUTE\\PATH\\TO\\Cogito\\.venv\\Scripts\\python.exe",
      "args": ["-m", "ai_play.mcp_server"],
      "env": {
        "PYTHONPATH": "C:\\ABSOLUTE\\PATH\\TO\\Cogito\\ai_play\\src"
      }
    }
  }
}
```

常用配置文件位置：

- macOS：`~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows：`%APPDATA%\Claude\claude_desktop_config.json`

保存配置后重新启动 Claude Desktop。桌面应用启动 stdio 服务时工作目录可能不确定，
因此 `command` 和 `PYTHONPATH` 必须使用绝对路径。更多信息见
[MCP 本地服务接入文档](https://modelcontextprotocol.io/docs/develop/connect-local-servers)。

### 其他 stdio MCP Host

把以下可执行文件注册为本地 stdio MCP Server：

```text
/ABSOLUTE/PATH/TO/Cogito/ai_play/start_ai.sh
```

Windows Host 可以直接运行：

```text
C:\ABSOLUTE\PATH\TO\Cogito\.venv\Scripts\python.exe
```

并传入参数 `-m ai_play.mcp_server`，同时把 `PYTHONPATH` 设置为
`C:\ABSOLUTE\PATH\TO\Cogito\ai_play\src`。

### 只有模型 API 时

如果没有现成的 Codex 或 Claude Desktop，可以自行实现一个很薄的 MCP Host：
启动 stdio MCP Server、读取工具定义、把工具交给模型 API、执行模型请求的工具调用，
再把结果送回模型。仓库提供了可直接阅读和运行的 Python 示例：
[`tutorial/ai_play_api_host.py`](tutorial/ai_play_api_host.py)，使用说明见
[`tutorial/README.md`](tutorial/README.md)。

如果要让同一任务最多重玩 3 局，并在失败后重启 Godot、总结流程级错误、把改进策略带入
下一局，使用 [`tools/ai_play_codex_orchestrator.py`](tools/ai_play_codex_orchestrator.py)；完整
用法和隔离边界见 [`ai_play/README.md`](ai_play/README.md)。[`ai_host/`](ai_host/README.md)
仅保留用于兼容和实验。

## 3. 启动游戏

先让 MCP Host 启动 `cogito-ai-play` 服务，再从仓库根目录单独启动 Godot Lobby：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=find_contract
```

`find_key` 可以在普通模式下游玩，也可以接入 AI：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=find_key

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=find_key
```

`put_book` 也可以在普通模式下游玩，或接入 AI：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=put_book

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=put_book
```

`greet_npc_meeting` 也可以在普通模式下游玩，或接入 AI：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=greet_npc_meeting

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=greet_npc_meeting
```

`repair_lighting_circuit` 也可以在普通模式下游玩，或接入 AI：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=repair_lighting_circuit

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=repair_lighting_circuit
```

该任务要求玩家读取任务卡上的四组目标状态，通过往返观察推断入口面板 A～D 与入口、
CEO 办公室、大厅和休息室灯组的未知映射，找出一条跳闸线路，并在唯一一次断路器选择后
配置所有灯光、按 Verify 提交。映射、故障线路和回合种子只保存在可信 Godot 运行时，
不会进入 briefing、MCP 结果或玩家提示。

`arrange_meeting_briefings` 也可以在普通模式下游玩，或接入 AI：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=arrange_meeting_briefings

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=arrange_meeting_briefings
```

该任务要求玩家分别在 CEO 办公室、档案室和休息室读取三条关系线索，推断李明、王芳、
陈宇、赵宁与会议桌电视侧、门侧、电视对面侧、内墙侧的唯一对应关系。
资料可在提交前取回调整，Verify 只有一次机会。隐藏排列、候选解和线索生成过程只保存在
可信 Godot Monitor 中，不会进入 briefing、MCP 结果、玩家提示或日志。

`daily_routine_cleanup` 位于导入的日常清理场景，也可以在普通模式下游玩，或接入 AI：

```bash
godot --path . dailyroutine/scenes/home_daily_routine.tscn \
  -- --ai-play-scenario=daily_routine_cleanup

godot --path . dailyroutine/scenes/home_daily_routine.tscn \
  -- --ai-play --ai-play-scenario=daily_routine_cleanup
```

`garden_watering` 位于导入的花园场景，也可以在普通模式下游玩，或接入 AI：

```bash
godot --path . garden/scenes/garden_vertical_slice.tscn \
  -- --ai-play-scenario=garden_watering

godot --path . garden/scenes/garden_vertical_slice.tscn \
  -- --ai-play --ai-play-scenario=garden_watering
```

`--ai-play` 必须作为 Godot 用户参数精确传入：

- 第一个 `--` 把后续内容作为 Godot 用户参数传入游戏。
- `--ai-play` 显式启用 AI 控制。
- `--ai-play-scenario=<id>` 选择同一 Lobby 中的玩法脚本；省略时默认使用
  `find_contract`。ID 只允许小写 ASCII 字母、数字和下划线。
- `--ai-play-seed=<N>` 可选；外层 `ai_host` 多局运行时会自动为每局传入不同 seed。
  该 seed 只影响 Godot 运行时随机内容，不会进入 MCP 简报、观察或桥协议结果。

普通 Lobby 启动保持 AI 控制关闭。MCP 服务也不会自动启动、重启或关闭 Godot。
Godot 会在桥握手中上报实际玩法 ID，MCP 只接受 Python 白名单中注册的 ID，并据此
选择 `briefing()`；未知玩法和同一命令中重复的玩法参数都会被拒绝。

需要直接指定 Python 入口时，可以使用以下等价命令。

macOS / Linux：

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m ai_play.mcp_server
```

Windows PowerShell：

```powershell
$env:PYTHONPATH = "ai_play/src"
.\.venv\Scripts\python.exe -m ai_play.mcp_server
```

这些命令会进入 stdio MCP 协议循环，适合 MCP Host 配置或协议诊断，不是交互式
终端程序。

## 4. AI Agent 的标准游玩循环

连接成功后，agent 应严格按以下顺序行动：

1. 调用一次 `briefing()`，阅读公开任务说明和物体参考图；参考图不代表当前位置。
2. 调用 `observe()`。
3. 只有返回 `status: "ready"` 时才规划动作。
4. 只依据公开简报、当前截图、公开玩家状态、界面状态、按键绑定和动作结果决策。
5. 从 `observation.observation_id` 复制最新观察编号。
6. 调用 `act`，提交 1～3 个动作；同一时间只能有一个 `act` 调用。
7. 把 `act` 返回的新观察视为唯一的当前状态，然后重复第 3～6 步。
8. 收到 `game_over`、`stopped` 或 `disconnected` 后停止提交动作。
9. 放弃本次游玩、无法安全继续或需要退出时调用 MCP 工具 `stop()`。

每次进入 Python `act()` 的调用都会计入请求上限，即使观察编号过期、动作非法、上下文
不允许或已有动作在途；`briefing`、`observe`、`stop` 和工作流记忆工具不计数。
`find_contract` 的硬上限为 300 次，允许 `success/correct_password`、
`failure/wrong_password` 和
`failure/max_requests`；当前 `find_key` 每局使用 50 次硬上限，允许
`success/key_picked_up` 和 `failure/max_requests`；`put_book` 的硬上限为 150 次，允许
`success/books_in_ceo_office`、`failure/wrong_book_pickup` 和 `failure/max_requests`；
`greet_npc_meeting` 的硬上限为 100 次，
允许 `success/meeting_door_closed` 和 `failure/max_requests`；`daily_routine_cleanup`
的硬上限为 150 次，允许 `success/cleanup_complete`、`failure/cleanup_incomplete`
和 `failure/max_requests`；`garden_watering` 的硬上限为 300 次，允许
`success/garden_tasks_complete`、`failure/garden_task_failed` 和
`failure/max_requests`；`repair_lighting_circuit` 的硬上限为 100 次，允许
`success/circuit_repaired`、`failure/wrong_breaker`、
`failure/incorrect_circuit_configuration` 和 `failure/max_requests`。
`arrange_meeting_briefings` 的硬上限为 100 次，允许 `success/meeting_prepared`、
`failure/incorrect_seating_assignment` 和 `failure/max_requests`。
`find_key` 和 `greet_npc_meeting` 没有答错失败。
`AI_PLAY_MAX_ACT_REQUESTS` 只能收紧所选玩法的硬上限。第 N 次调用先按正常规则处理：
若产生该玩法的合法终局，以该终局为准，否则以 `failure/max_requests` 结束并显示
“达到最大步长”。Godot 成功重连、重新进入 Lobby 或重启 MCP Server 后计数清零。
`find_key` 只在内部版本 4 握手中发送经过验证的上限，不发送所选位置；Python 桥为兼容
旧 Godot 仍接受 50 或 100。该上限不进入 MCP 工具结果或轨迹日志，同一 MCP 会话重连时
必须保持一致。

最小的 `act` 参数示例：

```json
{
  "observation_id": 12,
  "actions": [
    {"type": "look", "direction": "left", "degrees": 15},
    {"type": "move", "forward": 0.4, "right": 0, "duration_ms": 100}
  ]
}
```

`observation_id` 必须来自最近一次返回的观察。不要猜测编号、复用旧编号或并行调用
`act`。

可以把下面这段规则加入 MCP Host 给游玩 agent 的指令：

```text
先调用一次 briefing，了解公开目标、玩法和物体参考；参考图不代表当前位置。
随后调用 observe，再使用最新 observation_id 调用 act；一次只进行一个 act 调用。
每次 act 已返回下一份观察；直接用其中的新截图、状态和 movement_feedback 重新规划，
不要重复调用 observe。只有 act 未返回观察且会话仍可继续时才再次 observe。
不得使用仓库源码、节点路径、测试、规格、
game_script、code_read 或任何隐藏的谜题答案。
若返回 game_over、stopped 或 disconnected，停止行动。
若无法安全继续，调用 MCP 的 stop 工具结束控制。
```

## 5. 允许的动作

每个动作对象只允许包含该动作规定的字段。

### 视角与移动

```json
{"type": "look", "direction": "left", "degrees": 15}
{"type": "look", "direction": "up", "degrees": 5}
{"type": "move", "forward": 0.4, "right": 0, "duration_ms": 100}
{"type": "sprint", "forward": 1, "right": 0, "duration_ms": 250}
{"type": "jump"}
{"type": "crouch"}
{"type": "wait", "duration_ms": 500}
```

- `look.direction`：`left`、`right`、`up`、`down`
- `look.degrees`：`1..45`；不要填写 `yaw`、`pitch` 或正负号
- `move` / `sprint` 的 `forward`、`right`：`-1..1`
- `move` / `sprint` 的 `duration_ms`：`50..250`
- `wait.duration_ms`：`50..2000`

动作 schema 不包含 `{"type":"stop"}`；需要结束控制时调用 MCP 工具 `stop()`。

### 交互与界面

```json
{"type": "interact", "action": "interact"}
{"type": "interact", "action": "interact2"}
{"type": "enter_digits", "digits": "1234"}
{"type": "close_ui"}
{"type": "probe_interaction", "target_x": 0.5, "target_y": 0.5}
```

- `interact.action` 只能是当前观察的
  `interface.available_interactions` 中实际提供的 `interact` 或 `interact2`。
- `enter_digits` 只能在界面打开时使用，`digits` 必须是 1～6 位 ASCII 数字。
- `close_ui` 只能在界面打开时使用。
- `probe_interaction` 只能在界面关闭时使用；坐标是截图中的归一化位置，两个轴都在
  `0..1` 范围内。
- `probe_interaction` 必须单独构成一个动作批次。

### 批次规则

- 每次 `act` 必须提交 1～3 个动作。
- `interact`、`enter_digits`、`close_ui` 会改变上下文，必须是批次的最后一个动作。
- 非法批次会被 Python 拒绝，不会向 Godot 注入输入；Godot 还会再次验证合法批次。

## 6. 状态与常见问题

MCP 结果的常见状态：

- `ready`：可以使用所附最新观察继续行动。
- `game_over`：Demo 已产生成功或失败终局，不再调用 `act`。
- `stopped`：AI 控制已经停止。
- `disconnected`：Godot 控制器已经断开。
- `error`：工具调用被安全拒绝；检查返回的 `code`。

常见错误处理：

- `observation_timeout`：确认使用了精确的 Lobby 启动命令，并等待 Godot 完成连接。
- `disconnected` / `transport_unavailable`：确认 Godot 仍在运行，并且双方端口都是
  `8765`。
- `stale_observation`：使用最近一次工具结果中的 `observation_id`，必要时重新调用
  `observe`。
- `action_in_flight`：等待当前 `act` 返回，不要并发调用。
- `controller_busy`：已有另一个启用 AI Play 的 Lobby 连接；关闭多余实例。
- 动作字段或上下文错误：对照当前 `interface`、可用交互和本页数值范围，不要重试同一个
  非法批次。

默认桥配置为：

```dotenv
AI_PLAY_WS_HOST=127.0.0.1
AI_PLAY_WS_PORT=8765
AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS=30
AI_PLAY_STOP_TIMEOUT_SECONDS=5
AI_PLAY_MAX_ACT_REQUESTS=500
AI_PLAY_LOG_ROOT=~/workspace/cogito_logs/mcplogs
```

服务器只接受精确的数字回环地址 `127.0.0.1`，不要改成局域网地址、`0.0.0.0`
或公网地址。请求上限只接受 `1..1000000` 的整数。日志根目录支持 `~` 展开且不能为空。

Godot 成功连接后，MCP Server 会在日志根目录的
`<scenario_id>/<YYYYMMDD-HH-MM>/` 下创建运行目录，并在 `attempt-01` 至
`attempt-03` 中保存 `trajectory.json` 和 `imgs/`。同一运行只包含一个任务；
`run.json` 保存任务 ID、尝试状态、步数和终局原因。轨迹只包含 `observe`、`act`、
`stop` 的获准公开请求与结果；图片以 JPEG 文件保存，JSON 不包含 Base64。运行日志
只负责记录，不会自动重启游戏或让模型复盘。

## 7. 安全与隐私

- 键盘上的物理 Escape 始终是紧急停止键：它会取消当前动作、释放模拟输入并停止 AI
  控制。
- Godot 断线、无效数据、Python 退出和相关节点销毁也会释放保持中的移动输入。
- Agent 只能接收获准公开的简报和运行时观察。简报不包含内部类名、节点路径、线索原文、
  密码或正确解谜顺序；其他仓库文件和隐藏状态不能进入 MCP 结果或 agent 提示。
- `game_script/`、`code_read/`、测试、规格和计划是开发资料，绝不能成为游玩 agent
  的输入。
- MCP 服务端会把获准公开的工具轨迹和截图保存到 `AI_PLAY_LOG_ROOT`；它不保存
  `briefing`、提示词、令牌、模型上下文、隐藏状态或仓库文件。MCP Host 仍可能有自己
  的持久化策略。
- 未经操作者明确确认截图、令牌、费用和本地轨迹影响，不要运行真实外部模型验收。

## 8. 开发与验证

协议和实现细节：

- [AI First Play MCP 说明](ai_play/README.md)
- [AI First Play 系统指南](docs/wiki/ai-play/system-guide.md)
- [开发协作与验证命令](docs/wiki/development/contributor-guide.md)

与启动流程最相关的本地检查：

```bash
bash tests/check_ai_play_start_script.sh
bash tests/check_ai_play_mcp_only.sh
bash tests/check_ai_play_arrange_meeting_briefings_monitor.sh
git diff --check
```

修改公开协议、环境变量、控制方式、隐私行为或日志布局时，还必须同步更新
`ai_play/README.md`、对应 Wiki 和测试。
