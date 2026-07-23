# 仓库协作指南

## 项目概览

Cogito 是一个基于 Godot 4 的第一人称沉浸式模拟游戏模板。引擎版本和启用的插件以
`project.godot` 为准；当前项目面向 Godot 4.7，启动场景为
`addons/cogito/DemoScenes/COGITO_0_MainMenu.tscn`。

当前分支还包含 AI First Play，这是一套需要显式启用的自主游玩系统：

- `addons/cogito/AIPlay/` 下的 Godot 代码负责捕获获准公开的观察数据，并执行有严格
  限制的输入动作。
- `ai_play/` 下的 Python 边车进程负责模型调用、数据验证、记忆、日志和本机回环
  WebSocket 服务器。
- 两端默认通过 `127.0.0.1:8765` 通信，协议版本为 1。

## 仓库地图

- `addons/cogito/`：主要的 Godot 插件。
  - `Components/`：可复用的玩家、UI、属性和交互组件。大多数世界交互都是继承自
    `InteractionComponent` 的子节点。
  - `CogitoObjects/`：玩家、门、密码盘、开关、容器和其他可交互世界对象。
  - `InventoryPD/` 和 `Wieldables/`：库存数据、物品资源、武器和消耗品。
  - `CogitoNPC/`：可复用的 NPC 和状态机实现。
  - `SceneManagement/`、`QuestSystem/` 和 `EasyMenus/`：由自动加载单例支持的全局
    系统。
  - `DemoScenes/`：可游玩内容。`COGITO_3_Lobby.tscn` 是 AI First Play 场景。
  - `AIPlay/`：观察器、执行器、WebSocket 桥接器、控制器和可复用控制器场景。
- `addons/input_helper/` 和 `addons/quick_audio/`：仓库内附带的第三方插件。除非任务
  明确涉及它们，否则不要修改。
- `ai_play/src/ai_play/`：Python 边车源代码。
  - `config.py` 和 `main.py`：配置与进程入口。
  - `bridge_server.py`：本机回环 WebSocket 协议和会话所有权。
  - `agent_loop.py`：串行化的观察、决策、行动生命周期。
  - `api_client.py`、`prompts.py`：多模态 API 调用和模型消息。
  - `action_schema.py`、`observation_schema.py`：严格的传输数据验证。
  - `memory.py`、`run_logger.py`：有容量限制的持久化和只追加运行轨迹。
- `ai_play/tests/`：pytest 单元测试和本机回环集成测试。
- `tests/ai_play/`：Godot 无界面契约测试。
- `tests/*.sh`：场景、启动、NPC 和凭据的静态检查。
- `docs/`：Sphinx 源文件和项目文档。将 `docs/_build/` 视为生成输出；应编辑 `.rst`
  源文件。
- `docs/superpowers/specs/` 和 `docs/superpowers/plans/`：针对当前分支工作的带日期
  设计与实现记录。
- `code_read/` 和 `game_script/`：关于场景内部结构和关卡设计的开发者笔记，绝不能
  成为运行时模型的输入。

## 不可妥协的 AI 安全边界

- AI 游玩必须保持显式启用。正常启动 Lobby 时 `auto_start = false`；精确的 Godot
  用户参数是 `-- --ai-play`。
- Escape 是物理紧急停止键。断开连接、无效数据、API 失败和节点销毁都必须释放所有
  模拟输入。
- Godot 到 Python 的服务器必须使用精确的数字回环地址 `127.0.0.1`，不得扩大到局域网
  或公网接口。
- 绝不能提交 API 密钥，也不能把密钥复制到源代码、测试、文档、测试夹具、命令参数或日志。
  使用 `AI_PLAY_API_KEY`，或采用 `ai_play/README.md` 中记录且已被忽略的本地
  `api_key.py` 机制。
- 游玩模型只能接收文档规定的相机图像、可见交互文本、获准公开的玩家状态、动作结果、
  运行时按键绑定，以及从这些观察中产生的记忆。
- 绝不能把场景源码、节点路径、隐藏状态、仓库文件、谜题答案，或来自
  `game_script/`、`code_read/`、测试、规格和计划的事实加入提示词、种子记忆、API
  载荷或黑盒验收提示。
- 除非用户明确要求，并且了解截图、令牌、费用和本地轨迹持久化的影响，否则不要运行
  真实外部模型验收。自动化测试必须不依赖真实凭据。

## 跨层契约规则

- Python 和 GDScript 两端的协议常量、数据包字段、动作名称、数值边界和上下文门控必须
  保持同步。
- 所有不可信数据都必须在两端验证。保留精确字段检查、有限数检查、观察编号关联、每批
  最多三个动作，以及改变上下文的动作必须位于批次末尾等规则。
- 在动作批次成功送达之前，Python 边车不得修改实时记忆。
- Godot 执行器必须使用 COGITO 的常规输入、用专用设备 ID 标记合成事件，并在所有退出
  路径中释放持续按下的移动输入。
- 修改公开协议、环境变量、控制方式、隐私行为或日志布局时，必须在同一改动中更新
  `ai_play/README.md` 和对应测试。

## 编码与资源约定

- 遵循相邻代码的风格。新增 GDScript 使用制表符缩进、`snake_case` 成员和函数、
  `PascalCase` 的 `class_name` 声明；在合适时使用带类型的函数签名和导出属性。
- Python 使用四空格缩进和 `snake_case`，标准库导入位于本地模块导入之前，并保持模块
  职责集中。仓库没有可安装的 Python 包元数据，因此运行时需要把 `ai_play/src` 加入
  `PYTHONPATH`。
- 优先使用小型组件和信号，不要向玩家或场景脚本添加无关职责。
- 保留 Godot 资源路径、节点名、导出属性类型和 UID 引用。场景检查依赖有意设计的连线
  和部分精确值。
- 可以使用 Godot 编辑器时，范围较大的 `.tscn` 或 `.tres` 改动应通过编辑器完成。手动
  编辑时保持差异最小，并运行编辑器导入和解析检查。
- 不要手动编辑 `.godot/`、Python 缓存、运行时记忆和日志、`docs/_build/` 等生成缓存。
  没有资源相关理由时，不要删除或重新生成已跟踪的 `.uid` 和 `.import` 文件。

## 环境配置与运行

在 PowerShell 中配置 Python 边车：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ai_play\requirements.txt
$env:PYTHONPATH = "ai_play/src"
```

运行边车：

```powershell
.\.venv\Scripts\python.exe -m ai_play.main
```

边车开始监听后，需要显式启用 AI 的 Lobby 启动命令为：

```text
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn -- --ai-play
```

环境变量、恢复记忆、轨迹位置、隐私影响和模型提供方要求请参阅
`ai_play/README.md`。

## 验证

先运行与改动最相关的最小测试，再运行受影响的完整测试套件。

Python 边车：

```powershell
$env:PYTHONPATH = "ai_play/src"
.\.venv\Scripts\python.exe -m pytest ai_play\tests -q
```

Godot AI 契约测试：

```text
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --editor --quit
```

静态集成和密钥检查：

```bash
bash tests/check_ai_play_lobby.sh
bash tests/check_ai_play_start_script.sh
bash tests/check_friendly_human_npc.sh
bash tests/check_lobby_friendly_npc.sh
bash tests/test_ai_play_secret_scan.sh
```

修改 Sphinx 文档时：

```bash
python -m pip install -r docs/requirements.txt
sphinx-build -b html docs docs/_build/html
```

最后始终运行 `git diff --check`。如果无法使用 Godot，应运行其余所有相关检查，并明确
说明尚未执行的引擎验证。
