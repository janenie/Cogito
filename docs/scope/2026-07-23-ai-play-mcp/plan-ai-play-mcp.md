
# AI Play MCP 服务实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox ([ ]) syntax for tracking.

**Goal:** 将 AI First Play 的内置模型 sidecar 改造成一个只通过 stdio 提供 observe、act、stop 的 MCP Server，并让现有 find_contract Lobby 通过版本 2 的安全桥协议接受外部 AI 控制。

**Architecture:** Python 使用官方 MCP Python SDK v1.x 的 FastMCP stdio 入口运行，在后台线程维护唯一的 127.0.0.1:8765 Godot WebSocket 连接。线程安全的 GameSession 管理当前观察、观察 ID、串行动作回合、终局、停止和超时；Godot 仍在两端负责最终动作校验、正常输入执行与输入释放。已批准的 Wiki 已同步，本计划不再改写 Wiki 内容。

**Tech Stack:** Python 3.10+、mcp[cli]>=1.28,<2、websockets>=14,<16、pytest、Godot 4.7 GDScript。MCP SDK 的内存测试使用 mcp.shared.memory.create_connected_server_and_client_session。

---

## 文件结构

### Create

- ai_play/src/ai_play/game_session.py：线程安全的 MCP/Godot 会话状态机和工具级结果 DTO。
- ai_play/src/ai_play/mcp_server.py：FastMCP 工具注册、MCP 图片/结构化结果序列化和 stdio 入口。
- ai_play/tests/test_game_session.py：会话串行化、观察关联、停止、终局和断线测试。
- ai_play/tests/test_mcp_server.py：官方 SDK 内存传输下的工具列表、工具输入/输出和图片测试。
- tests/check_ai_play_mcp_only.sh：检查旧模型运行时和凭据引用已从当前入口移除。

### Modify

- ai_play/requirements.txt、ai_play/.env.example、ai_play/start_ai.sh：依赖、配置示例和 MCP 启动入口。
- ai_play/src/ai_play/config.py：移除模型/API 配置，保留回环桥和有界等待配置。
- ai_play/src/ai_play/action_schema.py：保留安全动作规则，提供独立的动作批次校验，移除记忆/模型决策 DTO。
- ai_play/src/ai_play/observation_schema.py：增加不含 Base64 的 MCP 公开观察序列化。
- ai_play/src/ai_play/bridge_server.py：改为版本 2 Godot 桥，并将数据交给 GameSession。
- ai_play/tests/test_config.py、test_action_schema.py、test_observation_schema.py、test_bridge_server.py：改写为 MCP 桥契约测试。
- addons/cogito/AIPlay/ai_play_bridge.gd：升级协议版本，接收 stop_request，拒绝旧/未知服务端包。
- addons/cogito/AIPlay/ai_play_controller.gd：移除模型请求计数与远程 game_over，发送/接收版本 2 数据，处理 MCP 停止。
- tests/ai_play/test_ai_play_controller.gd：更新假桥、协议字段、终局和停止回归测试。
- ai_play/README.md：改写为 MCP 使用、安全和工具契约说明。
- AGENTS.md：同步协议版本和无 API Key 的当前架构事实。

### Delete

以下模块只服务于被批准移除的内置模型路径：

- ai_play/src/ai_play/main.py
- ai_play/src/ai_play/agent_loop.py
- ai_play/src/ai_play/api_client.py
- ai_play/src/ai_play/game_context.py
- ai_play/src/ai_play/memory.py
- ai_play/src/ai_play/prompts.py
- ai_play/src/ai_play/run_logger.py
- ai_play/goals/find_contract.py
- ai_play/tests/test_main.py
- ai_play/tests/test_agent_loop.py
- ai_play/tests/test_api_client.py
- ai_play/tests/test_game_context.py
- ai_play/tests/test_memory.py
- ai_play/tests/test_prompts.py
- ai_play/tests/test_run_logger.py

ai_play/assets/find_contract/ 保留为仓库中的用户视觉资产，不再由运行时加载。

已完成且在本分支保留的文档/工作流文件：

- docs/scope/2026-07-23-ai-play-mcp/spec-ai-play-mcp.md
- docs/wiki/ai-play/system-guide.md
- docs/wiki/ai-play/ai-play.md
- docs/wiki/development/contributor-guide.md
- .gitignore 中的 .worktree/ 忽略项

---

### Task 1: Replace credential/model configuration with bridge configuration

**Files:**
- Modify: ai_play/tests/test_config.py
- Modify: ai_play/src/ai_play/config.py
- Modify: ai_play/.env.example
- Modify: ai_play/requirements.txt

- [ ] **Step 1: Write the failing configuration tests**

Replace credential-oriented tests with these behavior checks:

~~~python
from ai_play.config import Config


def test_config_has_no_model_or_credential_fields(monkeypatch):
    monkeypatch.delenv("AI_PLAY_API_KEY", raising=False)
    monkeypatch.delenv("AI_PLAY_MODEL", raising=False)

    config = Config.from_env()

    assert config.ws_host == "127.0.0.1"
    assert config.ws_port == 8765
    assert config.wait_timeout_seconds == 30.0
    assert config.stop_timeout_seconds == 5.0
    assert not hasattr(config, "api_key")
    assert not hasattr(config, "model")


def test_config_rejects_non_loopback_host(monkeypatch):
    monkeypatch.setenv("AI_PLAY_WS_HOST", "localhost")

    with pytest.raises(ValueError, match="127.0.0.1"):
        Config.from_env()


