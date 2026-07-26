# 黑盒 Codex AI Play 玩家 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 AI Play orchestrator 每局启动一个模型和思考强度均显式固定、只能通过四个公开 MCP 工具获取游戏信息的本机硬化 Codex 玩家。

**Architecture:** 将 MCP 服务从“由 Codex 从仓库启动的 stdio 子进程”拆为由 orchestrator 在可信侧启动的 `127.0.0.1` Streamable HTTP 边车。Codex 在空工作区、每局临时 `CODEX_HOME` 和自定义最小权限 profile 中运行；认证只从专用目录复制 `auth.json`，日志和桥环境只留在可信侧。

**Tech Stack:** Python 3、`mcp[cli]>=1.28,<2` 的 `FastMCP`、Codex CLI `config.toml` 权限 profile、pytest、Godot supervisor。

---

## 文件结构

- `ai_play/src/ai_play/mcp_server.py`：保留 stdio 默认入口，并新增严格回环的 Streamable HTTP transport 参数；不新增 MCP 工具、资源或提示词。
- `ai_play/tests/test_mcp_server.py`：验证 HTTP transport 的解析、回环限制和对 `FastMCP.run()` 的调用，同时保留四工具契约。
- `tools/ai_play_codex_orchestrator.py`：负责隔离路径校验、认证副本、临时 Codex 配置、最小环境、可信 MCP 边车和三进程生命周期。
- `tests/test_ai_play_codex_orchestrator.py`：只用临时目录和伪进程覆盖黑盒启动器的输入、配置、环境和失败关闭行为。
- `ai_play/README.md`：记录新的专用认证、必填模型参数、可信边车端口、运行目录和本机边界。
- `docs/wiki/ai-play/system-guide.md`、`docs/wiki/development/contributor-guide.md`：将已批准的“待实现”描述替换为当前实现约定和验证要求。

### Task 1: 为现有 MCP 服务加入本地 Streamable HTTP transport

**Files:**
- Modify: `ai_play/src/ai_play/mcp_server.py:1-195`
- Modify: `ai_play/tests/test_mcp_server.py:1-455`

- [ ] **Step 1: 写出 HTTP transport 的失败测试**

在 `ai_play/tests/test_mcp_server.py` 增加以下测试和所需的 `argparse.Namespace`/`unittest.mock.Mock` 导入。测试直接调用将新增的纯函数，因此不启动真实监听器：

```python
def test_parse_server_options_defaults_to_stdio():
    options = mcp_server.parse_server_options([])

    assert options.transport == "stdio"
    assert options.http_host == "127.0.0.1"
    assert options.http_port == 8766


@pytest.mark.parametrize("host", ["localhost", "::1", "0.0.0.0"])
def test_parse_server_options_rejects_non_numeric_loopback(host):
    with pytest.raises(ValueError, match="MCP HTTP host must be 127.0.0.1"):
        mcp_server.parse_server_options(
            [
                "--transport", "streamable-http",
                "--http-host", host,
                "--http-port", "8766",
            ]
        )


def test_configure_transport_sets_fastmcp_http_listener(monkeypatch):
    options = mcp_server.ServerOptions(
        transport="streamable-http",
        http_host="127.0.0.1",
        http_port=8766,
    )

    transport = mcp_server.configure_transport(options)

    assert transport == "streamable-http"
    assert mcp_server.mcp.settings.host == "127.0.0.1"
    assert mcp_server.mcp.settings.port == 8766
```

- [ ] **Step 2: 运行新增测试并确认其因缺少接口失败**

Run:

```powershell
$env:PYTHONPATH = "ai_play/src"
.\.venv\Scripts\python.exe -m pytest ai_play\tests\test_mcp_server.py -k "server_options or configure_transport" -q
```

Expected: `FAIL`，报出 `parse_server_options`、`ServerOptions` 或 `configure_transport` 尚不存在；不得因为导入 MCP、网络或真实监听器失败。

- [ ] **Step 3: 实现最小 transport 参数和配置函数**

