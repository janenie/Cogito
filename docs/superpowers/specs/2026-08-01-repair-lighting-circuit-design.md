# 未知照明电路修复任务设计

## 目标

在现有 `COGITO_3_Lobby.tscn` 中增加白名单玩法
`repair_lighting_circuit`，利用入口、CEO 办公室、中央大厅和休息室的照明设备，测试玩家的
因果推理、空间记忆和长程规划。玩法不复制 Lobby，不使用实验室或移动平台，也不增加新的
美术资源。

玩家需要通过入口控制面板反复实验，推断 A～D 与四条照明线路之间的一对一映射，识别唯一的
跳闸线路，选择一次断路器复位，再把四组灯调整为任务卡给出的目标状态并提交验证。

## 范围

本次实现包括完整玩法、确定性随机化、场景接线、公开 briefing、跨层终局白名单、文档和自动化
测试。推理效率指标不进入现有桥协议、MCP 结果或轨迹日志；Monitor 的集中交互回调将作为以后
增加可信侧指标的扩展点。

## 方案选择

采用“现有 A 开关 + 独立任务子场景 + 专用 Monitor”的混合方案：

- 复用入口附近现有红色 `GenericSwitch` 作为 A。
- 新任务子场景提供 B～D、四个断路器按钮、Verify、面板文字、专用出生点、任务卡锚点和
  休息室落地灯。
- 专用 Monitor 引用子场景控件以及 Lobby 中现有的三组照明设备，独占随机状态和终局逻辑。

不把所有新增节点直接展开到大型 Lobby 场景，避免场景差异过大；也不在运行时从脚本动态搭建
整个面板，以保留编辑器中的位置可调性和稳定的场景测试。

## 场景结构

`AIPlayController` 增加直属子节点 `RepairLightingCircuitMonitor`，其导出
`scenario_id = "repair_lighting_circuit"`。Monitor 必须先调用父 Controller 的
`is_requested_scenario()`；未选中本任务时，不得生成随机状态、连接谜题信号、移动玩家、改写
任务卡、改变灯具或改变现有开关。

新增小型任务子场景 `AIPlayRepairLightingCircuitSetup`，作为 Lobby 根节点的一个实例。它包含：

- 面板背板和 `LIGHTING CONTROL`、A～D、`RESET BREAKERS`、四个区域名及 `Verify` 的
  `Label3D`；
- 三个现有 `GenericSwitch` 实例，分别作为 B、C、D；
- 五个现有 `GenericButton` 实例，分别作为 Entrance、CEO、Lobby、Break Room 断路器和
  Verify；
- `PanelSpawn` 和 `TaskCardAnchor`；
- 在休息室位置实例化的现有 `lamp_round_floor`。

该子场景默认不可见、无碰撞、交互组件禁用且不参与处理。只有选中的 Monitor 才会显式启用
面板和休息室灯，保证普通 Lobby 及其他玩法没有额外可见物、碰撞体或交互提示。

Monitor 通过导出 NodePath 引用以下现有设备：

- 入口 `ENTRANCE_AREA/lampRoundFloor`；
- CEO 办公室 `UPPER_OFFICE_CEO/lampRoundFloor`；
- `LIGHTS_CEILING_WALL/lampSquareCeiling8` 至 `lampSquareCeiling13` 六盏大厅顶灯；
- 入口现有根节点 `GenericSwitch`，作为控制开关 A。

任务启用后，Monitor 保存 A 原有的 `objects_call_interact`，清除其直连大厅六灯的行为，再将
A～D 的 `switched` 信号统一接入本任务。入口、CEO、六盏大厅灯和休息室灯自身的
`BasicInteraction` 在本任务中禁用，只允许通过面板控制。Monitor 离开树时断开新增信号并恢复
它改过的既有配置，避免编辑器测试或场景复用留下状态。

初始化延迟到 Lobby 子节点全部 ready 之后，避免复用的 A 开关自身 `_ready()` 所发出的初始
`switched` 信号被误认为玩家操作。

## 可信回合模型

四条设备线路使用固定内部 ID：

- `entrance`
- `ceo`
- `lobby`
- `break_room`

