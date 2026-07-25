from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, ImageContent, TextContent

from .config import HostConfig


@dataclass
class OpenAIToolResult:
    payload: dict[str, Any]
    image_messages: list[dict[str, Any]] = field(default_factory=list)


class McpGameClient:
    def __init__(self, config: HostConfig, cwd: Path | None = None) -> None:
        self.config = config
        self.cwd = cwd or Path.cwd()
        self._stdio_context = None
        self._session_context = None
        self.session: ClientSession | None = None
        self.tools: list[Any] = []

    async def connect(self) -> None:
        server = StdioServerParameters(
            command=str(self.config.mcp_command),
            cwd=self.cwd,
        )
        self._stdio_context = stdio_client(server)
        read_stream, write_stream = await self._stdio_context.__aenter__()
        self._session_context = ClientSession(read_stream, write_stream)
        self.session = await self._session_context.__aenter__()
        await self.session.initialize()
        listed = await self.session.list_tools()
        self.tools = list(listed.tools)

    async def openai_tools(self) -> list[dict[str, Any]]:
        if self.session is None:
            raise RuntimeError("MCP client is not connected")
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
                "strict": False,
            }
            for tool in self.tools
        ]

    async def call_openai_tool(self, name: str, arguments_json: str) -> OpenAIToolResult:
        if self.session is None:
            raise RuntimeError("MCP client is not connected")
        arguments = json.loads(arguments_json or "{}")
        if not isinstance(arguments, dict):
            raise ValueError("OpenAI tool arguments must decode to an object")
        result = await self.session.call_tool(name, arguments)
        return OpenAIToolResult(
            payload=result_to_payload(result),
            image_messages=result_to_image_messages(name, result),
        )

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None):
        if self.session is None:
            raise RuntimeError("MCP client is not connected")
        return await self.session.call_tool(name, arguments or {})

    async def stop(self) -> None:
        if self.session is not None:
            try:
                await self.session.call_tool("stop", {})
            except Exception:
                pass
        if self._session_context is not None:
            await self._session_context.__aexit__(None, None, None)
            self._session_context = None
            self.session = None
        if self._stdio_context is not None:
            await self._stdio_context.__aexit__(None, None, None)
            self._stdio_context = None


def result_to_payload(result: CallToolResult) -> dict[str, Any]:
    text_parts = [
        item.text for item in result.content if isinstance(item, TextContent)
    ]
    structured = result.structuredContent
    if isinstance(structured, dict):
        payload = dict(structured)
    else:
        payload = {"structured_content": structured}
    payload["is_error"] = bool(result.isError)
    if text_parts:
        payload["text"] = text_parts
    return payload


def result_to_image_messages(tool_name: str, result: CallToolResult) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    for item in result.content:
        if not isinstance(item, ImageContent):
            continue
        if not content:
            content.append({
                "type": "input_text",
                "text": f"Images returned by MCP tool {tool_name}:",
            })
        content.append({
            "type": "input_image",
            "image_url": f"data:{item.mimeType};base64,{item.data}",
            "detail": "high",
        })
    if not content:
        return []
    return [{"role": "user", "content": content}]
