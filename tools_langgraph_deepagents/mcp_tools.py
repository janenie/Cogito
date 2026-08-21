from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.types import CallToolResult, TextContent

from tools.ai_play_orchestrator_common import (
    AWM_PLAYER_TOOL_NAMES,
    BASE_PLAYER_TOOL_NAMES,
)


MCP_SERVER_NAME = "cogito_ai_play"


async def append_structured_content(request: Any, handler: Any) -> Any:
    """Make public structured MCP results visible without dropping images."""
    result = await handler(request)
    if (
        isinstance(result, CallToolResult)
        and result.structuredContent is not None
    ):
        result.content.append(
            TextContent(
                type="text",
                text=json.dumps(
                    result.structuredContent,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )
        )
    return result


def select_player_tools(
    tools: Sequence[Any],
    *,
    workflow_memory_enabled: bool,
) -> list[Any]:
    """Expose only the public player surface and fail closed if incomplete."""
    expected = (
        AWM_PLAYER_TOOL_NAMES
        if workflow_memory_enabled
        else BASE_PLAYER_TOOL_NAMES
    )
    by_name = {tool.name: tool for tool in tools}
    missing = [name for name in expected if name not in by_name]
    if missing:
        raise RuntimeError(
            "MCP missing required player tools: " + ", ".join(missing)
        )
    return [by_name[name] for name in expected]


def build_stdio_mcp_connection(
    *,
    python_bin: str,
    repo_root: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    return {
        "transport": "stdio",
        "command": python_bin,
        "args": [
            "-m",
            "ai_play.mcp_server",
            "--transport",
            "stdio",
            "--preserve-unconsumed-workflow-memory",
        ],
        "cwd": str(repo_root),
        "env": env,
    }


def build_mcp_client(
    *,
    python_bin: str,
    repo_root: Path,
    env: dict[str, str],
) -> MultiServerMCPClient:
    connection = build_stdio_mcp_connection(
        python_bin=python_bin,
        repo_root=repo_root,
        env=env,
    )
    return MultiServerMCPClient(
        {MCP_SERVER_NAME: connection},
        tool_interceptors=[append_structured_content],
        handle_tool_errors=True,
    )


async def load_player_tools(
    client: MultiServerMCPClient,
    session: Any,
    *,
    workflow_memory_enabled: bool,
) -> list[Any]:
    tools = await load_mcp_tools(
        session,
        server_name=MCP_SERVER_NAME,
        tool_interceptors=client.tool_interceptors,
        handle_tool_errors=True,
    )
    return select_player_tools(
        tools,
        workflow_memory_enabled=workflow_memory_enabled,
    )
