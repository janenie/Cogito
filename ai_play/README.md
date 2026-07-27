# AI First Play MCP

AI First Play 提供本地 stdio MCP 入口：外部 AI 客户端负责观察和决策，Python 提供经过白名单筛选的公开游玩简报，并把回合工具调用转发给已显式启用的 Godot Lobby。黑盒 Codex 启动器则在可信侧启动同一服务的仅回环 Streamable HTTP 边车。Godot 仍是动作校验、输入执行、运行时观察公开范围和安全停止的最终权威。

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
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=find_contract
```

找钥匙玩法可普通启动，也可显式启用 AI：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=find_key

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=find_key
```

放书玩法同样可普通启动，也可显式启用 AI：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=put_book

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=put_book
```

先和 NPC 打招呼再进会议室的玩法同样可普通启动，也可显式启用 AI：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=greet_npc_meeting

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=greet_npc_meeting
```

日常清理玩法位于导入的 home daily routine 场景，也可普通启动或接入 AI：

```bash
godot --path . dailyroutine/scenes/home_daily_routine.tscn \
  -- --ai-play-scenario=daily_routine_cleanup

godot --path . dailyroutine/scenes/home_daily_routine.tscn \
  -- --ai-play --ai-play-scenario=daily_routine_cleanup
```

花园玩法位于导入的 garden 场景，也可普通启动或接入 AI：

```bash
godot --path . garden/scenes/garden_vertical_slice.tscn \
  -- --ai-play-scenario=garden_watering

godot --path . garden/scenes/garden_vertical_slice.tscn \
  -- --ai-play --ai-play-scenario=garden_watering
```

普通 Lobby 不会自动启用 AI；只有精确的用户参数 `-- --ai-play` 才会连接本地桥。MCP Server 不会自动启动、重启或关闭 Godot。
`--ai-play-scenario=<id>` 在同一 Lobby 中选择玩法脚本，省略时默认
`find_contract`。Godot 在 `hello` 中上报实际 ID，Python 只接受
`ai_play.scenarios` 白名单中的玩法，并使用同一 ID 选择公开简报。

## 黑盒 Codex 玩家连续 3 局

`tools/ai_play_codex_orchestrator.py` 用于让一个新的、受限的 Codex 会话连续游玩。可信侧
由 orchestrator 启动 MCP HTTP 边车与 Godot supervisor；玩家 Codex 只可发现
`cogito_ai_play` 的 `briefing`、`observe`、`act`、`stop`。游戏目标、规则和物体操作说明只从
`briefing` 返回，初始提示词、工作区、环境和临时配置均不包含玩法 ID、源码、日志或仓库路径。

首次使用前，在**专用认证目录**登录：

```bash
CODEX_HOME=~/.codex-cogito-player codex login
```

每次启动都必须显式指定模型与思考强度：

```bash
python3 tools/ai_play_codex_orchestrator.py \
  --runs 3 \
  --scenario find_contract \
  --model gpt-5.6 \
  --reasoning-effort high \
  --codex-auth-home ~/.codex-cogito-player
```

`--model` 与 `--reasoning-effort` 没有默认值；空白或控制字符会在启动子进程前被拒绝。
`--codex-auth-home` 默认是 `~/.codex-cogito-player`，只作为 `auth.json` 的来源：启动器既不
读取也不合并其中的 `config.toml`、MCP、插件、技能、记忆或会话。每局创建临时 `CODEX_HOME`，
仅复制该凭据、写入确定性配置，然后在所有退出路径删除它。

该临时配置固定模型/思考强度，唯一 MCP 为 `http://127.0.0.1:<mcp-port>/mcp`，并只允许四个
游玩工具；它关闭 Web 搜索、子代理、记忆、登录 shell 和模型生成命令的网络访问。不要传递旧的
`--codex-home`、`--sandbox`、`--approval-policy`、`--ws-host` 或 `--ws-port`：它们不是此启动器
接受的参数。在 Windows 上，该配置请求 Codex 的原生 `elevated` sandbox；无法建立该沙箱时应
修复本机 Codex/权限环境，而不是改用宽松配置。权限 profile 还显式拒绝模型生成命令读取本局
临时 `CODEX_HOME`。CLI 和 MCP OAuth 凭据存储均固定为 `file`，不会回退读取系统凭据库。

运行目录位于隔离的 `--session-root` 下。Windows 默认使用当前仓库所在驱动器根目录的
`cogito_ai_player_runs/`，非 Windows 默认使用 `/tmp/cogito_ai_player_runs/`；自定义根及其祖先
不得位于当前仓库内，也不得含 `.git`、`AGENTS.md` 或 `.codex/config.toml`。每局的布局为：

```text
<isolated-session-root>/
└── 20260726-170000/
    ├── player_workspace/   # 创建时为空；orchestrator 不写入游戏产物
    └── trusted_mcplogs/    # 仅可信 MCP 侧可见
```

