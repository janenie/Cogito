> 摘要：本页维护 AI First Play 的架构、不可妥协的安全边界和跨层契约。

# AI First Play 系统指南

AI First Play 是一套需要显式启用的自主游玩系统：

- `addons/cogito/AIPlay/` 下的 Godot 代码捕获获准公开的观察数据，并执行有严格限制的输入动作。
- `ai_play/` 下的 Python 进程是 stdio MCP Server，负责暴露 `briefing`、`observe`、`act`、`stop` 工具、验证 DTO，并通过本机回环 WebSocket 桥与 Godot 串行交换观察和动作结果。
- 外部 MCP 客户端负责游玩决策；Python 不调用模型 API、不读取任务源码，只把获准公开的 MCP 游玩轨迹和截图保存到操作者配置的本地日志目录。
- Godot 与 Python 默认通过精确地址 `127.0.0.1:8765` 通信，内部桥协议版本为 3。
- 同一 Lobby 可用 `--ai-play-scenario=<id>` 选择玩法脚本；省略时默认
  `find_contract`。Controller 只激活直属子节点中 `scenario_id` 匹配的终局监视器。
  Godot 在 `hello` 中上报所选 ID，Python 使用独立白名单选择公开简报。

只有模型 API 时，可使用 [`tutorial/ai_play_api_host.py`](../../../tutorial/ai_play_api_host.py)
作为最小 Host 参考实现。该教学代码在客户端侧连接本地 stdio MCP、把工具定义映射为
模型 function tools，并将 MCP 的结构化结果和图片送回模型；它不改变 MCP Server 或
Godot 桥的安全边界。

## 不可妥协的安全边界

- AI 游玩必须保持显式启用。正常启动 Lobby 时 `auto_start = false`；精确的 Godot 用户参数是 `-- --ai-play`。
- Escape 是物理紧急停止键。断开连接、无效数据、API 失败和节点销毁都必须释放所有模拟输入。
- Godot 到 Python 的服务器必须使用精确的数字回环地址 `127.0.0.1`，不得扩大到局域网或公网接口。
- 绝不能提交 API 密钥，也不能把密钥复制到源代码、测试、文档、测试夹具、命令参数或日志。MCP Server 本身不需要 API Key；外部 MCP 客户端的凭据不进入本仓库或 Godot/Python 桥协议。
- 外部 AI 只能通过 MCP 工具接收 `ai_play.scenarios` 注册并由对应 loader 筛选的公开
  简报和参考图，以及文档规定的相机图像、可见交互文本、获准公开的玩家状态、动作结果
  和运行时按键绑定。
- 绝不能把场景源码、节点路径、隐藏状态、仓库文件、谜题答案，或来自 `game_script/`、`code_read/`、测试、规格和计划的事实加入提示词、种子记忆、API 载荷或黑盒验收提示。
- 除非用户明确要求，并且了解截图、令牌、费用和本地轨迹持久化的影响，否则不要运行真实外部 MCP/模型验收。自动化测试必须不依赖真实凭据。
- 隔离 Codex 玩家多局验收应由外部 supervisor 重启 Godot。玩家 Codex 只使用
  `briefing`、`observe`、`act`、`stop`；supervisor 只监听 Godot 终局标识和进程状态，
  不读取轨迹、截图、源码或模型上下文。

## 跨层契约

- Python 和 GDScript 两端的协议常量、数据包字段、动作名称、数值边界和上下文门控必须保持同步。版本 3 的桥协议使用 `action_batch`、`action_results`、`game_over`、`stop_request`、`stop_ack`，以及仅由 Python 发给 Godot 的 `end_game/failure/max_requests` 明确关联回合和终局。
- 所有不可信数据都必须在两端验证。保留精确字段检查、有限数检查、观察编号关联、每批最多三个动作，以及改变上下文的动作必须位于批次末尾等规则。
- Godot 的 JSON 解析会把数值规范化为浮点；其接收边界将非布尔且数值精确等于 `3` 的 `protocol_version` 规范化为整数 `3`，并将有限安全整数 `observation_id` 规范化为整数后再发出桥信号或发送确认包。字符串、布尔、非整数和越界 ID 必须继续被拒绝。
- `act` 必须携带最近的 `observation_id`，服务端只允许一个动作回合在途；校验失败或观察过期时不得向 Godot 派发输入。
- 公开 briefing 必须说明 `look` 的角度单位和 `move`/`sprint` 的按键持续时间量级，
  让黑盒玩家知道何时用扫视、微调和小步移动；`look` 单次最大 15 度，
  `move`/`sprint` 单次最大 250ms。