非零 `round_seed` 直接作为 `RandomNumberGenerator.seed`；零值使用运行时随机种子。每局按同一
顺序生成：

1. A～D 到四条设备线路的一对一随机排列；
2. 一条随机故障线路；
3. 四组灯的随机初始状态；
4. 四组灯的随机目标状态。

目标状态必须与初始物理灯光状态至少有两项不同，且故障线路的目标强制为开启。算法先随机
生成四个目标位并强制故障目标开启；若差异不足两项，则用同一 RNG 洗牌三个非故障线路，按
顺序把其目标改为初始状态的反值，直到恰好补足两个差异。该过程有界、确定且保留随机选择。
正确断路器复位本身也是成功前置条件，因此即使故障灯初始恰好亮着，也不能绕过维修。

初始化开关时使用配置保护标志：每个控制开关的指示状态设置为其映射线路的初始灯光状态，灯具
设置为同一初始状态，但这些信号不执行玩家操作逻辑。隐藏映射、故障线路、种子、初始状态和
内部处理状态只保存在可信 Godot Monitor 中。

Monitor 可提供测试用 `get_round_snapshot()`，但该方法不被 Controller、Bridge、Observer 或
MCP 调用，也不能把返回值加入任何公开结果。

## 操作语义

玩家操作一个控制开关时：

- 开关自身仍通过现有 `CogitoSwitch` 改变红色指示状态；
- 正常线路对应的一组物理灯同步为该指示状态；
- 故障线路对应物理灯保持原状态，不响应控制开关；
- 大厅线路始终把六盏顶灯作为一个原子灯组设置，但验证时逐盏检查。

断路器按钮按设备区域命名，而不是按 A～D 命名。玩家只有一次选择机会：

- 按下正确线路的断路器后，故障清除，并立即把该设备同步到映射控制开关的当前指示状态；
- 随后所有断路器按钮禁用；
- 按下错误线路立即产生 `failure/wrong_breaker`。

按下 Verify 后：

- 正确断路器已经复位，且入口灯、CEO 灯、六盏大厅灯和休息室灯逐组符合目标时，产生
  `success/circuit_repaired`；
- 未正确复位或任一灯不符合目标时，产生
  `failure/incorrect_circuit_configuration`。

错误断路器和错误 Verify 都直接结束本局。Monitor 在首次终局前设置 `_round_finished`，然后
只发出一次 `game_finished(outcome, reason)`；之后所有开关、断路器和 Verify 回调都是幂等
空操作。Controller 继续负责把合法终局传给桥和游戏结束界面。
Monitor 提供与其他 Lobby 玩法一致的 `show_result(outcome, reason)`，转发到共享的
`AIPlayGameOverScreen`。

## 玩家起点和任务卡

玩家固定移动到面板旁的 `PanelSpawn`，唯一任务卡移动到 `TaskCardAnchor`。任务卡可重复阅读，
标题为“未知照明电路修复”，内容公开：

- 四个区域各自要求的 `ON` / `OFF` 目标；
- A～D 与区域接线未知；
- 一条线路已跳闸；
- 断路器只能选择一次，错误选择立即失败；
- 调整完成后按 Verify，错误提交立即失败。

任务卡不公开本局映射、故障线路、初始状态的生成规则、种子或内部节点信息。

## 普通 Lobby 隔离

未选择 `repair_lighting_circuit` 时：

- Setup 保持隐藏、无碰撞、不可交互；
- 休息室新增灯不存在于可见玩法空间；
- 现有 A 开关仍按原有配置控制大厅六灯；
- 入口灯和 CEO 灯仍保留原本的直接交互；
- Monitor 不连接控件或灯具信号，也不生成隐藏状态。

通过 `-- --ai-play-scenario=repair_lighting_circuit` 可以普通人工游玩；追加 `--ai-play` 才启用
AI 控制。该任务不改变 AI Play 的显式启用或 Escape 紧急停止边界。

## 公开 briefing 和安全边界

新增显式注册的 `repair_lighting_circuit_briefing.py` loader，并在 `ai_play.scenarios` 中将
玩法硬上限设为 100 次 `act` 请求。briefing 只公开：

