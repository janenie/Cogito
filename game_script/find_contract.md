# 解谜脚本：find_contract

## 核心目标

玩家需要打开 `ARCHIVE` 档案室。

当前场景中已经存在：

- 房间：`ARCHIVE`
- 密码盘：`ARCHIVE/Keypad`
- 门：`ARCHIVE/ArchiveDoor/FrontDoor`
- 可用 NPC：`FriendlyHumanNPC`
- 最终密码：`083001`

说明：`083001` 是设计者配置备注，不应该在前置线索中直接暴露给玩家。

## 谜题核心

这个谜题不再是单纯“找到合同日期”。玩家需要按顺序拿到两段密码信息：

1. `CUBICLE_AREA/computerScreen` 给出合同版本号：`01`
2. `MEETING_ROOM` 的审核记录告诉玩家：档案室门禁密码规则是 `签署日期 + 版本号`
3. `FriendlyHumanNPC` 告诉玩家合同不在档案室纸箱，而在老板办公室抽屉
4. `UPPER_OFFICE_CEO/deskCorner/Drawer` 中找到合同，合同签署日期是 `08/30`
5. 玩家组合得到 `0830 + 01 = 083001`
6. 在 `ARCHIVE/Keypad` 输入 `083001`，打开档案室

这样即使玩家提前乱翻房间，也最多只能找到合同日期 `0830` 或版本号 `01` 的其中一部分，不能稳定解出完整 6 位密码。

## 当前场景可用物件确认

已在 `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn` 中确认存在的可用物件：

- `CUBICLE_AREA/computerScreen`
- `CUBICLE_AREA/computerScreen2`
- `CUBICLE_AREA/computerScreen3`
- `CUBICLE_AREA/computerScreen4`
- `CUBICLE_AREA/computerKeyboard`
- `CUBICLE_AREA/desk`
- `CUBICLE_AREA/desk2`
- `CUBICLE_AREA/desk3`
- `CUBICLE_AREA/desk4`
- `MEETING_ROOM/tableGlass`
- `MEETING_ROOM/tableGlass2`
- `MEETING_ROOM/desk`
- `UPPER_OFFICE_CEO/deskCorner`
- `UPPER_OFFICE_CEO/deskCorner/Drawer`
- `ARCHIVE/cardboardBoxClosed`
- `ARCHIVE/cardboardBoxClosed2`
- `ARCHIVE/cardboardBoxClosed3`
- `ARCHIVE/cardboardBoxOpen`
- `ARCHIVE/cardboardBoxOpen2`
- `ARCHIVE/Keypad`
- `ARCHIVE/ArchiveDoor/FrontDoor`
- `FriendlyHumanNPC`

未确认存在的物件：

- `Whiteboard`
- `Reception`
- `front desk`

因此本脚本不依赖白板或前台电脑，而是使用当前场景已有的办公电脑、会议室桌面、NPC、CEO 办公室抽屉和档案室密码盘。

## 玩家顺序流程

### 第一步：办公区电脑拿到版本号

地点：

- `CUBICLE_AREA`

交互对象：

- `CUBICLE_AREA/computerScreen`
- 或 `CUBICLE_AREA/computerScreen2`

建议组件：

- `ReadableComponent`

玩家看到的内容：

```text
电脑终端：合同检索系统

最近访问记录：

文件名：LUMEN Renewal Contract
负责人：H. Voss
版本号：01
状态：临时借出
签署日期：被会议复核锁定
审核地点：MEETING_ROOM

备注：档案室访问码不只使用日期。请查看审核会记录中的门禁规则。
```

玩家获得的信息：

- 合同名：`LUMEN Renewal Contract`
- 负责人：`H. Voss`
- 版本号：`01`
- 下一步地点：`MEETING_ROOM`

设计目的：

这里给玩家第一段密码信息 `01`，但不告诉它应该放在密码前面还是后面，也不给日期。玩家需要去会议室理解密码规则。

### 第二步：会议室得知密码规则

地点：

- `MEETING_ROOM`

交互对象：

- `MEETING_ROOM/tableGlass`
- 或 `MEETING_ROOM/desk`

表现方式：

- 会议桌上的审核记录
- 或会议桌旁的文件夹

建议组件：

- `ReadableComponent`

玩家看到的内容：

```text
会议记录：LUMEN Renewal 审核会

结论：
合同原件需要重新核对签署日期。

门禁备注：
临时档案室密码格式为 6 位：
签署日期四位 + 合同版本两位

例：MMDD + VV

下一步：
签署日期不在系统里。请询问 H. Voss，他最后接触过合同原件。
```

玩家获得的信息：

- 密码是 6 位
- 规则是 `MMDD + VV`
- 已知 `VV = 01`
- 还缺签署日期 `MMDD`
- 下一步需要找 `H. Voss`

设计目的：

这一步让玩家知道完整密码不是 `0830`，而是 `日期 + 版本`。这能避免玩家看到日期后直接误以为 4 位密码。

### 第三步：询问 H. Voss / FriendlyHumanNPC

地点：

- 使用当前场景中的 `FriendlyHumanNPC`

交互对象：

- `FriendlyHumanNPC`

建议组件/脚本：

- 现有 `friendly_human_npc.gd`
- 或临时使用 `ReadableComponent` / 简单对话文本表现 NPC 提示

玩家看到的内容：

```text
H. Voss：

LUMEN 那份合同？
我没有放回档案室。审计那天太乱了，我把它塞进老板办公室的抽屉里了。

就是 CEO 办公室那张转角桌，下面的抽屉。
别去翻档案室门口的纸箱，那里只有旧包装。
```