在 `mcp_server.py` 导入 `argparse`、`dataclass`、`Literal` 和 `Sequence`，在全局 `mcp` 定义后加入以下实现；`FastMCP` 1.28 的 `run()` 从 `mcp.settings.host`/`port` 读取监听设置，因此不要向 `run()` 传递未支持的 host/port 关键字：

```python
@dataclass(frozen=True)
class ServerOptions:
    transport: Literal["stdio", "streamable-http"]
    http_host: str
    http_port: int


def parse_server_options(argv: Sequence[str]) -> ServerOptions:
    parser = argparse.ArgumentParser(
        description="Run the Cogito AI Play MCP server.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
    )
    parser.add_argument("--http-host", default="127.0.0.1")
    parser.add_argument("--http-port", type=int, default=8766)
    args = parser.parse_args(argv)
    if args.transport == "streamable-http" and args.http_host != "127.0.0.1":
        raise ValueError("MCP HTTP host must be 127.0.0.1")
    if not 1 <= args.http_port <= 65535:
        raise ValueError("MCP HTTP port must be between 1 and 65535")
    return ServerOptions(
        transport=args.transport,
        http_host=args.http_host,
        http_port=args.http_port,
    )


def configure_transport(options: ServerOptions) -> str:
    if options.transport == "streamable-http":
        mcp.settings.host = options.http_host
        mcp.settings.port = options.http_port
    return options.transport
```

把 `main()` 改为 `main(argv: Sequence[str] | None = None)`，在创建 bridge 前解析 options，并把最后一行替换为：

```python
mcp.run(transport=configure_transport(options))
```

模块入口改为 `main(sys.argv[1:])`，仍只把 `ValueError` 写入 stderr 并以状态码 `2` 退出。保留默认 stdio 行为与现有四个 `@mcp.tool()` 函数，不添加 HTTP 健康检查、资源、提示词或其他接口。

- [ ] **Step 4: 运行 MCP 单元测试并确认通过**

Run:

```powershell
$env:PYTHONPATH = "ai_play/src"
.\.venv\Scripts\python.exe -m pytest ai_play\tests\test_mcp_server.py -q
```

Expected: `PASS`；既有工具列表仍恰好是 `briefing`、`observe`、`act`、`stop`，并且新的 transport 测试不创建真实端口。

- [ ] **Step 5: 提交可独立验证的 MCP transport 变更**

```powershell
git add ai_play/src/ai_play/mcp_server.py ai_play/tests/test_mcp_server.py
git commit -m "feat(ai-play): add local HTTP MCP transport"
```

### Task 2: 建立玩家隔离根、临时认证 home 和确定性 Codex 配置

**Files:**
- Modify: `tools/ai_play_codex_orchestrator.py:1-190,397-491`
- Modify: `tests/test_ai_play_codex_orchestrator.py:1-178`

- [ ] **Step 1: 写出路径、认证和配置的失败测试**

先删除旧的“玩家工作区包含 run config 和 mcplogs”断言，改为下面的覆盖。测试中的 `auth.json` 内容是无效占位字符串，绝不使用真实凭据：

