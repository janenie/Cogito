# AI First Play MCP

AI First Play 提供本地 stdio MCP 入口：外部 AI 客户端负责观察和决策，Python 提供经过白名单筛选的公开游玩简报，并把回合工具调用转发给已显式启用的 Godot Lobby。黑盒 Codex 启动器则在可信侧启动同一服务的仅回环 Streamable HTTP 边车。Godot 仍是动作校验、输入执行、运行时观察公开范围和安全停止的最终权威。

## 快速启动

在仓库根目录创建 Python 环境并安装依赖：

```bash
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r ai_play/requirements.lock.txt
```

`requirements.lock.txt` 固定黑盒基准依赖及哈希，并以 Python 3.10 为最低目标；仅在更新依赖
范围时使用 `uv pip compile ai_play/requirements.txt --python-version 3.10 --generate-hashes
--output-file ai_play/requirements.lock.txt` 重新生成该锁文件。

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

未知照明电路修复玩法同样可普通启动，也可显式启用 AI：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=repair_lighting_circuit

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=repair_lighting_circuit
```

会议席位与资料分发玩法同样可普通启动，也可显式启用 AI：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=arrange_meeting_briefings

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=arrange_meeting_briefings
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

回转带利润玩法位于独立经营场景，也可普通启动或显式接入 AI：

```bash
godot --path . conveyor_profit/scenes/conveyor_profit_preview.tscn \
  -- --ai-play-scenario=conveyor_profit

godot --path . conveyor_profit/scenes/conveyor_profit_preview.tscn \
  -- --ai-play --ai-play-scenario=conveyor_profit
```

`conveyor_profit` 的白名单 `briefing` 会返回墙上同样可见的十道固定菜谱，包括十六种食材
ID、成本、完整配方、基础售价和基础净利润，并公开每道菜整局最多成功制作两次的规则。
每轮 `observation.conveyor.market` 只公开五类菜品的精确当前需求倍率，以及前九轮各两条
指向下一轮涨跌方向的自然语言线索；线索可能强化或冲突。客户端必须根据截图识别当前可见
食材，按当前倍率重算售价，并根据 accepted 收据自行维护次数。每局还会在
`observation.conveyor.contracts` 公开三份第 3、6、10 窗截止的分类合同及其奖励、违约金和
状态；合同结算进入 `net_profit`，隐藏在线基准使用同一套合同约束。当前窗口的结构化食材清单、
可行菜、缺失食材、累计次数表、未来倍率与供给、内部脚本标识和绝对目标金额仍不公开。

循环楼梯异常玩法位于独立场景，实验室推理玩法位于 Cogito Laboratory 场景；两者也可普通启动：

```bash
godot --path . addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn \
  -- --ai-play-scenario=loop_staircase_anomaly

godot --path . addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn \
  -- --ai-play --ai-play-scenario=loop_staircase_anomaly

godot --path . addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn \
  -- --ai-play-scenario=laboratory_experiment

godot --path . addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn \
  -- --ai-play --ai-play-scenario=laboratory_experiment
```

普通 Lobby 不会自动启用 AI；只有精确的用户参数 `-- --ai-play` 才会连接本地桥。MCP Server 不会自动启动、重启或关闭 Godot。
`--ai-play-scenario=<id>` 在同一 Lobby 中选择玩法脚本，省略时默认
`find_contract`。Godot 在 `hello` 中上报实际 ID，Python 只接受
`ai_play.scenarios` 白名单中的玩法，并使用同一 ID 选择公开简报。

## 黑盒模型玩家连续多局

### Codex

`tools/ai_play_codex_orchestrator.py` 用于让一个新的、受限的 Codex 会话连续游玩。可信侧
由 orchestrator 启动 MCP HTTP 边车与 Godot supervisor；玩家 Codex 只可发现
`cogito_ai_play` 的 `briefing`、`workflow_memory_read`、`observe`、`act` 和
`workflow_memory_update`。传入 `--workflow-memory disabled` 时，黑盒玩家只获准使用
`briefing`、`observe` 和 `act`，可用于同一分支上的无结构化 AWM 对照。游戏目标、规则和物体操作说明只从
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
并通过 `developer_instructions` 给两种模式加载相同的黑盒视觉权限：模型应像人类玩家一样遵循
`briefing` 规则，并比较当前与本会话先前 `observe` 或 `act` 直接返回的截图，以画面变化推断相对位移、
转向、遮挡和地标关系。若公开规则要求先读出生点附近任务卡，玩家会在离开出生区前优先扫描、
靠近并探测可见的悬浮标志、纸张或文件。高优先级指令会进一步说明任务卡是细杆
底座上的青绿色/蓝绿色同心发光圆环标志，而不是普通纸张。玩家必须保持在出生区，以 45 度扇区
扫描最多 360 度；如果首帧已经显示该标志，则不启动整圈扫描，而是用 5–15 度微调和短步靠近，
并避免把附近门的 `Open` 提示误判为读卡提示。每次确认新截图后再继续，找到标志便对准并探测，读卡后才能离开。
该权限不允许读取或保存磁盘截图、轨迹、仓库内容或隐藏状态。
隔离玩家的网络 profile 只允许字面量 `127.0.0.1`，用于连接编排器启动的本机 MCP HTTP
边车，并为大小写代理变量显式设置回环 `NO_PROXY`；不允许公网域名，也不启用宽泛的本地网络访问。
仅复制该凭据、写入确定性配置，然后在所有退出路径删除它。

该临时配置固定模型/思考强度，唯一 MCP 为 `http://127.0.0.1:<mcp-port>/mcp`，并只允许上述
五个工具；它关闭 Web 搜索、子代理、Codex 内建记忆、登录 shell 和模型生成命令的公网访问。
不要传递旧的
`--codex-home`、`--sandbox`、`--approval-policy`、`--ws-host` 或 `--ws-port`：它们不是此启动器
接受的参数。在 Windows 上，该配置请求 Codex 的原生 `elevated` sandbox；无法建立该沙箱时应
修复本机 Codex/权限环境，而不是改用宽松配置。权限 profile 还显式拒绝模型生成命令读取本局
临时 `CODEX_HOME`。CLI 和 MCP OAuth 凭据存储均固定为 `file`，不会回退读取系统凭据库。

