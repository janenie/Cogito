> 由 scope skill 于 2026-07-26 生成；实施状态：已于同日落地。

# 黑盒 Codex AI Play 玩家

## 目标

将 `tools/ai_play_codex_orchestrator.py` 从“提示词约束的隔离玩家”改为本机硬化的黑盒
玩家启动器。每次游玩都启动一个新的 Codex 会话；该会话不能通过本地文件、继承配置、环境
变量、Web 搜索、额外 MCP 或玩家目录中的运行产物取得当前仓库、场景/关卡配置、隐藏状态、
测试、规格或日志信息。它获得的信息仅限初始操作约束，以及 `cogito_ai_play` 的公开
`briefing`、`observe`、`act`、`stop` 结果；实际游戏目标由 `briefing` 提供。

本规格采用用户选择的本机硬化方案，而非容器、VM 或独立 OS 用户。它使用 Codex 的本机
最小权限配置来限制该会话的工具可读范围，但不宣称可抵抗同一 Windows 用户下绕过 Codex
沙箱的恶意本机进程。

## 决策

- 每次启动必须显式提供 `--model` 和 `--reasoning-effort`。启动器不再依赖 Codex 的动态
  默认模型或思考强度；值会写入本次临时 Codex 配置，并由 Codex 验证模型与强度是否兼容。
- 持久目录 `--codex-auth-home` 只用作专用认证来源，默认
  `~/.codex-cogito-player`。它必须含有 Codex 的文件凭据；启动器只复制该凭据到本局的临时
  `CODEX_HOME`，绝不读取、合并或保留其中的 `config.toml`、插件、技能、MCP、记忆、会话或
  其他文件。运行结束（包括异常）后删除临时 home 及其凭据副本。
- 每局的 `player_workspace` 必须为空，且不能位于当前仓库之内或任何带有项目配置、Git 根、
  `.codex/config.toml` 或 `AGENTS.md` 的祖先目录下。启动器不得在其中写入
  `ai_play_run_config.json`、MCP 日志、截图、轨迹、提示词、模型输出或任何其他可被玩家读取的
  游戏产物；不满足该隔离根条件的 `--session-root` 必须失败关闭。
- 编排器作为可信侧直接启动 Python MCP 服务，而不是让 Codex 通过仓库中的
  `ai_play/start_ai.sh` 启动它。MCP 服务新增仅绑定 `127.0.0.1` 的本地 Streamable HTTP
  传输，默认监听独立的 `--mcp-port 8766`；现有 stdio 入口保持兼容。玩家配置只保存这个
  本地 URL，不包含仓库路径、Python 路径、启动脚本路径或玩法 ID。
- 玩家 Codex 的临时配置只启用名为 `cogito_ai_play` 的 MCP Server，且以
  `enabled_tools = ["briefing", "observe", "act", "stop"]` 固定工具白名单；服务无法初始化
  时 Codex 启动失败。任何已有用户 MCP、插件、技能、项目配置或会话状态都不得被加载。
- 临时配置使用自定义权限 profile，而不混用旧式 `--sandbox` 参数：模型生成的本地命令只可读
  `:minimal` 和空的工作区，不可访问仓库、认证来源、临时 Codex home、运行目录、日志目录或
  网络。配置同时关闭 Web 搜索、子代理、记忆读写和登录 shell，并将子进程环境策略设为
  `inherit = "none"`；CLI 与 MCP OAuth 凭据存储固定为 `file`，避免访问系统凭据库。在 Windows
  上配置请求 Codex 原生 `elevated` sandbox；无法建立时应失败并修复本机权限环境，而不是回退到
  更宽松模式。
- 启动器为 Codex、MCP 和 supervisor 分别构建环境。Codex 环境只包含运行所需的系统变量和
  指向临时 home 的路径；不得继承 `AI_PLAY_*`、`PYTHONPATH`、代理、凭据或任意用户环境变量。
  可信 MCP 进程才接收桥地址、日志根和 `PYTHONPATH`。
- 玩家初始提示词只说明黑盒游玩规则和四个 MCP 工具的使用顺序，不含玩法 ID、仓库路径、
  运行配置文件名、日志位置、关卡信息或任何实现事实。目标、规则、物体操作说明和参考图只由
  `briefing` 的既有白名单结果提供。
- 固定的 Godot 桥仍只绑定 `127.0.0.1:8765`。启动器必须先确认桥端口和 MCP HTTP 端口均未被
  占用，启动可信 MCP 边车并等待其桥与 HTTP 监听就绪，之后才启动 Codex 和 supervisor。
  任一可信子进程或 Codex 异常退出时，启动器终止其余子进程；MCP 退出仍走既有断线和输入释放
  路径。
- 不保留可弱化边界的 `--sandbox`、`--approval-policy` 或旧 `--codex-home` 行为。前两者由
  固定临时配置管理；`--codex-auth-home` 是唯一的持久 Codex 目录接口。旧命令文档同步替换。

## 架构

```text
可信侧（可读取仓库）
orchestrator
  ├─ trusted MCP sidecar (127.0.0.1:<mcp-port>)
  │    └─ Godot bridge (127.0.0.1:8765) + trusted trajectory logs
  └─ supervisor ────────────────────────────────┘

受限玩家侧（Codex）
empty player_workspace + per-run temporary CODEX_HOME
  └─ only cogito_ai_play remote MCP: briefing / observe / act / stop
```

orchestrator 将可信日志根、MCP 配置和临时凭据与玩家工作区分开。玩家工作区仅是 Codex 的
工作目录，创建后保持为空；可信日志仍可按现有审计策略保留在本次运行目录，但没有路径或
环境变量会传给玩家。Windows 默认运行根位于当前仓库所在驱动器根目录的
`cogito_ai_player_runs/`，非 Windows 默认位于 `/tmp/cogito_ai_player_runs/`，以避免从用户
home 的项目配置继承上下文。

