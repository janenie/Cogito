from __future__ import annotations

import asyncio
import argparse
import base64
import sys
from dataclasses import dataclass
from typing import Literal, Sequence

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, ImageContent, TextContent

from .bridge_server import start
from .config import Config
from .game_session import GameSession, SessionError
from .mcp_tool_schema import (
    ActionBatchInput,
    AvoidInput,
    FailureReviewInput,
    LandmarksInput,
    ObservationIdInput,
    PublicText,
    WorkflowInput,
)
from .scenarios import load_scenario_briefing
from .trajectory_logger import (
    LogPersistenceError,
    TrajectoryLogger,
)
from .workflow_memory import SessionWorkflowMemory, WorkflowMemoryError


mcp = FastMCP("Cogito AI Play", json_response=True)
game_session = None
config = None
trajectory_logger = None
workflow_memory = None


@dataclass(frozen=True)
class ServerOptions:
    transport: Literal["stdio", "streamable-http"]
    http_host: str
    http_port: int


def _parse_http_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "MCP HTTP port must be an integer"
        ) from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(
            "MCP HTTP port must be between 1 and 65535"
        )
    return port


def parse_server_options(argv: Sequence[str] | None = None) -> ServerOptions:
    parser = argparse.ArgumentParser(
        description="Run the Cogito AI Play MCP server."
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
    )
    parser.add_argument("--http-host", default="127.0.0.1")
    parser.add_argument(
        "--http-port",
        type=_parse_http_port,
        default=8766,
    )
    parsed = parser.parse_args(argv)
    if (
        parsed.transport == "streamable-http"
        and parsed.http_host != "127.0.0.1"
    ):
        raise ValueError("MCP HTTP host must be 127.0.0.1")
    return ServerOptions(
        transport=parsed.transport,
        http_host=parsed.http_host,
        http_port=parsed.http_port,
    )


def configure_transport(options: ServerOptions) -> str:
    if options.transport == "streamable-http":
        mcp.settings.host = options.http_host
        mcp.settings.port = options.http_port
    return options.transport


def _result(payload, image_bytes=None, depth_image_bytes=None):
    content = []
    if image_bytes is not None:
        content.append(ImageContent(
            type="image",
            data=base64.b64encode(image_bytes).decode("ascii"),
            mimeType="image/jpeg",
        ))
    if depth_image_bytes is not None:
        content.append(ImageContent(
            type="image",
            data=base64.b64encode(depth_image_bytes).decode("ascii"),
            mimeType="image/png",
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
    return (
        game_session is not None
        and config is not None
        and trajectory_logger is not None
    )


def _begin_logged_call(tool, request):
    try:
        return trajectory_logger.begin_tool_call(tool, request), None
    except LogPersistenceError:
        return None, _error("logging_failed")


def _complete_logged_call(token, result, image_bytes=None):
    try:
        trajectory_logger.complete_tool_call(
            token,
            bool(result.isError),
            result.structuredContent,
            image_bytes,
        )
    except LogPersistenceError:
        return _error("logging_failed")
    return result


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
    """Read the latest approved observation and local-navigation images.

    Use once after briefing; each successful act already returns the next
    observation. The first image is the colour JPEG screenshot. When present,
    the second image is a depth PNG where darker pixels are nearer and white is
    20 metres or unavailable depth.
    """
    if not _configured():
        return _error("server_not_ready")
    token, log_error = _begin_logged_call("observe", {})
    if log_error is not None:
        return log_error
    try:
        result = await asyncio.to_thread(
            game_session.observe,
            config.wait_timeout_seconds,
        )
    except SessionError as error:
        return _complete_logged_call(token, _error(str(error)))
    payload, image_bytes, depth_image_bytes = game_session.to_mcp_payload(result)
    return _complete_logged_call(
        token,
        _result(payload, image_bytes, depth_image_bytes),
        image_bytes,
    )


@mcp.tool()
async def act(
    observation_id: ObservationIdInput,
    actions: ActionBatchInput,
) -> CallToolResult:
    """Execute one typed batch and return the next observation.

    probe_interaction must be alone. interact, enter_digits, and close_ui must
    be last and match the current interface context.
    """
    if not _configured():
        return _error("server_not_ready")
    request = {
        "observation_id": observation_id,
        "actions": actions,
    }
    token, log_error = _begin_logged_call("act", request)
    if log_error is not None:
        return log_error
    try:
        result = await asyncio.to_thread(
            game_session.act,
            observation_id,
            actions,
            config.wait_timeout_seconds,
        )
    except SessionError as error:
        return _complete_logged_call(token, _error(str(error)))
    payload, image_bytes, depth_image_bytes = game_session.to_mcp_payload(result)
    return _complete_logged_call(
        token,
        _result(payload, image_bytes, depth_image_bytes),
        image_bytes,
    )


@mcp.tool()
async def stop() -> CallToolResult:
    """Stop AI control and release all simulated inputs."""
    if not _configured():
        return _error("server_not_ready")
    token, log_error = _begin_logged_call("stop", {})
    if log_error is not None:
        return log_error
    try:
        result = await asyncio.to_thread(
            game_session.stop,
            config.stop_timeout_seconds,
        )
    except SessionError as error:
        return _complete_logged_call(token, _error(str(error)))
    payload, _, _ = game_session.to_mcp_payload(result)
    return _complete_logged_call(token, _result(payload))


@mcp.tool()
async def workflow_memory_read() -> CallToolResult:
    """Read validated workflows learned in this orchestrator session."""
    if not _configured() or workflow_memory is None:
        return _error("server_not_ready")
    try:
        scenario_id = await asyncio.to_thread(
            game_session.wait_for_scenario,
            config.wait_timeout_seconds,
        )
        payload = workflow_memory.read(scenario_id)
    except SessionError as error:
        return _error(str(error))
    except WorkflowMemoryError as error:
        return _error(error.code)
    return _result(payload)


@mcp.tool()
async def workflow_memory_update(
    goal_pattern: PublicText,
    workflow: WorkflowInput,
    landmarks: LandmarksInput,
    avoid: AvoidInput,
    failure_review: FailureReviewInput | None = None,
) -> CallToolResult:
    """Promote a validated workflow candidate after a trusted terminal result."""
    if not _configured() or workflow_memory is None:
        return _error("server_not_ready")
    candidate = {
        "goal_pattern": goal_pattern,
        "workflow": workflow,
        "landmarks": landmarks,
        "avoid": avoid,
        "failure_review": (
            failure_review.model_dump()
            if failure_review is not None
            else None
        ),
    }
    try:
        return _result(workflow_memory.update(candidate))
    except WorkflowMemoryError as error:
        return _error(error.code)


def main(argv: Sequence[str] | None = None) -> None:
    global config, game_session, trajectory_logger, workflow_memory
    options = parse_server_options(argv)
    config = Config.from_env()
    trajectory_logger = TrajectoryLogger(config.log_root)
    workflow_memory = SessionWorkflowMemory()
    game_session = GameSession(
        config,
        trajectory_logger=trajectory_logger,
        attempt_observer=workflow_memory,
    )
    bridge = start(config, game_session)
    try:
        mcp.run(transport=configure_transport(options))
    finally:
        bridge.close()
        game_session.detach("mcp_shutdown")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
