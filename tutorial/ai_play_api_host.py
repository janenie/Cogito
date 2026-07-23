#!/usr/bin/env python3
"""Minimal local MCP host that lets an OpenAI API model play Cogito."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import suppress
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, ImageContent, TextContent
from openai import AsyncOpenAI


REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_COMMAND = REPO_ROOT / "ai_play" / "start_ai.sh"
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6")
MAX_AGENT_TURNS = int(os.environ.get("AI_PLAY_MAX_AGENT_TURNS", "200"))

AGENT_INSTRUCTIONS = """
你正在通过 Cogito AI Play 工具玩一个第一人称解谜游戏。

严格遵守以下循环：
1. 首先只调用一次 briefing，阅读公开背景、目标、规则和物体参考图。
2. 然后调用 observe。
3. 只有工具返回 status=ready 时才规划动作。
4. 每次只调用一个工具；使用最新 observation_id 调用 act。
5. 每次 act 返回后，根据新截图和公开状态重新规划，不得猜测 observation_id。
6. 只能依据 briefing、游戏截图、公开玩家状态、界面状态和动作结果决策。
7. 不得使用仓库源码、节点路径、测试、规格、game_script、code_read 或隐藏答案。
8. 密码证据不足时继续探索，不能盲猜。
9. 收到 game_over、stopped 或 disconnected 后停止调用游戏工具并简短总结结果。
10. 无法安全继续时调用 stop。

不要向用户询问下一步。请自主游玩，直到成功、失败、断开或达到安全停止条件。
""".strip()


def openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    """Translate MCP tool declarations into Responses API function tools."""
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
            "strict": False,
        }
        for tool in mcp_tools
    ]


def result_text(result: CallToolResult) -> str:
    """Serialize the non-image portion of one MCP result for the model."""
    text_parts = [
        item.text for item in result.content if isinstance(item, TextContent)
    ]
    payload = {
        "is_error": bool(result.isError),
        "structured_content": result.structuredContent,
        "text": text_parts,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def result_images(
    tool_name: str,
    result: CallToolResult,
) -> list[dict[str, Any]]:
    """Turn MCP image blocks into an additional multimodal input message."""
    content: list[dict[str, Any]] = []
    for item in result.content:
        if not isinstance(item, ImageContent):
            continue
        if not content:
            content.append(
                {
                    "type": "input_text",
                    "text": f"以下图片由刚才的 {tool_name} 工具返回：",
                }
            )
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:{item.mimeType};base64,{item.data}",
                "detail": "high",
            }
        )
    if not content:
        return []
    return [{"role": "user", "content": content}]


async def run_agent(
    mcp_session: ClientSession,
    tools: list[dict[str, Any]],
) -> None:
    client = AsyncOpenAI()
    response_input: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "开始游戏，并按照规则自主完成公开任务。",
                }
            ],
        }
    ]
    previous_response_id: str | None = None

    for turn in range(1, MAX_AGENT_TURNS + 1):
        response = await client.responses.create(
            model=MODEL,
            instructions=AGENT_INSTRUCTIONS,
            input=response_input,
            previous_response_id=previous_response_id,
            tools=tools,
            parallel_tool_calls=False,
            store=True,
        )
        previous_response_id = response.id

        if response.output_text:
            print(f"\n[agent turn {turn}] {response.output_text}", flush=True)

        calls = [
            item for item in response.output if item.type == "function_call"
        ]
        if not calls:
            print("\nAgent 已结束工具调用循环。", flush=True)
            return

        response_input = []
        for call in calls:
            try:
                arguments = json.loads(call.arguments)
                if not isinstance(arguments, dict):
                    raise ValueError("tool arguments must be an object")
                print(
                    f"\n[tool] {call.name} "
                    f"{json.dumps(arguments, ensure_ascii=False)}",
                    flush=True,
                )
                result = await mcp_session.call_tool(call.name, arguments)
                output = result_text(result)
                print(f"[result] {output}", flush=True)
            except Exception as error:
                output = json.dumps(
                    {
                        "is_error": True,
                        "error": f"{type(error).__name__}: {error}",
                    },
                    ensure_ascii=False,
                )
                result = None

            response_input.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": output,
                }
            )
            if result is not None:
                response_input.extend(result_images(call.name, result))

    print(
        f"\n达到 AI_PLAY_MAX_AGENT_TURNS={MAX_AGENT_TURNS}，停止本次运行。",
        flush=True,
    )


async def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("请先设置 OPENAI_API_KEY。")
    if not MCP_COMMAND.is_file():
        raise SystemExit(f"找不到 MCP 启动脚本：{MCP_COMMAND}")

    server = StdioServerParameters(
        command=str(MCP_COMMAND),
        cwd=REPO_ROOT,
    )
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as mcp_session:
            await mcp_session.initialize()
            listed = await mcp_session.list_tools()
            names = [tool.name for tool in listed.tools]
            print(f"MCP 已连接，工具：{', '.join(names)}", flush=True)
            print(
                "\n现在请启动 Godot Lobby：\n"
                "godot --path . "
                "addons/cogito/DemoScenes/COGITO_3_Lobby.tscn "
                "-- --ai-play\n",
                flush=True,
            )
            prompt = "看到游戏窗口后按 Enter 开始 API Agent..."
            await asyncio.to_thread(input, prompt)

            try:
                await run_agent(mcp_session, openai_tools(listed.tools))
            finally:
                with suppress(Exception):
                    await mcp_session.call_tool("stop")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已中止；MCP 连接关闭并释放模拟输入。")
