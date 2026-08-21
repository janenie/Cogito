# LangGraph Deep Agents Yibu AI Play Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one Python Deep Agents application that calls Yibu Chat Completions directly and autonomously plays supervised Cogito AI Play runs through a persistent stdio MCP session, with no Codex process or dependency.

**Architecture:** `tools_langgraph_deepagents` owns configuration, credentials, the Yibu `ChatOpenAI` instance, persistent MCP tool loading, Deep Agents middleware, SQLite checkpoints, terminal rendering, and lifecycle cleanup. It reuses only the provider-neutral AI Play run-path helpers, `ai_play_supervisor.py`, and the existing stdio MCP server; the model sees only allowlisted MCP tools and public MCP results.

**Tech Stack:** Python 3.11+, Deep Agents 0.7, LangChain 1.3, `langchain-openai`, `langchain-mcp-adapters`, LangGraph SQLite checkpoints, MCP 1.x, pytest.

---

### Task 1: Package skeleton, launch configuration, and safe Yibu credentials

**Files:**
- Create: `tools_langgraph_deepagents/__init__.py`
- Create: `tools_langgraph_deepagents/config.py`
- Create: `tools_langgraph_deepagents/credentials.py`
- Create: `tests/tools_langgraph_deepagents/test_config_credentials.py`

- [ ] **Step 1: Write failing tests for defaults, validation, and literal credential loading**

```python
from pathlib import Path

import pytest

from tools_langgraph_deepagents.config import parse_args
from tools_langgraph_deepagents.credentials import load_yibu_credentials


def test_defaults_use_chat_gemini_and_newak():
    args = parse_args([])
    assert args.model == "gemini-3.6-flash"
    assert args.yibu_credentials.name == "newak.py"
    assert args.credential_name == "ak"
    assert args.runs == 3


def test_explicit_external_confirmation_is_a_flag():
    args = parse_args(["--confirm-external-run"])
    assert args.confirm_external_run is True


def test_loads_only_selected_literal_dictionary(tmp_path: Path):
    source = tmp_path / "keys.py"
    source.write_text(
        "ak1 = {'key': 'first', 'url': 'https://yibuapi.com'}\n"
        "ak = {'key': 'chosen', 'url': 'https://yibuapi.com/v1'}\n",
        encoding="utf-8",
    )
    credentials = load_yibu_credentials(source, "ak")
    assert credentials.api_key == "chosen"
    assert credentials.base_url == "https://yibuapi.com/v1"


@pytest.mark.parametrize(
    "text, message",
    [
        ("ak = dynamic()", "literal dictionary"),
        ("ak = {'key': '', 'url': 'https://yibuapi.com'}", "non-empty"),
        ("ak = {'key': 'x', 'url': 'http://yibuapi.com'}", "https"),
        ("ak = {'key': 'x', 'url': 'https://user@yibuapi.com'}", "credentials"),
    ],
)
def test_rejects_unsafe_credentials(tmp_path: Path, text: str, message: str):
    source = tmp_path / "keys.py"
    source.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_yibu_credentials(source, "ak")
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv/bin/python -m pytest tests/tools_langgraph_deepagents/test_config_credentials.py -q`

Expected: collection fails because `tools_langgraph_deepagents.config` does not exist.

- [ ] **Step 3: Implement the package constants, parser, and credential loader**

```python
# tools_langgraph_deepagents/__init__.py
"""Direct Yibu Chat Completions host for Cogito AI Play."""

DEFAULT_MODEL = "gemini-3.6-flash"
IMAGE_CONTEXT_LIMIT = 10
```

