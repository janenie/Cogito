# 可操作内容梳理

本文档基于当前项目中的 `addons/cogito/CogitoObjects` 和 `addons/cogito/Components/Interactions` 脚本整理。

说明文字使用中文；但类名、文件名、字段名、信号名保留原始代码命名，方便在 Godot Inspector 和脚本中直接查找。

## 交互系统的基本结构

当前项目的大多数玩家交互都遵循这个结构：

1. 世界物体被加入 `interactable` group。
2. 物体下面挂一个或多个继承自 `InteractionComponent` 的子节点。
3. 玩家准星或交互检测系统找到这个物体。
4. 对应的 `InteractionComponent` 调用 `interact(player_interaction_component)`。
5. 父节点物体执行真正的操作逻辑。

关键基础脚本：

- `addons/cogito/Components/Interactions/InteractionComponent.gd`
- `addons/cogito/Components/Interactions/BasicInteraction.gd`
- `addons/cogito/Components/Interactions/CustomInteraction.gd`
- `addons/cogito/Components/Interactions/HoldInteraction.gd`
- `addons/cogito/Components/Interactions/DualInteraction.gd`

## 最适合放线索的内容

### ReadableComponent

文件：`addons/cogito/Components/Interactions/ReadableComponent.gd`

用途：

用于纸条、日记、墙面提示、电脑文本、海报、地图、说明牌等需要打开阅读 UI 的线索。

常用导出字段：

- `readable_title`
- `readable_content`
- `rich_text`
- `interact_sound`

适合的解谜用法：

- 在纸条里写 `CogitoKeypad` 的密码。
- 写谜语、开关顺序、物品摆放顺序。
- 把一个线索拆成多份，让玩家组合。
- 用叙事文本提示某个物品的用途。

是否推荐放线索：推荐。

### PickupComponent

文件：`addons/cogito/Components/Interactions/PickupComponent.gd`

用途：

用于可以被玩家拾取并进入背包的物品。

常用导出字段：

- `slot_data`
- `display_item_name`

适合的解谜用法：

- 钥匙。
- 碎纸片。
- 电池。
- 任务道具。
- 激活 `CogitoButton` 或 `CogitoSwitch` 所需的物品。

是否推荐放线索：推荐，尤其适合实体线索或关键道具。

### CogitoContainer / LootableContainer

文件：

- `addons/cogito/CogitoObjects/cogito_container.gd`
- `addons/cogito/CogitoObjects/cogito_lootable_container.gd`
- `addons/cogito/CogitoObjects/cogito_loot_drop_container.gd`

用途：

用于箱子、抽屉、柜子、储物箱、保险柜一类可以打开或查看库存的容器。

适合的解谜用法：

- 把纸条藏在抽屉里。
- 把钥匙或道具藏在柜子里。
- 解开一个小谜题后给玩家奖励物。
- 用容器作为关卡推进节点。

是否推荐放线索：推荐。

## 直接可操作的谜题对象

### CogitoButton

文件：`addons/cogito/CogitoObjects/cogito_button.gd`

用途：

可按下的按钮。可以重复使用，也可以设置成一次性使用。

重要信号：

- `pressed()`
- `pressed_ref(button)`

常用导出字段：

- `usable_interaction_text`
- `allows_repeated_interaction`
- `press_cooldown_time`
- `needs_item_to_operate`
- `required_item`
- `objects_call_interact`
- `objects_call_delay`

适合的解谜用法：

- 按下按钮开门。
- 多按钮顺序谜题。
- 需要指定物品才能按的按钮。
- 触发动画、灯光、机关或 `PuzzleController`。

是否推荐放线索：不推荐作为线索本体，但适合作为线索指向的目标。

### CogitoSwitch

文件：`addons/cogito/CogitoObjects/cogito_switch.gd`

用途：

有开关状态的交互物。和 `CogitoButton` 不同，`CogitoSwitch` 有 `is_on` 状态。

重要信号：

- `switched(is_on)`

常用导出字段：

