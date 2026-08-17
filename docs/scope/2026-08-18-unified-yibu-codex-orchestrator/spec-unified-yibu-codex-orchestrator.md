> 由 scope skill 于 2026-08-18 生成

# 统一 Yibu Codex Orchestrator

> 实施状态：已在 `feature/unified-yibu-codex-orchestrator` 完成代码与本地自动化验证；未运行真实收费模型 preflight。

## 目标

Cogito 当前为 Gemini、xAI Grok 和 Doubao 分别维护 Codex orchestrator，其中 Gemini 的未知模型
metadata 会回退为纯文本能力，且默认 MCP 输出表示会让 Codex 0.145 丢弃工具结果中的图片。
本项目新增一个面向 Yibu Responses API 的通用 Codex AI Play 入口，使任意视觉模型 ID 无需新增
provider 专用代码即可使用同一套隔离配置、图片传输、MCP namespace 兼容、AWM、Godot supervisor
和可信日志。首批目标模型为 `gemini-3.1-pro-preview`、`grok-4.6`、
`h:qwen3.8-max-preview`、`MiniMax-M3` 和 `hy3`。

## 决策

- 新入口为 `tools/ai_play_codex_yibu_orchestrator.py`，模型通过 `--model <id>` 选择；模型 ID
  经过非空、长度和控制字符校验后按字面量写入配置，不参与命令拼接。
- 所有目标模型使用 `opus.py` 中同一个 Yibu HTTPS Responses URL 和 API key。凭据继续仅通过
  Python AST 读取字面量 `ak` 字典，不导入或执行文件。
- 任意未知 Yibu 模型默认声明 `input_modalities = ["text", "image"]`。AI Play 不允许在图片
  不兼容时静默降级为纯文本；上游拒绝图片时必须失败关闭。
- 默认 `context_window = 128000`、`auto_compact_token_limit = 90000`，并提供
  `--context-window` 和 `--auto-compact-token-limit` 覆盖。压缩阈值必须小于上下文窗口，二者均
  写入安全运行元数据；前者进入 model catalog 和 Codex 顶层 `model_context_window`，后者进入
  顶层 `model_auto_compact_token_limit`。
- 通用入口不设置或接受 reasoning effort，默认不声明并行工具调用。不得根据模型名猜测这些能力。
- Gemini 旧入口保留为薄兼容包装，复用通用实现并保留现有默认值和 CLI 行为。xAI 官方 Grok
  入口和具有专用协议转换、恢复语义的 Doubao 入口不迁移。
- 通用 Yibu 入口始终用 `--codex-media-output` 启动 MCP 边车，使公开 JSON payload 以文本内容
  紧邻 `ImageContent` 返回，不再同时返回会导致 Codex 丢媒体的 `structuredContent`。
- 第一版只审计图片传输，不在代理中主动裁剪历史图片。每个正式终局后继续切换到干净 Codex
  turn，由 Codex 根据声明的窗口执行上下文压缩。
- 只移植 CC Switch 的 model catalog 设计与 Responses namespace flatten/restore 算法。移植代码
  必须注明来源 commit `a98829ba1e8bd99a1df671e3c36c8bb6aa537e47`、MIT copyright 和许可，
  并在 `tools/third_party/cc-switch/` 保存来源说明及 MIT license；不得引入 CC Switch 桌面应用、
  SQLite、全局配置管理或运行时依赖。
- 按已确认目标更新 `docs/wiki/ai-play/system-guide.md` 和 `ai_play/README.md`，不新建 Wiki 页面。

## 架构

### 通用 Yibu 入口

`ai_play_codex_yibu_orchestrator.py` 负责解析通用 CLI、读取 Yibu 凭据、创建隔离 session、生成临时
Codex 配置并编排现有 MCP、provider proxy、Codex 玩家和 Godot supervisor。provider key 只进入
Codex 玩家环境，不进入代理、Godot、MCP、命令行、运行元数据或日志。

### 临时模型目录

每次会话在权限为 `0700` 的临时 `CODEX_HOME` 内生成权限为 `0600` 的 `model-catalog.json` 和
`config.toml`。catalog 只包含本次请求模型，至少声明 Codex parser 必需字段、文本与图片输入、
上下文窗口以及禁用并行工具调用。`config.toml` 通过 `model_catalog_json` 引用该文件，并设置
`model_context_window` 和 `model_auto_compact_token_limit`；继续关闭非 AI Play 工具、外部网络、
记忆和本地文件图片查看能力，只允许字面量回环地址访问 MCP 与 provider proxy。

### Yibu Responses 代理

现有回环代理继续只绑定 `127.0.0.1`、只接受 `POST /v1/responses` 并只转发到验证后的 HTTPS
Yibu `/v1/responses`。请求侧把获准 MCP namespace 的子工具提升为普通 function，并用确定性的
扁平名称表示；同时重写历史中的 namespace function call。响应侧依据同一请求建立的反向映射，
将流式和非流式 function call 恢复为 Codex 需要的 `name + namespace`。名称冲突、未知工具、
无效映射和审计落盘失败均在外发或交付工具调用前失败关闭。

