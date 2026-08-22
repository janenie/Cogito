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

MCP 返回的 RGB JPEG 和深度 PNG 直接作为标准多模态 `ToolMessage` 进入下一轮。Host 每累计
10 组可玩观察（通常为 10 张 RGB + 10 张深度图），就用同一模型和凭据的独立零内部重试 Chat
实例异步生成一条批次视觉摘要。摘要只保留任务进展、最多四条关键事实和一个未解决事项，各字段
还受 Host 字符上限约束，不逐图复述 RGB/深度图，也忽略重复装饰和未变化 HUD。第 11～19 组可以
与上一批并行；拿到第 20 组、准备继续下一步前，必须等待上一批成功。未生成摘要的原图临时受
保护，可能使请求短暂超过常规图片窗口；成功后摘要只附加到该批最后一条历史 ToolMessage，供
后续观察使用并在滚动摘要之前可见，旧图再恢复为最多保留最新十组观察的 RGB+深度图。

视觉摘要的瞬时网络、限流和服务错误按 30、60、120 秒退避重试；400/413 会先把 10 组拆成
5+5 并在本地合并为一条摘要，401/403 等确定性错误不重复调用。到下一批边界仍无法得到摘要
时，Host 以异常码 2 失败关闭并安全停止当前游戏，不允许缺失视觉历史后继续。正式终局会取消
仍在处理的摘要，并把不足 10 组的尾批标为 `skipped_terminal`，不跨局混批也不事后补齐。

模型默认声明 `32768` token 的活跃上下文预算（`--context-window-tokens` 可覆盖），供 Deep
Agents 在约 85% 时触发对旧文字/工具历史的滚动摘要；这只控制 Agent 压缩时机，不修改 Yibu
模型自身的真实上下文上限。摘要会产生周期性的模型请求，但避免每一步都重传从开局累积至今的
完整文本历史。

## 续跑与产物

每次新运行会打印 `run_dir`。中断后使用同一模型、场景、AWM 模式和 benchmark seed；总局数可保持
或增加，但不能减少：

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
增加总局数时会原子扩展 `session.json` 的 benchmark attempt 计划；若上一个正式终局尚未消费，
Agent 必须先用既有公开对话提交一次精炼的纯文本 AWM，再调用新的游戏观察工具。AWM 继续受既有
字段数、条目数和文本长度校验限制，不保存图片、Base64、完整对话或逐帧动作。
为此 Deep Agents 的私有 stdio MCP 启动会保留单个尚未学习的正式终局；只有同时持有原
LangGraph 公开对话 checkpoint 的该 Host 才启用，其他玩家恢复时仍默认把陈旧终局标为已消费。
最终一局结束后，应用默认等待当前 Agent turn 最多 30 秒
（`--agent-final-grace-seconds` 可覆盖），使其消费终局、确认 `workflow_memory_update` 并输出
总结，然后才停止 MCP 和清理进程。

主要本地产物：

- `session.json`：不含凭据的运行配置与版本元数据。
- `trusted_mcplogs/`：白名单轨迹、RGB 截图、AWM、`supervisor.log` 和
  `image_captions.json`；caption sidecar 只含短文本、观察/消息索引、状态、尝试次数和脱敏错误码，
  不含图片 Base64、凭据或 provider 错误正文；深度图仍按现有契约不落轨迹。
- `deepagents_checkpoint.sqlite`：可续跑的模型消息状态，可能包含此前传给模型的图片 Base64。

`Ctrl-C`、模型/MCP 异常或 supervisor 异常都会先由 Host 调用 MCP `stop`，再关闭子进程与会话，
确保释放模拟输入。自动化测试使用本地假模型、假 MCP 和假进程，不读取真实凭据，也不产生外部
请求。