启动器创建临时 `CODEX_HOME` 后，写入完整、确定性的配置模板，而不是追加到已有文件。该模板
包含模型、思考强度、唯一 MCP URL、工具白名单及权限 profile。认证副本仅存在于临时 home。
启动器在 `finally` 中终止所有子进程并移除该 home，即使 MCP、Codex 或 supervisor 的启动失败。

MCP 服务的 HTTP 模式沿用同一 `FastMCP` 工具注册、`GameSession`、公开 briefing loader 与
轨迹记录器；它不是新的游戏 API，也不额外公开资源、提示词、文件、场景、节点或状态端点。
stdio 模式继续服务于现有手动 MCP Host 用例。

## 流程

1. 操作者先在专用认证目录执行 `codex login`，然后调用启动器，并传入 `--model`、
   `--reasoning-effort`、玩法和运行次数。
2. 启动器校验所有数值、`127.0.0.1` 地址、两个端口不同且空闲、认证文件、玩家工作区祖先不含
   仓库或项目指令，以及模型/思考强度字符串不含空白或控制字符注入。
3. 启动器创建一个空玩家目录、可信日志目录和临时 Codex home；只复制认证文件并写入固定的
   玩家配置。它构造独立的最小 Codex 与可信侧环境。
4. 启动器用受信任 Python 环境在仓库侧启动 MCP HTTP 边车。边车先建立 Godot bridge；两个
   监听地址均就绪后，启动器才启动 Codex。
5. Codex 在空工作区运行，读取固定的初始提示词并只能发现四个 MCP 工具。它先调用
   `briefing`，再经 `observe` 和 `act` 完成独立游玩；它不能从本地目录、Web 或其他工具取得
   游戏信息。
6. 启动器只在可信 MCP 边车已监听且 Codex 启动存活时启动 supervisor。supervisor 维持现有的
   Godot 多局生命周期，不读取模型上下文或可信轨迹。
7. 终局、异常、超时或中断时，启动器收束所有子进程；MCP 断连释放模拟输入，临时 Codex home
   被删除，可信日志按现有位置保留。

## 验收标准

- 启动器的参数解析拒绝缺失的 `--model` 或 `--reasoning-effort`，并将两个精确值写入临时
  Codex 配置；无默认模型或默认思考强度。
- 认证复制只接受专用认证目录中的预期凭据文件；源目录的 `config.toml`、MCP、插件、会话和
  其他内容都不会出现在临时 home。缺失或不可读凭据会在启动任何子进程前失败。
- 每局玩家工作区为空，并且 run config、日志、截图、轨迹和认证文件均位于该目录之外。将
  `--session-root` 放到仓库、其他项目根或含 `AGENTS.md`/`.codex` 配置的祖先下会失败，而非让
  Codex 继承项目配置或指令。
- 玩家配置只含一个 `cogito_ai_play` MCP URL、四项 `enabled_tools`、指定模型/思考强度和固定的
  最小权限设置；它关闭 Web 搜索、子代理和记忆，不包含仓库或启动脚本路径。
- Codex 子环境不继承任意 caller 环境中的秘密、`AI_PLAY_*`、`PYTHONPATH`、代理或额外路径；
  MCP 子环境拥有运行桥所需的最小变量，且两者不能混用。
- 可信 MCP 边车绑定精确 `127.0.0.1`，只在启动器指定的本地端口提供已有的四个工具。stdio 模式
  仍保持现有行为；HTTP 模式不增加工具、资源或隐藏状态输出。
- MCP HTTP 端口、Godot bridge 端口、认证文件或边车就绪检查失败时，启动器不会启动 supervisor，
  并确保已启动的子进程和临时凭据副本被清理。
- 玩家提示词不包含玩法 ID、源码/场景/测试/计划事实、日志或配置路径；它仅要求通过 MCP 获取
  目标和操作信息。
- 自动化测试只使用临时目录、伪进程和 MCP 本地测试替身；不得启动真实 Codex、真实 Godot 或
  使用真实凭据、截图、令牌或外部模型调用。

### 测试

- 为 orchestrator 增加单元测试：必填模型/思考强度、拒绝危险路径和注入字符串、空工作区、
  临时 home 的凭据白名单和清理、确定性配置、MCP URL/工具白名单、环境隔离、提示词清洁性、
  端口/边车启动顺序，以及异常分支的三进程终止。
- 为 MCP Server 增加测试：HTTP 参数解析、仅允许 `127.0.0.1`、正确调用 Streamable HTTP
  transport，以及现有 stdio 入口与四工具列表不回归。
- 运行现有 orchestrator、supervisor 和 `ai_play` Python 测试；静态检查 README/Wiki 中不再描述
  持久玩家配置、玩家可读日志或由 Codex 启动仓库脚本。
- 最后运行 `git diff --check`。真实 Codex/Godot 黑盒验收需要用户另行确认截图、令牌、费用和
  本地轨迹持久化影响，不能作为本改动的自动化测试。

## 范围之外

- 容器、VM、Windows Sandbox、专用 OS 用户、网络命名空间或抵抗同一用户恶意本机进程的强隔离。
- 远程公网 MCP、跨主机访问、OAuth、额外 MCP 工具、资源、提示词或浏览器能力。
- 修改 Godot 场景、玩法目标、公开观察 schema、动作白名单或隐藏状态规则。
- 自动选择模型/思考强度、调用外部模型 API、保存模型记忆、从轨迹自动学习或真实外部玩家验收。
