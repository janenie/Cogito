from types import SimpleNamespace

import pytest
from mcp.types import CallToolResult, ImageContent

from tutorial.ai_play_api_host import (
    PLAYER_TOOL_NAMES,
    openai_tools,
    require_player_tool_name,
    result_output,
    select_player_tools,
)


def _tool(name: str):
    return SimpleNamespace(
        name=name,
        description=f"{name} description",
        inputSchema={
            "type": "object",
            "title": f"{name}Arguments",
            "properties": {},
        },
    )


def test_select_player_tools_excludes_workflow_memory_tools():
    tools = [
        _tool("workflow_memory_update"),
        _tool("act"),
        _tool("briefing"),
        _tool("stop"),
        _tool("observe"),
        _tool("workflow_memory_read"),
    ]

    selected = select_player_tools(tools)

    assert tuple(tool.name for tool in selected) == PLAYER_TOOL_NAMES


def test_select_player_tools_requires_the_complete_player_surface():
    with pytest.raises(RuntimeError, match="observe"):
        select_player_tools([_tool("briefing"), _tool("act"), _tool("stop")])


def test_openai_tools_enable_strict_mode_and_normalize_nested_objects():
    tool = _tool("act")
    tool.inputSchema = {
        "type": "object",
        "title": "actArguments",
        "properties": {
            "action": {
                "anyOf": [{
                    "type": "object",
                    "title": "MoveAction",
                    "properties": {
                        "type": {
                            "type": "string",
                            "const": "move",
                            "title": "Type",
                        },
                    },
                    "required": ["type"],
                }],
            },
        },
        "required": ["action"],
    }

    converted = openai_tools([tool])[0]

    assert converted["strict"] is True
    parameters = converted["parameters"]
    assert "title" not in parameters
    assert parameters["additionalProperties"] is False
    assert parameters["required"] == ["action"]
    nested = parameters["properties"]["action"]["anyOf"][0]
    assert nested["additionalProperties"] is False
    assert nested["properties"]["type"] == {
        "type": "string",
        "enum": ["move"],
    }


def test_result_output_attaches_images_to_function_call_output():
    result = CallToolResult(
        structuredContent={"status": "ready"},
        content=[
            ImageContent(
                type="image",
                data="ZmFrZS1qcGVn",
                mimeType="image/jpeg",
            ),
            ImageContent(
                type="image",
                data="ZmFrZS1wbmc=",
                mimeType="image/png",
            ),
        ],
    )

    output = result_output(result)

    assert isinstance(output, list)
    assert output[0]["type"] == "input_text"
    assert '"status":"ready"' in output[0]["text"]
    assert [item["type"] for item in output[1:]] == [
        "input_image",
        "input_image",
    ]
    assert all(item["detail"] == "high" for item in output[1:])


def test_player_tool_name_allowlist_fails_closed():
    assert require_player_tool_name("act") == "act"
    with pytest.raises(ValueError, match="not available"):
        require_player_tool_name("workflow_memory_read")
