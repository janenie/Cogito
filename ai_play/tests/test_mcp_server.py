import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import ImageContent, TextContent

from ai_play.common_briefing_rules import COMMON_CONTROL_RULES
from ai_play.config import Config
from ai_play.game_session import SessionError, SessionResult
from ai_play.trajectory_logger import LogPersistenceError, ToolCallToken
from ai_play.workflow_memory import SessionWorkflowMemory
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
                    "protocol_version": 4,
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
                    "protocol_version": 4,
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
        depth_image_bytes = None
        if result.observation is not None:
            payload["observation"] = {
                **result.observation,
                "image": {
                    "mime_type": "image/jpeg",
                    "width": 1024,
                    "height": 576,
                },
                "depth_image": {
                    "mime_type": "image/png",
                    "width": 1024,
                    "height": 576,
                    "encoding": "linear_depth_normalized_8bit",
                    "near_meters": 0.05,
                    "far_meters": 20.0,
                },
            }
            image_bytes = b"\xff\xd8\xffmcp-image\xff\xd9"
            depth_image_bytes = b"\x89PNG\r\n\x1a\nmcp-depthIEND\xaeB`\x82"
        return payload, image_bytes, depth_image_bytes


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


def configure_server(
    monkeypatch,
    session=None,
    logger=None,
    memory=None,
):
    monkeypatch.setattr(mcp_server, "game_session", session or fake_ready_session())
    monkeypatch.setattr(mcp_server, "config", Config())
    monkeypatch.setattr(
        mcp_server,
        "trajectory_logger",
        logger or RecordingTrajectoryLogger(),
        raising=False,
    )
    monkeypatch.setattr(
        mcp_server,
        "workflow_memory",
        memory or SessionWorkflowMemory(),
        raising=False,
    )


def valid_workflow_candidate():
    return {
        "goal_pattern": "依据公开线索逐步完成当前任务",
        "workflow": [{
            "step": "先确认任务入口物",
            "precondition": "尚未获得第一条公开任务线索",
            "success_signal": "观察中出现下一阶段目标",
        }],
        "landmarks": [{"relation": "先建立出生区域与主要地标的相对方向"}],
        "avoid": ["没有交互提示时不要重复 interact"],
        "failure_review": None,
    }


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
                "workflow_memory_read",
                "workflow_memory_update",
            ]
            update_tool = next(
                tool for tool in tools.tools
                if tool.name == "workflow_memory_update"
            )
            assert "failure_review" in update_tool.inputSchema["properties"]
            assert "failure_review" not in update_tool.inputSchema.get("required", [])
            review = update_tool.inputSchema["$defs"]["FailureReviewInput"]
            assert review["additionalProperties"] is False
            assert review["properties"]["stage"]["maxLength"] == 240
            assert review["properties"]["bottlenecks"]["minItems"] == 1
            assert review["properties"]["bottlenecks"]["maxItems"] == 3
            assert review["properties"]["optimizations"]["minItems"] == 1
            assert review["properties"]["optimizations"]["maxItems"] == 4

    asyncio.run(run())