运行目录位于隔离的 `--session-root` 下。Windows 默认使用当前仓库所在驱动器根目录的
`cogito_ai_player_runs/`，非 Windows 默认使用 `/tmp/cogito_ai_player_runs/`；自定义根及其祖先
不得位于当前仓库内，也不得含 `.git`、`AGENTS.md` 或 `.codex/config.toml`。每次 orchestrator
会话的目录名同时标明玩家、模型、玩法和 AWM 模式；模型等动态参数会先转换为不含路径分隔符的
安全目录组件，完整原值仍保存在 `session.json`。同秒同配置的后续会话追加 `-02`、`-03` 等
序号。布局为：

```text
<isolated-session-root>/
└── 20260726-170000__codex__gpt-5.6__find_contract__awm/
    ├── session.json        # 0600；安全的运行描述，不含凭据或环境变量
    ├── player_workspace/   # 创建时为空；orchestrator 不写入游戏产物
    ├── godot_environment/  # 隔离的 Godot 用户、应用数据与临时目录
    └── trusted_mcplogs/    # 仅可信 MCP 侧可见
```

`session.json` 的 v2 结构记录上述身份与时间字段、基准 cycle seed 和逐局实际 seed（传送带
任务另含 draw index）、Git 可用性、commit/脏状态、Python 与 MCP/Pydantic/WebSockets 版本、Godot 与
玩家 CLI 版本，以及端口、重试和超时等纯数值执行配置。Claude 和 Kimi 入口使用相同布局，例如
`20260726-170000__claude__claude-opus-5__find_contract__awm/` 与
`20260726-170000__kimi__kimi-code_kimi-k3__find_contract__awm/`。该文件不得记录 API key、
auth token、settings/auth 路径、子进程环境或完整启动命令。
在会话目录不处于可读 Git 工作树时，`repository.available` 为 `false`，无法取得的 `commit`
与 `dirty` 为 `null`，不会把“无法检测”误记成干净工作树。

Godot supervisor 使用该隔离环境写入 `user://`、着色器缓存和临时场景状态，不继承主机凭据
环境。

`127.0.0.1:8765` 是 Godot 固定桥端口；`--mcp-port` 默认是独立的 `8766`，且不能使用 8765。
启动器会先检查两个端口空闲，启动可信 MCP 边车并分别用 HTTP/TCP 与完整 WebSocket 握手等待
监听就绪，再启动 Codex，最后
启动 supervisor；任一进程异常、中断或退出都会终止其余进程。所有子进程连续 600 秒没有输出时，
`--idle-timeout-seconds` 看门狗会以退出码 5 收束卡死会话。supervisor 正常结束后，orchestrator
默认再给 Codex 30 秒（`--codex-final-grace-seconds`）消费终局、更新 AWM 并输出总结，然后才清理
边车。`--mcp-port` 可用于改变 HTTP 边车端口，但 Godot bridge 不能通过该启动器改端口。

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

orchestrator 和 supervisor 会按白名单解析场景：`daily_routine_cleanup` 使用家庭场景，
`garden_watering` 使用花园场景，`conveyor_profit` 使用独立经营场景，
`loop_staircase_anomaly` 使用循环楼梯场景，`laboratory_experiment` 使用实验室场景，
其余六个任务使用 Lobby。
未知 scenario 即使显式传入 `--scene` 也会在创建运行目录或启动 Godot 前被拒绝。

`--ai-play-exit-on-game-over` 只有在同一启动参数中包含精确的 `--ai-play` 时才会生效。
不含 `--ai-play` 的手动试玩不会隐式开启 AI 或终局自动退出；任务结束后可点击
“退出游戏（Esc）”或按物理 Escape 退出当前 Godot 进程。该终局快捷键不接受 AI 合成输入。
合法终局会输出固定标识：

```text
AI_PLAY_GAME_OVER outcome=<success|failure> reason=<reason>
```

supervisor 将带有该标识的进程退出计为一局完成；未看到标识的提前退出、超时或连接异常
按异常局处理并有限重试。控制器因协议或执行错误输出的其他 `AI_PLAY disabled` 也属于异常局，
supervisor 会终止该 Godot 并重试，而不是让玩家永久等待断开的观察。若玩家 Codex 或人工 Escape 通过 MCP/Godot 停止控制，Godot
输出 `AI_PLAY disabled; reason=mcp_stop` 或 `AI_PLAY disabled; reason=escape_stop` 时，
supervisor 返回 `stopped` 并立即中止整次多局运行，不重试也不把它计为任务失败。桥断开、
MCP shutdown、超时和没有正式终局的提前退出属于异常，只重试同一个有效局次；重试耗尽后以
退出码 2 收束。跨局“自进化”只能发生在隔离
玩家 Codex 基于公开 MCP 结果做出的策略总结中。

### Codex + Gemini（Yibu Responses）

`tools/ai_play_codex_gemini_orchestrator.py` 复用上面的 Codex harness、可信 MCP 边车、Godot
supervisor、空玩家工作区和 AWM，只把 Codex 的模型 provider 切换为 Yibu 的 Responses API。
默认模型是 `gemini-3.6-flash`，默认连续运行三局 `find_contract`，不设置也不接受
`--reasoning-effort`：第三方模型是否支持该 Codex 参数不能从模型名安全推断，运行元数据中因此
固定记录 `reasoning_effort: "none"`。

凭据默认从仓库根目录中已忽略的 `opus.py` 读取，也可用 `--yibu-credentials` 指定其他文件。
入口只用 Python AST 读取字面量 `ak` 字典，不导入或执行该文件；`ak["key"]` 必须为非空字符串，
`ak["url"]` 必须是 HTTPS URL，且路径为空或 `/v1`。空路径会规范化为 `/v1`。API key 只以
`YIBU_API_KEY` 注入 Codex 玩家进程；Codex 的 `shell_environment_policy` 不把它传给模型生成的
命令。key、凭据文件路径和玩家环境都不会写入 `config.toml`、`session.json`、可信 MCP 日志或
启动命令。临时 `CODEX_HOME` 只含本局生成的 `0600` 配置，退出时删除，不读取或复制
`auth.json`，也不需要 `codex login`。

