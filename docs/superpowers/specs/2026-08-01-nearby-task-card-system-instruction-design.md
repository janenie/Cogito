# 出生点任务卡 System Instruction

## 目标

让黑盒 Codex 玩家在 briefing 要求先读取出生点附近任务卡时，正确识别任务卡的可见外观，先在原地完成系统扫描并读取任务卡，避免把它误判为装饰物后远距离探索。

## 设计决策

- 规则写入 `build_player_developer_instructions()`，作为 Codex 配置中的高优先级 developer/system instruction，不只依赖普通玩家 user prompt。
- 该规则仅在 briefing 明确要求先读取出生点附近任务卡时启用。
- 明确公开可见外观：任务卡不是普通纸张，而是青绿色/蓝绿色的独立标志；细杆底座上方带同心圆、靶心或旋涡状发光圆环，中间有白色小牌。它可能看起来像装饰标记，但应作为最高优先级任务卡候选。
- 首次观察后保持原地，每次水平旋转 45 度并获取新 observation，最多覆盖 360 度；一旦找到任务卡候选立即停止扫描。
- 截图未随公开朝向变化时，不得把旧截图当成已检查的新扇区；等待全新 observation 后再继续。
- 发现候选后用短步靠近，将准星对准标志中央，再调用 `probe_interaction`；远距离 `not_found` 不能作为排除依据。出现读取交互后执行 `interact` 并读完任务卡。
- 读卡前不得离开出生区域或开始跨房间寻找最终目标。水平一圈仍未找到时，才在原地补充向上和向下扫描。

## 验收标准

- 单元测试确认 developer/system instruction 包含任务卡外观、45 度分区、360 度上限、截图刷新约束、靠近后探测及读卡前不离开。
- 既有黑盒安全断言继续通过，instruction 不包含场景源码、节点路径、内部 ID、坐标、答案或日志路径。
- orchestrator 测试和 `git diff --check` 通过。
- 使用已授权的 `gpt-5.6-sol`、`high` reasoning、AWM 连续三局真实 `find_key` 验收，观察是否能先读卡再完成任务。

## 范围之外

- 不修改任务卡模型、场景位置、Godot 交互距离或 MCP 协议。
- 不修改剩余钥匙候选、50 步上限、AWM 数据结构或 supervisor 终局解析。