```python
# tools_langgraph_deepagents/config.py
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from tools.ai_play_orchestrator_common import DEFAULT_SESSION_ROOT
from tools.ai_play_scene_registry import SUPPORTED_SCENARIOS
from tools_langgraph_deepagents import DEFAULT_MODEL

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Play Cogito with Deep Agents and Yibu Chat Completions.",
    )
    parser.add_argument("--scenario", choices=SUPPORTED_SCENARIOS, default="find_contract")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--yibu-credentials", type=Path, default=REPO_ROOT / "newak.py")
    parser.add_argument("--credential-name", default="ak")
    parser.add_argument("--session-root", type=Path, default=DEFAULT_SESSION_ROOT)
    persistence = parser.add_mutually_exclusive_group()
    persistence.add_argument("--artifact-root", type=Path)
    persistence.add_argument("--resume-run", type=Path)
    parser.add_argument("--workflow-memory", choices=("enabled", "disabled"), default="enabled")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--godot-bin", default="godot")
    parser.add_argument("--scene")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=100000.0)
    parser.add_argument("--model-timeout-seconds", type=float, default=600.0)
    parser.add_argument("--model-max-retries", type=int, default=4)
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    parser.add_argument("--benchmark-cycle-seed", type=int, default=20260809)
    parser.add_argument("--confirm-external-run", action="store_true")
    args = parser.parse_args(list(argv))
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if args.max_retries < 0 or args.model_max_retries < 0:
        parser.error("retry counts must be nonnegative")
    if args.timeout_seconds <= 0 or args.model_timeout_seconds <= 0:
        parser.error("timeouts must be positive")
    if not 1 <= args.max_output_tokens <= 32768:
        parser.error("--max-output-tokens must be between 1 and 32768")
    return args
```

```python
# tools_langgraph_deepagents/credentials.py
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class YibuCredentials:
    api_key: str
    base_url: str


def _normalize_base_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("yibu credential URL must be non-empty")
    url = value.strip().rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise ValueError("yibu credential URL must use https")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("yibu credential URL must not contain credentials")
    if not parsed.hostname or parsed.query or parsed.fragment:
        raise ValueError("invalid yibu credential URL")
    if parsed.path in ("", "/"):
        return url + "/v1"
    if parsed.path.rstrip("/") != "/v1":
        raise ValueError("yibu credential URL path must be /v1 or empty")
    return url


def load_yibu_credentials(path: Path, variable: str) -> YibuCredentials:
    source = path.expanduser()
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    except FileNotFoundError as error:
        raise ValueError(f"missing yibu credential file: {source}") from error
    except (OSError, SyntaxError) as error:
        raise ValueError("invalid yibu credential file") from error
    for node in tree.body:
        value = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable for target in node.targets
        ):
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == variable:
            value = node.value
        if value is None:
            continue
        try:
            payload = ast.literal_eval(value)
        except (ValueError, TypeError, SyntaxError) as error:
            raise ValueError("credential must be a literal dictionary") from error
        if not isinstance(payload, dict):
            raise ValueError("credential must be a literal dictionary")
        key = payload.get("key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("yibu credential key must be non-empty")
        return YibuCredentials(key.strip(), _normalize_base_url(payload.get("url")))
    raise ValueError(f"missing credential variable: {variable}")
```

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/tools_langgraph_deepagents/test_config_credentials.py -q`

Expected: all tests pass without printing credential values.

- [ ] **Step 5: Commit the scoped design and configuration slice**

```bash
git add docs/scope/2026-08-22-langgraph-deepagents-yibu docs/wiki/ai-play/system-guide.md tools_langgraph_deepagents tests/tools_langgraph_deepagents/test_config_credentials.py
git commit -m "feat(ai-play): scaffold direct deep agents host"
```

### Task 2: Direct Yibu Chat Completions model factory

**Files:**
- Create: `tools_langgraph_deepagents/model.py`
- Create: `tests/tools_langgraph_deepagents/test_model.py`

- [ ] **Step 1: Write failing tests that inspect the model and a local HTTP request**

```python
import json

import httpx
import pytest
from langchain_core.messages import HumanMessage

from tools_langgraph_deepagents.credentials import YibuCredentials
from tools_langgraph_deepagents.model import build_yibu_model


@pytest.mark.asyncio
async def test_model_posts_chat_completions_and_disables_parallel_tools():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1,
                "model": "gemini-3.6-flash",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    model = build_yibu_model(
        YibuCredentials("secret", "https://yibuapi.com/v1"),
        model="gemini-3.6-flash",
        timeout_seconds=5,
        max_retries=0,
        max_output_tokens=4096,
        http_async_client=async_client,
    )
    reply = await model.ainvoke([HumanMessage(content="hello")])
    await async_client.aclose()

    assert reply.text == "ok"
    assert requests[0].url.path == "/v1/chat/completions"
    payload = json.loads(requests[0].content)
    assert payload["model"] == "gemini-3.6-flash"
    assert payload["parallel_tool_calls"] is False
```

- [ ] **Step 2: Run the test and verify RED**

Run: `.venv/bin/python -m pytest tests/tools_langgraph_deepagents/test_model.py -q`

Expected: import fails because `model.py` does not exist.

- [ ] **Step 3: Implement an explicitly non-Responses `ChatOpenAI` model**

```python
from __future__ import annotations

