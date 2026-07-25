# Find Key 150 次请求上限设计

## 目标

将 `find_key` 玩法的 MCP `act` 请求硬上限从 200 降至 150。150 次足以完成找钥匙任务，
同时避免无效游玩持续过久。

## 行为

- `find_key` 的场景硬上限为 150 次 `act` 请求。
- 实际上限仍为 `min(150, AI_PLAY_MAX_ACT_REQUESTS)`，全局配置只能进一步收紧上限。
- 第 150 次请求若成功拾取钥匙，沿用既有终局优先级并返回
  `success/key_picked_up`；否则返回 `failure/max_requests`。
- 其他玩法、桥协议、观察内容和输入释放行为均不改变。

## 修改范围

- 更新 Python 场景注册表中的 `find_key` 请求上限。
- 更新场景上限和会话终局相关测试。
- 更新当前 `ai_play/README.md` 和 AI Play Wiki 的上限说明。
- 不改写已经归档的历史设计规格和实施计划。

## 验证

先修改测试期望并确认其因运行时仍返回 200 而失败，再修改生产代码使其通过。随后运行受影响的
Python 测试套件，并最终运行 `git diff --check`。若本次改动不涉及 Godot 文件，则无需新增
Godot 引擎验证。