```python
def test_create_run_paths_keeps_player_workspace_empty_and_logs_trusted(tmp_path):
    orchestrator = load_orchestrator()

    paths = orchestrator.create_run_paths(tmp_path, timestamp="20260726-170000")

    assert list(paths.player_workspace.iterdir()) == []
    assert paths.log_root == paths.run_dir / "trusted_mcplogs"
    assert paths.log_root.is_dir()
    assert not hasattr(paths, "run_config")


@pytest.mark.parametrize("marker", ["AGENTS.md", ".git"])
def test_validate_session_root_rejects_project_instruction_ancestors(tmp_path, marker):
    orchestrator = load_orchestrator()
    root = tmp_path / "session-root"
    root.mkdir()
    (root / marker).mkdir() if marker == ".git" else (root / marker).write_text("x")

    with pytest.raises(ValueError, match="isolated"):
        orchestrator.validate_isolated_session_root(root)


def test_temporary_player_codex_home_copies_only_auth_and_removes_it(tmp_path):
    orchestrator = load_orchestrator()
    auth_home = tmp_path / "auth-home"
    auth_home.mkdir()
    (auth_home / "auth.json").write_text('{"token":"fixture"}', encoding="utf-8")
    (auth_home / "config.toml").write_text('model = "leak"\n', encoding="utf-8")

    with orchestrator.temporary_player_codex_home(auth_home) as player_home:
        assert (player_home / "auth.json").read_text(encoding="utf-8") == '{"token":"fixture"}'
        assert not (player_home / "config.toml").exists()
    assert not player_home.exists()


def test_write_player_codex_config_is_complete_and_has_no_repo_command(tmp_path):
    orchestrator = load_orchestrator()
    config_path = orchestrator.write_player_codex_config(
        tmp_path,
        model="gpt-test",
        reasoning_effort="high",
        mcp_url="http://127.0.0.1:8766/mcp",
    )
    text = config_path.read_text(encoding="utf-8")

    assert 'model = "gpt-test"' in text
    assert 'model_reasoning_effort = "high"' in text
    assert 'url = "http://127.0.0.1:8766/mcp"' in text
    assert 'enabled_tools = ["briefing", "observe", "act", "stop"]' in text
    assert 'web_search = "disabled"' in text
    assert 'default_permissions = "ai_play_player"' in text
    assert "start_ai.sh" not in text
    assert str(orchestrator.REPO_ROOT) not in text
```

为这组测试导入 `pytest`。再补充参数解析测试，断言省略 `--model` 或 `--reasoning-effort` 时
`argparse` 返回状态码 `2`，以及模型/强度中包含换行、制表符或空字符串时 `main()` 在启动子进程前
以 `SystemExit` 失败。

- [ ] **Step 2: 运行隔离状态测试并确认它们失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ai_play_codex_orchestrator.py -k "run_paths or session_root or temporary_player or player_codex_config or required" -q
```

Expected: `FAIL`，原因是旧 `RunPaths` 把日志放在玩家目录、没有认证 context manager、没有确定性配置函数或参数仍为可选。

- [ ] **Step 3: 用最小文件系统边界替换旧持久 home 行为**

在 orchestrator 中移除 `json`、`write_player_run_config()`、`last_message`、`run_config`、
`DEFAULT_CODEX_HOME`、`ensure_player_codex_config()` 和 `_missing_cogito_mcp_config_blocks()`。新增
`from contextlib import contextmanager`、`shutil`、`tempfile`、`Iterator` 和常量：

```python
AUTH_FILE_NAME = "auth.json"
DEFAULT_CODEX_AUTH_HOME = Path("~/.codex-cogito-player")
DEFAULT_MCP_PORT = 8766
PLAYER_TOOL_NAMES = ("briefing", "observe", "act", "stop")
```

把 `RunPaths` 缩为 `run_dir`、`player_workspace`、`log_root`。让 `create_run_paths()` 在
`validate_isolated_session_root(session_root)` 成功后创建：

```python
player_workspace = run_dir / "player_workspace"
log_root = run_dir / "trusted_mcplogs"
player_workspace.mkdir(mode=0o700)
log_root.mkdir(mode=0o700)
```

实现以下路径和认证 helper。`_is_relative_to()` 使用 `Path.resolve()` 和 `relative_to()`，以兼容
不支持 `Path.is_relative_to()` 的 Python 版本；检查 `REPO_ROOT`、`.git`、`AGENTS.md` 与
`.codex/config.toml`，任何命中都抛出包含 `isolated` 的 `ValueError`：

```python
@contextmanager
def temporary_player_codex_home(auth_home: Path) -> Iterator[Path]:
    source = auth_home.expanduser() / AUTH_FILE_NAME
    if not source.is_file():
        raise ValueError(f"missing Codex credential file: {source}")
    with tempfile.TemporaryDirectory(prefix="cogito-ai-play-codex-") as raw_home:
        player_home = Path(raw_home)
        shutil.copyfile(source, player_home / AUTH_FILE_NAME)
        yield player_home
