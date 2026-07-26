> 摘要：本页维护 Cogito 的代码与资源约定、本地运行方式和验证流程。

# 开发协作指南

## 编码与资源约定

- 遵循相邻代码的风格。新增 GDScript 使用制表符缩进、`snake_case` 成员和函数、`PascalCase` 的 `class_name` 声明；在合适时使用带类型的函数签名和导出属性。
- Python 使用四空格缩进和 `snake_case`，标准库导入位于本地模块导入之前，并保持模块职责集中。仓库没有可安装的 Python 包元数据，因此运行时需要把 `ai_play/src` 加入 `PYTHONPATH`。
- 优先使用小型组件和信号，不要向玩家或场景脚本添加无关职责。
- 保留 Godot 资源路径、节点名、导出属性类型和 UID 引用。场景检查依赖有意设计的连线和部分精确值。
- 可以使用 Godot 编辑器时，范围较大的 `.tscn` 或 `.tres` 改动应通过编辑器完成。手动编辑时保持差异最小，并运行编辑器导入和解析检查。
- 不要手动编辑 `.godot/`、Python 缓存、运行时记忆和日志、`docs/_build/` 等生成缓存。没有资源相关理由时，不要删除或重新生成已跟踪的 `.uid` 和 `.import` 文件。

## Python MCP 环境与运行

在 PowerShell 中配置 Python 边车：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ai_play\requirements.txt
$env:PYTHONPATH = "ai_play/src"
```

运行 stdio MCP Server（通常由 MCP 宿主启动）：

```powershell
.\.venv\Scripts\python.exe -m ai_play.mcp_server
```

MCP Server 不需要 API Key 或模型配置；它只在 `127.0.0.1:8765` 等待已显式启用的
Godot 桥连接。启动 MCP 进程后，Lobby 命令为：

```text
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=find_contract
```

WebSocket 桥配置、MCP 客户端配置和隐私边界见 [`ai_play/README.md`](../../../ai_play/README.md)。

## 验证

先运行与改动最相关的最小测试，再运行受影响的完整测试套件。

Python/MCP：

```powershell
$env:PYTHONPATH = "ai_play/src"
.\.venv\Scripts\python.exe -m pytest ai_play\tests -q
```

MCP 相关测试还必须验证工具列表、结构化结果、图片内容、串行动作、过期观察 ID、
Godot 断线和停止时的输入释放；测试不得启动真实外部模型或使用真实凭据。

修改 Codex orchestrator 或 Godot supervisor 时，运行对应的纯本地 Python 单元测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ai_play_codex_orchestrator.py tests\test_ai_play_supervisor.py -q
```

这些测试只使用临时目录和伪进程，覆盖隔离运行目录、四个 MCP 工具审批段、异常重试及
停止标识解析；它们不启动真实 Codex、MCP Server 或 Godot。当前 controller 的 Escape 停止会
输出可被 supervisor 记为 `failure/stopped` 的标识；MCP `stop` 只完成 `stop_ack` 并释放输入，
不产生监督回合终局标识。

Godot AI 契约测试：

```text
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_interaction_probe.gd
godot --headless --path . --script tests/ai_play/test_cogito_keypad_result.gd
godot --headless --path . --script tests/garden/test_garden_ai_play.gd
godot --headless --path . --script tests/garden/test_garden_game1.gd
godot --headless --path . --script tests/garden/test_garden_scene.gd
godot --headless --path . --editor --quit
```

隔离 Codex 玩家多局验收的 Godot 生命周期由 supervisor 管理：

```bash
python3 tools/ai_play_codex_orchestrator.py --runs 3 --scenario find_contract
python3 tools/ai_play_supervisor.py --runs 3 --scenario find_contract
```

orchestrator 每次在 `--session-root` 下创建新的玩家启动目录和 `AI_PLAY_LOG_ROOT`。
supervisor 只监听 Godot 的 `AI_PLAY_GAME_OVER outcome=<success|failure> reason=<reason>`
终局标识、`AI_PLAY disabled; reason=mcp_stop|escape_stop` 停止标识和进程状态；
MCP/Godot 停止标识按 `failure/stopped` 计入该局并继续后续局数。两者都不得扩展为读取
轨迹、截图、源码或模型上下文。隔离玩家 Codex 可以读取本次 `AI_PLAY_LOG_ROOT` 下的
轨迹、摘要和截图来复盘，但不得读取仓库源码、测试、spec、`game_script/`、`code_read/`、
其他运行目录或凭据。

桥协议变更还必须覆盖 Godot JSON 数值规范化：协议版本只接受非布尔且数值精确等于 `3`
的表示，安全整数 `observation_id` 必须在回调、`stop_ack` 和终局确认中保持整数语义。

静态集成和密钥检查：

```bash
bash tests/check_ai_play_lobby.sh
bash tests/check_ai_play_garden.sh
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

最后始终运行 `git diff --check`。如果无法使用 Godot，应运行其余所有相关检查，并明确说明尚未执行的引擎验证。

## 来源

本页整理自仓库根目录的 [`AGENTS.md`](../../../AGENTS.md) 和已批准的
[`AI Play MCP spec`](../../scope/2026-07-23-ai-play-mcp/spec-ai-play-mcp.md)。
