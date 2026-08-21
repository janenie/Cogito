from __future__ import annotations

import asyncio
import argparse
import base64
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
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
codex_media_output = False


@dataclass(frozen=True)
class ServerOptions:
    transport: Literal["stdio", "streamable-http"]
    http_host: str
    http_port: int
    codex_media_output: bool = False
    preserve_unconsumed_workflow_memory: bool = False


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
    parser.add_argument(
        "--codex-media-output",
        action="store_true",
        help=(
            "return approved JSON as text beside media so Codex preserves "
            "MCP image content"
        ),
    )
    parser.add_argument(
        "--preserve-unconsumed-workflow-memory",
        action="store_true",
        help=(
            "preserve an eligible terminal for a resumed agent that retains "
            "its public conversation checkpoint"
        ),
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
        codex_media_output=parsed.codex_media_output,
        preserve_unconsumed_workflow_memory=(
            parsed.preserve_unconsumed_workflow_memory
        ),
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
    try:
        approved_paths = _export_approved_images(
            payload,
            image_bytes,
            depth_image_bytes,
        )
    except OSError:
        return _error("image_export_failed")
    if approved_paths:
        payload = {**payload, "approved_image_paths": approved_paths}
    if codex_media_output:
        content.append(
            TextContent(
                type="text",
                text=json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )
        )
        return CallToolResult(content=content)
    return CallToolResult(
        content=content,
        structuredContent=payload,
    )


def _export_approved_images(payload, image_bytes, depth_image_bytes):
    root = getattr(config, "approved_image_root", None)
    if root is None or image_bytes is None:
        return {}
    root = Path(root).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)

    observation = payload.get("observation")
    if isinstance(observation, dict):
        observation_id = observation.get("observation_id")
        if type(observation_id) is not int or observation_id < 0:
            return {}
        stem = f"observation-{observation_id:06d}"
        paths = {"color": _write_private_image(root, stem + ".jpg", image_bytes)}
        if depth_image_bytes is not None:
            paths["depth"] = _write_private_image(
                root,
                stem + "-depth.png",
                depth_image_bytes,
            )
        return paths
    if "briefing" in payload:
        return {
            "reference": _write_private_image(
                root,
                "briefing-reference.jpg",
                image_bytes,
            )
        }
    return {}


def _write_private_image(root, filename, data):
    target = root / filename
    descriptor, temporary_name = tempfile.mkstemp(
        dir=root,
        prefix=".approved-image-",
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, target)
        os.chmod(target, 0o600)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return str(target)


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
        logged_content = result.structuredContent
        if logged_content is None and codex_media_output:
            for item in result.content:
                if not isinstance(item, TextContent):
                    continue
                candidate = json.loads(item.text)
                if isinstance(candidate, dict):
                    logged_content = candidate
                    break
        if isinstance(logged_content, dict) and "approved_image_paths" in logged_content:
            logged_content = {
                key: value
                for key, value in logged_content.items()
                if key != "approved_image_paths"
            }
        trajectory_logger.complete_tool_call(
            token,
            bool(result.isError),
            logged_content,
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
    """Execute one schema-valid batch and return the next observation.

    The actions schema has two exclusive forms: exactly one probe_interaction,
    or one to three non-probe actions. interact, enter_digits, and close_ui
    must be last and match the current interface context.
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
    global codex_media_output
    options = parse_server_options(argv)
    codex_media_output = options.codex_media_output
    config = Config.from_env()
    resume_existing = (
        config.workflow_memory_path is not None
        and config.workflow_memory_path.exists()
    )
    trajectory_logger = TrajectoryLogger(config.log_root)
    if resume_existing:
        trajectory_logger.recover_interrupted()
    workflow_memory = SessionWorkflowMemory(
        config.workflow_memory_path,
        preserve_unconsumed=(
            options.preserve_unconsumed_workflow_memory
        ),
    )
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