```bash
.venv/bin/python tools/ai_play_codex_gemini_orchestrator.py \
  --runs 3 \
  --scenario find_contract \
  --model gemini-3.6-flash \
  --yibu-credentials ./opus.py \
  --workflow-memory enabled
```

临时 Codex 配置使用 `model_provider = "yibu"` 和 `wire_api = "responses"`。由于 Codex 当前会把
MCP 工具作为 Responses `namespace` 容器发送，而兼容 provider 可能只返回无 namespace 的普通
`function_call`，编排器先启动一个受信任的回环 Responses 代理（默认 `127.0.0.1:18767`）。Codex
只连接这个代理；代理通过已验证的 HTTPS `/v1/responses` 转发到 Yibu，并且只对当前启用的
Cogito MCP 工具补上缺失的 `mcp__cogito_ai_play` namespace。它不修改参数或工具结果，不记录请求、
响应、图片或 key，并随编排器在正常退出、中断和失败路径中终止。可用
`--provider-proxy-port` 改用其他空闲回环端口。

模型生成的工具/命令仍受既有玩家权限 profile 限制，只能访问字面量回环地址，不能借此进行 Web
搜索或访问公网。Yibu API key 仍只注入 Codex 玩家进程，并由 Codex 的 provider 请求以 HTTP
Authorization 经过本机代理转发；代理进程环境、命令和配置均不含 key。临时配置还显式关闭 Codex 的 shell、
unified exec、apps、plugins、subagents、goals、tool suggestions 和本地图片工具，避免第三方模型
偏离到非游戏工具；玩家只保留白名单 AI Play MCP 工具。若当前 Codex 尚无该模型的内建 metadata，
CLI 可能显示 fallback metadata 警告，但不会因此启用 reasoning effort。真实 Gemini/Godot
验收仍会产生截图、令牌、费用和本地轨迹，必须单独获得用户确认；自动化测试只使用伪凭据和
伪进程，不调用 Yibu 或启动游戏。

### Claude Code

`tools/ai_play_claude_orchestrator.py` 已按
[`Claude AI Player spec`](../docs/scope/2026-08-04-claude-ai-player/spec-claude-ai-player.md)
实施。它保留 Codex 入口，并通过 `tools/ai_play_orchestrator_common.py` 复用可信 MCP HTTP 边车、
Godot supervisor、隔离运行目录、玩家提示词、进程监控和失败收束；Claude 专用层只处理 settings
白名单、临时认证配置和 CLI 参数。

可信编排器从操作者指定的 `.claude/settings.local.json` 提取白名单 Claude 服务环境变量，写入
本局私有临时配置；玩家进程不读取源 settings，也不获得其仓库路径。Claude 在空目录中使用
`--bare`、`--print`、`--no-session-persistence`、`--strict-mcp-config` 和显式工具白名单启动，
不加载仓库指令、skills、plugins、hooks、agents 或其他 MCP Server。workflow memory 启用时只
开放五个玩家工具，禁用时只开放 `briefing`、`observe`、`act`，两种模式都排除 `stop`。

Claude Code 2.1.212 不会把 MCP tool result 中的 `ImageContent` 交给模型。Claude 入口因此把
已经过同一公开投影的参考图、彩色观察和可选深度图原子写入本局私有临时目录，并在
`approved_image_paths` 中返回对应绝对路径。玩家额外只开放内建 `Read`，其 allowlist 精确限制为
该图片目录；不能读取源 settings、轨迹、仓库或其他本地文件。目录权限为 `0700`，图片权限为
`0600`，会话退出时随 Claude 临时配置一并删除；这些临时路径不写入可信轨迹日志。其他 MCP
客户端继续直接使用标准 `ImageContent`，默认不启用磁盘图片导出。

源 settings 的 `env` 只允许 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN`、
`ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL`、`ANTHROPIC_SMALL_FAST_MODEL`、
`CLAUDE_CODE_AUTO_COMPACT_WINDOW` 和 `CLAUDE_CODE_MAX_CONTEXT_TOKENS`；必须提供前两个凭据之一，
自定义 base URL 必须使用 HTTPS。后两个变量只用于显式约束第三方 Claude Code 兼容模型的
上下文压缩阈值与最大窗口，不会放宽玩家工具或文件权限。模型和 effort 没有默认值：

```bash
python3 tools/ai_play_claude_orchestrator.py \
  --runs 3 \
  --scenario find_contract \
  --model claude-opus-5 \
  --effort high \
  --claude-settings .claude/settings.local.json
```

`--effort` 只接受 `low`、`medium`、`high`、`xhigh` 或 `max`。真实 Claude/Godot 多局验收仍须另行确认截图、令牌、
费用和本地轨迹持久化影响；自动化测试不得使用真实凭据或发起模型请求。

Claude 以退出码 0 提前结束、但 supervisor 尚未收到正式终局时，orchestrator 会在同一 MCP/AWM
会话内启动恢复 turn；恢复 turn 先读取 workflow memory、briefing 和当前 observation，再继续游玩。
`--claude-max-restarts` 默认 8，用于限制恢复次数和费用；非零 Claude 退出码仍立即失败收束。
`observation_id` 既不是 act 请求计数，也不是完成局数，只有工具返回的正式 `game_over` 才计入一局。

### Kimi Code

`tools/ai_play_kimi_orchestrator.py` 为 Kimi Code CLI 提供同样的可信 MCP 边车、Godot
supervisor、隔离运行目录、AWM 和失败收束。`--kimi-home` 默认指向仓库中已被 Git 忽略的
`.kimi-code/`；入口只把其中通过 TOML 校验的 `config.toml` 复制到本局 `0700` 临时
`KIMI_CODE_HOME`，副本权限为 `0600`，正常或异常退出都会删除。模型玩家不会获得源配置路径，
API key 不进入命令参数、进程环境、`session.json`、MCP 协议或可信日志。为避免把可执行配置带入
黑盒会话，源配置只允许 provider/model、thinking、loop、MCP timeout、token counting 和 identity
等纯数据节；hooks、插件目录、额外 agent/skill 目录和其他未批准顶层节会在创建运行目录前拒绝。

Kimi 在空 `player_workspace` 中用 `--prompt` 非交互运行。orchestrator 使用内部 stdin runner
转交提示词，因此完整提示词不会出现在父进程启动日志中。每局生成显式 `--agent-file`：启用 AWM
时只允许 `briefing`、`workflow_memory_read`、`observe`、`act`、
`workflow_memory_update`，禁用时只允许前三个基础玩家工具；两种模式都排除 `stop`、内建文件、
shell、Web、skill 和子代理工具。Kimi 0.34.0 的 print mode 禁止把 `--prompt` 与
`--auto`/`--yolo` 组合；入口因此不传这两个旗标，而是在临时 `config.toml` 中为每个获准 MCP
工具写入精确的 `[[permission.rules]] decision = "allow"`，不使用服务器级通配符。临时
`mcp.json` 只连接 `http://127.0.0.1:<mcp-port>/mcp`，Kimi 沿用 MCP 标准
`ImageContent`，不会获得 Claude 专用图片交换目录。