- `find_contract` 的请求硬上限是 300，终局只允许 `success/correct_password`、
  `failure/wrong_password` 和 `failure/max_requests`；`find_key` 根据本局位置使用
  50 或 100 次请求硬上限，公开 briefing 只说明最大值 100，
  终局只允许 `success/key_picked_up` 和 `failure/max_requests`；`put_book` 的请求硬上限
  是 50，终局只允许 `success/book_in_box` 和 `failure/max_requests`；
  `greet_npc_meeting` 的请求硬上限是 100，终局只允许
  `success/meeting_door_closed` 和 `failure/max_requests`；`daily_routine_cleanup`
  的请求硬上限是 150，终局只允许 `success/cleanup_complete`、
  `failure/cleanup_incomplete` 和 `failure/max_requests`；`garden_watering` 的请求
  硬上限是 300，终局只允许 `success/garden_tasks_complete`、
  `failure/garden_task_failed` 和 `failure/max_requests`。`find_key`、`put_book` 和
  `greet_npc_meeting` 没有答错失败。
  `AI_PLAY_MAX_ACT_REQUESTS` 只能进一步收紧所选玩法的硬上限。所有到达 Python `act()`
  的调用都计数，即使随后因观察过期、动作非法、上下文不允许或动作在途而失败；其他
  三个工具不计数。第 N 次请求先按正常规则处理，合法玩法终局优先，否则返回
  `failure/max_requests`。Godot 成功附加或重连时计数清零。
- Godot 执行器必须使用 COGITO 的常规输入、用专用设备 ID 标记合成事件，并在所有退出路径中释放持续按下的移动输入。
- `observe` 和 `act` 返回获准结构化状态及 MCP 图片内容；结构化结果不得重复 Base64 图片，也不得包含隐藏状态。
- `briefing` 只返回经过筛选的任务目标、规则和物体操作说明，并把固定参考图作为 MCP 图片内容；不得返回 `assets.json` 的内部类名、任何文件路径、线索原文、密码或正确解谜顺序。
- `briefing` 必须等待 Godot 握手确定 `scenario_id`。桥只接受
  `ai_play.scenarios` 白名单中的 ID；重连时玩法不一致必须拒绝，避免观察和简报错配。
- `find_key` 的版本 3 `hello` 可额外携带 `act_request_limit`，只允许整数 50 或 100；
  省略时默认 100，其他玩法携带、非法类型和值都必须拒绝。首次握手后重连上限必须一致。
  该字段只供 Python 内部计数，不进入 MCP 工具结果或轨迹日志。
- `AI_PLAY_LOG_ROOT` 默认是 `~/workspace/cogito_logs/mcplogs`。Godot 成功附加后在
  `<scenario_id>/<YYYYMMDD-HH-MM>/` 下创建运行/尝试目录；一个运行最多分组同一任务的
  三次连接，不同任务绝不混入同一个运行。`run.json` 重复保存经过验证的
  `scenario_id`，尝试摘要用 `terminal_reason` 区分任务终局、MCP 停止、Escape、
  bridge 断开和 MCP shutdown。
- 本地轨迹只记录 `observe`、`act`、`stop` 的 MCP 请求、获准结构化结果和 JPEG 相对路径，绝不记录 `briefing`、图片 Base64、提示词、凭据、隐藏状态或仓库文件。`trajectory.json` 的 `total_steps` 统计终局前到达 Python 的全部 `act()` 调用，`result` 仍严格只包含 `total_steps` 和 `status`，状态使用 `in_progress`、`success`、`failure`、`stopped`。日志器不负责自动重玩或模型复盘。
- 运行时观察截图统一缩放为 1024x576 JPEG；Godot 和 Python 桥的单包上限为 8 MiB，
  用于容纳包含截图 Base64 的观察 JSON。
- 修改公开协议、环境变量、控制方式、隐私行为或日志布局时，必须在同一改动中更新 `ai_play/README.md` 和对应测试。

## Codex orchestrator 多局验收

### 当前黑盒玩家边界

> 状态：已于 2026-07-26 实施；设计来源见 [黑盒 Codex 玩家 spec](../../scope/2026-07-26-blackbox-codex-player/spec-blackbox-codex-player.md)。

orchestrator 把可信游戏侧和受限 Codex 会话拆开：它在仓库侧启动仅绑定 `127.0.0.1` 的
Streamable HTTP MCP 边车，边车连接 Godot bridge 并保存可信轨迹；Codex 只配置该边车的
`briefing`、`observe`、`act` 三个工具。玩家提示词、环境、工作区和临时配置不含
仓库路径、启动脚本路径、玩法 ID、日志位置或关卡信息；游戏目标只由 `briefing` 的既有白名单
结果提供。