from typing import Any

import httpx
from langchain_openai import ChatOpenAI

from tools_langgraph_deepagents.credentials import YibuCredentials


def build_yibu_model(
    credentials: YibuCredentials,
    *,
    model: str,
    timeout_seconds: float,
    max_retries: int,
    max_output_tokens: int,
    http_async_client: httpx.AsyncClient | None = None,
) -> ChatOpenAI:
    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": credentials.api_key,
        "base_url": credentials.base_url,
        "use_responses_api": False,
        "disable_streaming": True,
        "timeout": timeout_seconds,
        "max_retries": max_retries,
        "max_completion_tokens": max_output_tokens,
        "model_kwargs": {"parallel_tool_calls": False},
    }
    if http_async_client is not None:
        kwargs["http_async_client"] = http_async_client
    return ChatOpenAI(**kwargs)
```

- [ ] **Step 4: Run the model tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/tools_langgraph_deepagents/test_model.py -q`

Expected: the only captured path is `/v1/chat/completions`; no network leaves the process.

- [ ] **Step 5: Commit the direct Chat model slice**

```bash
git add tools_langgraph_deepagents/model.py tests/tools_langgraph_deepagents/test_model.py
git commit -m "feat(ai-play): add direct yibu chat model"
```

### Task 3: Persistent stdio MCP tools and public multimodal results

**Files:**
- Create: `tools_langgraph_deepagents/mcp_tools.py`
- Create: `tests/tools_langgraph_deepagents/test_mcp_tools.py`

- [ ] **Step 1: Write failing tests for the allowlist and structured-content interceptor**

```python
import json
from types import SimpleNamespace

import pytest
from mcp.types import CallToolResult, ImageContent

from tools_langgraph_deepagents.mcp_tools import (
    append_structured_content,
    select_player_tools,
)


def test_selects_only_awm_game_tools():
    tools = [SimpleNamespace(name=name) for name in (
        "stop", "act", "workflow_memory_update", "briefing", "observe", "workflow_memory_read"
    )]
    selected = select_player_tools(tools, workflow_memory_enabled=True)
    assert [tool.name for tool in selected] == [
        "briefing", "workflow_memory_read", "observe", "act", "workflow_memory_update"
    ]


def test_rejects_an_incomplete_tool_surface():
    with pytest.raises(RuntimeError, match="observe"):
        select_player_tools([SimpleNamespace(name="briefing")], workflow_memory_enabled=False)


@pytest.mark.asyncio
async def test_interceptor_appends_public_json_without_dropping_images():
    result = CallToolResult(
        structuredContent={"status": "ready", "observation": {"observation_id": 7}},
        content=[ImageContent(type="image", data="ZmFrZQ==", mimeType="image/jpeg")],
    )

    async def handler(_request):
        return result

    converted = await append_structured_content(SimpleNamespace(), handler)
    assert isinstance(converted.content[0], ImageContent)
    assert json.loads(converted.content[-1].text)["status"] == "ready"
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv/bin/python -m pytest tests/tools_langgraph_deepagents/test_mcp_tools.py -q`

Expected: import fails because `mcp_tools.py` does not exist.

- [ ] **Step 3: Implement stdio connection construction, interception, and fail-closed selection**

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.types import CallToolResult, TextContent

BASE_TOOL_NAMES = ("briefing", "observe", "act")
AWM_TOOL_NAMES = (
    "briefing", "workflow_memory_read", "observe", "act", "workflow_memory_update"
)


async def append_structured_content(request, handler):
    result = await handler(request)
    if isinstance(result, CallToolResult) and result.structuredContent is not None:
        result.content.append(TextContent(
            type="text",
            text=json.dumps(result.structuredContent, ensure_ascii=False, separators=(",", ":")),
        ))
    return result


def select_player_tools(tools: Sequence[Any], *, workflow_memory_enabled: bool) -> list[Any]:
    expected = AWM_TOOL_NAMES if workflow_memory_enabled else BASE_TOOL_NAMES
    by_name = {tool.name: tool for tool in tools}
    missing = [name for name in expected if name not in by_name]
    if missing:
        raise RuntimeError("MCP missing required player tools: " + ", ".join(missing))
    return [by_name[name] for name in expected]


