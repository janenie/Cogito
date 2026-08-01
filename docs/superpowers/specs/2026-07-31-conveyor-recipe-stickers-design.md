# Conveyor Profit 双语配方贴纸设计

## 目标

把当前菜单板上的英文缩写列表改成六张独立的双语配方贴纸，使玩家无需记忆
`L/T/M/B/E/C/F` 等缩写，就能在游戏镜头下直接读懂每道菜需要哪些食材、售价和净利润。

## 已确认决策

- 使用中英双语菜名和食材名。
- 六张贴纸采用 `3 列 × 2 行` 布局。
- 贴纸统一使用米白色背景和深色正文，每道菜使用不同颜色的标题条。
- 保留现有深色大菜单板作为贴纸的承托背景。
- 删除当前 `Recipes` 节点中的缩写菜单，不保留任何字母配方缩写。
- 不修改食材成本、配方匹配、售价、利润、点击入口、终局或 MCP 边界。

## 单张贴纸结构

每张贴纸由独立的 `Node3D` 组成，包含背景面板和三个信息层级：

1. 双语菜名标题。
2. 使用完整中英文名称的食材组合。
3. 双语售价与净利润。

格式示例：

```text
沙拉 SALAD
生菜 LETTUCE + 番茄 TOMATO + 蘑菇 MUSHROOM
售价 SALE $7  ·  净利 PROFIT +$3
```

## 六张贴纸内容

| 菜品 | 完整食材 | 售价 | 净利润 |
| --- | --- | ---: | ---: |
| 沙拉 SALAD | 生菜 LETTUCE + 番茄 TOMATO + 蘑菇 MUSHROOM | $7 | +$3 |
| 鸡蛋吐司 EGG TOAST | 面包 BREAD + 鸡蛋 EGG | $8 | +$4 |
| 奶酪吐司 CHEESE TOAST | 面包 BREAD + 奶酪 CHEESE | $10 | +$5 |
| 汉堡 BURGER | 面包 BREAD + 肉 MEAT + 生菜 LETTUCE + 番茄 TOMATO | $15 | +$6 |
| 鱼肉三明治 FISH SANDWICH | 面包 BREAD + 鱼 FISH + 生菜 LETTUCE | $14 | +$7 |
| 蘑菇蛋卷 MUSHROOM OMELET | 鸡蛋 EGG + 奶酪 CHEESE + 蘑菇 MUSHROOM | $14 | +$7 |

## 布局与视觉

- 第一行：沙拉、鸡蛋吐司、奶酪吐司。
- 第二行：汉堡、鱼肉三明治、蘑菇蛋卷。
- 每张贴纸宽度优先保证最长的双语配方不与相邻贴纸重叠。
- 标题条使用六种克制的强调色；背景、正文和价格区保持统一，避免菜单墙过于杂乱。
- 菜名最大，食材组合次之，价格信息最小但仍需在当前预览镜头下可读。
- 贴纸略微离开深色底板，避免深度冲突；不加入动画、卷角或物理摆动。

## 场景结构

在 `Stations/MenuBoard` 下新增 `RecipeStickers` 容器，并创建恰好六个稳定命名的贴纸：

```text
RecipeStickers/
  Salad
  EggToast
  CheeseToast
  Burger
  FishSandwich
  MushroomOmelet
```

每个贴纸包含 `Background`、`TitleBar`、`Title`、`Ingredients` 和 `Economy`。旧的
`Stations/MenuBoard/Recipes` 节点删除。标题节点可继续保留
`CONVEYOR KITCHEN · RECIPE BOARD`，但不得与第一排贴纸重叠。

## 验证

- 场景测试确认 `RecipeStickers` 存在且恰好有六张贴纸。
- 场景测试确认旧 `Recipes` 节点不存在。
- 测试逐张读取公开 Label3D 文本，确认完整中英文食材名存在且不含旧配方缩写。
- 重新渲染 1280×720 总览图并以原始分辨率检查标题、食材和价格没有互相重叠。
- 启动实时 Godot 窗口，在当前游戏镜头下人工确认六张贴纸可读。
- 重跑现有玩法、场景、配方和供应测试，最后运行 `git diff --check`。

## 范围之外

- 不改变菜单配方或经济数值。
- 不新增语言切换或本地化系统。
- 不把贴纸文字做成运行时模型输入；后续 MCP briefing 仍由白名单 loader 单独提供公开规则。
- 不新增贴纸点击、动画、音效或物理效果。