```

实现 `validate_model_argument(name, value)`，拒绝空值、所有空白字符和 Unicode 控制字符；再使用
`json.dumps(value, ensure_ascii=False)` 写入 TOML basic string，确保引号不能注入新的 TOML 行。

`write_player_codex_config(home, model, reasoning_effort, mcp_url)` 必须覆盖临时 home 中新建的
`config.toml`，使用以下完整内容骨架：

```toml
model = <quoted model>
model_reasoning_effort = <quoted effort>
approval_policy = "never"
allow_login_shell = false
web_search = "disabled"
project_doc_max_bytes = 0
default_permissions = "ai_play_player"

[agents]
enabled = false

[memories]
generate_memories = false
use_memories = false

[shell_environment_policy]
inherit = "none"

[permissions.ai_play_player.filesystem]
":minimal" = "read"

[permissions.ai_play_player.filesystem.":workspace_roots"]
"." = "read"

[permissions.ai_play_player.network]
enabled = false

[mcp_servers.cogito_ai_play]
url = <quoted local URL>
required = true
enabled_tools = ["briefing", "observe", "act", "stop"]
default_tools_approval_mode = "approve"
```

不要在命令行再传 `--sandbox`；Codex 文档规定 legacy sandbox 参数会覆盖 permission profiles。

- [ ] **Step 4: 运行隔离状态测试并确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ai_play_codex_orchestrator.py -k "run_paths or session_root or temporary_player or player_codex_config or required" -q
```

Expected: `PASS`；临时测试 home 在 context 退出后消失，源 `config.toml` 永不读取，玩家工作区保持为空。

- [ ] **Step 5: 提交隔离状态和临时配置变更**

```powershell
git add tools/ai_play_codex_orchestrator.py tests/test_ai_play_codex_orchestrator.py
git commit -m "feat(ai-play): isolate Codex player runtime"
```

### Task 3: 隔离命令、环境和模型可见提示词

**Files:**
- Modify: `tools/ai_play_codex_orchestrator.py:80-246,397-491`
- Modify: `tests/test_ai_play_codex_orchestrator.py:1-178`

- [ ] **Step 1: 写出命令、环境和提示词的失败测试**

新增以下测试。`base_env` 明确含有不应泄漏的值，所有断言均只检查字典而不启动进程：

```python
def test_build_player_env_drops_game_and_secret_environment(tmp_path):
    orchestrator = load_orchestrator()
    env = orchestrator.build_player_env(
        tmp_path / "player-home",
        base_env={
            "PATH": "C:/safe-bin",
            "SystemRoot": "C:/Windows",
            "OPENAI_API_KEY": "secret",
            "AI_PLAY_LOG_ROOT": "C:/logs",
            "PYTHONPATH": "C:/repo/ai_play/src",
            "HTTPS_PROXY": "http://proxy",
        },
    )

    assert env["CODEX_HOME"] == str(tmp_path / "player-home")
    assert env["PATH"] == "C:/safe-bin"
    assert "OPENAI_API_KEY" not in env
    assert "AI_PLAY_LOG_ROOT" not in env
    assert "PYTHONPATH" not in env
    assert "HTTPS_PROXY" not in env


def test_build_trusted_mcp_env_has_bridge_and_log_but_no_player_credentials(tmp_path):
    orchestrator = load_orchestrator()
    env = orchestrator.build_trusted_mcp_env(
        log_root=tmp_path / "trusted_mcplogs",
        ws_port=8765,
        base_env={"PATH": "C:/safe-bin", "OPENAI_API_KEY": "secret"},
    )

    assert env["AI_PLAY_WS_HOST"] == "127.0.0.1"
    assert env["AI_PLAY_WS_PORT"] == "8765"
    assert env["AI_PLAY_LOG_ROOT"] == str(tmp_path / "trusted_mcplogs")
    assert env["PYTHONPATH"] == str(orchestrator.REPO_ROOT / "ai_play" / "src")
    assert "OPENAI_API_KEY" not in env


def test_blackbox_commands_and_prompt_do_not_reveal_repo_or_scenario(tmp_path):
    orchestrator = load_orchestrator()
    mcp_command = orchestrator.build_mcp_command("python", 8766)
    codex_command = orchestrator.build_codex_command("codex", tmp_path / "workspace")
    prompt = orchestrator.build_player_prompt(runs=3)

    assert mcp_command == [
        "python", "-m", "ai_play.mcp_server", "--transport", "streamable-http",
        "--http-host", "127.0.0.1", "--http-port", "8766",
    ]
    assert "--sandbox" not in codex_command
    assert "start_ai.sh" not in " ".join(codex_command)
    assert "find_contract" not in prompt
    assert "ai_play_run_config.json" not in prompt
    assert str(orchestrator.REPO_ROOT) not in prompt
```