先用同一配置目录确认 API key 可用并查看服务实际返回的模型别名，再显式传给 orchestrator：

```bash
KIMI_CODE_HOME="$PWD/.kimi-code" kimi provider list

.venv/bin/python tools/ai_play_kimi_orchestrator.py \
  --runs 3 \
  --scenario find_contract \
  --model kimi-code/kimi-k3 \
  --effort high \
  --kimi-home .kimi-code
```

示例别名以 `kimi provider list` 的实际输出为准；`[1m]` 不是 Kimi Code CLI 的模型名后缀，
Kimi K3 的上下文窗口由服务返回的模型配置决定。`--model` 与 `--effort` 必填，K3 effort 只接受
`low`、`high`、`max`。Kimi 正常提前退出而 supervisor 尚无正式终局时，入口保持同一 MCP/AWM
会话并启动恢复 turn；`--kimi-max-restarts` 默认 8。Kimi 自身 session/wire 轨迹只存在于本局临时
home 并随退出删除，可信 MCP 截图与轨迹仍保存在隔离 `--session-root`。真实 Kimi/Godot 验收会
发送截图、消耗令牌或配额并持久化可信轨迹，仍须操作者单独确认；自动化测试不读取真实配置、
不发起模型请求。

### 会话级 Agent Workflow Memory

同一次 orchestrator 多局运行共享 MCP sidecar 进程内的 `SessionWorkflowMemory`。每局先调用
`briefing`，再调用 `workflow_memory_read`，随后才用 `observe`/`act` 游玩；终局后调用一次
`workflow_memory_update` 提交固定结构的抽象流程。服务端依据 `GameSession` 的真实终局决定
晋升范围：成功局可以合并 workflow、地标关系和避坑规则，正常失败局只能合并避坑规则，
并可额外提交一个 `failure_review`：

```json
{
  "stage": "接近目标并准备交互",
  "bottlenecks": ["在相似交互物之间反复判断"],
  "optimizations": ["先组合验证环境名称与目标物特征"]
}
```

服务端把可信终局原因注入已存 review 的 `terminal_reason`，模型不能提供或覆盖该字段。review
必须包含 1 个 stage、1～3 个 bottlenecks 和 1～4 个 optimizations；旧客户端省略 review
仍有效。memory 最多保留最近 3 个规范化后不同的失败复盘，重复项不刷新顺序。成功局携带
非空 review 会整笔拒绝，不会部分晋升其他字段；
stopped、disconnected、MCP shutdown、异常退出和未终局局次不学习，也不计入
`completed_runs`；disconnected、shutdown 和其他基础设施异常由 supervisor 重试且不占用
`--runs` 的有效局次数，stopped 则中止整次运行。调用方不能自行声明胜负。

下一局读取 `failure_reviews` 后，玩家必须用最新 briefing 和观察判断哪些优化仍适用，公开说明
证据以及它们如何改变当前计划，不适用的建议必须忽略。要观察这条生产/消费链，至少要在同一
orchestrator 进程中运行两局，且前一局确实产生合格失败；不得为了测试而制造或伪造失败。

AWM 只保存经过严格字段、长度和内容校验的语言化程序性记忆。运行时截图可以作为玩家提炼经验
的依据，但 memory 不保存图片、图片引用、Base64、embedding、逐帧动作、坐标、随机密码或其他
本局答案。两个 AWM 工具不接入 `TrajectoryLogger`，其请求和结果不进入 `trajectory.json`、
`run.json` 或其他文件；MCP sidecar 退出后 memory 自然消失，下一次 orchestrator 不会加载。
Codex 配置中的 `[memories]` 仍保持禁用。

无论是否启用 AI，`find_contract` 每次载入 Lobby 都会生成一个新回合：从 8 个日期和 8 个版本号候选中
各抽取一个值，随机选择 `MMDD + VV` 或 `VV + MMDD`，并从三条固定的三地点路线中
选择一条。玩家会在入口、大厅或 ARCHIVE 门外开始，任务卡位于出生点 1～2 米内。
这是解谜任务，第一步一定要先找到并读取任务卡；在读到任务卡之前，不要开始寻找合同记录、
猜测地点顺序或尝试密码。任务卡只公开三个调查地点中的第一处，并说明密码为六位、记录可能是圆形 COGITO Hint、
实体文件或书本；第一、第二份记录再依次公开下一处地点。三份记录分别公开日期、版本号
和拼接顺序。CEO OFFICE 使用桌面上的 RippedPageA 外观可读文件；BREAK ROOM 使用电视柜
顶面的 RippedPageA 外观可读文件。这两个地点都不使用或移动悬浮 Hint。第三份记录读完前，
密码盘不会接受任何数字密码。任务卡和三份记录始终可以重复读取；提前发现后续记录不会
推进谜题进度，仍需按任务卡、第一份、第二份、第三份的顺序完成调查。
随机谜题属于游戏规则；`-- --ai-play` 只决定是否连接 MCP 和接受 AI 控制。回合随机
种子和生成答案只存在于 Godot 运行时，不进入 MCP 简报、观察或桥协议。