def build_mcp_client(
    *, python_bin: str, repo_root: Path, env: dict[str, str]
) -> MultiServerMCPClient:
    connection = build_stdio_mcp_connection(
        python_bin=python_bin,
        repo_root=repo_root,
        env=env,
    )
    return MultiServerMCPClient(
        {"cogito_ai_play": connection},
        tool_interceptors=[append_structured_content],
        handle_tool_errors=True,
    )


def build_stdio_mcp_connection(*, python_bin: str, repo_root: Path, env: dict[str, str]):
    return {
        "transport": "stdio",
        "command": python_bin,
        "args": ["-m", "ai_play.mcp_server", "--transport", "stdio"],
        "cwd": str(repo_root),
        "env": env,
    }


async def load_player_tools(client, session, *, workflow_memory_enabled: bool):
    tools = await load_mcp_tools(
        session,
        server_name="cogito_ai_play",
        tool_interceptors=client.tool_interceptors,
        handle_tool_errors=True,
    )
    return select_player_tools(tools, workflow_memory_enabled=workflow_memory_enabled)
```

- [ ] **Step 4: Add a conversion test using an actual MCP image block**

```python
from langchain_core.messages import ToolMessage
from langchain_mcp_adapters.tools import convert_mcp_tool_to_langchain_tool
from mcp.types import Tool


@pytest.mark.asyncio
async def test_adapter_keeps_mcp_image_for_the_next_model_turn():
    class Session:
        async def call_tool(self, _name, _args, progress_callback=None):
            return CallToolResult(
                structuredContent={"status": "ready"},
                content=[ImageContent(type="image", data="ZmFrZQ==", mimeType="image/jpeg")],
            )

    converted = convert_mcp_tool_to_langchain_tool(
        Session(),
        Tool(name="observe", description="observe", inputSchema={"type": "object", "properties": {}}),
        tool_interceptors=[append_structured_content],
    )
    message = await converted.ainvoke(
        {"type": "tool_call", "name": "observe", "args": {}, "id": "call-1"}
    )
    assert isinstance(message, ToolMessage)
    assert message.content[0] == {
        "type": "image", "base64": "ZmFrZQ==", "mime_type": "image/jpeg"
    }
    assert json.loads(message.content[1]["text"])["status"] == "ready"
```

- [ ] **Step 5: Run the MCP tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/tools_langgraph_deepagents/test_mcp_tools.py -q`

Expected: the allowlist excludes `stop`, and images remain standard LangChain content blocks.

- [ ] **Step 6: Commit the MCP adapter slice**

```bash
git add tools_langgraph_deepagents/mcp_tools.py tests/tools_langgraph_deepagents/test_mcp_tools.py
git commit -m "feat(ai-play): connect deep agents to persistent mcp"
```

### Task 4: Hard ten-image context limit and locked-down Deep Agent

**Files:**
- Create: `tools_langgraph_deepagents/middleware.py`
- Create: `tools_langgraph_deepagents/prompt.py`
- Create: `tools_langgraph_deepagents/agent.py`
- Create: `tests/tools_langgraph_deepagents/test_agent.py`

- [ ] **Step 1: Write failing tests for image trimming and serial tool execution**

```python
import asyncio

import pytest
from langchain_core.messages import ToolMessage

from tools_langgraph_deepagents.middleware import SerialGameTools, trim_images


def test_trim_images_keeps_latest_ten_and_all_text():
    messages = [
        ToolMessage(
            content=[
                {"type": "text", "text": f"observation-{index}"},
                {"type": "image", "base64": str(index), "mime_type": "image/jpeg"},
            ],
            tool_call_id=f"call-{index}",
        )
        for index in range(12)
    ]
    trimmed = trim_images(messages, limit=10)
    images = [
        block["base64"]
        for message in trimmed
        for block in message.content
        if isinstance(block, dict) and block.get("type") == "image"
    ]
    assert images == [str(index) for index in range(2, 12)]
    assert [message.content[0]["text"] for message in trimmed] == [
        f"observation-{index}" for index in range(12)
    ]


@pytest.mark.asyncio
async def test_serial_middleware_never_overlaps_game_tools():
    middleware = SerialGameTools({"act"})
    active = 0
    maximum = 0

    async def handler(_request):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        active -= 1
        return "ok"

    request = type("Request", (), {"tool_call": {"name": "act"}})()
    await asyncio.gather(
        middleware.awrap_tool_call(request, handler),
        middleware.awrap_tool_call(request, handler),
    )
    assert maximum == 1
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv/bin/python -m pytest tests/tools_langgraph_deepagents/test_agent.py -q`

Expected: import fails because the middleware does not exist.