def test_act_tool_schema_declares_each_action_shape_and_bounds():
    async def run():
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
            raise_exceptions=True,
        ) as client:
            tools = await client.list_tools()
            act_tool = next(tool for tool in tools.tools if tool.name == "act")
            schema = act_tool.inputSchema
            actions = schema["properties"]["actions"]
            assert len(actions["anyOf"]) == 2
            probe_batch = next(
                branch
                for branch in actions["anyOf"]
                if branch["maxItems"] == 1
            )
            regular_batch = next(
                branch
                for branch in actions["anyOf"]
                if branch["maxItems"] == 3
            )
            assert probe_batch["minItems"] == 1
            assert probe_batch["items"] == {
                "$ref": "#/$defs/ProbeInteractionAction",
            }
            assert "Exactly one probe_interaction" in probe_batch["description"]
            assert regular_batch["minItems"] == 1
            assert "non-probe" in regular_batch["description"]
            references = regular_batch["items"]["anyOf"]
            definitions = schema["$defs"]
            action_types = {
                definitions[item["$ref"].rsplit("/", 1)[-1]][
                    "properties"
                ]["type"]["const"]
                for item in references
            }
            assert action_types == {
                "look",
                "move",
                "sprint",
                "jump",
                "crouch",
                "interact",
                "enter_digits",
                "close_ui",
                "wait",
                "select_ingredient",
                "make",
                "wait_next_window",
                "front",
                "back",
                "left",
                "right",
                "floor_up",
                "floor_down",
                "toggle_board",
                "board_up",
                "board_down",
                "toggle_mark",
                "submit_floor",
            }
            probe = definitions["ProbeInteractionAction"]
            assert probe["properties"]["type"]["const"] == "probe_interaction"
            assert probe["properties"]["target_x"]["minimum"] == 0
            assert probe["properties"]["target_x"]["maximum"] == 1
            look = definitions["LookAction"]
            assert set(look["properties"]) == {"type", "yaw", "pitch"}
            assert look["properties"]["yaw"]["minimum"] == -45
            assert look["properties"]["yaw"]["maximum"] == 45
            move = definitions["MoveAction"]
            assert move["additionalProperties"] is False
            assert move["properties"]["forward"]["minimum"] == -1
            assert move["properties"]["forward"]["maximum"] == 1
            assert move["properties"]["duration_ms"]["minimum"] == 50
            assert move["properties"]["duration_ms"]["maximum"] == 250
            front = definitions["FrontAction"]
            assert set(front["properties"]["step"]["enum"]) == {"small", "large"}
            select_ingredient = definitions["SelectIngredientAction"]
            assert set(select_ingredient["properties"]["ingredient"]["enum"]) == {
                "lettuce", "tomato", "carrot", "avocado", "sausage", "mushroom",
                "onion", "pumpkin", "bread", "meat", "egg", "cheese", "bacon",
                "broccoli", "corn", "fish",
            }

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
            scenario_rules = [
                rule
                for rule in briefing["rules"]
                if rule not in COMMON_CONTROL_RULES
            ]
            assert "1000" not in str({
                **briefing,
                "rules": scenario_rules,
            })
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
            for forbidden in [
                "POLARIS", "ATLAS", "ORBIT", "NOVA", "round_seed",
                "security_lockout", "0937", "ArchiveKey",
                "ai_play_find_key_round.gd", "--ai-play-round-seed",
            ]:
                assert forbidden not in serialized
            assert any(
                isinstance(item, ImageContent)
                for item in briefing_result.content
            )

            observe_result = await client.call_tool("observe", {})
            assert observe_result.structuredContent["status"] == "game_over"
            assert observe_result.structuredContent["game_over"] == {
                "type": "game_over",
                "protocol_version": 4,
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
                "width": 1024,
                "height": 576,
            }
            assert result.structuredContent["observation"]["depth_image"] == {
                "mime_type": "image/png",
                "width": 1024,
                "height": 576,
                "encoding": "linear_depth_normalized_8bit",
                "near_meters": 0.05,
                "far_meters": 20.0,
            }
            images = [item for item in result.content if isinstance(item, ImageContent)]
            assert [item.mimeType for item in images] == ["image/jpeg", "image/png"]

    asyncio.run(run())


def test_codex_media_output_preserves_images_and_moves_payload_to_text(monkeypatch):
    logger = RecordingTrajectoryLogger()
    configure_server(monkeypatch, logger=logger)
    monkeypatch.setattr(mcp_server, "codex_media_output", True)

    result = call_tool("observe", {})

    assert result.structuredContent is None
    images = [item for item in result.content if isinstance(item, ImageContent)]
    assert [item.mimeType for item in images] == ["image/jpeg", "image/png"]
    text_items = [item for item in result.content if isinstance(item, TextContent)]
    assert len(text_items) == 1
    payload = json.loads(text_items[0].text)
    assert payload["observation"]["observation_id"] == 7
    assert result.isError is False
    assert logger.completed[0][2] == payload
    assert logger.completed[0][3] == b"\xff\xd8\xffmcp-image\xff\xd9"