每局创建空的 `player_workspace` 和临时 `CODEX_HOME`。`--codex-auth-home` 默认
`~/.codex-cogito-player`，只作为 `auth.json` 的来源；不会读取、合并或保留其 `config.toml`、
MCP、插件、技能、记忆或会话。临时凭据副本和配置会在所有退出路径删除。工作区根及祖先不能
位于当前仓库内，也不能含 `.git`、`AGENTS.md` 或 `.codex/config.toml`；日志、截图、轨迹和
运行配置都不放入或传入玩家侧。

启动命令必须显式提供 `--model`、`--reasoning-effort` 和（需要覆盖默认值时）
`--codex-auth-home`。临时配置固定模型、思考强度、唯一 MCP URL、四工具白名单和自定义最小
权限 profile，并禁用 Web 搜索、子代理、记忆、登录 shell 及模型生成命令的网络访问。旧的
`--codex-home`、`--sandbox`、`--approval-policy`、`--ws-host`、`--ws-port` 都不被接受，不能
用来放宽此边界。Windows 配置还请求 Codex 原生 `elevated` sandbox；建立失败时应修复本机
权限环境，而不是降级该 profile。该 profile 对本局临时 `CODEX_HOME` 加显式 deny，禁止模型
生成的命令读取认证副本或临时配置；CLI 与 MCP OAuth 凭据存储固定为 `file`，不回退读取
系统凭据库。

```bash
CODEX_HOME=~/.codex-cogito-player codex login

python3 tools/ai_play_codex_orchestrator.py \
  --runs 3 \
  --scenario find_contract \
  --model gpt-5.6 \
  --reasoning-effort high \
  --codex-auth-home ~/.codex-cogito-player
```

默认运行根在 Windows 是当前仓库所在驱动器根目录的 `cogito_ai_player_runs/`，非 Windows 是
`/tmp/cogito_ai_player_runs/`；`--session-root` 必须同样通过隔离祖先检查。每局的
`trusted_mcplogs/` 位于运行目录的可信侧，玩家工作区创建时为空，orchestrator 不在其中写入
游戏产物。

Godot bridge 固定为 `127.0.0.1:8765`，可信 MCP HTTP 边车默认是
`http://127.0.0.1:8766/mcp`，可用 `--mcp-port` 改 HTTP 端口（不得使用 8765）。启动器先检查
两个端口空闲，按 MCP 边车、Codex、supervisor 的顺序启动，并在启动 Codex 前等待 HTTP 和桥
监听就绪。任一子进程退出、异常或中断时，它会逆序终止已启动的其余进程；MCP 断线仍走既有的
输入释放路径。

该本机方案限制 Codex 会话通过配置工具读取文件和使用网络的范围，但不是容器、VM 或独立 OS
用户级别的强隔离，不能抵抗同一 Windows 用户下的恶意本机进程。真实 Codex/Godot 多局验收
会涉及截图、令牌、费用和本地轨迹持久化，仍须用户单独确认。

## 外部 supervisor 多局验收

隔离玩家 Codex 不应负责启动或重启 Godot。需要连续运行 `find_contract` 三局时，从仓库
根目录启动外部 supervisor：

```bash
python3 tools/ai_play_supervisor.py --runs 3 --scenario find_contract
```