- [ ] **Step 3: Implement immutable message trimming and the game-tool runtime guard**

```python
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AnyMessage, ToolMessage

IMAGE_TYPES = frozenset({"image", "image_url", "input_image"})


def trim_images(messages: Sequence[AnyMessage], *, limit: int) -> list[AnyMessage]:
    remaining = limit
    result: list[AnyMessage] = []
    for message in reversed(messages):
        if not isinstance(message.content, list):
            result.append(message)
            continue
        kept_reversed = []
        for block in reversed(message.content):
            is_image = isinstance(block, dict) and block.get("type") in IMAGE_TYPES
            if not is_image or remaining > 0:
                kept_reversed.append(block)
                if is_image:
                    remaining -= 1
        result.append(message.model_copy(update={"content": list(reversed(kept_reversed))}))
    return list(reversed(result))


class ImageLimitMiddleware(AgentMiddleware):
    def __init__(self, limit: int) -> None:
        super().__init__()
        self.limit = limit

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        return await handler(request.override(messages=trim_images(request.messages, limit=self.limit)))


class SerialGameTools(AgentMiddleware):
    def __init__(self, allowed_names: set[str]) -> None:
        super().__init__()
        self.allowed_names = frozenset(allowed_names)
        self._lock = asyncio.Lock()

    async def awrap_tool_call(self, request, handler):
        name = request.tool_call["name"]
        if name not in self.allowed_names:
            return ToolMessage(
                content=f"tool is not available to the game player: {name}",
                tool_call_id=request.tool_call["id"],
                status="error",
            )
        async with self._lock:
            return await handler(request)
```

- [ ] **Step 4: Write the black-box game prompt without scenario answers or repository facts**

Create `prompt.py` with `build_system_prompt(runs, workflow_memory_enabled)`. It must require one initial `briefing`, one initial `observe`, direct consumption of each successful `act` result, latest `observation_id`, formal `game_over` as the only run boundary, caption text for every new RGB/depth image, AWM update only after eligible terminals, continued observation after reconnect, and no final answer before the target formal-terminal count. It must explicitly forbid filesystem, shell, repository, source, tests, plans, hidden state, and blind puzzle guesses.

- [ ] **Step 5: Implement the locked-down Deep Agent factory**

```python
from __future__ import annotations

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from deepagents.backends import StateBackend
from deepagents.middleware.filesystem import FilesystemPermission

from tools_langgraph_deepagents import IMAGE_CONTEXT_LIMIT
from tools_langgraph_deepagents.middleware import ImageLimitMiddleware, SerialGameTools

BUILTIN_TOOLS = frozenset({"ls", "read_file", "write_file", "edit_file", "glob", "grep", "execute"})


def register_game_profile() -> None:
    register_harness_profile(
        "openai",
        HarnessProfile(
            excluded_tools=BUILTIN_TOOLS,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )


def build_game_agent(*, model, tools, system_prompt: str, checkpointer):
    register_game_profile()
    names = {tool.name for tool in tools}
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=[ImageLimitMiddleware(IMAGE_CONTEXT_LIMIT), SerialGameTools(names)],
        subagents=[],
        skills=None,
        memory=None,
        backend=StateBackend(),
        permissions=[FilesystemPermission(operations=["read", "write"], paths=["/", "/**"], mode="deny")],
        checkpointer=checkpointer,
        name="cogito-yibu-player",
    )
```

- [ ] **Step 6: Add a scripted fake-model test for visible tools**

Use a `GenericFakeChatModel` subclass whose `bind_tools` records tool names. Build the Deep Agent with fixture `briefing`, `observe`, and `act` tools and assert that the recorded set is exactly those three; also script an `ls` tool call and assert `SerialGameTools` returns an error without invoking a filesystem handler.

- [ ] **Step 7: Run the agent tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/tools_langgraph_deepagents/test_agent.py -q`

Expected: every model request carries at most ten image blocks and every tool handler is allowlisted and serialized.

- [ ] **Step 8: Commit the harness slice**

```bash
git add tools_langgraph_deepagents/middleware.py tools_langgraph_deepagents/prompt.py tools_langgraph_deepagents/agent.py tests/tools_langgraph_deepagents/test_agent.py
git commit -m "feat(ai-play): lock down deep agents game harness"
```

### Task 5: Run paths, confirmation, resume validation, and safe child lifecycle

**Files:**
- Create: `tools_langgraph_deepagents/runtime.py`
- Create: `tests/tools_langgraph_deepagents/test_runtime.py`

- [ ] **Step 1: Write failing tests for explicit confirmation and Codex-free commands**

```python
from pathlib import Path