def test_observe_exports_only_approved_images_for_restricted_read(
    monkeypatch,
    tmp_path,
):
    logger = RecordingTrajectoryLogger()
    configure_server(monkeypatch, logger=logger)
    image_root = tmp_path / "approved-images"
    monkeypatch.setattr(
        mcp_server,
        "config",
        Config(approved_image_root=image_root),
    )

    result = call_tool("observe", {})

    paths = result.structuredContent["approved_image_paths"]
    assert paths == {
        "color": str(image_root / "observation-000007.jpg"),
        "depth": str(image_root / "observation-000007-depth.png"),
    }
    assert (image_root.stat().st_mode & 0o777) == 0o700
    color_path = Path(paths["color"])
    depth_path = Path(paths["depth"])
    assert color_path.read_bytes() == b"\xff\xd8\xffmcp-image\xff\xd9"
    assert depth_path.read_bytes() == b"\x89PNG\r\n\x1a\nmcp-depthIEND\xaeB`\x82"
    assert (color_path.stat().st_mode & 0o777) == 0o600
    assert (depth_path.stat().st_mode & 0o777) == 0o600
    assert "approved_image_paths" not in logger.completed[0][2]


def test_briefing_exports_approved_reference_image(monkeypatch, tmp_path):
    configure_server(monkeypatch)
    image_root = tmp_path / "approved-images"
    monkeypatch.setattr(
        mcp_server,
        "config",
        Config(approved_image_root=image_root),
    )

    result = call_tool("briefing", {})

    path = Path(result.structuredContent["approved_image_paths"]["reference"])
    assert path == image_root / "briefing-reference.jpg"
    assert path.is_file()


def test_observe_tool_description_explains_screenshot_and_depth_images(monkeypatch):
    configure_server(monkeypatch)

    async def run():
        async with create_connected_server_and_client_session(
            mcp_server.mcp,
            raise_exceptions=True,
        ) as client:
            tools = await client.list_tools()
            observe_tool = next(tool for tool in tools.tools if tool.name == "observe")
            assert "first image" in observe_tool.description
            assert "JPEG" in observe_tool.description
            assert "When present" in observe_tool.description
            assert "second image" in observe_tool.description
            assert "PNG" in observe_tool.description
            assert "darker" in observe_tool.description
            assert "white" in observe_tool.description

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


def test_workflow_memory_read_returns_current_session_snapshot(monkeypatch):
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    configure_server(monkeypatch, memory=memory)

    result = call_tool("workflow_memory_read", {})

    assert result.structuredContent == {
        "status": "ready",
        "scope": "current_orchestrator_session",
        "scenario": "find_contract",
        "version": 0,
        "completed_runs": 0,
        "memory": None,
    }


@pytest.mark.parametrize(
    ("outcome", "accepted"),
    [
        (
            "success",
            {
                "workflow": 1,
                "landmarks": 1,
                "avoid": 1,
                "failure_reviews": 0,
            },
        ),
        (
            "failure",
            {
                "workflow": 0,
                "landmarks": 0,
                "avoid": 1,
                "failure_reviews": 0,
            },
        ),
    ],
)
def test_workflow_memory_update_uses_trusted_attempt_outcome(
    monkeypatch,
    outcome,
    accepted,
):
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt(outcome, "terminal_reason")
    configure_server(monkeypatch, memory=memory)

    result = call_tool(
        "workflow_memory_update",
        valid_workflow_candidate(),
    )

    assert result.structuredContent == {
        "status": "updated",
        "version": 1,
        "accepted": accepted,
    }


def test_workflow_memory_tools_are_not_logged(monkeypatch):
    logger = RecordingTrajectoryLogger()
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    configure_server(monkeypatch, logger=logger, memory=memory)

    call_tool("workflow_memory_read", {})
    memory.finish_attempt("success", "correct_password")
    call_tool("workflow_memory_update", valid_workflow_candidate())

    assert logger.begun == []
    assert logger.completed == []