def test_config_reads_bounded_mcp_waits(monkeypatch):
    monkeypatch.setenv("AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("AI_PLAY_STOP_TIMEOUT_SECONDS", "2")

    config = Config.from_env()

    assert config.wait_timeout_seconds == 12.5
    assert config.stop_timeout_seconds == 2.0
~~~

- [ ] **Step 2: Run the focused tests to verify the intended failure**

Run:

~~~powershell
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_config.py -q
~~~

Expected: FAIL because the existing Config requires AI_PLAY_API_KEY and has no MCP wait fields.

- [ ] **Step 3: Implement the credential-free Config**

Replace the dataclass and parsing with this contract:

~~~python
from dataclasses import dataclass
import math
import os


@dataclass(frozen=True)
class Config:
    ws_host: str = "127.0.0.1"
    ws_port: int = 8765
    wait_timeout_seconds: float = 30.0
    stop_timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "Config":
        config = cls(
            ws_host=os.environ.get("AI_PLAY_WS_HOST", cls.ws_host).strip(),
            ws_port=_read_int("AI_PLAY_WS_PORT", cls.ws_port),
            wait_timeout_seconds=_read_float(
                "AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS",
                cls.wait_timeout_seconds,
            ),
            stop_timeout_seconds=_read_float(
                "AI_PLAY_STOP_TIMEOUT_SECONDS",
                cls.stop_timeout_seconds,
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.ws_host != "127.0.0.1":
            raise ValueError("AI_PLAY_WS_HOST must be 127.0.0.1")
        if type(self.ws_port) is not int or not 1 <= self.ws_port <= 65535:
            raise ValueError("AI_PLAY_WS_PORT must be between 1 and 65535")
        for name, value, lower, upper in [
            ("AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS", self.wait_timeout_seconds, 0.1, 120.0),
            ("AI_PLAY_STOP_TIMEOUT_SECONDS", self.stop_timeout_seconds, 0.1, 30.0),
        ]:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number")
            if not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f"{name} is outside its allowed range")


def _read_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


def _read_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error
~~~

Update requirements.txt:

~~~text
mcp[cli]>=1.28,<2
websockets>=14.0,<16.0
pytest>=8.0,<9.0
~~~

- [ ] **Step 4: Run the configuration tests to verify they pass**

Run:

~~~powershell
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_config.py -q
~~~

Expected: PASS with no credential-related failure.

- [ ] **Step 5: Update the environment example**

Replace the example with:

~~~dotenv
AI_PLAY_WS_HOST=127.0.0.1
AI_PLAY_WS_PORT=8765
AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS=30
AI_PLAY_STOP_TIMEOUT_SECONDS=5
~~~

- [ ] **Step 6: Commit the completed configuration slice**

~~~powershell
git add ai_play/requirements.txt ai_play/.env.example ai_play/src/ai_play/config.py ai_play/tests/test_config.py
git commit -m "refactor: make AI Play configuration MCP-only"
~~~

### Task 2: Expose independent action-batch and MCP-observation DTO validation

**Files:**
- Modify: ai_play/tests/test_action_schema.py
- Modify: ai_play/src/ai_play/action_schema.py
- Modify: ai_play/tests/test_observation_schema.py
- Modify: ai_play/src/ai_play/observation_schema.py

- [ ] **Step 1: Add failing tests for the new public validators**

Add tests that do not use reason or memory_updates:

~~~python
from ai_play.action_schema import ActionValidationError, validate_action_batch


def test_validate_action_batch_accepts_current_safe_actions():
    actions = [
        {"type": "look", "yaw": 5, "pitch": -2},
        {"type": "move", "forward": 1, "right": 0, "duration_ms": 100},
    ]

    assert validate_action_batch(actions, {"interact"}, False) == actions


def test_validate_action_batch_rejects_unavailable_interaction():
    actions = [{"type": "interact", "action": "interact2"}]

    with pytest.raises(ActionValidationError, match="currently available"):
        validate_action_batch(actions, {"interact"}, False)
~~~

Add an observation projection test:

~~~python
def test_prepare_mcp_observation_removes_base64_from_structured_state():
    observation = valid_observation_with_jpeg_base64()

    public, image_bytes = prepare_mcp_observation(observation)

    assert public["image"] == {
        "mime_type": "image/jpeg",
        "width": 768,
        "height": 432,
    }
    assert image_bytes == b"jpeg-bytes"
~~~

The fixture must create the Base64 field from base64.b64encode(b"jpeg-bytes") and must pass through validate_observation.

- [ ] **Step 2: Run the focused schema tests to verify the intended failure**

Run:

~~~powershell
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_action_schema.py ai_play/tests/test_observation_schema.py -q
~~~

Expected: FAIL with missing validate_action_batch and prepare_mcp_observation symbols.

- [ ] **Step 3: Implement the public action batch validator**

Keep the existing action keys, numeric bounds, interaction gating, digit checks, probe exclusivity, and context-changing-last rule. Expose this function:

~~~python
def validate_action_batch(actions, available_interactions, interface_open):
    if not isinstance(actions, list) or not 1 <= len(actions) <= 3:
        raise ActionValidationError("actions must contain 1..3 entries")

    available = set(available_interactions)
    for index, action in enumerate(actions):
        _validate_action(action, available, interface_open)
        if action["type"] in {"stop", "interact", "enter_digits", "close_ui"}:
            if index != len(actions) - 1:
                raise ActionValidationError("context-changing action must be last")
    if any(action["type"] == "probe_interaction" for action in actions) and len(actions) != 1:
        raise ActionValidationError("probe_interaction must be the only action")
    return actions
~~~

Delete MEMORY_UPDATE_KEYS, validate_memory_updates, and validate_decision after all remaining tests use validate_action_batch.

- [ ] **Step 4: Implement the MCP observation projection**

Add this public function after validate_observation:

~~~python
def prepare_mcp_observation(value):
    safe = validate_observation(value)
    encoded = safe["image"]["base64"]
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ObservationValidationError("image base64 is invalid") from error

    public = {key: item for key, item in safe.items()}
    public["image"] = {
        key: item
        for key, item in safe["image"].items()
        if key != "base64"
    }
    return public, image_bytes
~~~

The function must not mutate the cached observation.

- [ ] **Step 5: Run the schema tests to verify they pass**

Run:

~~~powershell
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_action_schema.py ai_play/tests/test_observation_schema.py -q
~~~

Expected: PASS.

- [ ] **Step 6: Commit the DTO slice**

~~~powershell
git add ai_play/src/ai_play/action_schema.py ai_play/src/ai_play/observation_schema.py ai_play/tests/test_action_schema.py ai_play/tests/test_observation_schema.py
git commit -m "feat: expose MCP action and observation DTO validation"
~~~

### Task 3: Build the thread-safe GameSession state machine

**Files:**
- Create: ai_play/src/ai_play/game_session.py
- Create: ai_play/tests/test_game_session.py

- [ ] **Step 1: Write failing tests for observation wait and action correlation**

Use a fake send_packet callback and a valid observation fixture:

~~~python
def test_observe_waits_for_and_returns_latest_observation():
    session, sent = make_session()
    result_holder = []

    thread = threading.Thread(
        target=lambda: result_holder.append(session.observe(timeout=0.5))
    )
    thread.start()
    time.sleep(0.02)
    session.receive_observation(observation(7))
    thread.join()

    assert result_holder == [
        SessionResult(status="ready", observation=observation(7))
    ]
    assert sent == []


def test_act_rejects_stale_observation_without_sending_to_godot():
    session, sent = make_session()
    session.receive_observation(observation(7))

    with pytest.raises(SessionError, match="stale_observation"):
        session.act(
            6,
            [{"type": "wait", "duration_ms": 50}],
            timeout=0.5,
        )

    assert sent == []
~~~

- [ ] **Step 2: Run the session tests to verify the intended failure**

Run:

~~~powershell
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_game_session.py -q
~~~

Expected: FAIL because game_session.py does not exist.

- [ ] **Step 3: Create the session result and public state surface**

Define the session result and state storage before adding the transition methods:

~~~python
from dataclasses import dataclass
from threading import Condition, Lock

from .observation_schema import prepare_mcp_observation


class SessionError(RuntimeError):
    pass


@dataclass(frozen=True)
class SessionResult:
    status: str
    observation: dict | None = None
    action_results: list[dict] | None = None
    game_over: dict | None = None


class GameSession:
    def __init__(self, config):
        self.config = config
        self._condition = Condition(Lock())
        self._send_packet = None
        self._latest_observation = None
        self._pending_observation_id = None
        self._pending_results = None
        self._pending_next_observation = None
        self._game_over = None
        self._state = "waiting_for_game"

    def attach(self, send_packet):
        with self._condition:
            if self._send_packet is not None:
                raise SessionError("controller_busy")
            self._send_packet = send_packet
            self._state = "waiting_for_observation"
            self._condition.notify_all()

    def detach(self, reason):
        with self._condition:
            self._send_packet = None
            self._pending_observation_id = None
            self._pending_results = None
            self._pending_next_observation = None
            if self._game_over is None:
                self._state = "disconnected"
            self._condition.notify_all()

    def to_mcp_payload(self, result):
        payload = {
            "status": result.status,
            "action_results": result.action_results or [],
            "game_over": result.game_over,
        }
        image_bytes = None
        if result.observation is not None:
            public, image_bytes = prepare_mcp_observation(result.observation)
            payload["observation"] = public
        else:
            payload["observation"] = None
        return payload, image_bytes
~~~

The transition methods receive_observation, receive_action_results, receive_game_over, receive_stop_ack, observe, act, and stop must be implemented in the next steps with the signatures used by the tests and MCP server.

- [ ] **Step 4: Implement validated packet receivers**

receive_observation must call validate_observation, reject an unexpected observation while a batch is pending, update the latest observation, and notify all waiters. receive_action_results must call validate_action_results and match the pending observation ID. receive_game_over must accept only success/correct_password or failure/wrong_password, complete the pending turn if its ID matches, set state game_over, and notify all waiters. receive_stop_ack must validate the exact acknowledgement fields, clear pending data, set state stopped, and notify all waiters.

- [ ] **Step 5: Implement serialized act**

The action call must validate before sending and wait for results plus the next observation:

~~~python
with self._condition:
    self._require_ready_action_state(observation_id)
    validate_action_batch(
        actions,
        self._available_interactions(self._latest_observation),
        self._interface_open(self._latest_observation),
    )
    self._pending_observation_id = observation_id
    self._pending_results = None
    self._pending_next_observation = None
    packet = {
        "type": "action_batch",
        "protocol_version": 2,
        "observation_id": observation_id,
        "actions": deepcopy(actions),
    }
    sender = self._send_packet
    if sender is None or not sender(packet):
        self._clear_pending_locked("action_send_failed")
        raise SessionError("transport_unavailable")

deadline = time.monotonic() + (timeout or self.config.wait_timeout_seconds)
while True:
    with self._condition:
        if self._pending_next_observation is not None:
            return self._complete_turn_locked()
        if self._game_over is not None:
            return self._complete_terminal_turn_locked()
        if self._state in {"stopped", "disconnected"}:
            raise SessionError(self._state)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            self._clear_pending_locked("action_timeout")
            raise SessionError("action_timeout")
        self._condition.wait(timeout=remaining)
~~~

The implementation must reject a second act while _pending_observation_id is set and must never send an unvalidated packet.

- [ ] **Step 6: Implement stop and cleanup paths**

stop() sends exactly:

~~~python
{
    "type": "stop_request",
    "protocol_version": 2,
    "observation_id": pending_id,
    "reason": "mcp_stop",
}
~~~

It waits for stop_ack until stop_timeout_seconds; on ack or disconnect it sets stopped, clears pending action data, notifies all waiters, and returns a stopped result. Repeated calls return the same safe stopped result. detach() clears pending state and notifies waiters without fabricating a successful action result.

- [ ] **Step 7: Add the remaining session tests and run them**

Cover one in-flight action, valid action_batch packet, action results followed by next observation, game_over before next observation, invalid result fields, mcp_stop, timeout, disconnect, repeated stop, and second caller rejection.

Run:

~~~powershell
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_game_session.py -q
~~~

Expected: PASS.

- [ ] **Step 8: Commit the session slice**

~~~powershell
git add ai_play/src/ai_play/game_session.py ai_play/tests/test_game_session.py
git commit -m "feat: add serialized AI Play game session"

### Task 4: Replace the WebSocket AgentLoop bridge with a protocol v2 bridge

**Files:**
- Modify: ai_play/src/ai_play/bridge_server.py
- Modify: ai_play/tests/test_bridge_server.py

- [ ] **Step 1: Write failing protocol v2 bridge tests**

Rewrite AgentLoop fakes around GameSession:

~~~python
def test_bridge_accepts_exact_protocol_two_hello():
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)

    with connect(uri, proxy=None) as connection:
        assert send(connection, {
            "type": "hello",
            "protocol_version": 2,
        }) == {
            "type": "hello",
            "protocol_version": 2,
        }

    handle.close()


@pytest.mark.parametrize("version", [1, 3, True, 2.0, "2"])
def test_bridge_rejects_non_integer_protocol_two(version):
    session = GameSession(Config())
    uri, handle = start_test_bridge(session)
    with connect(uri, proxy=None) as connection:
        result = send(connection, {
            "type": "hello",
            "protocol_version": version,
        })
    handle.close()

    assert result["code"] == "unsupported_protocol"
~~~

Add tests that a valid observation reaches GameSession, a second controller gets controller_busy, invalid packets do not consume a later valid connection, and stop_ack/game_over are routed to the session.

- [ ] **Step 2: Run the bridge tests to verify the intended failure**

Run:

~~~powershell
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_bridge_server.py -q
~~~

Expected: FAIL because the current server only supports AgentLoop and protocol version 1.

- [ ] **Step 3: Implement the bridge server lifecycle**

Keep websockets.sync.server.serve, but expose a stoppable background handle:

~~~python
class BridgeHandle:
    def __init__(self, server, thread):
        self._server = server
        self._thread = thread

    def close(self):
        self._server.shutdown()
        self._thread.join(timeout=2.0)


def start(config, session) -> BridgeHandle:
    ready = threading.Event()
    holder = {}

    def run():
        with websocket_serve(
            lambda connection: _handler(connection, config, session),
            config.ws_host,
            config.ws_port,
            max_size=MAX_PACKET_SIZE,
            compression=None,
        ) as server:
            holder["server"] = server
            ready.set()
            server.serve_forever()

    thread = threading.Thread(
        target=run,
        name="ai-play-godot-bridge",
        daemon=True,
    )
    thread.start()
    if not ready.wait(timeout=2.0):
        raise RuntimeError("Godot bridge did not start")
    return BridgeHandle(holder["server"], thread)
~~~

The handler must enforce the five-second hello timeout, exact 127.0.0.1 config validation, one active controller, MAX_PACKET_SIZE, JSON object packets, exact protocol version 2, and hello before all other packet types. After hello it must call session.attach(connection.send) and route observation, action_results, stop, and game_over to the corresponding receiver. It must not expose AgentLoop callbacks, memory directories, or data-dir handling.

- [ ] **Step 4: Run bridge tests to verify they pass**

Run:

~~~powershell
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_bridge_server.py -q
~~~

Expected: PASS with protocol 2 and no model references.

- [ ] **Step 5: Commit the bridge slice**

~~~powershell
git add ai_play/src/ai_play/bridge_server.py ai_play/tests/test_bridge_server.py
git commit -m "refactor: route Godot through protocol v2 game session"
~~~

### Task 5: Expose the three FastMCP tools and standard image results

**Files:**
- Create: ai_play/src/ai_play/mcp_server.py
- Create: ai_play/tests/test_mcp_server.py

- [ ] **Step 1: Write failing SDK in-memory tests**

Use the official in-memory helper:

~~~python
import asyncio

from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import ImageContent

from ai_play.config import Config
from ai_play.mcp_server import mcp


def test_mcp_exposes_only_game_tools():
    async def run():
        async with create_connected_server_and_client_session(
            mcp,
            raise_exceptions=True,
        ) as client:
            tools = await client.list_tools()
            assert [tool.name for tool in tools.tools] == [
                "observe",
                "act",
                "stop",
            ]

    asyncio.run(run())


def test_observe_contains_structured_state_and_mcp_image(monkeypatch):
    async def run():
        session = fake_ready_session()
        monkeypatch.setattr("ai_play.mcp_server.game_session", session)
        monkeypatch.setattr("ai_play.mcp_server.config", Config())
        async with create_connected_server_and_client_session(
            mcp,
            raise_exceptions=True,
        ) as client:
            result = await client.call_tool("observe", {})
            assert result.structuredContent["observation"]["image"] == {
                "mime_type": "image/jpeg",
                "width": 768,
                "height": 432,
            }
            assert any(isinstance(item, ImageContent) for item in result.content)

    asyncio.run(run())
~~~

Add calls for stale act, invalid actions, successful synchronous result, stop, terminal response, and MCP error result with isError true.

- [ ] **Step 2: Run MCP tests to verify the intended failure**

Run:

~~~powershell
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_mcp_server.py -q
~~~

Expected: FAIL because mcp_server.py and its tool registrations do not exist.

- [ ] **Step 3: Implement FastMCP server and tool serialization**

Register one shared GameSession and direct CallToolResult responses:

~~~python
import asyncio
import base64
import sys

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, ImageContent, TextContent

from .bridge_server import start
from .config import Config
from .game_session import GameSession, SessionError


mcp = FastMCP("Cogito AI Play", json_response=True)
game_session = None
config = None


def _result(payload, image_bytes=None):
    content = []
    if image_bytes is not None:
        content.append(ImageContent(
            type="image",
            data=base64.b64encode(image_bytes).decode("ascii"),
            mimeType="image/jpeg",
        ))
    return CallToolResult(
        content=content,
        structuredContent=payload,
    )


def _error(code):
    return CallToolResult(
        isError=True,
        content=[TextContent(type="text", text=code)],
        structuredContent={
            "status": "error",
            "code": code,
        },
    )


@mcp.tool()
async def observe() -> CallToolResult:
    """Read the latest approved game observation and screenshot."""
    try:
        result = await asyncio.to_thread(
            game_session.observe,
            config.wait_timeout_seconds,
        )
    except SessionError as error:
        return _error(str(error))
    payload, image_bytes = game_session.to_mcp_payload(result)
    return _result(payload, image_bytes)


@mcp.tool()
async def act(observation_id: int, actions: list[dict]) -> CallToolResult:
    """Execute one validated batch of one to three player actions."""
    try:
        result = await asyncio.to_thread(
            game_session.act,
            observation_id,
            actions,
            config.wait_timeout_seconds,
        )
    except SessionError as error:
        return _error(str(error))
    payload, image_bytes = game_session.to_mcp_payload(result)
    return _result(payload, image_bytes)


@mcp.tool()
async def stop() -> CallToolResult:
    """Stop AI control and release all simulated inputs."""
    try:
        result = await asyncio.to_thread(
            game_session.stop,
            config.stop_timeout_seconds,
        )
    except SessionError as error:
        return _error(str(error))
    payload, _ = game_session.to_mcp_payload(result)
    return _result(payload)


def main() -> None:
    global config, game_session
    config = Config.from_env()
    game_session = GameSession(config)
    bridge = start(config, game_session)
    try:
        mcp.run(transport="stdio")
    finally:
        bridge.close()
        game_session.detach("mcp_shutdown")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
~~~

The final implementation must keep tool names, argument names, direct structured results, image content, asyncio.to_thread, and stderr-only diagnostics. mcp.run(transport="stdio") is the only stdio writer.

- [ ] **Step 4: Run SDK tests to verify they pass**

Run:

~~~powershell
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_mcp_server.py -q
~~~

Expected: PASS; exactly three tools are listed and image bytes are present only in MCP image content.

- [ ] **Step 5: Commit the MCP tool slice**

~~~powershell
git add ai_play/src/ai_play/mcp_server.py ai_play/tests/test_mcp_server.py
git commit -m "feat: expose AI Play through stdio MCP tools"
~~~

### Task 6: Update the Godot bridge for protocol v2 and remote stopping

**Files:**
- Modify: tests/ai_play/test_ai_play_controller.gd
- Modify: addons/cogito/AIPlay/ai_play_bridge.gd

- [ ] **Step 1: Add failing Godot tests for incoming stop_request and protocol 2**

Extend FakeBridge with the new signal and add:

~~~gdscript
signal stop_request_received(request: Dictionary)


func _test_bridge_accepts_protocol_two_and_emits_stop_request() -> void:
	var bridge_script: GDScript = load("res://addons/cogito/AIPlay/ai_play_bridge.gd")
	var bridge: Node = bridge_script.new()
	var requests: Array[Dictionary] = []
	bridge.stop_request_received.connect(
		func(request: Dictionary): requests.append(request)
	)
	bridge._handle_text_packet(JSON.stringify({
		"type": "stop_request",
		"protocol_version": 2,
		"observation_id": 9,
		"reason": "mcp_stop",
	}))

	_assert(requests == [{
		"type": "stop_request",
		"protocol_version": 2,
		"observation_id": 9,
		"reason": "mcp_stop",
	}], "bridge emits validated MCP stop request")
	bridge.free()
~~~

Add negative cases for protocol 1, stop_request with extra fields, escape_stop received from Python, and unknown packet types.

- [ ] **Step 2: Run the focused Godot test to verify the intended failure**

Run:

~~~powershell
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
~~~

Expected: FAIL because the bridge still uses protocol 1 and has no stop_request_received signal.

- [ ] **Step 3: Implement the bridge protocol changes**

Update the bridge surface:

~~~gdscript
signal stop_request_received(request: Dictionary)

const PROTOCOL_VERSION: int = 2


func _has_exact_keys(packet: Dictionary, expected: Array[String]) -> bool:
	if packet.size() != expected.size():
		return false
	for key: String in expected:
		if not packet.has(key):
			return false
	return true


func _handle_text_packet(raw_packet: String) -> void:
	var json := JSON.new()
	if json.parse(raw_packet) != OK or not json.data is Dictionary:
		_protocol_error("invalid_packet", "packet must be a JSON object")
		return
	var packet: Dictionary = json.data
	if not _is_protocol_version_two(packet.get("protocol_version")):
		_protocol_error("unsupported_protocol", "protocol version must be 2")
		return
	match packet.get("type"):
		"hello":
			pass
		"action_batch":
			action_batch_received.emit(packet)
		"stop_request":
			if _has_exact_keys(
				packet,
				["type", "protocol_version", "observation_id", "reason"],
			) and packet["reason"] == "mcp_stop":
				stop_request_received.emit(packet)
			else:
				_protocol_error("invalid_stop_request", "invalid stop request")
		"error":
			remote_error.emit(packet)
		_:
			_protocol_error("unexpected_packet", "unexpected packet type")
~~~

Keep the exact loopback predicate and MAX_PACKET_SIZE. Replace the version helper and all tests with integer version 2 checks. game_over is no longer a Python-to-Godot packet.

- [ ] **Step 4: Run bridge and executor tests**

Run:

~~~powershell
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
~~~

Expected: PASS for the updated bridge and existing executor behavior.

- [ ] **Step 5: Commit the Godot bridge slice**

~~~powershell
git add addons/cogito/AIPlay/ai_play_bridge.gd tests/ai_play/test_ai_play_controller.gd
git commit -m "feat: add protocol v2 MCP stop requests to Godot bridge"
~~~

### Task 7: Make AIPlayController MCP-driven and preserve every input release path

**Files:**
- Modify: addons/cogito/AIPlay/ai_play_controller.gd
- Modify: tests/ai_play/test_ai_play_controller.gd

- [ ] **Step 1: Write failing controller tests for the new batch and stop contract**

Add or replace tests so a valid incoming batch contains only four fields and remote stopping sends an acknowledgement:

~~~gdscript
func _test_remote_stop_releases_and_acknowledges(controller_script: GDScript) -> void:
	var fixture := await _create_controller_fixture(controller_script)
	fixture.controller._state = fixture.controller.State.EXECUTING
	fixture.bridge.stop_request_received.emit({
		"type": "stop_request",
		"protocol_version": 2,
		"observation_id": 17,
		"reason": "mcp_stop",
	})
	await get_tree().process_frame

	_assert(
		fixture.executor.cancel_reasons == ["mcp_stop"],
		"remote stop cancels executor",
	)
	_assert(
		fixture.controller.get_state() == fixture.controller.State.DISABLED,
		"remote stop disables controller",
	)
	_assert(
		fixture.bridge.sent_packets[-1] == {
			"type": "stop_ack",
			"protocol_version": 2,
			"observation_id": 17,
			"results": [{
				"status": "cancelled",
				"reason": "mcp_stop",
			}],
		},
		"remote stop sends ack",
	)
	fixture.free()
~~~

Update action-batch tests to reject request_count, request_limit, and reason. Update terminal tests to send only game_over with observation_id, outcome, and reason.

- [ ] **Step 2: Run the focused controller test to verify the intended failure**

Run:

~~~powershell
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
~~~

Expected: FAIL because the controller currently requires model request metadata and has no remote stop handler.

- [ ] **Step 3: Remove model request state and change the handshake**

Connect stop_request_received in _ready. In _on_bridge_connected send only:

~~~gdscript
var hello: Dictionary = {
	"type": "hello",
	"protocol_version": PROTOCOL_VERSION,
}
~~~

Remove _active_request_count, _active_request_limit, the max-request branch in _on_batch_finished, and _on_remote_game_over. _on_action_batch_received must require type, protocol_version, observation_id, and actions, verify the observation ID, and call the existing executor validation path without model metadata.

- [ ] **Step 4: Implement the remote stop handler**

Use this order so executor cancellation cannot trigger a new observation:

~~~gdscript
func _on_stop_request_received(request: Dictionary) -> void:
	if (
		not _has_exact_keys(
			request,
			["type", "protocol_version", "observation_id", "reason"],
		)
		or request.get("type") != "stop_request"
		or request.get("protocol_version") != PROTOCOL_VERSION
		or request.get("reason") != "mcp_stop"
	):
		_pause_for_error("invalid_stop_request")
		return
	var parsed_id: Dictionary = _parse_observation_id(
		request.get("observation_id")
	)
	if not parsed_id["valid"] and request.get("observation_id") != null:
		_pause_for_error("invalid_stop_request")
		return
	_capture_generation += 1
	_state = State.DISABLED
	_pending_observation_id = -1
	_executing_observation_id = -1
	_observation_timer.stop()
	_executor.cancel_all("mcp_stop")
	_bridge.send_packet({
		"type": "stop_ack",
		"protocol_version": PROTOCOL_VERSION,
		"observation_id": request.get("observation_id"),
		"results": [{
			"status": "cancelled",
			"reason": "mcp_stop",
		}],
	})
	_bridge.disconnect_from_server()
~~~

Validate the request ID against the currently executing or pending observation when one exists. State.DISABLED must be assigned before cancel_all.

- [ ] **Step 5: Preserve Escape, disconnect, teardown and local terminal behavior**

Keep _send_stop_packet("escape_stop"), keep _on_bridge_disconnected calling cancel_all, and keep _exit_tree generation invalidation. Change _finish_game to send protocol 2 game_over without request count, accepting only:

~~~gdscript
{
	"type": "game_over",
	"protocol_version": 2,
	"observation_id": observation_id,
	"outcome": "success" or "failure",
	"reason": "correct_password" or "wrong_password",
}
~~~

- [ ] **Step 6: Run all focused Godot tests**

Run:

~~~powershell
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_interaction_probe.gd
godot --headless --path . --script tests/ai_play/test_cogito_keypad_result.gd
~~~

Expected: PASS, including no late recapture after remote stop and no held synthetic input after disconnect.

- [ ] **Step 7: Commit the controller slice**

~~~powershell
git add addons/cogito/AIPlay/ai_play_controller.gd tests/ai_play/test_ai_play_controller.gd
git commit -m "refactor: let MCP own AI Play turns"

### Task 8: Make the launcher and entrypoint credential-free

**Files:**
- Modify: ai_play/start_ai.sh
- Modify: tests/check_ai_play_start_script.sh
- Modify: ai_play/tests/test_mcp_server.py

- [ ] **Step 1: Add the launcher assertion before changing the script**

Change the shell fixture expectation to the MCP module and preserve arguments:

~~~bash
grep -q -- '-m ai_play.mcp_server "$@"' "$script"
output="$(cd /tmp && "$fixture/start_ai.sh" --test-flag)"
grep -q "args=-m ai_play.mcp_server --test-flag" <<<"$output"
~~~

Add a Python subprocess test that starts the module with an invalid bridge host and verifies the error is written to stderr while stdout remains empty.

- [ ] **Step 2: Run the launcher tests to verify the intended failure**

Run:

~~~powershell
bash tests/check_ai_play_start_script.sh
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_mcp_server.py -q
~~~

Expected: the shell check fails because it still launches ai_play.main; the subprocess test fails because the old entrypoint requires credentials.

- [ ] **Step 3: Update start_ai.sh**

Keep the working-directory and virtualenv checks, but change the final command to:

~~~bash
PYTHONPATH=ai_play/src .venv/bin/python -m ai_play.mcp_server "$@"
~~~

Do not add API keys, model arguments, or resume behavior.

- [ ] **Step 4: Run the launcher checks to verify they pass**

Run:

~~~powershell
bash tests/check_ai_play_start_script.sh
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_mcp_server.py -q
~~~

Expected: PASS with no stdout contamination.

- [ ] **Step 5: Commit the launcher slice**

~~~powershell
git add ai_play/start_ai.sh tests/check_ai_play_start_script.sh ai_play/tests/test_mcp_server.py
git commit -m "chore: launch AI Play as an MCP server"
~~~

### Task 9: Remove the old model runtime and its tests

**Files:**
- Delete: ai_play/src/ai_play/main.py
- Delete: ai_play/src/ai_play/agent_loop.py
- Delete: ai_play/src/ai_play/api_client.py
- Delete: ai_play/src/ai_play/game_context.py
- Delete: ai_play/src/ai_play/memory.py
- Delete: ai_play/src/ai_play/prompts.py
- Delete: ai_play/src/ai_play/run_logger.py
- Delete: ai_play/goals/find_contract.py
- Delete: ai_play/tests/test_main.py
- Delete: ai_play/tests/test_agent_loop.py
- Delete: ai_play/tests/test_api_client.py
- Delete: ai_play/tests/test_game_context.py
- Delete: ai_play/tests/test_memory.py
- Delete: ai_play/tests/test_prompts.py
- Delete: ai_play/tests/test_run_logger.py
- Create: tests/check_ai_play_mcp_only.sh

- [ ] **Step 1: Add a failing repository-level legacy reference check**

Create tests/check_ai_play_mcp_only.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

if rg -n --glob '!docs/scope/**' --glob '!docs/wiki/**' 'openai|AI_PLAY_API_KEY|AgentLoop|ApiClient|RunLogger|MemoryStore|build_messages|ai_play\.main' ai_play/src ai_play/start_ai.sh ai_play/.env.example; then
  echo "legacy model runtime reference found" >&2
  exit 1
fi

test -f ai_play/src/ai_play/mcp_server.py
test ! -f ai_play/src/ai_play/main.py
~~~

Run before deleting old files:

~~~powershell
bash tests/check_ai_play_mcp_only.sh
~~~

Expected: FAIL with references from the current legacy modules.

- [ ] **Step 2: Delete the model-only source, goal loader, and tests**

Remove exactly the files listed in this task. Do not delete ai_play/assets/find_contract/. Do not modify .godot/, .import, .uid, caches, logs, or runtime memory.

- [ ] **Step 3: Remove now-unused imports and schema references**

Run:

~~~powershell
rg -n --glob '*.py' 'AgentLoop|ApiClient|RunLogger|MemoryStore|build_messages|load_game_context|validate_decision|validate_memory_updates|OpenAI|AI_PLAY_API_KEY|AI_PLAY_MODEL' ai_play/src ai_play/tests
~~~

Expected: no matches. If a match remains in action_schema.py, remove the old memory/decision API rather than adding a compatibility shim.

- [ ] **Step 4: Run the legacy check and Python suite**

Run:

~~~powershell
bash tests/check_ai_play_mcp_only.sh
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests -q
~~~

Expected: the scan and all remaining MCP/schema/bridge tests pass.

- [ ] **Step 5: Commit the removal slice**

~~~powershell
git add -A ai_play/src/ai_play ai_play/goals ai_play/tests tests/check_ai_play_mcp_only.sh
git commit -m "refactor: remove embedded AI Play model runtime"
~~~

### Task 10: Rewrite user-facing README and immediate repository instructions

**Files:**
- Modify: ai_play/README.md
- Modify: AGENTS.md
- Modify: tests/check_ai_play_mcp_only.sh

- [ ] **Step 1: Write documentation checks before rewriting prose**

Extend tests/check_ai_play_mcp_only.sh:

~~~bash
grep -q 'stdio MCP' ai_play/README.md
grep -q 'observe' ai_play/README.md
grep -q 'act' ai_play/README.md
grep -q 'stop' ai_play/README.md
grep -q -- '-- --ai-play' ai_play/README.md
if rg -n 'AI_PLAY_API_KEY|OpenAI\(|AI_PLAY_MODEL|memory\.json|RunLogger|AgentLoop' ai_play/README.md; then
  echo "legacy credential/model documentation found" >&2
  exit 1
fi
~~~

- [ ] **Step 2: Run the documentation checks to verify the intended failure**

Run:

~~~powershell
bash tests/check_ai_play_mcp_only.sh
~~~

Expected: FAIL because the current README documents API keys, model calls, memory and run logs.

- [ ] **Step 3: Rewrite ai_play/README.md around the MCP workflow**

The README must document the exact quick start:

~~~~markdown
# AI First Play MCP

## 快速启动

~~~bash
python3 -m venv .venv
.venv/bin/pip install -r ai_play/requirements.txt
ai_play/start_ai.sh
~~~

Then, in another terminal:

~~~bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn -- --ai-play
~~~

The MCP host starts ai_play.mcp_server over stdio and calls only observe, act, and stop.
~~~~

Document act(observation_id, actions), current action names and bounds, standard image results, find_contract scope, 127.0.0.1:8765, explicit opt-in, Escape, disconnection cleanup, no server-side persistence, and credential-free tests. Do not document goals, reference atlases, model prompts, API providers, or hidden scenario facts as runtime context.

- [ ] **Step 4: Update AGENTS.md facts**

Change the current protocol line from version 1 to version 2, replace the API-key runtime requirement with “MCP Server 不需要 API Key；外部 MCP 客户端凭据不得进入仓库或桥协议”, and update the runtime model-input wording to “外部 MCP 工具只接收获准运行时观察”. Keep explicit -- --ai-play, auto_start = false, exact 127.0.0.1, Escape, and no-hidden-state boundaries unchanged.

- [ ] **Step 5: Run documentation and secret checks**

Run:

~~~powershell
bash tests/check_ai_play_mcp_only.sh
bash tests/check_ai_play_secrets.sh
bash tests/test_ai_play_secret_scan.sh
git diff --check
~~~

Expected: PASS with no credential or model-runtime reference in the documented MCP path.

- [ ] **Step 6: Commit the documentation slice**

~~~powershell
git add ai_play/README.md AGENTS.md tests/check_ai_play_mcp_only.sh
git commit -m "docs: document AI Play MCP workflow"
~~~

### Task 11: Run the affected full suites and perform final repository review

**Files:**
- Modify only if a test exposes an implementation defect: the files from Tasks 1–10.

- [ ] **Step 1: Run the smallest affected Python suite**

Run:

~~~powershell
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests/test_config.py ai_play/tests/test_action_schema.py ai_play/tests/test_observation_schema.py ai_play/tests/test_game_session.py ai_play/tests/test_bridge_server.py ai_play/tests/test_mcp_server.py -q
~~~

Expected: PASS.

- [ ] **Step 2: Run all remaining Python tests**

Run:

~~~powershell
$env:PYTHONPATH = "ai_play/src"
python -m pytest ai_play/tests -q
~~~

Expected: PASS with no skipped credential-dependent test.

- [ ] **Step 3: Run all relevant Godot headless tests**

Run:

~~~powershell
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_executor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_observer.gd
godot --headless --path . --script tests/ai_play/test_ai_play_interaction_probe.gd
godot --headless --path . --script tests/ai_play/test_cogito_keypad_result.gd
godot --headless --path . --editor --quit
~~~

Expected: every script exits successfully. If Godot is unavailable, record that limitation and continue with all Python and shell checks.

- [ ] **Step 4: Run shell integration and security checks**

Run:

~~~powershell
bash tests/check_ai_play_lobby.sh
bash tests/check_ai_play_start_script.sh
bash tests/check_ai_play_mcp_only.sh
bash tests/check_friendly_human_npc.sh
bash tests/check_lobby_friendly_npc.sh
bash tests/test_ai_play_secret_scan.sh
~~~

Expected: PASS.

- [ ] **Step 5: Review the final diff for forbidden runtime inputs and generated files**

Run:

~~~powershell
rg -n --glob '!docs/scope/**' --glob '!docs/wiki/**' 'game_script|code_read|AI_PLAY_API_KEY|OpenAI\(|AgentLoop|ApiClient|memory\.json|run_logger|request_count|request_limit' ai_play/src ai_play/tests addons/cogito/AIPlay tests AGENTS.md
git status --short
git diff --check
~~~

Expected: runtime source has none of the forbidden model-memory/API fields. No .godot/, cache, log, runtime memory, .uid, or .import generated changes may be staged.

- [ ] **Step 6: Commit the verified implementation**

Run:

~~~powershell
git add -A
git diff --cached --check
git commit -m "feat: convert AI Play to MCP control service"
~~~

- [ ] **Step 7: Report the verification matrix and remaining engine limitation**

Report exact pass/fail results for Python, Godot, shell, secret-scan, and git diff --check. If any Godot command could not run, name it and state that engine validation remains outstanding. Do not run a real external MCP/model acceptance session without explicit user confirmation of screenshot, token, cost, and local trace effects.

~~~

~~~
