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
from ai_play.trajectory_logger import LogPersistenceError, ToolCallToken
from ai_play import mcp_server


class FakeReadySession:
    def __init__(
        self,
        scenario_id="find_contract",
        terminal_reason="correct_password",
    ):
        self.mode = "ready"
        self.scenario_id = scenario_id
        self.terminal_reason = terminal_reason
        self.act_calls = []

    def observe(self, timeout):
        del timeout
        if self.mode == "terminal":
            return SessionResult(
                status="game_over",
                game_over={
                    "type": "game_over",
                    "protocol_version": 3,
                    "observation_id": 7,
                    "outcome": "success",
                    "reason": self.terminal_reason,
                },
            )
        return SessionResult(status="ready", observation={"observation_id": 7})

    def wait_for_scenario(self, timeout):
        del timeout
        return self.scenario_id

    def act(self, observation_id, actions, timeout):
        del timeout
        self.act_calls.append((observation_id, actions))
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
                    "protocol_version": 3,
                    "observation_id": 7,
                    "outcome": "success",
                    "reason": self.terminal_reason,
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


class RecordingTrajectoryLogger:
    def __init__(self, fail_begin=False, fail_complete=False):
        self.fail_begin = fail_begin
        self.fail_complete = fail_complete
        self.begun = []
        self.completed = []

    def begin_tool_call(self, tool, request):
        if self.fail_begin:
            raise LogPersistenceError("logging_failed")
        token = ToolCallToken(1, 1, len(self.begun) + 1)
        self.begun.append((tool, request))
        return token

    def complete_tool_call(
        self,
        token,
        is_error,
        structured_content,
        image_bytes=None,
    ):
        if self.fail_complete:
            raise LogPersistenceError("logging_failed")
        self.completed.append(
            (token, is_error, structured_content, image_bytes)
        )


def configure_server(monkeypatch, session=None, logger=None):
    monkeypatch.setattr(mcp_server, "game_session", session or fake_ready_session())
    monkeypatch.setattr(mcp_server, "config", Config())
    monkeypatch.setattr(
        mcp_server,
        "trajectory_logger",
        logger or RecordingTrajectoryLogger(),
        raising=False,
    )


def call_tool(name, arguments):
    async def run():
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
            raise_exceptions=True,
        ) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(run())


def test_mcp_exposes_only_game_tools():
    async def run():
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
            raise_exceptions=True,
        ) as client:
            tools = await client.list_tools()
            assert [tool.name for tool in tools.tools] == [
                "briefing",
                "observe",
                "act",
                "stop",
            ]

    asyncio.run(run())


def test_briefing_contains_public_context_and_reference_image(monkeypatch):
    configure_server(monkeypatch)

    async def run():
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
            raise_exceptions=True,
        ) as client:
            result = await client.call_tool("briefing", {})
            assert result.structuredContent["status"] == "ready"
            briefing = result.structuredContent["briefing"]
            assert briefing["game_id"] == "find_contract"
            assert "ARCHIVE" in briefing["objective"]
            assert {item["id"] for item in briefing["objects"]} == {
                "clue_hint",
                "carryable_cup",
                "operable_door",
                "pickup_key",
                "elevator_button",
                "keypad",
                "archive_goal_door",
                "operable_drawer",
                "readable_notebook",
                "readable_document",
                "friendly_npc",
            }
            serialized = str(briefing)
            assert "system_name" not in serialized
            assert "ArchiveDoor/FrontDoor" not in serialized
            assert "黄色" not in serialized
            assert "1000" not in serialized
            assert any(isinstance(item, ImageContent) for item in result.content)

    asyncio.run(run())


def test_find_key_briefing_and_terminal_state_use_selected_scenario(monkeypatch):
    session = FakeReadySession(
        scenario_id="find_key",
        terminal_reason="key_picked_up",
    )
    session.mode = "terminal"
    configure_server(monkeypatch, session)

    async def run():
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
            raise_exceptions=True,
        ) as client:
            briefing_result = await client.call_tool("briefing", {})
            briefing = briefing_result.structuredContent["briefing"]
            assert briefing["game_id"] == "find_key"
            serialized = str(briefing)
            assert "DesktopDeskAnchor" not in serialized
            assert "round_seed" not in serialized
            assert any(
                isinstance(item, ImageContent)
                for item in briefing_result.content
            )

            observe_result = await client.call_tool("observe", {})
            assert observe_result.structuredContent["status"] == "game_over"
            assert observe_result.structuredContent["game_over"] == {
                "type": "game_over",
                "protocol_version": 3,
                "observation_id": 7,
                "outcome": "success",
                "reason": "key_picked_up",
            }

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


def test_observe_logs_request_result_and_exact_image(monkeypatch):
    logger = RecordingTrajectoryLogger()
    configure_server(monkeypatch, logger=logger)

    result = call_tool("observe", {})

    assert logger.begun == [("observe", {})]
    assert logger.completed[0][1] is False
    assert logger.completed[0][2] == result.structuredContent
    assert logger.completed[0][3] == b"\xff\xd8\xffmcp-image\xff\xd9"


def test_act_error_is_logged(monkeypatch):
    logger = RecordingTrajectoryLogger()
    configure_server(monkeypatch, logger=logger)
    arguments = {
        "observation_id": 6,
        "actions": [{"type": "wait", "duration_ms": 50}],
    }

    result = call_tool("act", arguments)

    assert logger.begun == [("act", arguments)]
    assert logger.completed[0][1] is True
    assert logger.completed[0][2] == {
        "status": "error",
        "code": "stale_observation",
    }
    assert result.isError is True


def test_stop_is_logged_without_image(monkeypatch):
    logger = RecordingTrajectoryLogger()
    configure_server(monkeypatch, logger=logger)

    call_tool("stop", {})

    assert logger.begun == [("stop", {})]
    assert logger.completed[0][3] is None


def test_briefing_is_not_logged(monkeypatch):
    logger = RecordingTrajectoryLogger()
    configure_server(monkeypatch, logger=logger)

    call_tool("briefing", {})

    assert logger.begun == []
    assert logger.completed == []


def test_logging_begin_failure_prevents_session_call(monkeypatch):
    session = fake_ready_session()
    logger = RecordingTrajectoryLogger(fail_begin=True)
    configure_server(monkeypatch, session=session, logger=logger)

    result = call_tool("act", {
        "observation_id": 7,
        "actions": [{"type": "wait", "duration_ms": 50}],
    })

    assert result.structuredContent == {
        "status": "error",
        "code": "logging_failed",
    }
    assert session.act_calls == []


def test_logging_completion_failure_returns_stable_error(monkeypatch):
    logger = RecordingTrajectoryLogger(fail_complete=True)
    configure_server(monkeypatch, logger=logger)

    result = call_tool("observe", {})

    assert result.structuredContent == {
        "status": "error",
        "code": "logging_failed",
    }


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
