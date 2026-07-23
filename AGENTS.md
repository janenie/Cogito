# 仓库协作指南

## 项目锚点

Cogito 是一个基于 Godot 4 的第一人称沉浸式模拟游戏模板。引擎版本和启用的插件以
`project.godot` 为准；当前项目面向 Godot 4.7，启动场景为
`addons/cogito/DemoScenes/COGITO_0_MainMenu.tscn`。

当前分支包含需要显式启用的 AI First Play MCP 游玩系统。外部 MCP 客户端通过 stdio
调用 Python 服务，Godot 与 Python 桥默认通过 `127.0.0.1:8765` 通信，协议版本为 2。

## 项目 Wiki

长期项目知识已整理到 [`docs/wiki/wiki.md`](docs/wiki/wiki.md)：

- [项目概览与仓库地图](docs/wiki/architecture/repository-map.md)
- [AI First Play 系统指南](docs/wiki/ai-play/system-guide.md)
- [开发协作指南](docs/wiki/development/contributor-guide.md)

`AGENTS.md` 只保留协作时必须立即可见的约束。修改架构、长期约定、运行方式或验证流程时，
应同步更新对应 Wiki 页面及其索引。

## 不可妥协的 AI 安全边界

- AI 游玩必须保持显式启用。正常启动 Lobby 时 `auto_start = false`；精确的 Godot
  用户参数是 `-- --ai-play`。Escape 必须始终作为物理紧急停止键。
- Godot 到 Python 的服务器只能绑定精确的数字回环地址 `127.0.0.1`。断开连接、无效
  数据、API 失败和节点销毁都必须释放所有模拟输入。
- MCP Server 不需要 API Key；外部 MCP 客户端凭据不得进入仓库或 Godot/Python 桥协议。
- 外部 MCP 工具只能接收获准公开的运行时观察和 `briefing` 白名单简报；简报只允许
  `ai_play.briefing` 中经过筛选的目标、规则、物体操作说明和固定参考图。场景源码、
  节点路径、内部类名、隐藏状态、其他仓库文件、谜题答案，以及 `game_script/`、
  `code_read/`、测试、规格和计划中的事实不得进入工具结果或黑盒验收提示。
- 未经用户明确要求并确认截图、令牌、费用和本地轨迹持久化影响，不得运行真实外部 MCP
  客户端验收。自动化测试不得依赖真实凭据。

完整边界和跨层契约见 [AI First Play 系统指南](docs/wiki/ai-play/system-guide.md)。

## 协作规则

- 除非任务明确涉及，不要修改 `addons/input_helper/` 和 `addons/quick_audio/`。
- 遵循相邻代码的风格，优先使用小型组件和信号；保留 Godot 资源路径、节点名、导出
  属性类型、UID 引用和有意设计的场景连线。
- Python 与 GDScript 两端的公开协议、验证规则和安全退出行为必须同步。修改协议、
  环境变量、控制方式、隐私行为或日志布局时，同时更新 `ai_play/README.md` 和对应测试。
- 不要手动编辑 `.godot/`、Python 缓存、运行时记忆和日志、`docs/_build/` 等生成内容。
  没有资源相关理由时，不要删除或重新生成已跟踪的 `.uid` 和 `.import` 文件。
- `code_read/` 和 `game_script/` 是开发者笔记，绝不能成为运行时模型输入。

详细的编码、资源和本地运行约定见
[开发协作指南](docs/wiki/development/contributor-guide.md)。

## 验证要求

先运行与改动最相关的最小测试，再运行受影响的完整测试套件。最后始终运行
`git diff --check`；如果无法使用 Godot，应运行其余相关检查，并明确说明尚未执行的引擎
验证。具体命令见 [开发协作指南](docs/wiki/development/contributor-guide.md#验证)。
