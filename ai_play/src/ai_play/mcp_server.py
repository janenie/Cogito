from __future__ import annotations

import asyncio
import base64
import sys

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, ImageContent, TextContent

from .bridge_server import start
from .config import Config
from .game_session import GameSession, SessionError
from .scenarios import load_scenario_briefing


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


def _configured():
    return game_session is not None and config is not None


@mcp.tool()
async def briefing() -> CallToolResult:
    """Read the public game objective, rules, object guide, and reference atlas."""
    if not _configured():
        return _error("server_not_ready")
    try:
        scenario_id = await asyncio.to_thread(
            game_session.wait_for_scenario,
            config.wait_timeout_seconds,
        )
        public_briefing, image_bytes = load_scenario_briefing(scenario_id)
    except SessionError as error:
        return _error(str(error))
    except RuntimeError as error:
        return _error(str(error))
    return _result(
        {
            "status": "ready",
            "briefing": public_briefing,
        },
        image_bytes,
    )


@mcp.tool()
async def observe() -> CallToolResult:
    """Read the latest approved game observation and screenshot."""
    if not _configured():
        return _error("server_not_ready")
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
    if not _configured():
        return _error("server_not_ready")
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
    if not _configured():
        return _error("server_not_ready")
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