- `is_on`
- `allows_repeated_interaction`
- `needs_item_to_operate`
- `required_item_slot`
- `nodes_to_show_when_on`
- `nodes_to_hide_when_on`
- `objects_call_interact`
- `animation_player`
- `anim_when_switched_on`
- `anim_when_switched_off`

适合的解谜用法：

- 电源开关。
- 多开关组合谜题。
- 灯光开关谜题。
- 需要指定道具才能切换的机关。
- 开关后显示或隐藏某些场景物体。

是否推荐放线索：不推荐作为线索本体，但适合作为线索指向的目标。

### CogitoPressureplate

文件：`addons/cogito/CogitoObjects/cogito_pressure_plate.gd`

用途：

压力板。玩家或物体压上去后触发。

重要信号：

- `plate_activated()`
- `plate_deactivated()`

常用导出字段：

- `is_usable`
- `allows_repeated_interaction`
- `objects_call_interact`
- `plate_node`
- `unweighted_plate_position`
- `weighted_down_plate_position`

适合的解谜用法：

- 玩家站上压力板开门。
- 搬一个重物压住压力板，让门保持开启。
- 多个压力板同时激活才解锁。
- 压力板触发陷阱、灯光、门或控制器。

是否推荐放线索：不推荐，但很适合做物理解谜输入。

### CogitoKeypad

文件：`addons/cogito/CogitoObjects/cogito_keypad.gd`

用途：

数字密码盘，适合做输入密码类谜题。

重要信号：

- `correct_code_entered`

常用导出字段：

- `passcode`
- `check_when_entered`
- `doors_to_unlock`
- `open_when_unlocked`
- `interaction_text_when_locked`
- `interaction_text_when_unlocked`

适合的解谜用法：

- 阅读纸条后输入密码。
- 从多个环境线索组合出密码。
- 密码隐藏在场景、物品、NPC 对话里。
- 输入正确后解锁 `CogitoDoor` 或触发其他机关。

是否推荐放线索：不推荐作为线索本体，但非常适合作为线索解法的目标。

### CogitoDoor

文件：`addons/cogito/CogitoObjects/cogito_door.gd`

用途：

可开、可关、可锁、可解锁的门。

重要信号：

- `door_state_changed(is_open)`
- `lock_state_changed(is_locked)`
- `object_state_updated(interaction_text)`
- `lock_state_updated(lock_interaction_text)`

常用导出字段：

- `is_open`
- `is_locked`
- `key`
- `lockpick`
- `doors_to_sync_with`
- `door_type`
- `auto_close_time`
- `ignore_interaction_raycast`

适合的解谜用法：

- 锁住出口。
- 被 `CogitoKeypad`、`CogitoSwitch`、`CogitoButton` 或 `PuzzleController` 打开。
- 使用 `doors_to_sync_with` 做双开门。
- 用 `auto_close_time` 做限时门谜题。

是否推荐放线索：不推荐，通常作为谜题奖励或阻挡物。

### CogitoSnapSlot

文件：`addons/cogito/CogitoObjects/cogito_snap_slot.gd`

用途：

用于“把指定世界物体放到指定位置”的放置槽。

重要信号：

- `object_placed`
- `object_removed`

常用导出字段：

- `expected_object`
- `is_active`
- `interaction_text_to_place`
- `interaction_text_to_remove`
- `expected_object_hint`
- `snap_position`

当前逻辑：

- `CogitoSnapSlot` 期待一个 `PackedScene`。
- 当一个 `CogitoObject` 进入 `SnapArea3D` 时，会比较该物体的 `cogito_name`。
- 如果和 `expected_object` 实例化后的 `cogito_name` 一致，就会吸附到 `SnapPosition`。
- 吸附后会冻结物体，并发出 `object_placed`。

适合的解谜用法：

- 把雕像放到底座。
- 把电池放入机器。
- 把徽章放到门上的凹槽。
- 多个物品必须放到正确位置。

是否推荐放线索：不推荐，但非常适合做物品放置谜题。

### CogitoTurnwheel

文件：`addons/cogito/CogitoObjects/cogito_turnwheel.gd`