`find_key` 是六区域合同时间线排除题。MAIN LOBBY、CEO OFFICE、ARCHIVE、MEETING ROOM、
BREAK ROOM 和 CUBICLE AREA 各有一把外观相同的钥匙；三把位于收纳处，三把位于桌面。
CEO OFFICE、MEETING ROOM、CUBICLE AREA 的三份历史记录和三名如实回答的 NPC 共同描述
合同从三个月前初稿、会议前一日上午审查稿、会议前一日下午
`FINAL v1.0 / PREPARED FOR SUBMISSION` 到董事会会议开始（12:00）前
`v1.1 / SUBMITTED` 的变化。玩家需辨别 FINAL 与真正提交状态，向最终经手人确认当前
四位密码。密码输入满四位后立即验证：错误时显示“密码不对”并允许重新输入，不产生终局；
正确时解锁并打开档案室。提交错误钥匙产生 `failure/security_lockout`，提交当前钥匙才产生
`success/key_picked_up`。每局使用 100 次请求硬上限。

三个受维护的 orchestrator 默认使用相同的 `--benchmark-cycle-seed=20260809`，也可显式改为
0～1000000000。supervisor 从任务、cycle 和逻辑局次确定 `--ai-play-round-seed=N`；异常重试
复用原命令。`find_key` 连续四次逻辑尝试使用同一 cycle 的四个对齐种子，确定性覆盖四套脚本
且不放回；`conveyor_profit` 固定供给 seed，仅递增可信 draw index。逐局 seed 写入可信
`session.json`，启动日志把参数值替换为 `REDACTED`；seed、脚本 ID、NPC 映射、生成密码和正确
答案不得进入 MCP 简报、观察、hello、玩家轨迹或其他工具结果。
种子参数只接受单个 `0..9007199254740991` 十进制整数；空值、符号、非数字、越界值和重复参数
都会被拒绝。命令行 seed `0` 会确定性映射到非随机内部种子；只有未提供 CLI seed 时，各玩法
原有的导出值 `0` 才可继续表示普通游玩的随机初始化。

`put_book` 在档案室内彼此分开的三组书架上设置九个作者标定槽位，并以种子确定的均衡方式选择六个位置：
每组书架两本、低中高三层各两本。书本上方不显示悬浮身份标记；玩家靠近并对准书本后，
通过画面 HUD 显示的“任务书”或“普通书”判断身份，再一次搬运一本，按低层、中层、高层
顺序把三本任务书送到 CEO OFFICE 的同一个书籍放置点。该玩法会适度放宽近距离书本交互
命中，目标楼梯及办公室入口使用公开英文导视，CEO OFFICE 门保持打开；这些辅助不公开
书籍身份、随机布局或结构化路线。拿起普通书
或顺序错误的任务书会立即产生 `failure/wrong_book_pickup`；三本依序送达才产生
`success/books_in_ceo_office`。该玩法的请求硬上限为 100，仍可通过
`AI_PLAY_MAX_ACT_REQUESTS` 进一步收紧。

`greet_npc_meeting` 使用三名穿不同颜色上衣、沿三条固定路线移动的同事：蓝衣 H. Voss 沿
MAIN LOBBY—BREAK ROOM—SOFA，绿衣 M. Chen 从 CEO OFFICE 门外经过楼梯上层、
中段和下层，橙衣 R. Diaz 沿 CUBICLE AREA—MAIN LOBBY—BREAK ROOM。任务卡和简报公开这三条
路线；每局随机选择正确联系人、两种会议室内会面区域和三种问候语之一。玩家从入口开始，任务卡
位于出生点附近并按姓名与上衣颜色指定联系人。问候正确联系人后，对方通过可见提示告知本局
区域并开始带路；玩家与联系人都到达后，从室内关门才产生 `success/meeting_door_closed`。
第一次问候错误同事仍可恢复，同一人不会重复计数；第二次问候另一名错误同事产生
`failure/wrong_npc_limit`。

`repair_lighting_circuit` 每局随机生成入口控制面板 A～D 与入口、CEO 办公室、大厅和
休息室四组灯的一对一映射、一个跳闸线路以及初始和目标状态。玩家从控制面板附近开始，
读取任务卡上的目标后通过往返观察推断映射；只有一次断路器选择机会，选错会产生
`failure/wrong_breaker`。复位后须把四组灯配置到目标状态并按 Verify；正确时产生
`success/circuit_repaired`，否则产生 `failure/incorrect_circuit_configuration`。
映射、故障线路和回合种子只存在于可信 Godot 运行时，不进入 briefing、MCP 结果或玩家提示。

`arrange_meeting_briefings` 每局随机生成李明、王芳、陈宇、赵宁到会议桌电视侧、
门侧、电视对面侧和内墙侧的一对一排列，以及三条合并后唯一、缺少任意一条都不唯一的关系
线索。线索分别写入 CEO 办公室、档案室和休息室的世界内记录。玩家调查后把四份可搬运资料
单击拿起；拿取后资料会稳定贴近视角，无需持续按住或手动旋转。资料可吸附到对应席位，
提交前可以取回调整；一次性 Verify 正确时产生
`success/meeting_prepared`，缺失或摆错时产生 `failure/incorrect_seating_assignment`。
隐藏排列、候选解集合、线索分配和回合种子只存在于可信 Godot Monitor，不进入 briefing、
MCP 结果、玩家提示或轨迹日志。

`daily_routine_cleanup` 是家庭日常清理任务。玩家根据 HUD 目标和可见交互提示，把 4 个
散落垃圾和冰箱里的过期牛奶扔进客厅垃圾桶，确认冰箱关闭后点击垃圾桶旁边的完成按钮。
成功产生 `success/cleanup_complete`；任一完成条件未满足时提交会产生
`failure/cleanup_incomplete`，且不会公开具体缺少哪项条件。

`garden_watering` 是社区花园任务。玩家用 4 个满水壶浇完向日葵房和绣球花房各 2 块
草坪，并在约 10 分钟现实时间的下雨期间按下兰花房门铃。成功产生
`success/garden_tasks_complete`；浇错草坪、按错门铃、在非下雨时按兰花房门铃或错过
下雨警报会产生 `failure/garden_task_failed`。