supervisor 每局启动：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=find_contract --ai-play-exit-on-game-over
```

`AIPlayController` 只在同时存在 `--ai-play` 和 `--ai-play-exit-on-game-over` 时启用终局
自动退出。合法终局会先通过桥发送 `game_over`，再在 Godot 输出中打印：

```text
AI_PLAY_GAME_OVER outcome=<success|failure> reason=<reason>
```

supervisor 将该标识作为本局完成依据。没有该标识的提前退出、超时或连接异常按异常局
处理并有限重试。若外部 MCP 客户端调用 `stop` 或人工 Escape 触发 Godot 停止控制，
Godot 输出 `AI_PLAY disabled; reason=mcp_stop` 或
`AI_PLAY disabled; reason=escape_stop` 时，supervisor 将本局记为
`failure/stopped` 并继续后续局数。supervisor 不读取本地轨迹日志，不复盘截图，不修改
玩家 Codex 提示词，也不访问仓库内部知识；本次 `AI_PLAY_LOG_ROOT` 只属于可信 MCP
边车，绝不授权给隔离玩家 Codex。

## 增加同一 Lobby 的新玩法

不要复制完整的 `COGITO_3_Lobby.tscn`。新玩法应作为 `AIPlayController` 的直属子节点
加入同一场景，并遵守以下最小契约：

1. 节点导出唯一的 `scenario_id`，只使用小写 ASCII 字母、数字和下划线。
2. 玩法脚本在 `_ready()` 中调用父 Controller 的 `is_requested_scenario()`，未被选择时
   不得修改场景、连接谜题信号或生成隐藏状态。
3. 被选择的脚本负责本玩法初始化，并提供现有 Controller 使用的 `game_finished` 信号。
4. 在 `ai_play.scenarios` 中用同一个 ID 显式注册公开 briefing loader；不要根据用户输入
   拼接模块名、文件名或资源路径。
5. 为玩法选择、握手、公开简报和终局补充两端测试。未知 ID 必须在启用控制前或桥握手时
   被拒绝。

只有静态地图结构确实不同，才应创建另一个完整世界场景；共享地图上的任务、线索、出生点
和胜负条件变化应留在小型玩法脚本或玩法子场景中。

## find_contract 回合规则

- 随机谜题是 Lobby 自身的游戏规则，不依赖 AI Play。普通启动和 `-- --ai-play` 启动
  都会生成随机回合；后者只额外启用本地 MCP 控制。
- 每次载入 Lobby 时，Godot 从 8 个四位日期和 8 个两位版本号候选中各选一个，并随机
  决定密码采用 `MMDD + VV` 还是 `VV + MMDD`。同一随机源还选择三地点路线和出生点。
- 出生点只从入口、大厅、ARCHIVE 门外三个安全位置中选择；任务卡与所选出生点保持
  1～2 米距离。第三条路线中的 `LABORATORY` 指 Lobby 内、实验室入口标识后的连接区，不触发
  跨场景切换。
- 合法流程固定为：读取任务卡，从卡上唯一公开的第一处地点开始，按每份记录给出的下一处
  地点继续调查，读完三份合同记录后再使用密码盘。任务卡说明密码为六位，并说明记录可能
  是圆形 COGITO Hint、实体文件或书本，但不会提前公开后两处地点。CEO OFFICE 使用桌面
  上的 RippedPageA 外观可读文件，BREAK ROOM 使用电视柜顶面的 RippedPageA 外观可读文件。
  这两个地点不移动悬浮 Hint，也不改变电脑或柜门交互。三份记录依次提供日期、版本号和
  拼接顺序。任务卡和所有本局记录均可随时重复读取；提前读到后续记录不会推进进度，
  玩家仍需按任务卡、第一份、第二份、第三份的顺序完成调查。
- 对黑盒玩家的公开 briefing 必须强调这是解谜任务，第一步一定要找到并读取任务卡；
  在读到任务卡之前，不应寻找合同记录、猜测地点顺序或尝试密码。
- 密码盘在第三份记录被读取前使用非数字哨兵值保持锁定；此时输入数字不会成功，也
  不会触发“密码错误”终局。流程完成后才装载本局六位密码，之后正确输入成功、错误
  输入失败。
- 可通过场景导出的非零 `round_seed` 做本地确定性测试；默认值 `0` 使用运行时随机种子。
  种子、候选选择、当前进度和答案属于隐藏状态，不得进入公开观察、MCP 结果或日志。

## find_key 回合规则

普通游玩：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=find_key
```

AI 游玩：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=find_key
```

- 每局只存在一张任务卡和一把目标钥匙。钥匙在五类办公家具位置中随机选择一处，任务卡
  用环境特征描述目标位置，不公开内部节点或坐标。
- 游戏先选择钥匙位置，再从入口、大厅和 ARCHIVE 门外三个安全点中选择与钥匙世界坐标
  直线距离最远的出生点；任务卡与出生点保持 1～2 米距离。
- 只有成功执行 Pickup 才产生 `success/key_picked_up`；仅看到钥匙不算成功，本玩法没有
  wrong-answer 失败。
- 台式电脑桌、电视茶几和档案室沙发位置使用 50 次请求硬上限；笔记本电脑桌和会议长桌
  位置使用 100 次请求硬上限。Godot 只向内部桥发送 50/100 上限，不发送位置 ID。
- 非零 `round_seed` 仅供本地确定性测试。候选坐标、所选位置、出生点计算和种子都属于
  隐藏初始化状态，不得进入公开简报、观察或桥协议。

## put_book 回合规则

普通游玩：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=put_book
```