再增加解析测试，确认 `--codex-auth-home` 存在且 `--codex-home`、`--sandbox`、
`--approval-policy` 不再是可接受的参数；确认 `--mcp-port` 默认 8766，`--mcp-port` 与
`--ws-port` 相同会在 `main()` 启动前失败。

- [ ] **Step 2: 运行命令和环境测试并确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ai_play_codex_orchestrator.py -k "player_env or trusted_mcp_env or blackbox_commands or mcp_port" -q
```

Expected: `FAIL`，旧 `build_child_env()` 会泄漏桥和日志给 Codex，旧 command 会引用
`start_ai.sh`、玩法 ID 和 legacy sandbox。

- [ ] **Step 3: 实现分离环境、可信 MCP 命令和无玩法提示词**

新增 `build_core_env(base_env)`，只复制存在的 `PATH`、`SystemRoot`、`WINDIR`、`ComSpec`；
不得从调用方复制其他环境。`build_player_env()` 在该字典上设置 `CODEX_HOME`、`HOME`、
`USERPROFILE`、`APPDATA`、`LOCALAPPDATA`、`TEMP`、`TMP` 到临时 home 下新建的私有目录。
`build_trusted_mcp_env()` 在 core env 上设置唯一的：

```python
{
    "AI_PLAY_LOG_ROOT": str(log_root),
    "AI_PLAY_WS_HOST": "127.0.0.1",
    "AI_PLAY_WS_PORT": str(ws_port),
    "PYTHONPATH": str(REPO_ROOT / "ai_play" / "src"),
}
```

为 supervisor 使用单独的 `build_supervisor_env()`；它只需 core env，不能继承玩家 home 或
`AI_PLAY_*`。用以下精确构造替换旧 command builder：

```python
def build_mcp_command(python_bin: str, mcp_port: int) -> list[str]:
    return [
        python_bin,
        "-m",
        "ai_play.mcp_server",
        "--transport",
        "streamable-http",
        "--http-host",
        "127.0.0.1",
        "--http-port",
        str(mcp_port),
    ]


def build_codex_command(codex_bin: str, player_workspace: Path) -> list[str]:
    return [
        codex_bin,
        "exec",
        "--cd",
        str(player_workspace),
        "--skip-git-repo-check",
        "--ephemeral",
        "-",
    ]
```

把 `build_player_prompt()` 改为只接收 `runs`。它必须要求先 `briefing` 后 `observe`，要求只依据四个
工具结果决策、使用最新 `observation_id`、在终局或断线后停止本局动作，但不得插值 `scenario`、
`RunPaths`、日志、仓库路径或实现文件名。

在 `parse_args()` 中使用：

```python
parser.add_argument("--codex-auth-home", type=Path, default=DEFAULT_CODEX_AUTH_HOME)
parser.add_argument("--model", required=True)
parser.add_argument("--reasoning-effort", required=True)
parser.add_argument("--mcp-port", type=int, default=DEFAULT_MCP_PORT)
```

删除旧的 `--codex-home`、`--sandbox`、`--approval-policy` 和可变 `--ws-host`；bridge host 固定为
`127.0.0.1`。在 `main()` 中对两端口、模型、思考强度和隔离根完成全部校验后才调用
`create_run_paths()` 或 `_start_process()`。

- [ ] **Step 4: 运行命令和环境测试并确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ai_play_codex_orchestrator.py -k "player_env or trusted_mcp_env or blackbox_commands or mcp_port" -q
```