`conveyor_profit` 是十窗口经营任务。每个 60 秒窗口固定显示 16 盘食材，每个窗口只允许
制作一次；成功、非法组合和次数超限的 MAKE 都会锁定窗口。同一道菜整局最多成功制作两次；
第三次正确提交返回 `recipe_limit_exceeded`，扣除食材成本但没有收入。AI 使用
`select_ingredient`、`make` 和 `wait_next_window`，无需模拟相机或鼠标；选入托盘的食材不可
撤销，错误组合只能通过 `make` 消耗并锁定当前窗口，窗口到期时未提交的托盘也会按成本报废。
等待模型期间 Godot 暂停窗口时钟。每局三份公开分类合同分别在第 3、6、10 窗截止，按截止前 accepted
菜品类别结算奖励或违约金并计入净利润；在线策略基准也必须满足这些合同。十个窗口结束时，
达到隐藏在线策略基准的 90% 产生
`success/efficiency_target_reached`，否则产生 `failure/efficiency_below_target`。

`loop_staircase_anomaly` 是五轮累计证据调查任务。真人玩家在 2F 到 9F 之间用 Up/Down
切换楼层，每轮收齐八个房间的截图后才能推进；每轮只新增一条可见线索，旧线索继续保留。
部分证据位于不同墙面和初始视野盲区，briefing 推荐 AI 进入每层后用 `look(yaw,pitch)`
环顾，并用 `front/back/left/right` 的小步或普通步绕开遮挡；单张初始截图可能无法覆盖
该楼层的全部证据。
Tab 打开调查板后，Up/Down 选择楼层行，Space 只切换玩家自己的候选标记；调查板不自动
比较、计数或判断正误。第五轮关闭调查板后，Space 提交当前楼层。成功产生
`success/correct_floor_selected`，选错产生 `failure/wrong_floor_selected`。

`laboratory_experiment` 是随机实验回路任务。玩家读取 HUD 上的目标、环境和公开条件，
搬运并安装电池、样本、处理模块和金属棒，再根据公开测量反馈调整组合。只有完整配置才
消耗机会；三次内成功产生 `success/experiment_completed`，三次均失败产生
`failure/experiment_attempts_exhausted`。随机种子、材料隐藏属性和正确答案不公开。

只有模型 API、没有现成 MCP Host 时，可参考
[`tutorial/ai_play_api_host.py`](../tutorial/ai_play_api_host.py)。该示例在本地启动
stdio Server，把 MCP 工具转换成 Responses API function tools，并转发结构化结果和图片；
完整运行步骤见 [`tutorial/README.md`](../tutorial/README.md)。

## MCP 工具

服务注册六个工具；通用 MCP Host 可见全部六个，隔离 Codex 玩家固定只允许除 `stop`
之外的五个：

- `briefing()`：等待 Godot 握手确认玩法，再返回该玩法的公开目标、规则、物体操作说明
  和参考图谱；应在首个 `observe` 前调用一次。
- `workflow_memory_read()`：读取当前 orchestrator 会话中已经通过终局资格和内容校验的
  抽象工作流；第一局返回 `version: 0` 和 `memory: null`。
- `observe()`：等待并返回最新获准观察和截图；第一人称 3D 玩法还返回当前画面的深度图。通常只在
  `briefing` 后调用一次；已有观察会立即返回，未连接、断线、停止或终局会返回对应状态。
- `act(observation_id, actions)`：提交 1～3 个动作，`observation_id` 必须是最近观察的 ID。
  工具声明使用二十五种动作的精确联合 schema；`actions` 顶层进一步分成两个互斥分支：
  恰好一个 `probe_interaction`，或 1～3 个不含 probe 的普通动作，因此 MCP 客户端可在调用前
  拒绝把 probe 与移动、转向或等待组合。调用同步等待 Godot 返回动作结果、公开
  `movement_feedback` 和下一次观察，或返回终局/停止状态。成功后应直接使用所带观察，
  不要再调用 `observe` 获取同一帧。
- `workflow_memory_update(goal_pattern, workflow, landmarks, avoid, failure_review=null)`：在可信
  终局后提交一次固定结构候选；工具不接受调用方提供的胜负结果或终局原因。
- `stop()`：发送固定原因 `mcp_stop`，请求取消当前动作、释放模拟输入并结束 MCP 控制会话；重复调用安全幂等。

动作批次使用现有安全白名单：

- `look`：只接受 `{"type":"look","yaw":-45..45,"pitch":-45..45}`；两个轴都必须是
  有限、非布尔数。`yaw` 负数左转、正数右转；`pitch` 负数向下、正数向上。30～45 度适合
  扫视房间，5～15 度适合微调准星。Godot 映射会抵消玩家的垂直轴反转设置。
- `move` / `sprint`：`forward`、`right` 在 -1～1，`duration_ms` 在 50～250。
  `forward` 与 `right` 组成的输入向量长度会保留为实际移动力度（上限为 1）；单轴绝对值 1
  是满强度，0.2～0.4 适合精细对位。`duration_ms` 是按住移动键的毫秒数；250ms 满强度 `move`
  约等于连续走四分之一秒，满强度 `sprint` 约等于连续跑四分之一秒。接近普通目标时优先用
  100～150ms；穿过狭窄门口或贴近门框时优先用单轴 0.2～0.4、50～100ms，并在每步后
  使用 `act` 返回的新观察和 `movement_feedback` 修正，不要连续使用满强度 250ms。
  `movement_feedback` 只包含公开位置可推导出的平面位移、实际移动距离和受阻标记。
  Godot 执行器会补偿项目 Input Map 的移动死区，
  各场景玩家移动层会保留补偿后的向量长度，确保 MCP 幅值不会被死区或归一化吞掉；移动受阻
  判定阈值也会随请求力度缩放，避免把有效的精细小步误报为 `blocked`。
- `jump`、`crouch`、`close_ui`、`wait`；`wait.duration_ms` 在 50～2000。
- `interact` 和 `interact2` 是动态交互槽，不是固定含义的操作；必须从当前
  `available_interactions` 的 `action` 选择可用槽，并以 `prompt` 判断这次交互的实际含义。
  `binding` 只是人类按键提示，不能写入动作对象。`interact` 只能使用当前观察中可用的槽，
  动作对象必须精确写成
  `{"type":"interact","action":"interact"}` 或
  `{"type":"interact","action":"interact2"}`：`type` 固定表示动作类型，`action`
  才表示当前公开的交互槽。`{"type":"interact"}`、`{"action":"interact"}`、
  `{"type":"interact","target":"use"}`、`{"type":"interact2"}`，以及在 `interact`
  中放入 `target_x`/`target_y` 都是无效格式；运行时会拒绝且不产生任何游戏输入。玩家正在携带物体时，
  `available_interactions` 会公开携带物真实绑定对应的 Drop；准星命中带
  `prefer_while_carrying` 的放置点时，该放置交互优先替代普通 Drop，避免 HUD 可见但 MCP
  无法合法调用。`enter_digits` 只能在界面打开时输入 1～6 位 ASCII 数字。
