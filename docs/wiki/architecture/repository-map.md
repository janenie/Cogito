> 摘要：本页维护 Cogito 的项目入口、仓库地图和主要模块职责。

# 项目概览与仓库地图

Cogito 是一个基于 Godot 4 的第一人称沉浸式模拟游戏模板。引擎版本和启用的插件以 [`project.godot`](../../../project.godot) 为准；当前项目面向 Godot 4.7，启动场景为 `addons/cogito/DemoScenes/COGITO_0_MainMenu.tscn`。

当前分支包含需要显式启用的 AI First Play 自主游玩系统。它的完整架构和约束见 [AI First Play 系统指南](../ai-play/system-guide.md)。

## 仓库地图

- `addons/cogito/`：主要的 Godot 插件。
  - `Components/`：可复用的玩家、UI、属性和交互组件。大多数世界交互都是继承自 `InteractionComponent` 的子节点。
  - `CogitoObjects/`：玩家、门、密码盘、开关、容器和其他可交互世界对象。
  - `InventoryPD/` 和 `Wieldables/`：库存数据、物品资源、武器和消耗品。
  - `CogitoNPC/`：可复用的 NPC 和状态机实现。
  - `SceneManagement/`、`QuestSystem/` 和 `EasyMenus/`：由自动加载单例支持的全局系统。
  - `DemoScenes/`：可游玩内容。`COGITO_3_Lobby.tscn` 是 AI First Play 场景。
  - `AIPlay/`：观察器、执行器、WebSocket 桥接器、控制器和可复用控制器场景。
- `addons/input_helper/` 和 `addons/quick_audio/`：仓库内附带的第三方插件。除非任务明确涉及它们，否则不要修改。
- `ai_play/src/ai_play/`：Python 边车源代码。
  - `config.py` 和 `main.py`：配置与进程入口。
  - `bridge_server.py`：本机回环 WebSocket 协议和会话所有权。
  - `agent_loop.py`：串行化的观察、决策、行动生命周期。
  - `api_client.py` 和 `prompts.py`：多模态 API 调用和模型消息。
  - `action_schema.py` 和 `observation_schema.py`：严格的传输数据验证。
  - `memory.py` 和 `run_logger.py`：有容量限制的持久化和只追加运行轨迹。
- `ai_play/tests/`：pytest 单元测试和本机回环集成测试。
- `tests/ai_play/`：Godot 无界面契约测试。
- `tests/*.sh`：场景、启动、NPC 和凭据的静态检查。
- `docs/`：Sphinx 源文件和项目文档。`docs/_build/` 是生成输出，应编辑 `.rst` 源文件。
- `docs/superpowers/specs/` 和 `docs/superpowers/plans/`：当前分支工作的带日期设计与实施记录。
- `code_read/` 和 `game_script/`：场景内部结构和关卡设计的开发者笔记，不得成为运行时模型输入。

## 来源

本页整理自仓库根目录的 [`AGENTS.md`](../../../AGENTS.md)；该文件保留面向协作者的摘要、强制约束和 Wiki 导航。