Expected: `PASS`；玩家不接收任何游戏/日志/代理/凭据环境，Codex command 不含仓库 MCP command 或
legacy sandbox，提示词不含玩法或本地路径。

- [ ] **Step 5: 提交可复现的玩家命令边界**

```powershell
git add tools/ai_play_codex_orchestrator.py tests/test_ai_play_codex_orchestrator.py
git commit -m "feat(ai-play): harden Codex player boundary"
```

### Task 4: 先启动可信 MCP 边车并在所有退出路径收束三进程

**Files:**
- Modify: `tools/ai_play_codex_orchestrator.py:247-396,420-491`
- Modify: `tests/test_ai_play_codex_orchestrator.py:1-178`

- [ ] **Step 1: 写出可信侧启动顺序和失败关闭的失败测试**

在测试文件新增一个最小 `FakeProcess`（实现 `poll()`、`terminate()`、`wait()`、`kill()` 和可读
`stdout`）以及 monkeypatch 的 `_start_process()` 记录器。测试目标是新签名
`run_orchestrated_session(mcp_command=..., codex_command=..., supervisor_command=..., ...)`：

```python
def test_session_starts_trusted_mcp_before_codex_and_supervisor(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    started = []
    processes = {
        "mcp": FakeProcess(),
        "codex": FakeProcess(),
        "supervisor": FakeProcess(return_codes=[0]),
    }
    monkeypatch.setattr(
        orchestrator,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: started.append(label) or processes[label],
    )
    monkeypatch.setattr(orchestrator, "wait_for_listener", lambda *args, **kwargs: True)

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python", "-m", "ai_play.mcp_server"],
        codex_command=["codex", "exec"],
        supervisor_command=["python", "supervisor.py"],
        prompt="briefing",
        mcp_env={}, codex_env={}, supervisor_env={},
        mcp_cwd=tmp_path, codex_cwd=tmp_path, supervisor_cwd=tmp_path,
        ws_port=8765, mcp_port=8766,
        mcp_start_timeout_seconds=1.0, codex_exit_grace_seconds=0.0,
    )

    assert result == 0
    assert started == ["mcp", "codex", "supervisor"]
    assert processes["codex"].terminated
    assert processes["mcp"].terminated


def test_sidecar_readiness_failure_never_starts_codex_or_supervisor(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    started = []
    mcp = FakeProcess()
    monkeypatch.setattr(
        orchestrator,
        "_start_process",
        lambda label, command, cwd, env, stdin_text=None: started.append(label) or mcp,
    )
    monkeypatch.setattr(orchestrator, "wait_for_listener", lambda *args, **kwargs: False)

    result = orchestrator.run_orchestrated_session(
        mcp_command=["python"], codex_command=["codex"], supervisor_command=["supervisor"],
        prompt="briefing", mcp_env={}, codex_env={}, supervisor_env={},
        mcp_cwd=tmp_path, codex_cwd=tmp_path, supervisor_cwd=tmp_path,
        ws_port=8765, mcp_port=8766,
        mcp_start_timeout_seconds=1.0, codex_exit_grace_seconds=0.0,
    )

    assert result == 4
    assert started == ["mcp"]
    assert mcp.terminated
```

再为 Codex 提前退出、supervisor 提前退出和 `KeyboardInterrupt` 各写一个测试，断言已启动的其余
进程都经过 `_terminate_process()`，并在 `main()` 中 monkeypatch `run_orchestrated_session()` 后断言
`temporary_player_codex_home()` 已经退出。