AI 游玩：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=put_book
```

- 玩家固定从档案室门口开始，档案室门在本玩法中已打开，任务卡位于出生点附近。
- 每局从档案室初始可见的书中随机选择一本，其他书隐藏；目标书以可搬运物体形式放在
  选中书的位置。
- 目标纸箱以 50% 概率放在档案室地上靠近门口或远离门口的位置。
- 只有目标书进入目标纸箱检测区才产生 `success/book_in_box`；仅看到书、拿起书或靠近
  纸箱不算成功。
- 非零 `round_seed` 仅供本地确定性测试。候选书、目标箱选择和种子都属于隐藏初始化
  状态，不得进入公开简报、观察或桥协议。

## greet_npc_meeting 回合规则

普通游玩：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=greet_npc_meeting
```

AI 游玩：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=greet_npc_meeting
```

- 玩家固定从入口开始，任务卡位于出生点附近。
- NPC 沿会议室到休息室方向的既有路线循环移动；每局随机选择路线起点和方向。
- 每局从 `你好`、`要去开会了么？`、`hi` 中随机选择一种问候语作为 NPC 交互提示。
- 只有玩家在 1 米以内和 NPC 成功交互后，才记录为已打招呼。
- 会议室门在本玩法开始时打开并解锁；未打招呼前，进入会议室或关门不会成功。
- 已打招呼后，玩家在会议室内关上会议室门产生 `success/meeting_door_closed`。
- 路线点、路线起点、方向、问候语和随机种子属于隐藏初始化状态，不得进入公开简报、
  观察或桥协议。

## daily_routine_cleanup 回合规则

普通游玩：

```bash
godot --path . dailyroutine/scenes/home_daily_routine.tscn \
  -- --ai-play-scenario=daily_routine_cleanup
```

AI 游玩：

```bash
godot --path . dailyroutine/scenes/home_daily_routine.tscn \
  -- --ai-play --ai-play-scenario=daily_routine_cleanup
```

- 该玩法来自导入到当前仓库的 `dailyroutine/` 家庭日常清理场景，复用同一套
  stdio MCP Server、WebSocket 桥、动作执行器和终局上限机制。
- 玩家根据 HUD 目标、画面观察和可见交互提示，把 4 个散落垃圾和过期牛奶放进客厅
  垃圾桶，确认冰箱关闭后点击完成按钮。
- 完成按钮在所有目标垃圾已进入客厅垃圾桶且冰箱关闭后产生
  `success/cleanup_complete`；任一完成条件未满足就点击完成按钮，产生
  `failure/cleanup_incomplete`，且不会公开具体缺少哪项条件。
- 公开观察只包含相机图像、玩家基础状态、可见交互提示、HUD 级别的清理进度和持有物
  标签；不公开内部节点路径、脚本类名或候选物体源码。

## garden_watering 回合规则

普通游玩：

```bash
godot --path . garden/scenes/garden_vertical_slice.tscn \
  -- --ai-play-scenario=garden_watering
```

AI 游玩：

```bash
godot --path . garden/scenes/garden_vertical_slice.tscn \
  -- --ai-play --ai-play-scenario=garden_watering
```

- 该玩法来自导入到当前仓库的 `garden/` 场景，复用同一套 stdio MCP Server、
  WebSocket 桥、动作执行器、显式启用和 Escape 紧急停止机制。
- 玩家用中央广场的 4 个满水壶浇完向日葵房和绣球花房各 2 块草坪；每个水壶只能浇
  1 块。兰花房的草坪不是目标。
- HUD 天气显示下雨时，玩家必须在雨停前按下兰花房门铃。浇错草坪、按错门铃、
  非下雨时按兰花房门铃或错过警报都会失败。
- 公开观察只包含相机图像、玩家基础状态、可见交互提示，以及 HUD 级别的时间、天气、
  水壶、浇水和警报进度；不公开内部节点路径、脚本类名、随机下雨时间或运行种子。

## 来源

本页整理自仓库根目录的 [`AGENTS.md`](../../../AGENTS.md)、已批准的 [`AI Play MCP spec`](../../scope/2026-07-23-ai-play-mcp/spec-ai-play-mcp.md)、已实施的 [`黑盒 Codex 玩家 spec`](../../scope/2026-07-26-blackbox-codex-player/spec-blackbox-codex-player.md)、[`ai_play/README.md`](../../../ai_play/README.md)、[`tools/ai_play_codex_orchestrator.py`](../../../tools/ai_play_codex_orchestrator.py) 和 [`tools/ai_play_supervisor.py`](../../../tools/ai_play_supervisor.py)。