from tools_langgraph_deepagents.mcp_tools import build_stdio_mcp_connection
from tools_langgraph_deepagents.runtime import confirm_external_run


def test_noninteractive_confirmation_skips_input():
    called = False

    def input_fn(_prompt):
        nonlocal called
        called = True
        return ""

    assert confirm_external_run(
        confirmed=True,
        model="gemini-3.6-flash",
        scenario="find_contract",
        runs=3,
        input_fn=input_fn,
    )
    assert called is False


def test_interactive_confirmation_requires_run_word():
    assert not confirm_external_run(
        confirmed=False,
        model="gemini-3.6-flash",
        scenario="find_contract",
        runs=3,
        input_fn=lambda _prompt: "no",
    )


def test_stdio_connection_contains_no_codex_or_proxy(tmp_path: Path):
    connection = build_stdio_mcp_connection(
        python_bin="/python",
        repo_root=tmp_path,
        env={"AI_PLAY_WS_HOST": "127.0.0.1"},
    )
    serialized = repr(connection).lower()
    assert "codex" not in serialized
    assert "proxy" not in serialized
    assert connection["args"][-2:] == ["--transport", "stdio"]
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv/bin/python -m pytest tests/tools_langgraph_deepagents/test_runtime.py -q`

Expected: import fails because `runtime.py` does not exist.

- [ ] **Step 3: Implement confirmation and provider-neutral run preparation**

Implement these concrete interfaces in `runtime.py`:

```python
@dataclass(frozen=True)
class PreparedRun:
    paths: RunPaths
    completed_runs: int
    remaining_runs: int
    thread_id: str
    checkpoint_path: Path
    workflow_memory_path: Path


def confirm_external_run(*, confirmed, model, scenario, runs, input_fn=input) -> bool:
    notice = (
        f"Model={model} scenario={scenario} runs={runs}. "
        "This uploads approved RGB/depth screenshots, consumes paid tokens, "
        "and stores local trajectory plus agent checkpoints. Type RUN to continue: "
    )
    return True if confirmed else input_fn(notice).strip() == "RUN"


```

Add `prepare_run(args)` using `create_run_paths`/`resume_run_paths`, `resolve_scene`, and a new local `load_resume_progress` that validates `player == "deepagents"`, model, scenario, requested runs, workflow-memory mode, benchmark seed, and the schema-1 workflow checkpoint. Store `deepagents_checkpoint.sqlite` beside `session.json` and derive a stable thread ID from the resolved run directory with SHA-256.

- [ ] **Step 4: Implement an async supervisor process context**

```python
@asynccontextmanager
async def supervisor_process(command, *, cwd, env, output):
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    pump = asyncio.create_task(relay_output(process.stdout, output))
    try:
        yield process
    finally:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        await pump
```

`relay_output` must decode lines with replacement, write them to the trusted supervisor log and terminal, and never inspect model prompts, credentials, or Base64.

- [ ] **Step 5: Test normal exit, cancellation, and forced kill**

Use short Python fixture subprocesses: one exits zero, one waits and handles terminate, and one ignores terminate. Assert that the context closes all three and captures their non-secret stdout.

- [ ] **Step 6: Run runtime tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/tools_langgraph_deepagents/test_runtime.py -q`

Expected: confirmation, resume validation, and process cleanup tests pass; no command contains `codex`.

- [ ] **Step 7: Commit the runtime slice**

```bash
git add tools_langgraph_deepagents/runtime.py tests/tools_langgraph_deepagents/test_runtime.py
git commit -m "feat(ai-play): supervise deep agents game runtime"
```

### Task 6: Single application entry, streaming updates, continuation, and checkpointing

**Files:**
- Create: `tools_langgraph_deepagents/app.py`
- Create: `tools_langgraph_deepagents/console.py`
- Create: `tools_langgraph_deepagents/__main__.py`
- Create: `tests/tools_langgraph_deepagents/test_app.py`

- [ ] **Step 1: Write a failing integration test with fake agent, MCP, and supervisor**