- [ ] **Step 2: 运行生命周期测试并确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ai_play_codex_orchestrator.py -k "trusted_mcp_before or sidecar_readiness or terminates or cleanup" -q
```

Expected: `FAIL`，当前函数没有 MCP 参数、会先启动 Codex，并且把单一环境传给所有子进程。

- [ ] **Step 3: 以 `finally` 为中心重写编排生命周期**

新增 `wait_for_listener(process, host, port, timeout_seconds, outputs)`：循环读取输出，若子进程提前
退出则返回 `False`，若 `is_port_listening()` 成功则返回 `True`，到期返回 `False`。新的
`run_orchestrated_session()` 必须按以下顺序执行：

```python
mcp = _start_process("mcp", mcp_command, mcp_cwd, mcp_env)
if not wait_for_listener(mcp, "127.0.0.1", mcp_port, timeout, outputs):
    return 4
if not wait_for_listener(mcp, "127.0.0.1", ws_port, timeout, outputs):
    return 4
codex = _start_process("codex", codex_command, codex_cwd, codex_env, prompt)
if codex.poll() is not None:
    return codex.returncode or 3
supervisor = _start_process("supervisor", supervisor_command, supervisor_cwd, supervisor_env)
```

在返回、异常和 `KeyboardInterrupt` 的统一 `finally` 中，按 `supervisor`、`codex`、`mcp` 的逆序对
非空进程调用 `_terminate_process()`。保留 supervisor 成功/失败状态码和 Codex grace period 的现有
含义；不要把 MCP `stop` 误认为监督回合终局。

`main()` 必须在端口预检后使用：

```python
with temporary_player_codex_home(args.codex_auth_home) as player_home:
    write_player_codex_config(player_home, args.model, args.reasoning_effort, mcp_url)
    return run_orchestrated_session(...)
```

其中 `mcp_url` 精确为 `http://127.0.0.1:<mcp-port>/mcp`；MCP 用 `args.python_bin`、可信 MCP 环境和
`REPO_ROOT` 启动，Codex 用空玩家工作区和玩家环境启动，supervisor 用自己的可信环境和
`REPO_ROOT` 启动。打印运行目录和可信日志根即可；不得打印认证 home、临时 config 内容或玩家可读
游戏信息。

- [ ] **Step 4: 运行 lifecycle 和完整 orchestrator 测试并确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ai_play_codex_orchestrator.py tests\test_ai_play_supervisor.py -q
```

Expected: `PASS`；测试只创建临时文件和 fake process，MCP 未就绪时不会启动 Godot，所有退出路径均
删除临时凭据副本并终止剩余子进程。

- [ ] **Step 5: 提交可信边车生命周期变更**

```powershell
git add tools/ai_play_codex_orchestrator.py tests/test_ai_play_codex_orchestrator.py
git commit -m "feat(ai-play): supervise trusted MCP sidecar"
```

### Task 5: 将使用文档和 Wiki 从待实现设计更新为当前行为

**Files:**
- Modify: `ai_play/README.md:82-160`
- Modify: `docs/wiki/ai-play/system-guide.md:72-323`
- Modify: `docs/wiki/development/contributor-guide.md:37-136`
- Modify: `docs/scope/2026-07-26-blackbox-codex-player/spec-blackbox-codex-player.md:1-141`

- [ ] **Step 1: 写出文档命令表面失败测试**

在 `tests/test_ai_play_codex_orchestrator.py` 增加帮助输出和 parser 测试：

```python
def test_parse_args_exposes_only_hardened_player_options():
    orchestrator = load_orchestrator()
    args = orchestrator.parse_args(
        ["--model", "gpt-test", "--reasoning-effort", "high"]
    )

    assert args.codex_auth_home == orchestrator.DEFAULT_CODEX_AUTH_HOME
    assert args.mcp_port == 8766
    assert not hasattr(args, "sandbox")
    assert not hasattr(args, "approval_policy")
    assert not hasattr(args, "codex_home")
```

- [ ] **Step 2: 运行帮助表面测试并确认通过当前实现尚未满足**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ai_play_codex_orchestrator.py -k "hardened_player_options" -q
```

Expected: 在 Task 3 后此测试应已通过；若没有，通过前不得编辑文档声明新命令已可用。

- [ ] **Step 3: 更新 README、Wiki 和已批准规格的实施状态**

