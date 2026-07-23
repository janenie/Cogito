# AI Agent MCP README 设计

## 目标

在仓库根目录新增 `README.md`，让操作者和支持本地 stdio MCP 的 AI
agent 能够在不了解 Cogito 内部实现的情况下，安全地启动 AI First Play
服务、连接 Godot Lobby，并通过公开 MCP 工具游玩当前支持的
`find_contract` Demo。

## 受众与范围

README 使用中文主文，面向两类读者：

- 负责准备 Python 环境、配置 MCP Host 和启动 Godot 的操作者。
- 只能依据 MCP 返回的获准运行时观察进行决策的 AI agent。

文档同时提供通用 stdio MCP 接入说明、Codex 配置示例和 Claude Desktop
配置示例。协议实现细节仍由 `ai_play/README.md` 和项目 Wiki 维护，根目录
README 只提供完成首次接入和基本游玩所需的信息。

## 内容结构

README 采用操作手册式结构：

1. 简述 Cogito 和 AI First Play，并明确首版只支持
   `COGITO_3_Lobby.tscn` 的 `find_contract` 终局。
2. 列出 Godot 4.7、Python 3.10+ 和本地仓库等前置条件。
3. 给出 Python 虚拟环境和依赖安装命令。
4. 解释正确启动顺序：MCP Host 通过 stdio 启动 Python 服务，然后操作者用
   精确参数 `-- --ai-play` 单独启动 Godot Lobby。
5. 提供使用绝对仓库路径的 Codex TOML 和 Claude Desktop JSON 配置示例，
   同时标注需要替换的占位路径。
6. 给出 AI agent 的标准游玩循环：
   `observe` → 使用最新 `observation_id` 调用 `act` → 检查返回的新观察或终局
   → 重复；退出或异常时调用 `stop`。
7. 列出所有允许动作的合法 JSON 示例、数值范围、批次限制和界面上下文规则。
8. 说明常见错误、连接状态和最小检查方法。
9. 强调 Escape 物理急停、`127.0.0.1` 绑定、输入释放、凭据和隐私边界。
10. 链接 `ai_play/README.md`、AI First Play Wiki 和开发验证指南。

## 安全与隐私

README 不向 agent 提供场景源码、节点路径、隐藏状态、谜题答案，或来自
`game_script/`、`code_read/`、测试、规格和计划的游戏事实。它明确要求 agent
只根据 MCP 的 `observe`/`act` 结果和图片决策。

文档不会要求 API Key，也不会暗示 Python MCP 服务会调用模型。它明确说明
MCP Host 可能自行持久化工具结果，以及运行真实外部客户端前需要操作者确认
截图、令牌、费用和本地轨迹影响。

## 验证

完成 README 后运行：

```bash
bash tests/check_ai_play_start_script.sh
bash tests/check_ai_play_mcp_only.sh
git diff --check
```

另外以代码、`ai_play/README.md`、Wiki 和当前官方客户端文档交叉检查所有命令、
路径、工具名称、动作边界及客户端配置。纯文档改动不启动真实外部 MCP/模型验收。
