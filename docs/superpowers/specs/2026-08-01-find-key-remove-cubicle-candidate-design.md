# 移除 find_key 的 CUBICLE AREA 候选

## 目标

降低 `find_key` 中过于直接的答案比例：不再把钥匙生成在 `CUBICLE AREA` 的台式电脑办公桌上，同时保持该区域及其内容可供 `find_contract` 正常使用。

## 设计决策

- 从 `find_key` 的随机候选集合中完整移除内部候选 `desktop_desk`。
- 保留四个候选：笔记本电脑办公桌、档案室旁沙发、会议室长桌和大电视茶几。
- 删除 `find_key` 监控器中台式电脑候选的任务文本、导出锚点和映射，并删除 Lobby 中仅供该候选使用的 `DesktopDeskAnchor` 与监控器连线。
- 不删除或修改 `CUBICLE AREA`、其中的家具、标牌和 `find_contract` 线索；`find_contract` 行为不变。
- 所有剩余候选继续使用统一的 50 次 `act` 请求上限。
- 同步公开玩法说明、Wiki 和开发者玩法笔记；`game_script/` 只作为开发者文档，不进入运行时模型输入。

## 验收标准

- 多组确定性种子只能覆盖四个剩余候选，永远不会选择 `desktop_desk`。
- 每个剩余候选仍能正确放置唯一钥匙、写入匹配的任务卡、选择最远安全出生点，并上报 50 次请求上限。
- Lobby 不再为 `find_key` 连接 `DesktopDeskAnchor`。
- `find_contract` 的 CUBICLE AREA 锚点和线索连线保持不变。
- Godot 的 `find_key` 定向测试、AI Play 控制器测试、Python 测试及静态检查通过，最终执行 `git diff --check`。

## 范围之外

- 不调整剩余四个候选的概率、位置、任务卡措辞或请求上限。
- 不改变 CUBICLE AREA 的场景布局。
- 不修改 `find_contract` 玩法。