把 `ai_play/README.md` 的“隔离 Codex 玩家连续 3 局”替换为如下真实命令形式，并说明首次登录只写
专用认证目录：

```bash
CODEX_HOME=~/.codex-cogito-player codex login

python3 tools/ai_play_codex_orchestrator.py \
  --runs 3 \
  --scenario find_contract \
  --model gpt-5.6 \
  --reasoning-effort high \
  --codex-auth-home ~/.codex-cogito-player
```

文档须说明：`--model` 与 `--reasoning-effort` 必填；玩家目录为空；临时 home 仅含认证副本且会被
清理；可信日志在 `trusted_mcplogs/`；orchestrator 启动 `127.0.0.1:<mcp-port>/mcp`，默认 HTTP
端口 8766、Godot bridge 仍为 8765；玩家不继承持久配置、环境、日志或仓库路径；本机 profile
不是容器/独立用户级别隔离；真实外部验收仍需单独确认。

把两份 Wiki 的“待实现”状态改为当前事实，删除旧的“追加持久 `config.toml`、Codex 启动
`start_ai.sh`、玩家目录包含 run config/mcplogs”描述，并保留已批准 spec 的来源链接。把 spec 中
“待实现”措辞改为已实施的最终行为，但不新增未经测试的安全承诺。

- [ ] **Step 4: 运行文档表面测试和静态文档检查**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_ai_play_codex_orchestrator.py -k "hardened_player_options" -q
$matches = rg -n "ai_play_run_config\.json|player_workspace/mcplogs|Codex 启动.*start_ai\.sh|--codex-home|--sandbox|--approval-policy" ai_play\README.md docs\wiki\ai-play\system-guide.md docs\wiki\development\contributor-guide.md
if ($LASTEXITCODE -gt 1) { exit $LASTEXITCODE }
$matches
```

Expected: pytest 为 `PASS`；`rg` 只允许命中历史/禁止说明，不能把旧行为描述为当前 orchestration。

- [ ] **Step 5: 运行完整受影响测试、检查差异并提交文档**

Run:

```powershell
$env:PYTHONPATH = "ai_play/src"
.\.venv\Scripts\python.exe -m pytest ai_play\tests tests\test_ai_play_codex_orchestrator.py tests\test_ai_play_supervisor.py -q
bash tests/check_ai_play_mcp_only.sh
bash tests/check_ai_play_start_script.sh
git diff --check
git status -sb
```

Expected: 所有可用 Python/静态测试 `PASS`，`git diff --check` 无输出。不要运行真实 Codex、真实
MCP/Godot 多局游玩或任何需要登录凭据的验收；若 `.venv` 或 Godot 不可用，记录未运行的命令和
原因。

```powershell
git add ai_play/README.md docs/wiki/ai-play/system-guide.md docs/wiki/development/contributor-guide.md docs/scope/2026-07-26-blackbox-codex-player
git commit -m "docs(ai-play): document blackbox Codex player"
```

## 计划自审

### Spec 覆盖度

- 每局必填模型和思考强度：Task 2 的 parser/config 测试与实现。
- 专用认证目录、只复制凭据和退出清理：Task 2 的 context manager 测试与实现。
- 空且隔离的玩家目录、日志移至可信侧、无项目指令祖先：Task 2。
- 可信 Streamable HTTP 边车和不扩展 MCP 工具：Task 1、Task 4。
- 最小权限 profile、禁用 Web/子代理/记忆/登录 shell、工具白名单：Task 2、Task 3。
- 细分环境、无仓库/玩法/日志提示词：Task 3。
- 端口预检、MCP 先启动、退出收束：Task 4。
- `ai_play/README.md`、两份 Wiki、无真实外部验收：Task 5。

### 一致性和范围

所有任务使用同一组名称：`codex_auth_home`、`player_workspace`、`trusted_mcplogs`、`mcp_port`、
`temporary_player_codex_home()`、`write_player_codex_config()` 和 `build_trusted_mcp_env()`。计划未更改
Godot 场景、公开观察 schema、动作白名单或监督终局语义；真实 Codex/Godot 验收明确留在范围外。