```python
import pytest

from tools_langgraph_deepagents.app import continue_until_supervisor_finishes


@pytest.mark.asyncio
async def test_agent_final_is_continued_while_supervisor_is_running():
    prompts = []

    class Agent:
        async def astream(self, payload, config, stream_mode):
            prompts.append(payload["messages"][0].content)
            yield {"model": {"messages": []}}

    class Supervisor:
        returncode = None

        async def wait(self):
            self.returncode = 0
            return 0

    await continue_until_supervisor_finishes(
        agent=Agent(),
        supervisor=Supervisor(),
        graph_config={"configurable": {"thread_id": "thread"}},
        first_prompt="start",
        continuation_prompt="continue",
        render=lambda _event: None,
    )
    assert prompts[0] == "start"
    assert set(prompts).issubset({"start", "continue"})
```

- [ ] **Step 2: Run the test and verify RED**

Run: `.venv/bin/python -m pytest tests/tools_langgraph_deepagents/test_app.py -q`

Expected: import fails because `app.py` does not exist.

- [ ] **Step 3: Implement sanitized console rendering**

`console.py` must render only assistant text, tool name, tool status, observation ID, and formal terminal status. For content blocks it must replace image blocks with `[image image/jpeg]`; it must never serialize `base64`, API keys, full checkpoint state, or raw request headers.

- [ ] **Step 4: Implement agent continuation raced against supervisor completion**

```python
async def continue_until_supervisor_finishes(
    *, agent, supervisor, graph_config, first_prompt, continuation_prompt, render
) -> int:
    prompt = first_prompt
    while supervisor.returncode is None:
        agent_task = asyncio.create_task(_stream_once(agent, graph_config, prompt, render))
        supervisor_task = asyncio.create_task(supervisor.wait())
        done, _pending = await asyncio.wait(
            {agent_task, supervisor_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if supervisor_task in done:
            agent_task.cancel()
            with suppress(asyncio.CancelledError):
                await agent_task
            return supervisor_task.result()
        supervisor_task.cancel()
        with suppress(asyncio.CancelledError):
            await supervisor_task
        await agent_task
        prompt = continuation_prompt
    return supervisor.returncode
```

`_stream_once` must call
`agent.astream({"messages": [HumanMessage(content=prompt)]}, graph_config, stream_mode="updates")`,
pass each event to the renderer, and let transport/model errors escape to the outer safe-cleanup context.

- [ ] **Step 5: Implement the single `run(args)` application composition**

In `app.py`, compose the lifecycle in this exact order:

1. Validate arguments and load only the selected literal credential.
2. Obtain explicit external-run confirmation before any Yibu request or child process.
3. Create/resume trusted run paths and build MCP/supervisor environments.
4. Enter `MultiServerMCPClient.session("cogito_ai_play")` once.
5. Load and allowlist LangChain MCP tools from that persistent session.
6. Enter `AsyncSqliteSaver.from_conn_string(checkpoint_path)` and build the Yibu model plus Deep Agent.
7. Start `ai_play_supervisor.py` for only the remaining formal runs.
8. Stream one start prompt; whenever the Agent returns early while the supervisor is active, add the continuation prompt to the same checkpoint thread.
9. On every exit path call host-side MCP `stop`, close the MCP session/checkpointer, and terminate the supervisor if still active.

Return supervisor exit code `0` for all-success runs, `1` when formal runs include failure, `2` for abnormal supervisor termination, and `130` for `KeyboardInterrupt`.

- [ ] **Step 6: Add the only user-facing entry**

```python
# tools_langgraph_deepagents/__main__.py
from __future__ import annotations

import asyncio
import sys

from tools_langgraph_deepagents.app import run
from tools_langgraph_deepagents.config import parse_args


def main() -> int:
    return asyncio.run(run(parse_args(sys.argv[1:])))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Complete the fake integration test**

Inject fake factories into `run` so the test can assert one MCP session, one Deep Agent, zero Codex commands, ordered cleanup, the first start prompt, continuation after an early final, and no external socket connection. Add a `KeyboardInterrupt`/cancellation test that proves host-side `stop` runs before the MCP session closes.

- [ ] **Step 8: Run application tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/tools_langgraph_deepagents/test_app.py -q`

Expected: fake end-to-end execution reaches supervisor completion and cleanup without network or Godot.

- [ ] **Step 9: Commit the executable application slice**

```bash
git add tools_langgraph_deepagents/app.py tools_langgraph_deepagents/console.py tools_langgraph_deepagents/__main__.py tests/tools_langgraph_deepagents/test_app.py
git commit -m "feat(ai-play): add single deep agents application"
```

### Task 7: Isolated dependency lock, operator documentation, and full verification

