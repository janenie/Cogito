import asyncio
import os
from pathlib import Path
import subprocess
import sys

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import ImageContent

from ai_play.config import Config
from ai_play.game_session import SessionError, SessionResult
from ai_play import mcp_server


class FakeReadySession:
    def __init__(self):
        self.mode = "ready"

    def observe(self, timeout):
        del timeout
        if self.mode == "terminal":
            return SessionResult(
                status="game_over",
                game_over={
                    "type": "game_over",
                    "protocol_version": 2,
                    "observation_id": 7,
                    "outcome": "success",
                    "reason": "correct_password",
                },
            )
        return SessionResult(status="ready", observation={"observation_id": 7})

    def act(self, observation_id, actions, timeout):
        del timeout
        if observation_id != 7:
            raise SessionError("stale_observation")
        if not isinstance(actions, list) or not actions:
            raise SessionError("actions must contain 1..3 entries")
        if self.mode == "terminal":
            return SessionResult(
                status="game_over",
                action_results=[{"status": "completed", "type": "wait"}],
                game_over={
                    "type": "game_over",
                    "protocol_version": 2,
                    "observation_id": 7,
                    "outcome": "success",
                    "reason": "correct_password",
                },
            )
        return SessionResult(
            status="ready",
            observation={"observation_id": 8},
            action_results=[{"status": "completed", "type": "wait"}],
        )

    def stop(self, timeout):
        del timeout
        return SessionResult(status="stopped", action_results=[])

    def to_mcp_payload(self, result):
        payload = {
            "status": result.status,
            "action_results": result.action_results or [],
            "game_over": result.game_over,
            "observation": result.observation,
        }
        image_bytes = None
        if result.observation is not None:
            payload["observation"] = {
                **result.observation,
                "image": {
                    "mime_type": "image/jpeg",
                    "width": 768,
                    "height": 432,
                },
            }
            image_bytes = b"\xff\xd8\xffmcp-image\xff\xd9"
        return payload, image_bytes


def fake_ready_session():
    return FakeReadySession()


def configure_server(monkeypatch, session=None):
    monkeypatch.setattr(mcp_server, "game_session", session or fake_ready_session())
    monkeypatch.setattr(mcp_server, "config", Config())


def test_mcp_exposes_only_game_tools():
    async def run():
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
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
    configure_server(monkeypatch)

    async def run():
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
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


@pytest.mark.parametrize(
    ("name", "arguments", "code"),
    [
        (
            "act",
            {"observation_id": 6, "actions": [{"type": "wait", "duration_ms": 50}]},
            "stale_observation",
        ),
        (
            "act",
            {"observation_id": 7, "actions": []},
            "actions must contain 1..3 entries",
        ),
    ],
)
def test_mcp_returns_tool_errors_without_raising(monkeypatch, name, arguments, code):
    configure_server(monkeypatch)

    async def run():
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
            raise_exceptions=True,
        ) as client:
            result = await client.call_tool(name, arguments)
            assert result.isError is True
            assert result.structuredContent == {
                "status": "error",
                "code": code,
            }

    asyncio.run(run())


def test_act_returns_synchronous_action_results_and_next_image(monkeypatch):
    configure_server(monkeypatch)

    async def run():
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
            raise_exceptions=True,
        ) as client:
            result = await client.call_tool("act", {
                "observation_id": 7,
                "actions": [{"type": "wait", "duration_ms": 50}],
            })
            assert result.structuredContent["status"] == "ready"
            assert result.structuredContent["action_results"] == [
                {"status": "completed", "type": "wait"},
            ]
            assert any(isinstance(item, ImageContent) for item in result.content)

    asyncio.run(run())


def test_stop_returns_stopped_structured_result_without_image(monkeypatch):
    configure_server(monkeypatch)

    async def run():
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
            raise_exceptions=True,
        ) as client:
            result = await client.call_tool("stop", {})
            assert result.structuredContent == {
                "status": "stopped",
                "action_results": [],
                "game_over": None,
                "observation": None,
            }
            assert result.content == []

    asyncio.run(run())


def test_terminal_observe_returns_terminal_state_without_new_observation(monkeypatch):
    session = fake_ready_session()
    session.mode = "terminal"
    configure_server(monkeypatch, session)

    async def run():
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
            raise_exceptions=True,
        ) as client:
            result = await client.call_tool("observe", {})
            assert result.structuredContent["status"] == "game_over"
            assert result.structuredContent["observation"] is None
            assert result.structuredContent["game_over"]["reason"] == "correct_password"

    asyncio.run(run())


def test_module_reports_invalid_loopback_config_on_stderr_only():
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path("ai_play/src").resolve())
    environment["AI_PLAY_WS_HOST"] = "localhost"
    result = subprocess.run(
        [sys.executable, "-m", "ai_play.mcp_server"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "AI_PLAY_WS_HOST" in result.stderr