代理继续写入 metadata-only 的 `provider_requests.jsonl`，记录每次请求的图片数量、顺序、MIME、
字节数和 SHA-256，不记录 Base64/URL、prompt、工具参数、响应正文或 key。

### 兼容入口

Gemini 文件只保留默认模型、旧参数兼容和对通用 main 的委托，不复制配置、代理或生命周期逻辑。
公共实现不得反向依赖 Gemini 名称，以便后续 Yibu 模型只传新 `--model` 值即可运行。

## 流程

1. 入口校验模型、场景、隔离 session root、端口、上下文窗口及压缩阈值，然后以 AST 读取
   `opus.py`。
2. 创建临时 Codex home，写入单模型 catalog 和严格权限配置；启动带
   `--codex-media-output` 的可信 MCP、Yibu Responses 代理、Codex 和 Godot supervisor。
3. Codex 收到 briefing/observe/act 的公开文本与图片；代理将 namespace 工具声明扁平化后把
   Responses 请求原样发送给 Yibu，并记录不含内容的图片元数据。
4. Yibu 返回普通 function call；代理只按本请求的白名单反向映射恢复 namespace，Codex 再调用
   MCP 工具。
5. 正式终局后更新 AWM 并结束当前 Codex turn；多局会话用干净 turn 继续。会话结束时统一停止
   Godot、MCP 和代理并删除临时 Codex home，可信轨迹保留在隔离日志目录。

## 验收标准

- 单一入口能接受五个首批模型 ID，且新增其他合法 Yibu 模型 ID 不需要改代码或 registry。
- 生成的 catalog 精确声明 `text + image`、128000 默认上下文和禁用并行工具；配置顶层精确声明
  128000 上下文与 90000 默认压缩阈值；CLI 覆盖值进入对应配置、catalog 与 `session.json`。
- `auto_compact_token_limit >= context_window`、非正数、超范围值和含控制字符的模型 ID 在启动
  外部进程前被拒绝。
- MCP 命令包含 `--codex-media-output`；observe 的公开 JSON、RGB JPEG 和可用时的 depth PNG
  均可进入 Codex 模型输入，不把 Base64 写入可信轨迹。
- 请求侧 namespace 工具被确定性扁平化，流式与非流式响应能无损恢复；只允许当前 AI Play 工具
  白名单，碰撞及未知函数不能被误路由。
- `provider_requests.jsonl` 能证明实际请求是否携带图片；首次图片不兼容不能退化为无图游戏。
- API key、完整 prompt、工具参数、图片内容和响应正文不出现在配置、session metadata、进程命令
  或审计日志中。
- 旧 Gemini 命令继续工作且复用通用实现；xAI Grok、Doubao、标准 Codex、Claude 和 Kimi 入口
  行为不变。
- 中断、上游失败、无效数据和进程退出仍释放模拟输入并清理全部子进程。
- README 和系统 Wiki 明确记录统一入口、默认能力、覆盖参数、图片审计、CC Switch attribution 和
  真实 API 验收边界。
- 移植文件注明 CC Switch 来源 commit，`tools/third_party/cc-switch/` 包含原作者信息、来源 URL
  和完整 MIT license。

### 测试

- 单元测试覆盖 catalog 内容与 `0600` 权限、模型 ID 校验、上下文参数关系、AST 凭据读取、CLI
  默认值/覆盖值以及 Gemini 包装委托。
- 代理测试覆盖 namespace 声明扁平化、历史 call 重写、tool choice、长名称、名称碰撞、SSE 分块、
  非流式响应恢复、白名单拒绝和图片 metadata 审计。
- MCP 现有测试继续证明 `--codex-media-output` 保留 JPEG/PNG 并将公开 payload 移到文本内容。
- 主编排测试证明只有 Codex 玩家环境收到 key，MCP 命令启用媒体输出，运行元数据包含声明窗口，
  并且所有失败路径纳入统一清理。
- 自动化测试只使用本地 fixture/fake upstream，不读取真实 `opus.py`，不调用外部 API。
- 用户另行确认截图、token、费用和本地日志后，真实 preflight 对每个模型只运行到首次图片请求：
  审计必须出现预期 JPEG/PNG 且工具调用成功；在此之前不运行完整游戏或多局 benchmark。
- 运行最相关测试后运行受影响的完整 Python 套件，最后运行 `git diff --check`；Godot 行为有改动时
  再执行对应引擎测试，否则明确本次没有引擎资源改动。

## 范围之外

- 安装、启动或依赖 CC Switch 应用、数据库或本地代理。
- 写入或接管用户全局 `~/.codex`、同步通用 MCP/skills，或复制 `auth.json`。
- 支持 Chat Completions、Anthropic Messages、Gemini Native 等协议转换。
- 迁移或删除 xAI 官方 Grok 与专用 Doubao orchestrator。
- 在代理层保留最近 N 张图片、总结视觉历史或执行其他主动媒体裁剪。
- 未经用户单独确认运行五个模型的真实 API preflight、完整游戏或批量 benchmark。
