# AI Host: Multi-Attempt Cogito AI Play

> `ai_host` 是保留用于兼容和实验的旧 Host。当前受维护的黑盒多局入口是
> [`tools/ai_play_codex_orchestrator.py`](../tools/ai_play_codex_orchestrator.py)，其启动方式、
> 隔离边界和 AWM 契约以 [`ai_play/README.md`](../ai_play/README.md) 为准。

`ai_host` 是 AI Play 的外层 supervisor。它不修改 MCP server，也不把自进化逻辑塞进
Godot。它负责：

- 每局启动一个新的 Godot 进程；
- 通过现有 `ai_play/start_ai.sh` 启动 stdio MCP server；
- 让 agent 玩到成功、失败、停止或超出 MCP 交互上限；
- 失败后关闭 Godot，生成流程级复盘；
- 下一局重新启动 Godot，并传入新的 `--ai-play-seed=<N>`，让场景随机内容和 MCP act
  计数都按新局重置；
- 最多运行 3 局，成功则提前停止。

## 直接 OpenAI API 模式

这种模式下 `ai_host` 自己就是 MCP Host。它会把 MCP tools 转换成 Responses API
function tools，并执行模型请求的工具调用。

```bash
export OPENAI_API_KEY="..."
PYTHONPATH=. .venv/bin/python -m ai_host \
  --adapter openai \
  --scenario daily_routine_cleanup \
  --scene dailyroutine/scenes/home_daily_routine.tscn \
  --max-attempts 3 \
  --max-mcp-interactions 1000
```

如果你有本地 `api_key.py`，`ai_host` 会在 `OPENAI_API_KEY` 未设置时尝试读取其中的
`OPENAI_API_KEY`、`API_KEY` 或 `api_key` 变量。key 只进入 host 进程环境，不会传给
MCP server 或 Godot。

## 交互次数上限

`--max-mcp-interactions` 是用户层的主要安全上限。每次模型要求 host 调用一个 MCP
tool 都算 1 次交互，例如 `briefing`、`observe`、`act` 或 `stop`。一局超过该上限后，
host 会把本局判为失败：

```json
{
  "outcome": "failure",
  "reason": "max_mcp_interactions"
}
```

如果还有剩余局数，host 会关闭当前 Godot 进程并重新开一局。`--max-agent-turns` 仍然保留
为底层保护，表示最多请求模型多少次；一般使用时优先配置 `--max-mcp-interactions`。

## 每局随机种子

`ai_host` 每次启动 Godot 时都会追加 `--ai-play-seed=<N>` 用户参数。第 1 局默认使用
`1001`，第 2 局使用 `1002`，依此类推。这个 seed 只作为 Godot 运行时输入；当前
`daily_routine_cleanup` 使用固定的 4 个散落垃圾点，其他带随机规则的玩法可复用该
per-attempt seed。

## 外部 Agent / Codex 模式

### 本地 Codex 模式

`ai_host --adapter codex-local` 已明确禁用。仅把 Codex 工作目录设为空目录，不能阻止进程
通过文件系统或继承配置读取仓库、开发者笔记和凭据，因此不满足本项目的黑盒安全边界。
命令行和程序化入口都会在启动 Godot、Codex 或创建运行产物前拒绝该 adapter。

需要本地 Codex 黑盒多局验收时，使用受维护的
[`tools/ai_play_codex_orchestrator.py`](../tools/ai_play_codex_orchestrator.py)。该入口会建立
临时 `CODEX_HOME`、工具白名单、受限网络 profile、可信日志侧和独立 Godot 环境；具体命令与
确认要求见 [`ai_play/README.md`](../ai_play/README.md#黑盒-codex-玩家连续-3-局)。

### 通用外部命令模式

这种模式下 `ai_host` 只管理 Godot 的多局生命周期。Codex 或其他 agent 作为外部命令
运行，必须自己通过已配置的 Cogito MCP server 玩游戏，并在结束时写 JSON 报告。

```bash
export AI_HOST_AGENT_COMMAND='your-codex-command-using-{prompt_file}-and-{report_file}'
PYTHONPATH=. .venv/bin/python -m ai_host \
  --adapter external-command \
  --scenario daily_routine_cleanup \
  --scene dailyroutine/scenes/home_daily_routine.tscn \
  --max-attempts 3
```

`AI_HOST_AGENT_COMMAND` 支持这些占位符：

- `{prompt_file}`
- `{report_file}`
- `{run_dir}`
- `{repo_root}`
- `{attempt_id}`

外部 agent 必须写入：

```json
{
  "attempt_id": 1,
  "outcome": "success",
  "reason": "cleanup_complete",
  "summary": "short public summary",
  "mistakes": [],
  "next_strategy": []
}
```

## 复盘约束

每一局都是新随机种子。上一局具体物体位置、坐标、节点路径、源码事实都不能作为下一局
策略。允许保留的是流程级经验，例如：

- 搜索房间要系统化；
- 点击完成按钮前先检查 HUD；
- 不要忘记打开冰箱；
- 手上有垃圾时先送到客厅垃圾桶。

运行记录写入 `ai_host/runs/`，该目录应保持本地忽略，不提交截图、模型 transcript、
API key 或运行日志。