`127.0.0.1:8765` 是 Godot 固定桥端口；`--mcp-port` 默认是独立的 `8766`，且不能使用 8765。
启动器会先检查两个端口空闲，启动可信 MCP 边车并等待 HTTP 与桥监听就绪，再启动 Codex，最后
启动 supervisor；任一进程异常、中断或退出都会终止其余进程。`--mcp-port` 可用于改变 HTTP
边车端口，但 Godot bridge 不能通过该启动器改端口。

这是本机 Codex 权限 profile 的硬化边界，不是容器、VM 或独立 Windows 用户级别的隔离，不能
抵抗同一 Windows 用户下的恶意本机进程。真实 Codex/Godot 多局验收会产生截图、令牌、费用和
本地轨迹持久化影响，必须另行得到用户确认；自动化测试不执行该验收。

如果只想手动启动玩家 Codex，再让程序管理 Godot，仍可直接运行 supervisor：

```bash
python3 tools/ai_play_supervisor.py --runs 3 --scenario find_contract
```

supervisor 每局启动的 Godot 命令等价于：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=find_contract --ai-play-exit-on-game-over
```

`--ai-play-exit-on-game-over` 只有在同一启动参数中包含精确的 `--ai-play` 时才会生效。
合法终局会输出固定标识：

```text
AI_PLAY_GAME_OVER outcome=<success|failure> reason=<reason>
```

supervisor 将带有该标识的进程退出计为一局完成；未看到标识的提前退出、超时或连接异常
按异常局处理并有限重试。若玩家 Codex 或人工 Escape 通过 MCP/Godot 停止控制，Godot
输出 `AI_PLAY disabled; reason=mcp_stop` 或 `AI_PLAY disabled; reason=escape_stop` 时，
supervisor 将本局记为 `failure/stopped` 并继续后续局数。跨局“自进化”只能发生在隔离
玩家 Codex 基于公开 MCP 结果做出的策略总结中。

无论是否启用 AI，`find_contract` 每次载入 Lobby 都会生成一个新回合：从 8 个日期和 8 个版本号候选中
各抽取一个值，随机选择 `MMDD + VV` 或 `VV + MMDD`，并从三条固定的三地点路线中
选择一条。玩家会在入口、大厅或 ARCHIVE 门外开始，任务卡位于出生点 1～2 米内。
任务卡只公开三个调查地点中的第一处，并说明密码为六位、记录可能是圆形 COGITO Hint、
实体文件或书本；第一、第二份记录再依次公开下一处地点。三份记录分别公开日期、版本号
和拼接顺序。CEO OFFICE 使用桌面上的 RippedPageA 外观可读文件；BREAK ROOM 使用电视柜
顶面的 RippedPageA 外观可读文件。这两个地点都不使用或移动悬浮 Hint。第三份记录读完前，
密码盘不会接受任何数字密码。任务卡和三份记录始终可以重复读取；提前发现后续记录不会
推进谜题进度，仍需按任务卡、第一份、第二份、第三份的顺序完成调查。
随机谜题属于游戏规则；`-- --ai-play` 只决定是否连接 MCP 和接受 AI 控制。回合随机
种子和生成答案只存在于 Godot 运行时，不进入 MCP 简报、观察或桥协议。

`find_key` 每局把场景中唯一的钥匙放到五类办公家具位置之一，任务卡只描述本局目标
位置的环境特征。游戏先选择钥匙位置，再从入口、大厅和 ARCHIVE 门外三个安全点中选择
与钥匙直线距离最远的出生点；任务卡仍位于出生点 1～2 米内。成功拾取钥匙产生
`success/key_picked_up`，该玩法没有答错失败。台式电脑桌、电视茶几和档案室沙发位置
使用 50 次请求硬上限，笔记本电脑桌和会议长桌位置使用 100 次请求硬上限。

`put_book` 每局从档案室初始可见的书中随机选择一本，将其他书隐藏，并把一个打开纸箱
以 50% 概率放在档案室地上靠近门口或远离门口的位置。玩家从档案室门口开始，门已打开，
任务卡位于出生点附近。成功把目标书放入目标纸箱产生 `success/book_in_box`。

`greet_npc_meeting` 每局让 NPC 沿会议室到休息室方向的既有路线循环移动，并随机选择
NPC 的路线起点、方向和三种问候语之一。玩家从入口开始，任务卡位于出生点附近。玩家必须
先在 1 米内和 NPC 交互打招呼，再进入会议室并关上会议室门，才会产生
`success/meeting_door_closed`。

`daily_routine_cleanup` 是家庭日常清理任务。玩家根据 HUD 目标和可见交互提示，把 4 个
散落垃圾和冰箱里的过期牛奶扔进客厅垃圾桶，确认冰箱关闭后点击垃圾桶旁边的完成按钮。
成功产生 `success/cleanup_complete`；任一完成条件未满足时提交会产生
`failure/cleanup_incomplete`，且不会公开具体缺少哪项条件。

`garden_watering` 是社区花园任务。玩家用 4 个满水壶浇完向日葵房和绣球花房各 2 块
草坪，并在 HUD 显示下雨期间按下兰花房门铃。成功产生
`success/garden_tasks_complete`；浇错草坪、按错门铃、在非下雨时按兰花房门铃或错过
下雨警报会产生 `failure/garden_task_failed`。

只有模型 API、没有现成 MCP Host 时，可参考
[`tutorial/ai_play_api_host.py`](../tutorial/ai_play_api_host.py)。该示例在本地启动
stdio Server，把 MCP 工具转换成 Responses API function tools，并转发结构化结果和图片；
完整运行步骤见 [`tutorial/README.md`](../tutorial/README.md)。

## MCP 工具

服务只注册四个游玩工具：

- `briefing()`：等待 Godot 握手确认玩法，再返回该玩法的公开目标、规则、物体操作说明
  和参考图谱；应在首个 `observe` 前调用一次。
- `observe()`：等待并返回最新获准观察、截图和当前 3D 画面的深度图。已有观察会立即返回；未连接、断线、停止或终局会返回对应状态。
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
`find_contract` 的硬上限为 500 次，终局为 `success/correct_password`、
`failure/wrong_password` 或 `failure/max_requests`；`find_key` 根据本局位置使用
50 或 100 次硬上限，公开 briefing 只说明最大值 100 次，
终局为 `success/key_picked_up` 或 `failure/max_requests`；`put_book` 的硬上限为 50 次，
终局为 `success/book_in_box` 或 `failure/max_requests`；`greet_npc_meeting` 的硬上限
为 100 次，终局为 `success/meeting_door_closed` 或 `failure/max_requests`；
`daily_routine_cleanup` 的硬上限为 150 次，终局为 `success/cleanup_complete`、
`failure/cleanup_incomplete` 或 `failure/max_requests`；`garden_watering` 的硬上限
为 300 次，终局为 `success/garden_tasks_complete`、`failure/garden_task_failed`
或 `failure/max_requests`。环境变量
`AI_PLAY_MAX_ACT_REQUESTS` 只能进一步收紧所选玩法的硬上限。第 N 次 `act` 仍会完成
正常处理：若它产生该玩法的合法终局，以该终局为准；否则 Python 通过仅内部可见的桥
消息请求 Godot 以 `failure/max_requests` 结束。模型不能直接调用这个内部终局操作。

## 结果与隐私边界

工具结果使用标准 MCP 多模态内容：结构化 JSON 包含简报、观察、动作结果和终局状态，
截图、深度图及参考图作为 `ImageContent` 单独返回，结构化 JSON 不重复图片 Base64。
观察成功时，`observe` 和 `act` 的图片顺序固定为截图 `image/jpeg`，再是深度图
`image/png`。结构化 `observation.image` 与 `observation.depth_image` 只保留元数据；
深度图固定为 768×432，`encoding` 为 `linear_depth_normalized_8bit`，并公开
`near_meters=0.05`、`far_meters=4000.0`。它是同视角不透明 3D 几何的归一化线性深度
可视化（近处较黑、远处/背景较白）；HUD、其他 2D UI 及透明物体没有独立的可靠深度。
`briefing` 只公开 `ai_play.scenarios` 白名单选中的 loader 所返回的目标、规则、物体操作
说明和固定参考图；`find_contract` 当前读取
`ai_play/assets/find_contract/imgs/reference_atlas.jpg`。它不会返回资产清单里的内部类名或
文件路径。回合工具只公开观察 schema 允许的玩家、界面、绑定、动作结果和截图。所有工具
都不会返回源码、节点路径、隐藏状态、谜题答案、测试、规格或计划事实。

启用 AI Play 后，MCP Server 会在 Godot 成功连接时开始保存本地游玩轨迹。日志只记录
`observe`、`act`、`stop` 的请求、获准公开的结构化结果和工具返回的截图 JPEG；深度 PNG
只在当前 MCP 响应中返回，不写入轨迹目录。不记录 `briefing`、图片 Base64、提示词、令牌、
模型上下文、隐藏状态或仓库文件。MCP Host 是否另行保存工具结果不属于本服务的控制范围。
终局时 Godot 可在本地显示结果画面，MCP 同步返回受限的终局状态。

## 本地轨迹日志

默认日志根目录是 `~/workspace/cogito_logs/mcplogs`。第一个 Godot 控制器成功连接时
在对应任务的 `scenario_id` 目录下创建 `YYYYMMDD-HH-MM` 运行目录；同一任务的同名
目录使用 `-02`、`-03` 等后缀，不会覆盖。一个运行目录最多分组同一任务的三次连接：

```text
mcplogs/
└── daily_routine_cleanup/
    └── 20260725-14-45/
        ├── run.json
        ├── attempt-01/
        │   ├── trajectory.json
        │   └── imgs/
        ├── attempt-02/
        └── attempt-03/
