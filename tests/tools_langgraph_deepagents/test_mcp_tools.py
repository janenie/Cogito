import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage
from langchain_mcp_adapters.tools import convert_mcp_tool_to_langchain_tool
from mcp.types import CallToolResult, ImageContent, Tool

from tools_langgraph_deepagents.mcp_tools import (
    append_structured_content,
    build_stdio_mcp_connection,
    select_player_tools,
)


def test_selects_only_awm_game_tools():
    tools = [
        SimpleNamespace(name=name)
        for name in (
            "stop",
            "act",
            "workflow_memory_update",
            "briefing",
            "observe",
            "workflow_memory_read",
        )
    ]

    selected = select_player_tools(tools, workflow_memory_enabled=True)

    assert [tool.name for tool in selected] == [
        "briefing",
        "workflow_memory_read",
        "observe",
        "act",
        "workflow_memory_update",
    ]


def test_rejects_an_incomplete_tool_surface():
    with pytest.raises(RuntimeError, match="observe"):
        select_player_tools(
            [SimpleNamespace(name="briefing")],
            workflow_memory_enabled=False,
        )


def test_stdio_connection_is_direct_and_has_no_codex_layer():
    connection = build_stdio_mcp_connection(
        python_bin="/python",
        repo_root=Path("/repo"),
        env={"SAFE": "1"},
    )

    assert connection == {
        "transport": "stdio",
        "command": "/python",
        "args": [
            "-m",
            "ai_play.mcp_server",
            "--transport",
            "stdio",
            "--preserve-unconsumed-workflow-memory",
        ],
        "cwd": "/repo",
        "env": {"SAFE": "1"},
    }
    assert "codex" not in json.dumps(connection).lower()


@pytest.mark.asyncio
async def test_interceptor_appends_public_json_without_dropping_images():
    result = CallToolResult(
        structuredContent={
            "status": "ready",
            "observation": {"observation_id": 7},
        },
        content=[
            ImageContent(
                type="image",
                data="ZmFrZQ==",
                mimeType="image/jpeg",
            )
        ],
    )

    async def handler(_request):
        return result

    converted = await append_structured_content(
        SimpleNamespace(),
        handler,
    )

    assert isinstance(converted.content[0], ImageContent)
    assert json.loads(converted.content[-1].text)["status"] == "ready"


@pytest.mark.asyncio
async def test_adapter_keeps_mcp_image_for_the_next_model_turn():
    class Session:
        async def call_tool(
            self,
            _name,
            _args,
            progress_callback=None,
        ):
            return CallToolResult(
                structuredContent={"status": "ready"},
                content=[
                    ImageContent(
                        type="image",
                        data="ZmFrZQ==",
                        mimeType="image/jpeg",
                    )
                ],
            )

    converted = convert_mcp_tool_to_langchain_tool(
        Session(),
        Tool(
            name="observe",
            description="observe",
            inputSchema={"type": "object", "properties": {}},
        ),
        tool_interceptors=[append_structured_content],
    )
    message = await converted.ainvoke(
        {
            "type": "tool_call",
            "name": "observe",
            "args": {},
            "id": "call-1",
        }
    )

    assert isinstance(message, ToolMessage)
    assert message.content[0]["type"] == "image"
    assert message.content[0]["base64"] == "ZmFrZQ=="
    assert message.content[0]["mime_type"] == "image/jpeg"
    assert json.loads(message.content[1]["text"])["status"] == "ready"
