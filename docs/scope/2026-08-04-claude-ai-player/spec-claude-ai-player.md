> 由 scope skill 于 2026-08-04 生成

# Claude AI Player Orchestrator

## 目标

在保留现有 Codex 黑盒玩家入口的同时，为 Claude Code 新增完整的 AI First Play 编排入口。Claude 玩家必须沿用现有可信 MCP 边车与 Godot supervisor，在隔离空工作区中完成多局游玩，并保持与 Codex 玩家相同的公开信息边界、工具白名单、生命周期收束和真实验收确认要求。

## 决策

- 保留 `tools/ai_play_codex_orchestrator.py`，新增 `tools/ai_play_claude_orchestrator.py`。
- Claude 入口与 Codex 入口功能对等，包括多局运行、场景选择、workflow memory 开关、Godot 重试、超时、端口和终局 grace 参数。
- 抽取模型无关的公共编排层，由两个入口共同复用 MCP 边车、Godot supervisor、运行目录、进程监控、安全收束和玩家提示词逻辑；模型专用入口只负责认证、配置、命令行和模型特有参数。
- Claude 认证来源为仓库中的 `.claude/settings.local.json`。只有仓库侧可信编排器读取该文件，并只提取明确白名单内的 Claude 服务环境变量写入本局私有临时配置；玩家既不读取该文件，也不获得其仓库路径。编排器不复制其他项目设置、hooks、skills、插件或仓库指令，退出时删除临时配置。
- Claude 玩家使用 `--bare`、`--print`、`--no-session-persistence`、`--strict-mcp-config` 和显式 MCP/工具配置，在隔离空目录启动。`--print` 承载一次非交互 agent turn；该 turn 必须能连续调用 MCP 工具直至完成全部局数，而不是每次工具调用后重启 Claude。
- Claude 玩家只可调用当前 workflow memory 模式允许的 `cogito_ai_play` 工具；始终排除 `stop`，并禁用文件、Shell、Web、Agent、插件、项目设置和项目指令等额外信息源。
- MCP HTTP 服务与 Godot bridge 仍只绑定字面量 `127.0.0.1`。玩家不得获得可信日志根目录、轨迹、仓库路径或其他内部运行时信息。
- 本次实现不运行真实 Claude/Godot 黑盒验收。真实验收继续要求用户事先确认截图、令牌、费用和本地轨迹持久化影响。

## 架构

可信侧公共编排层创建隔离运行目录，启动仅回环 MCP HTTP 边车并等待 MCP 与 Godot bridge 监听，然后启动受限玩家进程和 Godot supervisor。Codex 与 Claude 入口分别生成其临时认证配置和 CLI 命令，但向公共层提供相同的玩家提示词、工具集合和生命周期参数。可信 MCP 边车持有日志根目录；玩家工作区保持为空，且玩家配置在会话结束后销毁。

## 流程

1. 解析并验证场景、端口、超时、运行次数、模型参数和隔离目录。
2. 可信编排器从仓库侧 Claude settings 中筛选认证环境变量，生成仅本局可读的临时配置与严格 MCP 配置；传给玩家的命令和提示词都不包含源 settings 路径。
3. 启动 MCP HTTP 边车，依次等待 MCP 端口和固定 Godot bridge 端口就绪。
4. 在空玩家工作区中以非交互、无持久化、bare 模式启动 Claude，并只开放获准 MCP 工具。
5. 启动 supervisor 管理显式启用 AI Play 的 Godot 多局生命周期。
6. 任一子进程失败、空闲超时、连接断开或正常终局时，公共编排层按现有安全规则收束所有进程并释放模拟输入；最后删除临时 Claude 配置。

## 验收标准

- `tools/ai_play_claude_orchestrator.py` 可独立解析并验证与 Codex 入口对等的公共参数，并提供 Claude 专用 settings、binary、model 和 effort 参数。
- Codex 现有 CLI 行为和安全边界保持兼容，现有相关测试继续通过。
- 两个入口复用同一份模型无关编排与玩家规则，公开协议、工具集合和异常收束逻辑不存在重复实现。
- Claude 临时配置只包含白名单认证环境变量和本局 MCP/权限设置，权限受限，并在正常退出与异常退出后删除；玩家进程不接收仓库 settings 路径。
- Claude 命令启用 bare、非交互、无会话持久化和 strict MCP 配置；不加载仓库 `.claude` 定制、CLAUDE.md、skills、plugins、hooks、agents 或其他 MCP Server。
- workflow memory 启用时只开放 `briefing`、`workflow_memory_read`、`observe`、`act`、`workflow_memory_update`；禁用时只开放 `briefing`、`observe`、`act`；两种模式都不开放 `stop`。
- 玩家环境不包含可信日志路径、Python 仓库路径或无关主机凭据，MCP 与 bridge 地址均为 `127.0.0.1`。
- MCP、Claude、supervisor 任一启动失败、提前退出或空闲超时时，其余子进程都会被终止。
- `ai_play/README.md` 与已确认的三份 Wiki 页面同步记录 Claude 入口、运行方式、安全限制和验证命令。

### 测试

- 新增纯本地 Python 单元测试，覆盖 settings 白名单筛选、临时配置权限与清理、Claude 命令、MCP 工具白名单、环境隔离、参数校验、启动顺序和失败收束。
- 运行 Codex orchestrator 与 supervisor 的相关回归测试，验证公共层抽取未改变现有行为。
- 使用本机 `claude --help`/配置解析能力做不发起模型请求的 CLI 探针；自动化测试不得依赖真实 Claude 凭据、MCP 客户端、Godot 或网络。
- 最后运行 `git diff --check`。若未运行 Godot 引擎验证，交付时明确说明。

## 范围之外

- 不替换或删除 Codex orchestrator。
- 不修改 Godot 到 Python 的协议版本、公开 observation/briefing 内容或场景白名单。
- 不把 Claude Desktop 作为自动多局玩家入口。
- 不运行真实外部 Claude/Godot 黑盒验收，不产生新的真实模型费用或持久化游玩轨迹。
- 不将仓库源码、测试、规格、计划、`code_read/` 或 `game_script/` 暴露给运行时玩家。
