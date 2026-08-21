# Deep Agents Yibu AI Play Host

这个目录提供一个单进程入口，以 LangGraph Deep Agents 代替 Codex Agent harness，直接通过
Yibu 的 OpenAI 兼容 Chat Completions 接口游玩 Cogito。它不会启动 `codex`、创建
`CODEX_HOME` 或使用 Responses 代理。

## 安装

使用 Python 3.11 或更高版本，推荐在仓库外或本地虚拟环境中安装锁定依赖：

```bash
python3.12 -m venv .venv-deepagents
.venv-deepagents/bin/python -m pip install \
  -r tools_langgraph_deepagents/requirements.lock.txt
```

默认凭据文件是仓库根目录中已被 Git 忽略的 `newak.py`。Host 只用 AST 读取所选的字面量
字典，不会执行该文件：

```python
ak = {"key": "replace-locally", "url": "https://yibuapi.com"}
```

可用 `--credential-name ak1` 选择同文件内另一个字典，或用 `--yibu-credentials` 指向其他
本地文件。URL 必须为 HTTPS，路径只能为空或 `/v1`；API key 不进入命令、日志、
`session.json` 或 checkpoint。

## 运行

从仓库根目录启动唯一入口：

```bash
.venv-deepagents/bin/python -m tools_langgraph_deepagents \
  --scenario find_contract \
  --runs 3 \
  --model gemini-3.6-flash \
  --artifact-root ~/workspace/ai_play/gemini_3p6_flash
```

启动时会明确提示：获准公开的 RGB/深度图将上传到外部模型、产生 token/费用，并把可信轨迹
和 Agent checkpoint 保存在本地。输入精确的 `RUN` 后，应用才会启动 stdio MCP Server、
Godot supervisor 和模型调用。已经由外层自动化完成同等确认时可传
`--confirm-external-run`。

应用默认启用 AWM，只向模型开放 `briefing`、`workflow_memory_read`、`observe`、`act` 和
`workflow_memory_update`；`--workflow-memory disabled` 时只开放前三个基本游戏工具。
Deep Agents 自带的文件、Shell 和子 Agent 工具从模型工具面移除，并在运行时再次拒绝；所有
MCP 工具调用严格串行。

MCP 返回的 RGB JPEG 和深度 PNG 直接作为标准多模态 `ToolMessage` 进入下一轮。每次模型
请求前硬性只保留最新十个图片内容块（通常最多五组 RGB + 深度），旧图片移除但文本和模型在
正常回复中生成的 caption 保留；不会额外发起 caption API 请求。

## 续跑与产物

每次新运行会打印 `run_dir`。中断后使用同一模型、场景、总局数、AWM 模式和 benchmark seed：

```bash
.venv-deepagents/bin/python -m tools_langgraph_deepagents \
  --scenario find_contract \
  --runs 3 \
  --model gemini-3.6-flash \
  --resume-run /absolute/path/to/run_dir
```

应用根据 `workflow_memory.json` 的正式 `success`/`failure` 终局计算剩余局数，并复用稳定的
LangGraph thread 与 `deepagents_checkpoint.sqlite`。Agent 在 supervisor 仍运行时提前结束，
应用会在同一 checkpoint 上继续新的 Agent turn，不设固定重启次数。

主要本地产物：

- `session.json`：不含凭据的运行配置与版本元数据。
- `trusted_mcplogs/`：白名单轨迹、RGB 截图、AWM 和 `supervisor.log`；深度图仍按现有契约不落轨迹。
- `deepagents_checkpoint.sqlite`：可续跑的模型消息状态，可能包含此前传给模型的图片 Base64。

`Ctrl-C`、模型/MCP 异常或 supervisor 异常都会先由 Host 调用 MCP `stop`，再关闭子进程与会话，
确保释放模拟输入。自动化测试使用本地假模型、假 MCP 和假进程，不读取真实凭据，也不产生外部
请求。