- 这是需要读取出生点附近任务卡的照明诊断任务；
- 控制面板、四个区域、一次断路器机会和 Verify 的可见规则；
- 正常开关与故障开关的可观察行为差异；
- 通用移动、观察、探测和交互方法；
- 最多 100 次 `act` 请求。

briefing 复用现有、受大小限制的 Lobby 交互参考图，不新增美术资源，并明确参考图不代表本局
映射、故障或目标。它不得包含场景路径、节点名、内部类名、seed、映射、故障答案、当前开关
状态或目标答案。目标状态只通过游戏内可见任务卡公开。

Godot Controller 和 Python registry 同步允许：

- `success/circuit_repaired`
- `failure/wrong_breaker`
- `failure/incorrect_circuit_configuration`
- `failure/max_requests`

游戏结束界面为前三个任务终局增加中文结果和原因文本。轨迹结构、观察 DTO、桥协议版本和日志
布局不改变。

## 推理指标扩展边界

本次不增加观察次数、移动距离或 MCP 请求数等日志字段，也不把分析指标显示给玩家。所有面板
操作都经过 Monitor 的 `_on_control_switch_changed()`、`_on_breaker_pressed()` 和
`_on_verify_pressed()` 等集中入口；后续可在可信侧为这些入口增加私有计数，并从 Controller、
Observer 或 GameSession 的既有可信事件汇总其他指标，而无需改变核心灯光状态机。

## 测试设计

新增专用 Godot Monitor 测试，覆盖：

- 同一非零 seed 生成完全相同的映射、故障、初始状态和目标状态；
- 多组固定 seed 的映射始终是 A～D 到四条线路的一对一排列；
- 初始物理状态与目标至少两项不同，故障目标始终开启；
- 正常线路随开关变化，故障线路复位前不响应，但控制指示仍变化；
- 正确复位只生效一次，并立即同步当前开关状态；
- 错误复位产生一次 `failure/wrong_breaker`；
- Verify 逐盏检查大厅六灯，并检查其他三组灯和复位前置条件；
- 正确配置产生一次 `success/circuit_repaired`；
- 未复位或灯光错误产生一次 `failure/incorrect_circuit_configuration`；
- 终局后重复开关、复位和 Verify 不再改变世界或重复发信号；
- 面板启用时四组灯的直接交互禁用。

Lobby 场景与静态检查覆盖：

- Monitor 是 Controller 的直属子节点，`scenario_id` 和所有 NodePath 正确；
- Setup 含有规定的开关、按钮、标签、Marker 和休息室灯；
- 大厅灯组恰好包含六盏指定顶灯；
- 默认启动选择其他任务时 Setup 完全惰性，A 开关和既有灯具行为不变；
- 普通 Lobby 没有新增可见控件、碰撞或交互提示。

Python 和跨层测试覆盖：

- `supported_scenario_ids()` 显式包含新 ID，未知 ID 继续拒绝；
- briefing 使用正确 game ID、100 次上限、共享控制规则和有效受限 JPEG；
- briefing 序列化结果不含 seed、mapping、fault、节点路径或其他隐藏答案；
- 场景请求硬上限为 100，环境配置只能收紧；
- 三个任务终局和 `max_requests` 只对本场景合法；
- Controller 的场景选择、终局白名单和终局幂等与 Python 保持一致。

最终按由小到大的顺序运行专用 Godot 测试、Controller 测试、Python briefing/scenario/session
测试、受影响的完整 AI Play Python 套件、Lobby 静态检查和密钥扫描，最后运行
`git diff --check`。不在本次自动验收中启动真实外部模型；真实多局验收仍需用户单独确认截图、
令牌费用和本地轨迹持久化。

## 文档同步

同步更新仓库根 `README_AI_PLAY.md`、`ai_play/README.md` 和
`docs/wiki/ai-play/system-guide.md`，增加玩法启动命令、100 次上限、公开规则、终局原因和隐藏
状态边界。若验证命令新增专用 Godot 脚本，也同步更新开发者验证清单。
