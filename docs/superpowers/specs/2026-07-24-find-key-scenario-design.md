# Find Key 场景模式设计

## 目标

在现有 Lobby 中增加独立的 `find_key` 模式。每局只生成一张任务卡和一把钥匙；
钥匙从五个语义位置中随机选择，玩家从三个安全出生点中距离钥匙最远的位置开始，
成功拾取钥匙即完成任务。

玩法细节以 [`game_script/find_key.md`](../../../game_script/find_key.md) 为准。

## 场景结构

继续复用 `COGITO_3_Lobby.tscn`，不复制大型场景。`AIPlayController` 下增加带有
`scenario_id = "find_key"` 的独立任务监视器。现有合同任务监视器继续使用
`scenario_id = "find_contract"`。

两个监视器在 `_ready()` 时都必须先检查 Controller 当前请求的模式，只有匹配的监视器
可以初始化玩家、任务卡、钥匙或终局信号。普通模式也使用同一场景参数选择机制，因此
是否连接 AI 不影响随机找钥匙规则。

## FindKeyMonitor 职责

- 持有唯一任务卡、唯一 `Pickup_Key`、五个钥匙锚点和三组出生点/任务卡锚点引用。
- 先随机选择钥匙锚点，再用世界坐标直线距离选择最远出生点。
- 在并列最远点中使用本局随机源选择，保证固定种子测试可复现。
- 更新任务卡为所选位置对应的单条语义描述。
- 保证钥匙稳定停留在候选家具表面，同时保持 Pickup 可用。
- 监听目标钥匙 `PickupComponent.was_interacted_with`。该信号只在背包成功接收钥匙后
  发出，因此适合作为 `success/key_picked_up` 的唯一成功来源。
- 提供与现有任务监视器相同的 `game_finished` 信号和 `show_result()` 接口。

## 通用 AI Play 变化

- Godot Controller 的终局白名单按当前场景接受：
  - `find_contract`: `success/correct_password`、`failure/wrong_password`
  - `find_key`: `success/key_picked_up`
  - 两者共同接受 `failure/max_requests`
- Python `GameSession` 当前的 `_validate_game_over()` 也使用固定的合同终局白名单；
  它必须根据握手保存的 `scenario_id` 校验同一组场景终局组合，不能全局接受
  `key_picked_up`。
- 游戏结束界面增加 `key_picked_up` 的公开文案。
- Python 场景 allowlist 增加 `find_key`，并使用独立的公开 briefing 和参考资源。
- briefing 只能说明任务目标、任务卡位于出生点附近、场景只有一把目标钥匙以及通用
  Pickup 操作方法；不得公开五个候选位置、本局选择、最远出生点算法、节点路径或随机种子。

## 场景请求上限

- `find_contract` 的 MCP `act` 请求硬上限为 500。
- `find_key` 的 MCP `act` 请求硬上限为 200。
- Python 在 Controller 握手确认 `scenario_id` 后选择当前场景硬上限，并将连接/重连时
  的请求计数清零。
- `AI_PLAY_MAX_ACT_REQUESTS` 保留为全局收紧配置。当前会话的有效上限是
  `min(场景硬上限, AI_PLAY_MAX_ACT_REQUESTS)`，因此环境变量不能将简单任务放宽到
  200 以上，也不能将合同任务放宽到 500 以上。
- 所有进入 `act()` 的请求都计数；其他 MCP 工具不计数。第 N 次请求先完成正常处理，
  如果同一请求产生合法场景终局，场景终局优先，否则才发送
  `end_game/failure/max_requests`。
- `find_key` 的公开 briefing 应说明最多 200 次 `act` 请求，但不得透露计数器内部状态。

## 验证边界

- 固定种子覆盖五个钥匙位置、对应任务卡内容和三个最远出生点。
- 每个回合只有一个世界钥匙，非选中锚点没有钥匙。
- 任务卡始终距出生点 1～2 米。
- 选择的出生点到钥匙距离不小于另外两个候选出生点。
- 拾取失败不结束；成功拾取恰好发出一次 `success/key_picked_up`。
- `find_key` 第 200 次请求成功拾取时以成功终局优先；没有终局时才以
  `failure/max_requests` 结束。
- `find_key` 不初始化合同谜题，`find_contract` 不移动找钥匙模式的钥匙。
- 普通启动、AI 启动、最大请求失败、安全断开和输入释放路径继续通过既有测试。