- `probe_interaction` 只能使用 probe 专用 schema 分支，例如
  `{"type":"probe_interaction","target_x":0.5,"target_y":0.6}`；`actions` 长度必须恰好为 1，目标坐标
  各在 0～1，且界面必须关闭。运行时若仍收到混合批次，会返回包含正确提交方式的稳定错误，
  不会向 Godot 产生输入。
- `conveyor_profit` 只允许 `select_ingredient`、`make` 和 `wait_next_window`：选材按
  固定英文食材 ID 请求当前画面中的同名盘；`wait_next_window` 必须单独提交，且只能推进一个
  已经锁定的窗口。托盘最多容纳五项；食材一旦选入就不可取回，第 6 次选材返回 `tray_full`
  且不改变托盘，此时只能用 `make` 结算并消耗托盘；窗口到期也会按成本报废未提交食材。
  三种动作均不得在其他玩法使用。
- `loop_staircase_anomaly` 额外允许 `front/back/left/right`，其 `step` 只能是映射为
  80ms 的 `small` 或映射为 180ms 的 `large`；`floor_up/floor_down` 只切换楼层；
  `toggle_board`、`board_up/board_down`、`toggle_mark` 只操作调查板；`submit_floor`
  只提交当前楼层。其他玩法必须拒绝这十一种动作，旧 `press_key` 不再公开。

Python 会先校验批次，Godot 会再次校验。Godot 在可信边界把语义方向映射为内部相机轴；
上下文变化动作必须是批次最后一个动作，非法批次不会产生 Godot 输入。AI 控制启用期间，
CogitoPlayer 只接受专用合成设备的鼠标移动，Escape 仍是物理紧急停止键；停用或退出后立即恢复
普通鼠标控制。所有动作的后续 observation 都由 Godot 在内部先等待一个完整输入/处理帧，再等待
最多 1 秒的 `RenderingServer.frame_post_draw` 后截图；后台窗口没有产生渲染信号时，Godot 会在
主线程调用 `RenderingServer.force_draw(false)` 重绘当前 Viewport，避免把新位置或朝向与动作前的
旧画面组合在一起，也避免等待到 Python action timeout。这项等待对 AI 和 MCP 客户端透明，不消耗
动作额度。若 Python 等待动作超时，会进入 `recovering`，暂停接受新动作并向
Godot 发送协议版本 4 的 `recover_action/action_timeout`。Godot 只取消该 observation 尚未完成的
动作、释放全部模拟输入，并从玩家已经到达的位置和当前世界状态捕获全新的 observation ID；旧
`action_results` 和延迟截图会被废弃。Python 收到新 observation 后恢复 `act`，不会重启场景或
把恢复计为新一局。重复恢复请求幂等；非法字段和不匹配 ID 仍然 fail-closed。
普通动作回合只有在相同 `observation_id` 的 `action_results` 和不同编号的后续 observation
都到达后才完成；两者允许乱序到达，但任何一方缺失都不得提前向 MCP 返回。Godot 断线后重新
附加会清除旧终局和缓存观察，`observe` 必须等待新连接的第一帧，不能返回上一连接的截图。

每个到达 Python `act()` 函数的请求都会消耗一次请求额度，包括过期观察、非法动作、
上下文不允许和已有动作在途等被拒绝的调用；`briefing`、`workflow_memory_read`、
`workflow_memory_update`、`observe`、MCP `stop()` 不计数。
所有玩法统一使用 100 次请求硬上限。`find_contract` 的终局为 `success/correct_password`、
`failure/wrong_password` 或 `failure/max_requests`；`find_key` 的
终局为 `success/key_picked_up`、`failure/security_lockout` 或 `failure/max_requests`；`put_book` 的终局为
`success/books_in_ceo_office`、`failure/wrong_book_pickup` 或
`failure/max_requests`；`greet_npc_meeting` 的终局为
`success/meeting_door_closed`、`failure/wrong_npc_limit` 或 `failure/max_requests`；
`daily_routine_cleanup` 的终局为 `success/cleanup_complete`、
`failure/cleanup_incomplete` 或 `failure/max_requests`；`garden_watering` 的终局为
`success/garden_tasks_complete`、`failure/garden_task_failed`
或 `failure/max_requests`；`repair_lighting_circuit` 的终局为
`success/circuit_repaired`、`failure/wrong_breaker`、
`failure/incorrect_circuit_configuration` 或 `failure/max_requests`；
`arrange_meeting_briefings` 的终局为 `success/meeting_prepared`、
`failure/incorrect_seating_assignment` 或 `failure/max_requests`；`conveyor_profit` 的终局为
`success/efficiency_target_reached`、`failure/efficiency_below_target` 或
`failure/max_requests`；`loop_staircase_anomaly` 的终局为
`success/correct_floor_selected`、`failure/wrong_floor_selected` 或
`failure/max_requests`；`laboratory_experiment` 的终局为
`success/experiment_completed`、`failure/experiment_attempts_exhausted` 或
`failure/max_requests`。环境变量
`AI_PLAY_MAX_ACT_REQUESTS` 只能进一步收紧所选玩法的硬上限。第 N 次 `act` 仍会完成
正常处理：若它产生该玩法的合法终局，以该终局为准；否则 Python 通过仅内部可见的桥
消息请求 Godot 以 `failure/max_requests` 结束。模型不能直接调用这个内部终局操作。

## 结果与隐私边界

