# Find Key 按位置设置请求上限设计

## 目标

`find_key` 根据本局选中的钥匙位置使用 50 或 100 次 MCP `act` 请求硬上限，缩短较近或
较容易位置的单局游玩时间，同时保留 Python 对所有工具请求的统一计数语义。

## 位置与上限

| `find_key` 内部位置 ID | 请求硬上限 |
| --- | ---: |
| `desktop_desk` | 50 |
| `tv_coffee_table` | 50 |
| `archive_sofa` | 50 |
| `laptop_desk` | 100 |
| `meeting_table` | 100 |

用户使用的房间名称映射为：

- `cubic_room` 对应 `desktop_desk`。
- `break_room` 对应 `tv_coffee_table`。
- `laboratory_room` 对应 `archive_sofa`。

## 跨层数据流

Godot 的 `AIPlayFindKeyMonitor` 在选择位置后计算本回合请求上限。Controller 在版本 3
`hello` 包中为 `find_key` 发送可选字段 `act_request_limit`，值只能是整数 50 或 100。
该字段只用于 Godot/Python 内部控制，不进入 MCP `briefing`、`observe`、`act`、`stop`
结果，也不写入轨迹日志。

Python 桥继续接受没有该可选字段的版本 3 `hello`，此时使用 `find_key` 的默认硬上限
100，以兼容旧 Godot。其他玩法不得发送该字段。Python 将已验证的回合上限交给
`GameSession.attach()`；会话用它与全局配置计算：

```text
实际上限 = min(本回合 50 或 100, AI_PLAY_MAX_ACT_REQUESTS)
```

请求计数仍发生在 Python `act()` 入口，因此过期观察、非法动作、上下文不允许和已有动作
在途等被拒绝的调用仍会消耗额度。Godot 不新增第二套动作计数器。

## 会话与安全行为

- 同一 MCP Server 进程内首次成功握手后，`scenario_id` 和本回合请求上限均被锁定。
- Godot 断开后以相同玩法和相同上限重连时，Python 接受连接并重置当前连接的请求计数。
- 重连上限不一致时返回通用的 `scenario_mismatch`，不向外部模型提供位置或上限细节。
- 非整数、布尔值、非 50/100 值、其他玩法携带字段或额外未知字段都被桥拒绝。
- 达到实际请求上限后继续沿用 `failure/max_requests`、输入释放和游戏结束界面。
- 第 50 或第 100 次请求若先产生 `success/key_picked_up`，沿用既有成功优先级。
- Escape 继续作为物理紧急停止键。

## 公开信息边界

所选位置、候选坐标、随机种子和内部位置 ID 仍不得进入公开简报、观察、动作结果、桥错误、
轨迹日志或黑盒验收提示。内部桥只传递 50/100 数字，不传递位置 ID。公开 briefing 只说明
`find_key` 最多允许 100 次请求，不能根据本回合上限提前透露位置分组。

## 修改范围

- Godot `find_key` 监视器计算本回合 50/100 上限。
- Godot Controller 在 `find_key` 握手中加入已验证的可选上限。
- Python 桥验证可选字段并传入 `GameSession`。
- Python 会话保存回合上限并保持既有计数、重连和终局行为。
- 同步 GDScript、Python 测试、`ai_play/README.md` 和 AI Play Wiki。
- 不改写历史设计规格和实施计划，不修改 `addons/input_helper/` 或
  `addons/quick_audio/`。

## 验证

按 TDD 先增加失败测试，再实现最小跨层修改。先运行相关 Python 与 Godot 测试，再运行
完整 `ai_play` Python 套件和受影响的 AI Play Godot 测试，最后始终运行
`git diff --check`。若无法运行 Godot，必须明确报告缺失的引擎验证。