用途：

转轮或阀门类交互物。

适合的解谜用法：

- 阀门谜题。
- 转动机关。
- 打开水流、蒸汽、气体路线。
- 控制计时门或压力系统。

是否推荐放线索：不推荐。

### CogitoSittable

文件：`addons/cogito/CogitoObjects/cogito_sittable.gd`

用途：

可坐下的物体，比如椅子、座位。

适合的解谜用法：

- 玩家坐下后从特定视角看到线索。
- 坐下触发某个对象。
- 用作环境叙事。

是否推荐放线索：视情况可以。比如“坐到椅子上才能看到墙上的密码”。

## 行为型 InteractionComponent

### BasicInteraction

文件：`addons/cogito/Components/Interactions/BasicInteraction.gd`

用途：

调用父节点的 `interact()` 方法。

适用场景：

- 父节点本身已经写好了交互逻辑。
- 需要一个普通按键交互。

### CustomInteraction

文件：`addons/cogito/Components/Interactions/CustomInteraction.gd`

用途：

调用父节点上的指定函数。

常用导出字段：

- `function_to_call`

适用场景：

- 父节点有多个可调用行为。
- 希望交互时调用 `activate`、`inspect`、`solve` 或其他自定义方法。

### LockInteraction

文件：`addons/cogito/Components/Interactions/LockInteraction.gd`

用途：

用于第二交互，常见于门的锁定/解锁操作。

适用场景：

- 一个门同时有开关门和锁门/解锁两种操作。
- 需要额外的锁交互提示。

### HoldInteraction

文件：`addons/cogito/Components/Interactions/HoldInteraction.gd`

用途：

需要长按一段时间才能完成的交互。

常用导出字段：

- `hold_time`

适用场景：

- 打开沉重舱门。
- 搜索物体。
- 强行开启机关。
- 需要等待或蓄力的交互。

### DualInteraction

文件：`addons/cogito/Components/Interactions/DualInteraction.gd`

用途：

组合短按和长按两种行为。

适用场景：

- 短按拾取。
- 长按使用。
- 同一个物体需要两个不同交互。

### PickupComponent

文件：`addons/cogito/Components/Interactions/PickupComponent.gd`

用途：

给物体添加进入背包的拾取行为。

适用场景：

- 世界里的物品被拾取后消失，并进入玩家库存。

### ExtendedPickupInteraction

文件：`addons/cogito/Components/Interactions/ExtendedPickupInteraction.gd`

用途：

把拾取、使用、装填、消耗等行为组合在一起。

适用场景：

- 拾取物品同时可以直接使用。
- 弹药或消耗品相关逻辑。

### CarryableComponent

文件：`addons/cogito/Components/Interactions/CarryableComponent.gd`

用途：

允许世界物体被搬起、放下、投掷、旋转。

常用导出字段：

- `carry_distance_offset`
- `lock_rotation_when_carried`
- `drop_distance`
- `enable_manual_rotating`
- `rotation_speed`

适合的解谜用法：

- 把箱子搬到 `CogitoPressureplate` 上。
- 把物体搬到 `CogitoSnapSlot`。
- 移动物理障碍物。
- 做空间放置谜题。

### ReadableComponent

文件：`addons/cogito/Components/Interactions/ReadableComponent.gd`

用途：

添加可阅读文本 UI。

适用场景：

- 玩家需要读一段文字线索。

### BackpackComponent

文件：`addons/cogito/Components/Interactions/BackpackComponent.gd`

用途：

修改或升级玩家背包尺寸。

适合的解谜用法：

- 作为奖励物。
- 作为进度道具。

## 其他可交互内容

### CogitoObject

文件：`addons/cogito/CogitoObjects/cogito_object.gd`

用途：

基础物理/交互物体。通常和各种 `InteractionComponent` 组合使用。

常见组合：

- `CogitoObject + PickupComponent`
- `CogitoObject + ReadableComponent`
- `CogitoObject + CarryableComponent`
- `CogitoObject + CustomInteraction`

### CogitoStaticInteractable