玩家获得的信息：

- 合同不在 `ARCHIVE` 门边纸箱
- 合同在 `UPPER_OFFICE_CEO/deskCorner/Drawer`

设计目的：

这一步解决你指出的问题：玩家如果直接去 `ARCHIVE` 找纸箱，不应该直接成功。纸箱可以作为干扰物，只放旧包装或无关文件。真正合同通过 NPC 指向 CEO 抽屉。

### 第四步：CEO 抽屉找到合同日期

地点：

- `UPPER_OFFICE_CEO`

交互对象：

- `UPPER_OFFICE_CEO/deskCorner/Drawer`

建议组件：

- `ReadableComponent`
- 或抽屉打开后露出一个 `Contract_LUMEN_Renewal` 可读文件

玩家看到的内容：

```text
合同文件：LUMEN Renewal Contract

供应方：Lumen Office Systems
负责人：H. Voss
签署日期：08/30
版本号：01

归档备注：
该文件应回收至 ARCHIVE。
```

玩家获得的信息：

- 签署日期：`08/30`
- 版本号确认：`01`

设计目的：

玩家在这里拿到第二段密码信息 `0830`。由于第二步已经告诉玩家规则是 `MMDD + VV`，所以玩家可以组合出 `083001`。

### 第五步：输入 6 位密码

地点：

- `ARCHIVE/Keypad`

玩家操作：

- 输入 `083001`

当前配置：

```gdscript
passcode = "083001"
check_when_entered = true
doors_to_unlock = [NodePath("../ArchiveDoor/FrontDoor")]
```

结果：

- `ARCHIVE/ArchiveDoor/FrontDoor` 解锁
- 玩家可以进入档案室

## 干扰物设计

### ARCHIVE 门边纸箱

可用物件：

- `ARCHIVE/cardboardBoxClosed`
- `ARCHIVE/cardboardBoxClosed2`
- `ARCHIVE/cardboardBoxClosed3`
- `ARCHIVE/cardboardBoxOpen`
- `ARCHIVE/cardboardBoxOpen2`

建议内容：

```text
旧包装箱

里面都是空文件夹和废弃包装。
没有 LUMEN Renewal Contract。
```

作用：

- 防止玩家直接去 `ARCHIVE` 纸箱就成功
- 呼应 NPC 的提示：“别去翻档案室门口的纸箱”
- 让玩家知道自己找错地方，而不是觉得游戏没反应

## 线索链总结

完整顺序：

1. `CUBICLE_AREA/computerScreen`：得到版本号 `01`，并知道去 `MEETING_ROOM`
2. `MEETING_ROOM/tableGlass` 或 `MEETING_ROOM/desk`：得到密码规则 `MMDD + VV`，并知道找 `H. Voss`
3. `FriendlyHumanNPC`：得知合同在 `UPPER_OFFICE_CEO/deskCorner/Drawer`
4. `UPPER_OFFICE_CEO/deskCorner/Drawer`：找到合同，得到签署日期 `08/30`
5. 组合密码：`0830 + 01 = 083001`
6. `ARCHIVE/Keypad` 输入 `083001`

## 推荐实现对象清单

### Cubicle_Computer_Record

建议使用现有物件：

- `CUBICLE_AREA/computerScreen`

推荐组件：

- `ReadableComponent`

功能：

- 给版本号 `01`
- 指向 `MEETING_ROOM`

### MeetingRoom_AuditRecord

建议使用现有物件：

- `MEETING_ROOM/tableGlass`
- 或 `MEETING_ROOM/desk`

推荐组件：

- `ReadableComponent`

功能：

- 说明密码规则 `MMDD + VV`
- 指向 `H. Voss`

### H_Voss_NPC

建议使用现有物件：

- `FriendlyHumanNPC`

推荐实现：

- 使用现有 NPC 对话脚本
- 或挂一个临时可读/交互提示

功能：

- 告诉玩家合同在 `UPPER_OFFICE_CEO/deskCorner/Drawer`
- 明确说明 `ARCHIVE` 门边纸箱不是正确位置

### CEO_Drawer_Contract

建议使用现有物件：

- `UPPER_OFFICE_CEO/deskCorner/Drawer`

推荐组件：

- `ReadableComponent`
- 可选：`PickupComponent`

功能：

- 显示合同签署日期 `08/30`
- 确认版本号 `01`

### Archive_DecoyBoxes

建议使用现有物件：

- `ARCHIVE/cardboardBoxClosed`
- `ARCHIVE/cardboardBoxOpen`

推荐组件：

- `ReadableComponent`

功能：

- 干扰玩家
- 提示这里没有合同

### ARCHIVE/Keypad

已有对象：

- `CogitoKeypad`

配置：

- `passcode = "083001"`
- `check_when_entered = true`
- `doors_to_unlock = [NodePath("../ArchiveDoor/FrontDoor")]`

## 最小可实现版本

最小版本需要 4 个交互线索和 1 个已有密码盘：

1. `CUBICLE_AREA/computerScreen`：可读，给版本号 `01` 和 `MEETING_ROOM`
2. `MEETING_ROOM/tableGlass`：可读，给规则 `MMDD + VV` 和 `H. Voss`
3. `FriendlyHumanNPC`：对话，指向 CEO 抽屉
4. `UPPER_OFFICE_CEO/deskCorner/Drawer`：可读，给合同日期 `08/30`
5. `ARCHIVE/Keypad`：输入 `083001`

这个版本满足“按顺序获取多个关联线索才能解谜”，同时保留玩家乱找的可能性，但不会让乱找直接成功。