def test_workflow_memory_update_accepts_old_call_without_failure_review(monkeypatch):
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("failure", "max_requests")
    configure_server(monkeypatch, memory=memory)
    candidate = valid_workflow_candidate()
    candidate.pop("failure_review")

    result = call_tool("workflow_memory_update", candidate)

    assert result.structuredContent["accepted"]["failure_reviews"] == 0


def test_workflow_memory_failure_review_uses_trusted_reason(monkeypatch):
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("failure", "max_requests")
    configure_server(monkeypatch, memory=memory)
    candidate = valid_workflow_candidate()
    candidate["failure_review"] = {
        "stage": "接近目标并准备交互",
        "bottlenecks": ["在相似交互物之间反复判断"],
        "optimizations": ["先组合验证环境名称与目标物特征"],
    }

    updated = call_tool("workflow_memory_update", candidate)
    snapshot = call_tool("workflow_memory_read", {})

    assert updated.structuredContent["accepted"]["failure_reviews"] == 1
    assert snapshot.structuredContent["memory"]["failure_reviews"] == [{
        "terminal_reason": "max_requests",
        **candidate["failure_review"],
    }]


def test_failure_review_memory_tools_are_not_logged(monkeypatch):
    logger = RecordingTrajectoryLogger()
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    configure_server(monkeypatch, logger=logger, memory=memory)
    call_tool("workflow_memory_read", {})
    memory.finish_attempt("failure", "max_requests")
    candidate = valid_workflow_candidate()
    candidate["failure_review"] = {
        "stage": "目标分类",
        "bottlenecks": ["候选区分不足"],
        "optimizations": ["先组合验证多个可见特征"],
    }

    call_tool("workflow_memory_update", candidate)

    assert logger.begun == []
    assert logger.completed == []


def test_workflow_memory_update_rejects_without_echo(monkeypatch):
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")
    configure_server(monkeypatch, memory=memory)
    candidate = valid_workflow_candidate()
    candidate["avoid"] = ["secret https://example.invalid/internal"]

    result = call_tool("workflow_memory_update", candidate)

    assert result.structuredContent == {
        "status": "error",
        "code": "invalid_workflow_memory",
    }
    assert "example.invalid" not in str(result)


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
            images = [item for item in result.content if isinstance(item, ImageContent)]
            assert [item.mimeType for item in images] == ["image/jpeg", "image/png"]

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


def test_parse_server_options_defaults_to_stdio():
    options = mcp_server.parse_server_options([])

    assert options.transport == "stdio"
    assert options.http_host == "127.0.0.1"
    assert options.http_port == 8766
    assert options.codex_media_output is False


def test_parse_server_options_enables_codex_media_output():
    options = mcp_server.parse_server_options(["--codex-media-output"])

    assert options.codex_media_output is True


def test_parse_server_options_can_preserve_checkpointed_agent_terminal():
    options = mcp_server.parse_server_options(
        ["--preserve-unconsumed-workflow-memory"]
    )

    assert options.preserve_unconsumed_workflow_memory is True


@pytest.mark.parametrize("host", ["localhost", "::1", "0.0.0.0"])
def test_parse_server_options_rejects_non_numeric_loopback(host):
    with pytest.raises(ValueError, match="MCP HTTP host must be 127.0.0.1"):
        mcp_server.parse_server_options(
            [
                "--transport",
                "streamable-http",
                "--http-host",
                host,
                "--http-port",
                "8766",
            ]
        )


def test_configure_transport_sets_fastmcp_http_listener():
    options = mcp_server.ServerOptions(
        transport="streamable-http",
        http_host="127.0.0.1",
        http_port=8766,
    )

    transport = mcp_server.configure_transport(options)

    assert transport == "streamable-http"
    assert mcp_server.mcp.settings.host == "127.0.0.1"
    assert mcp_server.mcp.settings.port == 8766


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