文件：`addons/cogito/CogitoObjects/cogito_static_interactable.gd`

用途：

静态可交互物体外壳。

适用场景：

- 不需要物理运动，但需要交互的场景物件。
- 环境交互物。

### NPC 交互物

文件：

- `addons/cogito/CogitoNPC/cogito_npc.gd`
- `addons/cogito/DemoScenes/friendly_human_npc.gd`
- `addons/cogito/DemoScenes/lobby_friendly_npc.gd`

用途：

用于 NPC 对话、任务提示、谜题提示。

适合的解谜用法：

- NPC 告诉玩家密码线索。
- NPC 暗示开关顺序。
- NPC 给玩家关键物品。
- NPC 作为剧情推进条件。

### CogitoVendor

文件：`addons/cogito/CogitoObjects/cogito_vendor.gd`

用途：

生成或售卖物体。

适合的解谜用法：

- 玩家购买关键道具。
- 玩家消耗货币获得线索物。
- 售卖某个谜题必须使用的物品。

### CogitoProjectile

文件：`addons/cogito/CogitoObjects/cogito_projectile.gd`

用途：

投射物。命中后可以触发伤害、生成物体，或在延迟后变成可拾取对象。

适合的解谜用法：

- 射击按钮。
- 射击目标。
- 投射物插在某处，之后可被拾取。

### CogitoSecurityCamera

文件：`addons/cogito/CogitoObjects/cogito_security_camera.gd`

用途：

检测玩家或物体的摄像头。

适合的解谜用法：

- 潜行谜题。
- 用开关关闭摄像头。
- 摄像头检测玩家是否进入区域。
- 摄像头检测特定物体是否被放置。

## 推荐的谜题搭建方式

### 简单线索到门

使用：

- `ReadableComponent`
- `CogitoKeypad`
- `CogitoDoor`

流程：

1. 玩家阅读纸条。
2. 纸条里写密码。
3. 玩家在 `CogitoKeypad` 输入密码。
4. 密码正确后解锁 `CogitoDoor`。

### 物品放置谜题

使用：

- `CogitoObject`
- `CarryableComponent`
- `CogitoSnapSlot`
- `CogitoDoor` 或 `PuzzleController`

流程：

1. 玩家搬起正确物体。
2. 玩家把物体带到 `CogitoSnapSlot` 区域。
3. `CogitoSnapSlot` 发出 `object_placed`。
4. 控制器检查是否所有槽位都已经放好。
5. 门解锁或机关启动。

### 压力板谜题

使用：

- `CarryableComponent`
- `CogitoPressureplate`
- `CogitoDoor` 或 `PuzzleController`

流程：

1. 玩家找到可以搬的重物。
2. 玩家把重物放到 `CogitoPressureplate` 上。
3. 压力板激活。
4. 门保持打开或机关启动。

### 多开关谜题

使用：

- `CogitoSwitch`
- `ReadableComponent`
- `PuzzleController`

流程：

1. 线索告诉玩家正确开关状态。
2. 玩家切换多个 `CogitoSwitch`。
3. 控制器检查每个开关的 `is_on`。
4. 状态正确后开门或显示隐藏物品。

### 按钮顺序谜题

使用：

- `CogitoButton`
- `ReadableComponent`
- `SequencePuzzleController`

流程：

1. 玩家找到按钮顺序线索。
2. 玩家按顺序按下多个 `CogitoButton`。
3. 错误顺序会重置谜题。
4. 正确顺序打开奖励路径。

## 当前 Demo 的优先建议

第一阶段建议先做最稳定的一组：

1. 一个带 `ReadableComponent` 的纸条。
2. 一个 `CogitoKeypad`。
3. 一个上锁的 `CogitoDoor`。

这是最容易验证的解谜闭环：读线索、输入密码、开门。

第二阶段再做物理谜题：

1. 一个带 `CarryableComponent` 的花园物体。
2. 一个 `CogitoSnapSlot`。
3. 一个监听 `object_placed` 的控制器。

这样既能复用当前已有系统，也不会一开始就把谜题逻辑做得太复杂。
