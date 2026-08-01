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

### 黑盒 Codex 玩家约定

黑盒 orchestrator 已把受限 Codex 和可信 MCP/Godot 侧分开：Codex 在空工作区与每局临时
`CODEX_HOME` 中启动，专用认证目录只复制 `auth.json`，MCP HTTP 边车由 orchestrator 在仓库侧
启动。不得把日志、截图、轨迹、运行配置、仓库路径、玩法 ID、`AI_PLAY_*` 或 `PYTHONPATH` 放进
玩家目录、提示词或环境。`--model` 与 `--reasoning-effort` 必填；临时配置而非持久配置或 legacy
sandbox 参数决定最小权限边界，且 CLI 与 MCP OAuth 凭据固定从临时 home 的 `file` 存储读取。

Godot bridge 固定为 `127.0.0.1:8765`，可信 HTTP MCP 默认端口为 8766；只能通过 `--mcp-port`
变更后者。`--codex-home`、`--sandbox`、`--approval-policy`、`--ws-host` 与 `--ws-port` 都不是
有效参数。Windows 临时配置请求原生 `elevated` sandbox；运行根必须通过仓库、Git、`AGENTS.md`
与 `.codex/config.toml` 祖先检查。

该设计使用本机 Codex 最小权限 profile，目标是限制该会话通过其配置工具读取仓库和关卡信息；
它不是容器或独立 OS 用户级别的安全边界。涉及真实 Codex、截图、令牌、费用或本地轨迹持久化的
验收，仍需用户单独确认。

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

这些测试只使用临时目录和伪进程，覆盖隔离运行目录、临时认证副本、HTTP MCP 工具白名单、
异常重试及停止标识解析；它们不启动真实 Codex、MCP Server 或 Godot。当前 controller 的 Escape 停止会
输出可被 supervisor 记为 `failure/stopped` 的标识；MCP `stop` 只完成 `stop_ack` 并释放输入，
不产生监督回合终局标识。

黑盒玩家测试覆盖模型/思考强度必填、认证文件白名单及临时副本清理、空且隔离的玩家目录、
确定性临时 Codex 配置、按 `--workflow-memory enabled|disabled` 选择的 HTTP MCP 工具白名单、
玩家/可信侧环境隔离、提示词不含游戏实现信息，
以及 MCP/Codex/supervisor 任一异常后的收束。测试仍不得启动真实 Codex、MCP Server 或 Godot。

Godot AI 契约测试：

```text
# 干净 worktree 首次测试前先生成忽略的导入产物和全局类缓存
godot --headless --path . --editor --quit
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_interaction_probe.gd
godot --headless --path . --script tests/ai_play/test_cogito_keypad_result.gd
godot --headless --path . --script tests/garden/test_garden_ai_play.gd
godot --headless --path . --script tests/garden/test_garden_game1.gd
godot --headless --path . --script tests/garden/test_garden_scene.gd
```

隔离 Codex 玩家多局验收的 Godot 生命周期由 supervisor 管理；真实运行前还须获得用户对截图、
令牌、费用和轨迹持久化的明确确认：

```bash
python3 tools/ai_play_codex_orchestrator.py \
  --runs 3 --scenario find_contract \
  --model gpt-5.6 --reasoning-effort high \
  --codex-auth-home ~/.codex-cogito-player
python3 tools/ai_play_supervisor.py --runs 3 --scenario find_contract
```

orchestrator 每次在隔离的 `--session-root` 下创建空玩家启动目录和可信的 `trusted_mcplogs/`。
supervisor 只监听 Godot 的 `AI_PLAY_GAME_OVER outcome=<success|failure> reason=<reason>`
终局标识、`AI_PLAY disabled; reason=mcp_stop|escape_stop` 停止标识和进程状态；
MCP/Godot 停止标识按 `failure/stopped` 计入该局并继续后续局数。两者都不得扩展为读取
轨迹、截图、源码或模型上下文。隔离玩家 Codex 不读取 `AI_PLAY_LOG_ROOT`、轨迹、摘要
或截图；这些内容只留在可信 MCP 边车侧，玩家只可通过获准的五个 MCP 工具取得公开结果。

桥协议变更还必须覆盖 Godot JSON 数值规范化：协议版本只接受非布尔且数值精确等于 `4`
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

本页整理自仓库根目录的 [`AGENTS.md`](../../../AGENTS.md)、已批准的
[`AI Play MCP spec`](../../scope/2026-07-23-ai-play-mcp/spec-ai-play-mcp.md) 和已实施的
[`黑盒 Codex 玩家 spec`](../../scope/2026-07-26-blackbox-codex-player/spec-blackbox-codex-player.md)。