**Files:**
- Modify: `.gitignore`
- Create: `tools_langgraph_deepagents/requirements.in`
- Create: `tools_langgraph_deepagents/requirements.lock.txt`
- Create: `tools_langgraph_deepagents/README.md`
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

- [ ] **Step 1: Declare the isolated direct dependencies**

```text
deepagents>=0.7.8,<0.8
langchain-openai>=1.3.5,<2
langchain-mcp-adapters>=0.3.2,<0.4
langgraph-checkpoint-sqlite>=3.1.1,<4
mcp[cli]>=1.28,<2
pytest>=8,<9
pytest-asyncio>=1.3,<2
```

Add `/newak.py` to `.gitignore` so the credential source remains local and cannot be accidentally staged.

- [ ] **Step 2: Generate a hash-locked dependency file with Python 3.12**

Run in an isolated temporary environment:

```bash
python3.12 -m venv /tmp/cogito-deepagents-lock
/tmp/cogito-deepagents-lock/bin/pip install pip-tools
/tmp/cogito-deepagents-lock/bin/pip-compile \
  --generate-hashes \
  --output-file tools_langgraph_deepagents/requirements.lock.txt \
  tools_langgraph_deepagents/requirements.in
```

Expected: a complete transitive lock with hashes and no local paths or credentials.

- [ ] **Step 3: Document the one-command workflow and explicit external impact**

`tools_langgraph_deepagents/README.md` and `ai_play/README.md` must show:

```bash
python3.12 -m venv .venv-deepagents
.venv-deepagents/bin/pip install --require-hashes -r tools_langgraph_deepagents/requirements.lock.txt
.venv-deepagents/bin/python -m tools_langgraph_deepagents \
  --scenario find_contract \
  --runs 3
```

Document that this is direct `/v1/chat/completions`, that `newak.py` remains ignored, that `--credential-name` selects but never auto-rotates an account, that no Codex process/config/proxy is used, that RGB/depth screenshots are uploaded, that requests are paid, that checkpoints may contain image Base64 outside the repository, that active model input keeps only ten images, and that `Ctrl-C` safely releases inputs. Include `--resume-run` and `--confirm-external-run` examples.

- [ ] **Step 4: Update the Wiki status from design-approved to implemented**

Change the Deep Agents section status line only after all local tests pass; add the final file paths, launch entry, dependency lock, and checkpoint filenames without including any credential path contents or API key.

- [ ] **Step 5: Install the locked environment and run focused tests**

```bash
python3.12 -m venv /tmp/cogito-deepagents-test
/tmp/cogito-deepagents-test/bin/pip install --require-hashes -r tools_langgraph_deepagents/requirements.lock.txt
PYTHONPATH=. /tmp/cogito-deepagents-test/bin/python -m pytest tests/tools_langgraph_deepagents -q
```

Expected: all new tests pass with no real Yibu request and no Godot process.

- [ ] **Step 6: Run affected existing Python tests**

```bash
PYTHONPATH=. /tmp/cogito-deepagents-test/bin/python -m pytest \
  ai_play/tests \
  tests/test_ai_play_supervisor.py \
  tests/test_ai_play_api_host.py \
  -q
```

Expected: all affected existing tests pass.

- [ ] **Step 7: Run safety and repository checks**

```bash
bash tests/test_ai_play_secret_scan.sh
git diff --check
git status --short
```

Expected: secret scan and whitespace validation pass; `newak.py` remains untracked and unchanged.

- [ ] **Step 8: Review the process boundary without making a paid call**

Run the parser/help and command-construction tests only. Do not pass `--confirm-external-run`, do not invoke Yibu, and do not launch Godot during this implementation session.

- [ ] **Step 9: Commit the verified documentation and dependency lock**

```bash
git add tools_langgraph_deepagents ai_play/README.md docs/wiki/ai-play/system-guide.md tests/tools_langgraph_deepagents
git commit -m "docs(ai-play): document deep agents yibu host"
```

- [ ] **Step 10: Rebase, rerun final checks, and push the feature branch**

```bash
git fetch origin
git rebase origin/save_token_ai_play
PYTHONPATH=. /tmp/cogito-deepagents-test/bin/python -m pytest tests/tools_langgraph_deepagents -q
bash tests/test_ai_play_secret_scan.sh
git diff --check
git push -u origin tools_langgraph_deepagents
```

Expected: the branch pushes without force; no merge into `ai_first_play` occurs until the user reviews the feature.