工具结果使用标准 MCP 多模态内容：结构化 JSON 包含简报、观察、动作结果和终局状态，
截图、可选深度图及参考图作为 `ImageContent` 单独返回，结构化 JSON 不重复图片 Base64。
当 Claude orchestrator 设置内部 `AI_PLAY_APPROVED_IMAGE_ROOT` 时，结构化结果会额外包含
`approved_image_paths`，仅指向该会话的私有获准图片目录；该字段不进入可信轨迹日志。
观察成功时，`observe` 和 `act` 先返回截图 `image/jpeg`；第一人称 3D 玩法再返回深度图
`image/png`，`conveyor_profit` 只返回截图。结构化 `observation.image` 与可选的
`observation.depth_image` 只保留元数据；
运行时截图和深度图统一缩放为 1024×576；深度图的 `encoding` 为
`linear_depth_normalized_8bit`，并公开
`near_meters=0.05`、`far_meters=20.0`。它是面向室内和门口导航的同视角不透明 3D
几何归一化线性深度可视化（近处较黑，20 米外和背景为白）；较短范围让 8 位灰度能分辨
精细站位变化。HUD、其他 2D UI 及透明物体没有独立的可靠深度。
Godot 和 Python 桥的单包上限为 8 MiB，用于容纳带有两张 Base64 图片的观察 JSON。
`briefing` 只公开 `ai_play.scenarios` 白名单选中的 loader 所返回的目标、规则、物体操作
说明和固定参考图；`find_contract` 当前读取
`ai_play/assets/find_contract/imgs/reference_atlas.jpg`。它不会返回资产清单里的内部类名或
文件路径。回合工具只公开观察 schema 允许的玩家、界面、绑定、动作结果、截图和对应任务的
HUD 级状态；循环楼梯只额外公开当前楼层、轮次和终局布尔值，实验室只额外公开当前安装材料、
尝试次数与已经执行的测量反馈。所有工具
都不会返回源码、节点路径、隐藏状态、谜题答案、测试、规格或计划事实。

启用 AI Play 后，MCP Server 会在 Godot 成功连接时开始保存本地游玩轨迹。日志只记录
`observe`、`act`、`stop` 的请求、获准公开的结构化结果和工具返回的截图 JPEG；深度 PNG
只在当前 MCP 响应中返回，不写入轨迹目录。不记录 `briefing`、图片 Base64、提示词、令牌、
模型上下文、隐藏状态或仓库文件。MCP Host 是否另行保存工具结果不属于本服务的控制范围。
终局时 Godot 可在本地显示结果画面，MCP 同步返回受限的终局状态。

## 本地轨迹日志

默认日志根目录是 `~/workspace/cogito_logs/mcplogs`。第一个 Godot 控制器成功连接时
在对应任务的 `scenario_id` 目录下创建 `YYYYMMDD-HH-MM` 运行目录；同一任务的同名
目录使用 `-02`、`-03` 等后缀，不会覆盖。一个运行目录最多分组同一任务的四次连接；
第五次连接会开始新的运行目录：

```text
mcplogs/
└── daily_routine_cleanup/
    └── 20260725-14-45/
        ├── run.json
        ├── attempt-01/
        │   ├── trajectory.json
        │   └── imgs/
        ├── attempt-02/
        ├── attempt-03/
        └── attempt-04/
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

- Python 与 Godot 只通过精确的 `127.0.0.1:8765` 通信，内部桥协议版本为 4。
- 一个 MCP 会话只允许一个 Godot 控制器；握手、包大小、JSON 对象、协议版本和消息字段都经过边界校验。
- 观察中的任务专用可选字段按当前握手玩法白名单校验；例如传送带、循环楼梯、实验室、日常和
  花园的公开状态不能出现在其他任务响应中。所有第一人称任务可按观察契约公开深度图。
- Godot 发送合法 `game_over` 后，Python 必须在记录可信终局和 AWM attempt 结果后回复
  精确字段的 `game_over_ack`。supervisor 启动的 Godot 只有收到匹配的
  `observation_id` ACK 后才退出；ACK 丢失时使用有界超时退出，避免永久挂起。
- `find_key` 的版本 4 `hello` 可携带仅内部使用的 `act_request_limit`；当前 Godot
  固定发送 `150`。Python 为兼容旧 Godot 仍接受整数 `50`、`100` 或 `150`，省略时默认 150，
  其他玩法不得携带。该字段不进入 MCP
  工具结果或轨迹日志，重连时必须与首次握手一致。
- Godot 会把 JSON 数值解析为浮点：Python 到 Godot 的协议版本接受非布尔且数值精确等于 `4` 的表示，并在桥内规范化为整数 `4`；有效的安全整数 `observation_id` 也会在发出信号或回复 `stop_ack`、`game_over` 前规范化为整数。字符串、布尔、非整数和越界 ID 仍会被拒绝。
- 请求计数属于当前 Python/Godot 桥连接；Godot 成功重连、重新进入 Lobby 或重启 MCP Server 都会清零。达到上限后，Python 只向 Godot 发送一次严格的 `end_game/failure/max_requests`，Godot 复用既有终局、输入释放和界面路径。
- Godot 断线、Python 退出、节点销毁、执行器取消和 `stop` 都必须释放 `forward`、`back`、`left`、`right`、`sprint` 等保持输入。
- Escape 始终是物理紧急停止键，优先于 MCP 控制；它发送 `escape_stop`，不会被普通输入或 MCP 工具禁用。
- 当前支持 `find_contract`、`find_key`、`put_book`、`greet_npc_meeting`、
  `repair_lighting_circuit`、`arrange_meeting_briefings`、`daily_routine_cleanup`、
  `garden_watering`、`conveyor_profit`、`loop_staircase_anomaly` 和
  `laboratory_experiment` 的运行时终局事件和独立公开简报；
  不通过 MCP 提供场景源码、线索原文、密码、钥匙候选位置、书籍的随机布局或任务书选择、
  NPC 路线起点、NPC 路线方向、照明电路映射或故障线路、会议资料隐藏排列或候选解、
  daily routine 或 garden 内部节点路径、随机下雨时间、传送带未来供给、内部牌组标识、
  理论最优路线、循环楼梯答案、实验材料隐藏属性、随机种子或任务内部知识。
- 旧 `ai_host --adapter codex-local` 因无法提供受维护入口同等级的本机权限隔离而明确禁用；
  Codex、Claude 和 Kimi 黑盒验收分别只使用对应的 `tools/ai_play_*_orchestrator.py`，并仍须先
  确认截图、令牌、费用和轨迹影响。

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
自身统一的 100 次硬上限；等待时间有界，日志根目录支持 `~`
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