```

`run.json` 顶层重复保存经过验证的 `scenario_id`，每次尝试摘要包含 `status`、
`total_steps` 和 `terminal_reason`。任务终局保留公开的具体原因，例如
`cleanup_complete`、`cleanup_incomplete` 或 `max_requests`；停止路径使用
`mcp_stop`、`escape_stop`、`bridge_disconnected` 或 `mcp_shutdown`。

`trajectory.json` 顶层固定包含 `trajectory` 和 `result`。`result.total_steps` 统计终局前
所有到达 Python `act()` 函数的请求，包括随后被校验拒绝的请求；触发终局的请求计入，
终局后的请求不计入也不追加。`result.status` 是 `in_progress`、`success`、`failure`
或 `stopped`；`result` 不增加任务或终局原因字段。图片按事件序号、工具名和观察 ID
存在 `imgs/`，JSON 只保存相对路径。

日志器只负责记录和分组，不会自动重启 Godot、调用模型或生成复盘。把持久化截图再次
发送给真实模型会产生额外令牌、费用和隐私影响，仍需操作者单独确认。

## 安全与桥协议

- Python 与 Godot 只通过精确的 `127.0.0.1:8765` 通信，内部桥协议版本为 3。
- 一个 MCP 会话只允许一个 Godot 控制器；握手、包大小、JSON 对象、协议版本和消息字段都经过边界校验。
- `find_key` 的版本 3 `hello` 可携带仅内部使用的 `act_request_limit`，只接受整数
  `50` 或 `100`；旧 Godot 省略时默认 100，其他玩法不得携带。该字段不进入 MCP
  工具结果或轨迹日志，重连时必须与首次握手一致。
- Godot 会把 JSON 数值解析为浮点：Python 到 Godot 的协议版本接受非布尔且数值精确等于 `3` 的表示，并在桥内规范化为整数 `3`；有效的安全整数 `observation_id` 也会在发出信号或回复 `stop_ack`、`game_over` 前规范化为整数。字符串、布尔、非整数和越界 ID 仍会被拒绝。
- 请求计数属于当前 Python/Godot 桥连接；Godot 成功重连、重新进入 Lobby 或重启 MCP Server 都会清零。达到上限后，Python 只向 Godot 发送一次严格的 `end_game/failure/max_requests`，Godot 复用既有终局、输入释放和界面路径。
- Godot 断线、Python 退出、节点销毁、执行器取消和 `stop` 都必须释放 `forward`、`back`、`left`、`right`、`sprint` 等保持输入。
- Escape 始终是物理紧急停止键，优先于 MCP 控制；它发送 `escape_stop`，不会被普通输入或 MCP 工具禁用。
- 当前支持 `find_contract`、`find_key`、`put_book`、`greet_npc_meeting`、
  `daily_routine_cleanup` 和 `garden_watering` 的运行时终局事件和独立公开简报；
  不通过 MCP 提供场景源码、线索原文、密码、钥匙候选位置、书和箱子的随机选择、
  NPC 路线起点、NPC 路线方向、daily routine 或 garden 内部节点路径、随机下雨时间、
  随机种子或任务内部知识。

## 配置

默认配置不需要凭据：

```dotenv
AI_PLAY_WS_HOST=127.0.0.1
AI_PLAY_WS_PORT=8765
AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS=30
AI_PLAY_STOP_TIMEOUT_SECONDS=5
AI_PLAY_MAX_ACT_REQUESTS=500
AI_PLAY_LOG_ROOT=~/workspace/cogito_logs/mcplogs
```

桥地址只能是 `127.0.0.1`。请求上限必须是 `1..1000000` 的整数，并且只能收紧玩法
自身的 500、50/100、50、100、150、300 次硬上限；等待时间有界，日志根目录支持 `~`
展开且不能为空。
配置错误会写入 stderr；MCP stdout 只由 MCP
协议使用。

## 测试

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
bash tests/check_ai_play_start_script.sh
bash tests/check_ai_play_mcp_only.sh
```

Godot headless 回归命令见 [`docs/wiki/development/contributor-guide.md`](../docs/wiki/development/contributor-guide.md)。架构、协议和验收边界见 [AI Play MCP spec](../docs/scope/2026-07-23-ai-play-mcp/spec-ai-play-mcp.md)、[黑盒 Codex 玩家 spec](../docs/scope/2026-07-26-blackbox-codex-player/spec-blackbox-codex-player.md) 与 [AI First Play 系统指南](../docs/wiki/ai-play/system-guide.md)。
